"""
Aggregation Service — tiered data retention.

Aggregates old detailed monitor events into daily summaries,
then prunes the raw events. Inspired by stock broker platforms:
- Recent data (< MONITOR_DETAIL_WINDOW_DAYS): full detail
- Older data: daily aggregated summaries retained indefinitely

Run on monitor startup and optionally on an hourly schedule.
"""

import json
import logging
import os
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Configurable via .env or defaults
MONITOR_DETAIL_WINDOW_DAYS = int(os.getenv("MONITOR_DETAIL_WINDOW_DAYS", "30"))


class AggregationService:
    """
    Handles tiered data retention for monitor events.

    - Events within MONITOR_DETAIL_WINDOW_DAYS: kept in full detail
    - Events older than the window: aggregated into daily summaries, then pruned
    """

    def __init__(self, session_factory):
        self._session_factory = session_factory

    def run_aggregation(self) -> dict:
        """
        Aggregate old events into daily summaries and prune them.

        Returns a summary of what was aggregated.
        """
        from core.models.monitor_models import MonitorEvent, MonitorDailySummary

        cutoff = datetime.now(timezone.utc) - timedelta(days=MONITOR_DETAIL_WINDOW_DAYS)
        session = self._session_factory()

        try:
            # Find all dates with un-aggregated events older than the cutoff
            old_events = (
                session.query(MonitorEvent)
                .filter(MonitorEvent.timestamp < cutoff)
                .all()
            )

            if not old_events:
                logger.info("Aggregation: no events older than %d days to aggregate", MONITOR_DETAIL_WINDOW_DAYS)
                return {"aggregated_days": 0, "events_pruned": 0}

            # Group events by (date, workspace)
            groups: dict[tuple[date, str], list] = {}
            for event in old_events:
                key = (event.timestamp.date(), event.workspace or "unknown")
                groups.setdefault(key, []).append(event)

            aggregated_days = 0
            for (event_date, workspace), events in groups.items():
                # Check if summary already exists
                existing = (
                    session.query(MonitorDailySummary)
                    .filter(
                        MonitorDailySummary.summary_date == event_date,
                        MonitorDailySummary.workspace == workspace,
                    )
                    .first()
                )

                if existing:
                    # Merge into existing summary
                    self._merge_into_summary(existing, events)
                else:
                    # Create new summary
                    summary = self._build_summary(event_date, workspace, events)
                    session.add(summary)

                aggregated_days += 1

            # Prune the raw events
            pruned_count = len(old_events)
            for event in old_events:
                session.delete(event)

            session.commit()
            logger.info(
                "Aggregation complete: %d day(s) aggregated, %d event(s) pruned",
                aggregated_days, pruned_count,
            )
            return {"aggregated_days": aggregated_days, "events_pruned": pruned_count}

        except Exception as e:
            logger.error("Aggregation failed: %s", e)
            session.rollback()
            return {"error": str(e)}
        finally:
            session.close()

    def _build_summary(self, event_date: date, workspace: str, events: list) -> "MonitorDailySummary":
        """Build a MonitorDailySummary from a list of events for a single day."""
        from core.models.monitor_models import MonitorDailySummary

        # Evaluation stats
        eval_starts = [e for e in events if e.event_type == "eval_start"]
        eval_completes = [e for e in events if e.event_type == "eval_complete"]
        eval_errors = [e for e in events if e.event_type == "eval_error"]

        scores = [e.overall_score for e in eval_completes if e.overall_score is not None]

        # Score histogram
        histogram = {f"{i*10}-{(i+1)*10}": 0 for i in range(10)}
        for score in scores:
            bucket = min(int(score // 10), 9)
            key = f"{bucket*10}-{(bucket+1)*10}"
            histogram[key] += 1

        # LLM stats
        llm_calls = [e for e in events if e.event_type == "llm_call"]
        llm_latencies = [e.llm_latency_ms for e in llm_calls if e.llm_latency_ms is not None]
        llm_errors = [e for e in llm_calls if e.llm_error]

        total_in = sum(e.llm_input_tokens or 0 for e in llm_calls)
        total_out = sum(e.llm_output_tokens or 0 for e in llm_calls)

        avg_latency = int(sum(llm_latencies) / len(llm_latencies)) if llm_latencies else None
        p90_latency = None
        if llm_latencies:
            sorted_lat = sorted(llm_latencies)
            p90_idx = int(len(sorted_lat) * 0.9)
            p90_latency = sorted_lat[min(p90_idx, len(sorted_lat) - 1)]

        # Pipeline duration
        step_events = [e for e in events if e.event_type == "pipeline_step"]
        step_latencies = [e.step_latency_ms for e in step_events if e.step_latency_ms is not None]
        avg_pipeline_ms = int(sum(step_latencies) / len(step_latencies)) if step_latencies else None

        # Domain breakdown
        domains = [e.banking_domain for e in eval_completes if e.banking_domain]
        domain_counts = dict(Counter(domains))

        return MonitorDailySummary(
            summary_date=event_date,
            workspace=workspace,
            eval_count=len(eval_starts),
            eval_success=len(eval_completes),
            eval_failed=len(eval_errors),
            avg_overall_score=round(sum(scores) / len(scores), 1) if scores else None,
            min_score=round(min(scores), 1) if scores else None,
            max_score=round(max(scores), 1) if scores else None,
            score_histogram_json=json.dumps(histogram),
            llm_call_count=len(llm_calls),
            llm_avg_latency_ms=avg_latency,
            llm_p90_latency_ms=p90_latency,
            llm_total_input_tokens=total_in,
            llm_total_output_tokens=total_out,
            llm_error_count=len(llm_errors),
            issues_critical=0,  # Will be enriched from issues table if needed
            issues_warning=0,
            legal_hold_count=0,
            avg_pipeline_duration_ms=avg_pipeline_ms,
            top_issues_json=None,
            domain_breakdown_json=json.dumps(domain_counts) if domain_counts else None,
        )

    def _merge_into_summary(self, summary, new_events: list):
        """Merge additional events into an existing daily summary."""
        # Simple additive merge for counts
        eval_starts = [e for e in new_events if e.event_type == "eval_start"]
        eval_completes = [e for e in new_events if e.event_type == "eval_complete"]
        eval_errors = [e for e in new_events if e.event_type == "eval_error"]
        llm_calls = [e for e in new_events if e.event_type == "llm_call"]

        summary.eval_count += len(eval_starts)
        summary.eval_success += len(eval_completes)
        summary.eval_failed += len(eval_errors)
        summary.llm_call_count += len(llm_calls)
        summary.llm_error_count += len([e for e in llm_calls if e.llm_error])
        summary.llm_total_input_tokens += sum(e.llm_input_tokens or 0 for e in llm_calls)
        summary.llm_total_output_tokens += sum(e.llm_output_tokens or 0 for e in llm_calls)

        # Recalculate avg score
        new_scores = [e.overall_score for e in eval_completes if e.overall_score is not None]
        if new_scores:
            all_scores = new_scores
            if summary.avg_overall_score is not None:
                # Weighted average approximation
                old_total = (summary.avg_overall_score or 0) * max(summary.eval_success - len(eval_completes), 1)
                new_total = sum(new_scores)
                summary.avg_overall_score = round(
                    (old_total + new_total) / summary.eval_success, 1
                )
