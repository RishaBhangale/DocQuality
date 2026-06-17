"""
Monitor API Routes.

Provides aggregated analytics endpoints for the monitoring dashboard.
All endpoints accept optional query parameters:
  - from_date / to_date: ISO date strings for filtering
  - workspace: "banking" | "compliance" | "all" (default: "all")
"""

import json
import logging
import os
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case, and_, or_, desc, extract
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Monitor"])


def _parse_date(d: Optional[str]) -> Optional[datetime]:
    """Parse an ISO date string to a NAIVE datetime (no tzinfo).
    The DB stores naive datetimes, so comparisons must stay naive.
    """
    if not d:
        return None
    try:
        return datetime.fromisoformat(d).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def _apply_date_filter(query, model, from_date, to_date, date_col="timestamp"):
    """Apply date range filter to a query."""
    col = getattr(model, date_col)
    if from_date:
        parsed = _parse_date(from_date)
        if parsed:
            query = query.filter(col >= parsed)
    if to_date:
        parsed = _parse_date(to_date)
        if parsed:
            query = query.filter(col <= parsed)
    return query


def _apply_workspace_filter(query, model, workspace):
    """Apply workspace filter."""
    if workspace and workspace != "all":
        query = query.filter(model.workspace == workspace)
    return query


def create_monitor_router(get_db):
    """Create the monitor router with database dependency injection."""

    # ═══════════════════════════════════════════════════════════════════
    # OVERVIEW
    # ═══════════════════════════════════════════════════════════════════

    @router.get("/overview")
    def get_overview(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        workspace: str = "all",
        db: Session = Depends(get_db),
    ):
        """Top-level KPIs for the dashboard."""
        from core.models.db_models import Evaluation, Job
        from core.models.monitor_models import MonitorEvent

        # Total evaluations
        eval_q = db.query(Evaluation)
        if workspace != "all":
            eval_q = eval_q.filter(Evaluation.workspace == workspace)
        eval_q = _apply_date_filter(eval_q, Evaluation, from_date, to_date, "created_at")
        total_evals = eval_q.count()

        # Average score
        avg_score_result = eval_q.with_entities(
            func.avg(Evaluation.overall_score)
        ).scalar()
        avg_score = round(avg_score_result, 1) if avg_score_result else 0

        # Job success rate
        job_q = db.query(Job)
        if workspace != "all":
            job_q = job_q.filter(Job.workspace == workspace)
        job_q = _apply_date_filter(job_q, Job, from_date, to_date, "created_at")
        total_jobs = job_q.count()
        completed_jobs = job_q.filter(Job.status == "completed").count()
        success_rate = round((completed_jobs / total_jobs) * 100, 1) if total_jobs > 0 else 100

        # LLM average latency
        llm_q = db.query(func.avg(MonitorEvent.llm_latency_ms)).filter(
            MonitorEvent.event_type == "llm_call",
            MonitorEvent.llm_latency_ms.isnot(None),
        )
        llm_q = _apply_workspace_filter(llm_q, MonitorEvent, workspace)
        llm_q = _apply_date_filter(llm_q, MonitorEvent, from_date, to_date)
        avg_latency = llm_q.scalar()
        avg_latency = int(avg_latency) if avg_latency else 0

        # Active jobs
        active_jobs = db.query(Job).filter(
            Job.status.in_(["queued", "processing"])
        ).count()

        # Workspace split
        ws_counts = (
            db.query(Evaluation.workspace, func.count(Evaluation.id))
            .group_by(Evaluation.workspace)
            .all()
        )
        workspace_split = {ws or "unknown": count for ws, count in ws_counts}

        return {
            "total_evaluations": total_evals,
            "average_score": avg_score,
            "success_rate": success_rate,
            "average_llm_latency_ms": avg_latency,
            "active_jobs": active_jobs,
            "total_jobs": total_jobs,
            "completed_jobs": completed_jobs,
            "workspace_split": workspace_split,
        }

    @router.get("/overview/kpis")
    def get_overview_kpis(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        workspace: str = "all",
        db: Session = Depends(get_db),
    ):
        overview = get_overview(from_date, to_date, workspace, db)
        return {
            "total_evaluations": overview["total_evaluations"],
            "success_rate": overview["success_rate"],
            "avg_score": overview["average_score"],
            "avg_llm_latency_ms": overview["average_llm_latency_ms"],
            "active_jobs": overview["active_jobs"],
        }

    @router.get("/overview/workspace-split")
    def get_overview_workspace_split(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        db: Session = Depends(get_db),
    ):
        from core.models.db_models import Evaluation
        q = db.query(
            Evaluation.workspace,
            func.count(Evaluation.id),
            func.avg(Evaluation.overall_score),
        ).group_by(Evaluation.workspace)
        q = _apply_date_filter(q, Evaluation, from_date, to_date, "created_at")
        rows = q.all()
        return [
            {
                "workspace": ws or "unknown",
                "count": count,
                "avg_score": round(avg, 2) if avg is not None else 0,
            }
            for ws, count, avg in rows
        ]

    @router.get("/overview/score-trend")
    def get_overview_score_trend(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        workspace: str = "all",
        db: Session = Depends(get_db),
    ):
        return get_evaluations_timeline(from_date, to_date, workspace, "daily", db)

    @router.get("/feed")
    def get_feed(
        limit: int = Query(50, le=200),
        workspace: str = "all",
        db: Session = Depends(get_db),
    ):
        """Live activity feed — latest N events."""
        from core.models.monitor_models import MonitorEvent

        q = db.query(MonitorEvent).order_by(desc(MonitorEvent.timestamp))
        q = _apply_workspace_filter(q, MonitorEvent, workspace)
        events = q.limit(limit).all()

        return [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "workspace": e.workspace,
                "event_type": e.event_type,
                "evaluation_id": e.evaluation_id,
                "job_id": e.job_id,
                "filename": e.filename,
                "pipeline_step": e.pipeline_step,
                "llm_latency_ms": e.llm_latency_ms,
                "llm_error": e.llm_error,
                "overall_score": e.overall_score,
                "banking_domain": e.banking_domain,
            }
            for e in events
        ]

    # ═══════════════════════════════════════════════════════════════════
    # EVALUATION ANALYTICS
    # ═══════════════════════════════════════════════════════════════════

    @router.get("/evaluations/timeline")
    def get_evaluations_timeline(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        workspace: str = "all",
        bucket: str = Query("daily", pattern="^(hourly|daily|weekly)$"),
        db: Session = Depends(get_db),
    ):
        """Evaluation counts and avg scores over time."""
        from core.models.db_models import Evaluation

        q = db.query(Evaluation)
        if workspace != "all":
            q = q.filter(Evaluation.workspace == workspace)
        q = _apply_date_filter(q, Evaluation, from_date, to_date, "created_at")
        evals = q.order_by(Evaluation.created_at).all()

        buckets: dict[str, dict] = {}
        for e in evals:
            if not e.created_at:
                continue
            if bucket == "hourly":
                key = e.created_at.strftime("%Y-%m-%d %H:00")
            elif bucket == "weekly":
                week_start = e.created_at - timedelta(days=e.created_at.weekday())
                key = week_start.strftime("%Y-%m-%d")
            else:
                key = e.created_at.strftime("%Y-%m-%d")

            if key not in buckets:
                buckets[key] = {"date": key, "count": 0, "total_score": 0, "scored": 0}
            buckets[key]["count"] += 1
            if e.overall_score is not None:
                buckets[key]["total_score"] += e.overall_score
                buckets[key]["scored"] += 1

        result = []
        for b in buckets.values():
            avg = round(b["total_score"] / b["scored"], 1) if b["scored"] > 0 else None
            result.append({"date": b["date"], "count": b["count"], "avg_score": avg})

        return result

    @router.get("/evaluations/distribution")
    def get_evaluations_distribution(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        workspace: str = "all",
        db: Session = Depends(get_db),
    ):
        """Score distribution histogram (10 buckets). Returns ScoreDistribution[]."""
        from core.models.db_models import Evaluation

        q = db.query(Evaluation.overall_score).filter(Evaluation.overall_score.isnot(None))
        if workspace != "all":
            q = q.filter(Evaluation.workspace == workspace)
        q = _apply_date_filter(q, Evaluation, from_date, to_date, "created_at")
        scores = [row[0] for row in q.all()]

        histogram: dict[str, int] = {f"{i*10}-{(i+1)*10}": 0 for i in range(10)}
        for score in scores:
            # Scores may be 0-1 or 0-100; normalise to 0-100
            normalised = score if score > 1 else score * 100
            bucket_idx = min(int(normalised // 10), 9)
            key = f"{bucket_idx*10}-{(bucket_idx+1)*10}"
            histogram[key] += 1

        # Return as array of {bucket, count} to match ScoreDistribution[]
        return [
            {"bucket": bucket, "count": count}
            for bucket, count in histogram.items()
        ]

    @router.get("/evaluations/by-workspace")
    def get_evaluations_by_workspace(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        db: Session = Depends(get_db),
    ):
        """Breakdown by workspace. Returns WorkspaceScore[]."""
        from core.models.db_models import Evaluation

        q = db.query(
            Evaluation.workspace,
            func.count(Evaluation.id),
            func.avg(Evaluation.overall_score),
        ).group_by(Evaluation.workspace)
        q = _apply_date_filter(q, Evaluation, from_date, to_date, "created_at")
        rows = q.all()

        # Fetch raw scores per workspace for median computation
        scores_per_ws: dict[str, list] = {}
        for ws, count, avg in rows:
            ws_key = ws or "unknown"
            raw = db.query(Evaluation.overall_score).filter(
                Evaluation.workspace == ws,
                Evaluation.overall_score.isnot(None),
            ).all()
            sorted_scores = sorted([r[0] for r in raw])
            n = len(sorted_scores)
            if n == 0:
                median = None
            elif n % 2 == 1:
                median = sorted_scores[n // 2]
            else:
                median = (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2
            scores_per_ws[ws_key] = {"avg": avg, "median": median, "count": count}

        return [
            {
                "workspace": ws or "unknown",
                "count": count,
                "avg_score": round(scores_per_ws.get(ws or "unknown", {}).get("avg") or 0, 1),
                "median_score": round(scores_per_ws.get(ws or "unknown", {}).get("median") or 0, 1),
            }
            for ws, count, avg in rows
        ]

    @router.get("/evaluations/by-domain")
    def get_evaluations_by_domain(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        db: Session = Depends(get_db),
    ):
        """Banking domain distribution."""
        from core.models.db_models import Evaluation

        q = db.query(
            Evaluation.banking_domain,
            func.count(Evaluation.id),
            func.avg(Evaluation.overall_score),
        ).filter(
            Evaluation.banking_domain.isnot(None),
            Evaluation.banking_domain != "",
        ).group_by(Evaluation.banking_domain)
        q = _apply_date_filter(q, Evaluation, from_date, to_date, "created_at")
        rows = q.all()

        return [
            {
                "domain": domain,
                "count": count,
                "avg_score": round(avg, 1) if avg else None,
            }
            for domain, count, avg in rows
        ]

    @router.get("/evaluations/by-status")
    def get_evaluations_by_status(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        workspace: str = "all",
        db: Session = Depends(get_db),
    ):
        """Status breakdown."""
        from core.models.db_models import Evaluation

        q = db.query(Evaluation.status, func.count(Evaluation.id)).group_by(Evaluation.status)
        if workspace != "all":
            q = q.filter(Evaluation.workspace == workspace)
        q = _apply_date_filter(q, Evaluation, from_date, to_date, "created_at")
        rows = q.all()

        return [{"status": status or "unknown", "count": count} for status, count in rows]

    @router.get("/evaluations/lowest")
    def get_lowest_evaluations(
        limit: int = Query(10, le=50),
        workspace: str = "all",
        db: Session = Depends(get_db),
    ):
        """Top N lowest-scoring documents. Returns LowestDocument[]."""
        from core.models.db_models import Evaluation, Issue

        q = db.query(Evaluation).filter(Evaluation.overall_score.isnot(None))
        if workspace != "all":
            q = q.filter(Evaluation.workspace == workspace)
        evals = q.order_by(Evaluation.overall_score.asc()).limit(limit).all()

        results = []
        for e in evals:
            # Fetch failing metric names from issues table
            failing = [
                i.issue_type
                for i in db.query(Issue.issue_type)
                .filter(Issue.evaluation_id == e.id)
                .limit(5)
                .all()
                if i.issue_type
            ]
            # Normalise score to 0-1 scale for consistent frontend comparison
            score = e.overall_score
            if score is not None and score > 1:
                score = round(score / 100, 4)
            results.append({
                "document_id": e.id,
                "filename": e.filename or "Unknown",
                "score": score if score is not None else 0,
                "workspace": e.workspace or "unknown",
                "evaluated_at": e.created_at.isoformat() if e.created_at else None,
                "failing_metrics": failing,
            })

        return results

    # ═══════════════════════════════════════════════════════════════════
    # LLM PERFORMANCE
    # ═══════════════════════════════════════════════════════════════════

    @router.get("/llm/performance")
    def get_llm_performance(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        workspace: str = "all",
        db: Session = Depends(get_db),
    ):
        """LLM latency percentiles, throughput, and error rate."""
        from core.models.monitor_models import MonitorEvent

        q = db.query(MonitorEvent).filter(
            MonitorEvent.event_type == "llm_call",
        )
        q = _apply_workspace_filter(q, MonitorEvent, workspace)
        q = _apply_date_filter(q, MonitorEvent, from_date, to_date)
        calls = q.all()

        latencies = sorted([c.llm_latency_ms for c in calls if c.llm_latency_ms is not None])
        errors = [c for c in calls if c.llm_error]
        total = len(calls)

        def _percentile(arr, p):
            if not arr:
                return 0
            idx = int(len(arr) * p / 100)
            return arr[min(idx, len(arr) - 1)]

        return {
            "total_calls": total,
            "error_count": len(errors),
            "error_rate": round((len(errors) / total) * 100, 2) if total > 0 else 0,
            "latency_p50_ms": _percentile(latencies, 50),
            "latency_p90_ms": _percentile(latencies, 90),
            "latency_p99_ms": _percentile(latencies, 99),
            "latency_avg_ms": int(sum(latencies) / len(latencies)) if latencies else 0,
            "latency_min_ms": min(latencies) if latencies else 0,
            "latency_max_ms": max(latencies) if latencies else 0,
        }

    @router.get("/llm/kpis")
    def get_llm_kpis(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        workspace: str = "all",
        db: Session = Depends(get_db),
    ):
        perf = get_llm_performance(from_date, to_date, workspace, db)
        cost = get_llm_cost(from_date, to_date, workspace, db)
        return {
            "total_calls": perf["total_calls"],
            "error_rate": perf["error_rate"],
            "avg_latency_ms": perf["latency_avg_ms"],
            "estimated_cost_usd": cost["estimated_cost_usd"],
        }

    @router.get("/llm/token-usage")
    def get_llm_token_usage(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        workspace: str = "all",
        bucket: str = Query("daily", pattern="^(hourly|daily|weekly)$"),
        db: Session = Depends(get_db),
    ):
        """Token consumption over time. Returns TokenUsage[]."""
        from core.models.monitor_models import MonitorEvent

        q = db.query(MonitorEvent).filter(MonitorEvent.event_type == "llm_call")
        q = _apply_workspace_filter(q, MonitorEvent, workspace)
        q = _apply_date_filter(q, MonitorEvent, from_date, to_date)
        calls = q.order_by(MonitorEvent.timestamp).all()

        buckets_data: dict[str, dict] = {}
        for c in calls:
            if not c.timestamp:
                continue
            if bucket == "hourly":
                key = c.timestamp.strftime("%Y-%m-%d %H:00")
            elif bucket == "weekly":
                week_start = c.timestamp - timedelta(days=c.timestamp.weekday())
                key = week_start.strftime("%Y-%m-%d")
            else:
                key = c.timestamp.strftime("%Y-%m-%d")

            if key not in buckets_data:
                buckets_data[key] = {"date": key, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}
            prompt = c.llm_input_tokens or 0
            completion = c.llm_output_tokens or 0
            buckets_data[key]["prompt_tokens"] += prompt
            buckets_data[key]["completion_tokens"] += completion
            buckets_data[key]["total_tokens"] += prompt + completion
            buckets_data[key]["calls"] += 1

        return list(buckets_data.values())

    @router.get("/llm/errors")
    def get_llm_errors(
        limit: int = Query(50, le=200),
        workspace: str = "all",
        db: Session = Depends(get_db),
    ):
        """Recent LLM errors. Returns LLMError[]."""
        from core.models.monitor_models import MonitorEvent

        q = db.query(MonitorEvent).filter(
            MonitorEvent.event_type == "llm_call",
            MonitorEvent.llm_error.isnot(None),
            MonitorEvent.llm_error != "",
        )
        q = _apply_workspace_filter(q, MonitorEvent, workspace)
        errors = q.order_by(desc(MonitorEvent.timestamp)).limit(limit).all()

        return [
            {
                "id": str(e.id),
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "step": e.pipeline_step or "unknown",
                "error_type": f"HTTP {e.llm_status_code}" if e.llm_status_code else "LLM Error",
                "message": e.llm_error or "",
                "model": e.llm_model or "unknown",
            }
            for e in errors
        ]

    @router.get("/llm/by-step")
    def get_llm_by_step(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        workspace: str = "all",
        db: Session = Depends(get_db),
    ):
        """Latency breakdown by pipeline step. Returns StepLatency[]."""
        from core.models.monitor_models import MonitorEvent

        q = db.query(MonitorEvent).filter(
            MonitorEvent.event_type == "llm_call",
            MonitorEvent.pipeline_step.isnot(None),
        )
        q = _apply_workspace_filter(q, MonitorEvent, workspace)
        q = _apply_date_filter(q, MonitorEvent, from_date, to_date)
        calls = q.all()

        # Group latencies per step for percentile computation
        step_latencies: dict[str, list] = {}
        for c in calls:
            step = c.pipeline_step or "unknown"
            if c.llm_latency_ms is not None:
                step_latencies.setdefault(step, []).append(c.llm_latency_ms)

        result = []
        for step, latencies in step_latencies.items():
            latencies.sort()
            n = len(latencies)
            avg = int(sum(latencies) / n) if n else 0
            p95_idx = min(int(n * 0.95), n - 1)
            p95 = latencies[p95_idx] if n else 0
            result.append({
                "step": step,
                "call_count": n,
                "avg_latency_ms": avg,
                "p95_latency_ms": p95,
                "min_latency_ms": latencies[0] if n else 0,
                "max_latency_ms": latencies[-1] if n else 0,
            })

        return result

    @router.get("/llm/cost")
    def get_llm_cost(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        workspace: str = "all",
        db: Session = Depends(get_db),
    ):
        """Estimated LLM cost based on token usage."""
        from core.models.monitor_models import MonitorEvent

        q = db.query(
            func.sum(MonitorEvent.llm_input_tokens),
            func.sum(MonitorEvent.llm_output_tokens),
            func.count(MonitorEvent.id),
        ).filter(MonitorEvent.event_type == "llm_call")
        q = _apply_workspace_filter(q, MonitorEvent, workspace)
        q = _apply_date_filter(q, MonitorEvent, from_date, to_date)
        row = q.first()

        total_in = row[0] or 0
        total_out = row[1] or 0
        total_calls = row[2] or 0

        # Approximate pricing (GPT-4o rates: $2.50/1M input, $10/1M output)
        input_cost = (total_in / 1_000_000) * 2.50
        output_cost = (total_out / 1_000_000) * 10.00

        return {
            "total_input_tokens": total_in,
            "total_output_tokens": total_out,
            "total_calls": total_calls,
            "estimated_cost_usd": round(input_cost + output_cost, 4),
            "input_cost_usd": round(input_cost, 4),
            "output_cost_usd": round(output_cost, 4),
        }

    # ═══════════════════════════════════════════════════════════════════
    # METRIC DEEP-DIVE
    # ═══════════════════════════════════════════════════════════════════

    @router.get("/metrics/averages")
    def get_metric_averages(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        workspace: str = "all",
        db: Session = Depends(get_db),
    ):
        """Average score per metric across all evaluations."""
        from core.models.db_models import MetricResultRow, Evaluation

        q = db.query(
            MetricResultRow.name,
            MetricResultRow.category,
            func.avg(MetricResultRow.score),
            func.count(MetricResultRow.id),
            func.min(MetricResultRow.score),
            func.max(MetricResultRow.score),
        ).join(Evaluation, MetricResultRow.evaluation_id == Evaluation.id)

        if workspace != "all":
            q = q.filter(Evaluation.workspace == workspace)
        q = _apply_date_filter(q, Evaluation, from_date, to_date, "created_at")
        q = q.group_by(MetricResultRow.name, MetricResultRow.category)
        rows = q.all()

        return [
            {
                "metric": name,
                "type": cat,
                "avg_score": round(avg, 1) if avg else 0,
                "evaluation_count": count,
                "min_score": round(mn, 1) if mn else 0,
                "max_score": round(mx, 1) if mx else 0,
            }
            for name, cat, avg, count, mn, mx in rows
        ]

    @router.get("/metrics/heatmap")
    def get_metric_heatmap(
        limit: int = Query(20, le=50),
        workspace: str = "all",
        db: Session = Depends(get_db),
    ):
        """Metric × evaluation score grid for heatmap visualization."""
        from core.models.db_models import MetricResultRow, Evaluation

        # Get recent evaluations
        eval_q = db.query(Evaluation).filter(Evaluation.overall_score.isnot(None))
        if workspace != "all":
            eval_q = eval_q.filter(Evaluation.workspace == workspace)
        evals = eval_q.order_by(desc(Evaluation.created_at)).limit(limit).all()
        eval_ids = [e.id for e in evals]

        if not eval_ids:
            return {"evaluations": [], "metrics": [], "data": []}

        # Get metric results for those evaluations
        metrics_q = db.query(MetricResultRow).filter(
            MetricResultRow.evaluation_id.in_(eval_ids)
        )
        metric_rows = metrics_q.all()

        # Build heatmap data
        eval_labels = [
            {"id": e.id, "filename": e.filename, "score": e.overall_score}
            for e in evals
        ]
        metric_names = sorted(set(m.name for m in metric_rows))

        data = []
        for m in metric_rows:
            data.append({
                "evaluation_id": m.evaluation_id,
                "metric": m.name,
                "score": m.score,
            })

        return {
            "evaluations": eval_labels,
            "metrics": metric_names,
            "data": data,
        }

    @router.get("/metrics/trends")
    def get_metric_trends(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        workspace: str = "all",
        db: Session = Depends(get_db),
    ):
        """Metric score trends over time."""
        from core.models.db_models import MetricResultRow, Evaluation

        q = db.query(
            Evaluation.created_at,
            MetricResultRow.name,
            MetricResultRow.score,
        ).join(Evaluation, MetricResultRow.evaluation_id == Evaluation.id)
        if workspace != "all":
            q = q.filter(Evaluation.workspace == workspace)
        q = _apply_date_filter(q, Evaluation, from_date, to_date, "created_at")
        q = q.order_by(Evaluation.created_at)
        rows = q.all()

        # Group by date and metric
        trends: dict[str, dict[str, list]] = {}
        for created_at, name, score in rows:
            if not created_at:
                continue
            date_key = created_at.strftime("%Y-%m-%d")
            if date_key not in trends:
                trends[date_key] = {}
            if name not in trends[date_key]:
                trends[date_key][name] = []
            trends[date_key][name].append(score)

        result = []
        for date_key, metrics in sorted(trends.items()):
            entry = {"date": date_key}
            for metric_name, scores in metrics.items():
                entry[metric_name] = round(sum(scores) / len(scores), 1)
            result.append(entry)

        return result

    @router.get("/metrics/det-vs-llm")
    def get_det_vs_llm(
        workspace: str = "all",
        limit: int = Query(50, le=200),
        db: Session = Depends(get_db),
    ):
        """Deterministic vs LLM score comparison for banking metrics."""
        from core.models.db_models import Evaluation

        q = db.query(Evaluation).filter(
            Evaluation.banking_metrics_json.isnot(None),
        )
        if workspace != "all":
            q = q.filter(Evaluation.workspace == workspace)
        evals = q.order_by(desc(Evaluation.created_at)).limit(limit).all()

        data = []
        for e in evals:
            try:
                bm = json.loads(e.banking_metrics_json or "[]")
                for m in bm:
                    if isinstance(m, dict):
                        data.append({
                            "evaluation_id": e.id,
                            "metric": m.get("name", ""),
                            "deterministic": m.get("deterministic_score", 0),
                            "llm": m.get("llm_score", 0),
                            "blended": m.get("score", 0),
                        })
            except (json.JSONDecodeError, TypeError):
                continue

        return data

    # ═══════════════════════════════════════════════════════════════════
    # REGULATORY
    # ═══════════════════════════════════════════════════════════════════

    @router.get("/regulatory/compliance-rate")
    def get_regulatory_compliance_rate(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        db: Session = Depends(get_db),
    ):
        """% of banking evaluations passing all regulatory thresholds."""
        from core.models.db_models import Evaluation

        q = db.query(Evaluation).filter(
            Evaluation.workspace == "banking",
            Evaluation.banking_metrics_json.isnot(None),
        )
        q = _apply_date_filter(q, Evaluation, from_date, to_date, "created_at")
        evals = q.all()

        total = len(evals)
        passing = 0
        for e in evals:
            try:
                bm = json.loads(e.banking_metrics_json or "[]")
                all_pass = all(
                    m.get("passes_regulatory_threshold", True)
                    for m in bm if isinstance(m, dict)
                )
                if all_pass:
                    passing += 1
            except (json.JSONDecodeError, TypeError):
                continue

        return {
            "total_evaluated": total,
            "total_passing": passing,
            "total_failing": total - passing,
            "overall_rate": round((passing / total) * 100, 1) if total > 0 else 100,
        }

    @router.get("/regulatory/legal-holds")
    def get_legal_holds(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        db: Session = Depends(get_db),
    ):
        """Legal hold history."""
        from core.models.db_models import Evaluation

        q = db.query(Evaluation).filter(Evaluation.legal_hold == True)
        q = _apply_date_filter(q, Evaluation, from_date, to_date, "created_at")
        holds = q.order_by(desc(Evaluation.created_at)).all()

        return [
            {
                "id": e.id,
                "document_id": e.id,
                "filename": e.filename,
                "banking_domain": e.banking_domain,
                "reason": e.legal_hold_reason,
                "overall_score": e.overall_score,
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "status": "active" if e.legal_hold else "released"
            }
            for e in holds
        ]

    @router.get("/regulatory/threshold-failures")
    def get_threshold_failures(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        db: Session = Depends(get_db),
    ):
        """Which regulatory thresholds fail most often."""
        from core.models.db_models import Evaluation

        q = db.query(Evaluation).filter(
            Evaluation.workspace == "banking",
            Evaluation.banking_metrics_json.isnot(None),
        )
        q = _apply_date_filter(q, Evaluation, from_date, to_date, "created_at")
        evals = q.all()

        failure_counts: dict[str, int] = Counter()
        for e in evals:
            try:
                bm = json.loads(e.banking_metrics_json or "[]")
                for m in bm:
                    if isinstance(m, dict) and not m.get("passes_regulatory_threshold", True):
                        failure_counts[m.get("name", "Unknown")] += 1
            except (json.JSONDecodeError, TypeError):
                continue

        return [
            {"metric": name, "failure_count": count}
            for name, count in failure_counts.most_common(20)
        ]

    # ═══════════════════════════════════════════════════════════════════
    # ISSUES
    # ═══════════════════════════════════════════════════════════════════

    @router.get("/issues/summary")
    def get_issues_summary(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        workspace: str = "all",
        db: Session = Depends(get_db),
    ):
        """Issue counts by severity."""
        from core.models.db_models import Issue, Evaluation

        q = db.query(Issue.severity, func.count(Issue.id)).join(
            Evaluation, Issue.evaluation_id == Evaluation.id
        ).group_by(Issue.severity)
        if workspace != "all":
            q = q.filter(Evaluation.workspace == workspace)
        q = _apply_date_filter(q, Evaluation, from_date, to_date, "created_at")
        rows = q.all()

        return [
            {"severity": sev or "unknown", "count": count}
            for sev, count in rows
        ]

    @router.get("/issues/top-recurring")
    def get_top_recurring_issues(
        limit: int = Query(15, le=50),
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        workspace: str = "all",
        db: Session = Depends(get_db),
    ):
        """Most frequently occurring issues."""
        from core.models.db_models import Issue, Evaluation

        q = db.query(
            Issue.issue_type,
            Issue.severity,
            func.count(Issue.id).label("count"),
        ).join(Evaluation, Issue.evaluation_id == Evaluation.id).group_by(
            Issue.issue_type, Issue.severity
        ).order_by(desc("count"))

        if workspace != "all":
            q = q.filter(Evaluation.workspace == workspace)
        q = _apply_date_filter(q, Evaluation, from_date, to_date, "created_at")
        rows = q.limit(limit).all()

        return [
            {"issue_type": itype, "severity": sev, "count": count}
            for itype, sev, count in rows
        ]

    # ═══════════════════════════════════════════════════════════════════
    # PIPELINE & SYSTEM
    # ═══════════════════════════════════════════════════════════════════

    @router.get("/pipeline/step-timings")
    def get_pipeline_step_timings(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        workspace: str = "all",
        db: Session = Depends(get_db),
    ):
        """Average time per pipeline step."""
        from core.models.monitor_models import MonitorEvent

        q = db.query(
            MonitorEvent.pipeline_step,
            func.count(MonitorEvent.id),
            func.avg(MonitorEvent.step_latency_ms),
            func.min(MonitorEvent.step_latency_ms),
            func.max(MonitorEvent.step_latency_ms),
        ).filter(
            MonitorEvent.event_type == "pipeline_step",
            MonitorEvent.pipeline_step.isnot(None),
        ).group_by(MonitorEvent.pipeline_step)
        q = _apply_workspace_filter(q, MonitorEvent, workspace)
        q = _apply_date_filter(q, MonitorEvent, from_date, to_date)
        rows = q.all()

        return [
            {
                "step": step,
                "call_count": count,
                "avg_duration_ms": int(avg) if avg else 0,
                "min_duration_ms": mn or 0,
                "max_duration_ms": mx or 0,
            }
            for step, count, avg, mn, mx in rows
        ]

    @router.get("/pipeline/success-rate")
    def get_pipeline_success_rate(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        workspace: str = "all",
        db: Session = Depends(get_db),
    ):
        """Job success vs failure rate."""
        from core.models.db_models import Job

        q = db.query(Job.status, func.count(Job.id)).group_by(Job.status)
        if workspace != "all":
            q = q.filter(Job.workspace == workspace)
        q = _apply_date_filter(q, Job, from_date, to_date, "created_at")
        rows = q.all()

        return [
            {"status": status or "unknown", "count": count}
            for status, count in rows
        ]

    @router.get("/pipeline/queue-depth")
    def get_pipeline_queue_depth(db: Session = Depends(get_db)):
        """Currently queued/processing jobs."""
        from core.models.db_models import Job

        queued = db.query(Job).filter(Job.status == "queued").count()
        processing = db.query(Job).filter(Job.status == "processing").count()

        return [
            {
                "queue_name": "main",
                "depth": queued,
                "processing": processing
            }
        ]

    @router.get("/documents/types")
    def get_document_types(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        workspace: str = "all",
        db: Session = Depends(get_db),
    ):
        """Document type distribution."""
        from core.models.db_models import Evaluation

        q = db.query(
            Evaluation.document_type, func.count(Evaluation.id)
        ).filter(
            Evaluation.document_type.isnot(None),
        ).group_by(Evaluation.document_type)
        if workspace != "all":
            q = q.filter(Evaluation.workspace == workspace)
        q = _apply_date_filter(q, Evaluation, from_date, to_date, "created_at")
        rows = q.all()

        total_count = sum(count for _, count in rows)
        return [
            {
                "doc_type": dtype or "unknown",
                "count": count,
                "percentage": round((count / total_count) * 100, 1) if total_count > 0 else 0
            }
            for dtype, count in rows
        ]

    @router.get("/documents/sizes")
    def get_document_sizes(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        workspace: str = "all",
        db: Session = Depends(get_db),
    ):
        """File size distribution from monitor events."""
        from core.models.monitor_models import MonitorEvent

        q = db.query(MonitorEvent.file_size_bytes).filter(
            MonitorEvent.event_type.in_(["eval_start", "upload"]),
            MonitorEvent.file_size_bytes.isnot(None),
            MonitorEvent.file_size_bytes > 0,
        )
        q = _apply_workspace_filter(q, MonitorEvent, workspace)
        q = _apply_date_filter(q, MonitorEvent, from_date, to_date)
        sizes = [row[0] for row in q.all()]

        if not sizes:
            return {"histogram": {}, "avg_bytes": 0, "total_files": 0}

        # Build size histogram (KB buckets)
        histogram = {"0-50KB": 0, "50-100KB": 0, "100-500KB": 0, "500KB-1MB": 0, "1MB-5MB": 0, "5MB+": 0}
        for s in sizes:
            kb = s / 1024
            if kb < 50:
                histogram["0-50KB"] += 1
            elif kb < 100:
                histogram["50-100KB"] += 1
            elif kb < 500:
                histogram["100-500KB"] += 1
            elif kb < 1024:
                histogram["500KB-1MB"] += 1
            elif kb < 5120:
                histogram["1MB-5MB"] += 1
            else:
                histogram["5MB+"] += 1

        return {
            "histogram": histogram,
            "avg_bytes": int(sum(sizes) / len(sizes)),
            "total_files": len(sizes),
        }

    @router.get("/system/health")
    def get_system_health(db: Session = Depends(get_db)):
        """System health overview."""
        from core.models.db_models import Evaluation, Job
        from core.models.monitor_models import MonitorEvent

        total_evals = db.query(Evaluation).count()
        total_jobs = db.query(Job).count()
        total_events = db.query(MonitorEvent).count()

        # DB file sizes
        db_sizes = {}
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for db_name in ["document_quality.db"]:
            db_path = os.path.join(backend_dir, db_name)
            if os.path.exists(db_path):
                db_sizes[db_name] = os.path.getsize(db_path)
        # Check data subdirectories too
        data_dir = os.path.join(backend_dir, "data")
        if os.path.isdir(data_dir):
            for ws in ["banking", "compliance"]:
                ws_db = os.path.join(data_dir, ws, "document_quality.db")
                if os.path.exists(ws_db):
                    db_sizes[f"{ws}/document_quality.db"] = os.path.getsize(ws_db)

        # LLM connectivity check
        llm_status = "unknown"
        try:
            from core.services.base_llm_service import BaseLLMService
            llm = BaseLLMService()
            llm_status = "configured" if llm.is_configured else "not_configured"
        except Exception:
            llm_status = "error"

        import psutil
        import time

        # Calculate uptime
        process = psutil.Process(os.getpid())
        uptime_seconds = int(time.time() - process.create_time())

        # Determine overall status
        status = "healthy"
        if llm_status == "error":
            status = "degraded"

        return {
            "status": status,
            "uptime_seconds": uptime_seconds,
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent,
            "last_check": datetime.now(timezone.utc).isoformat(),
        }

    # ═══════════════════════════════════════════════════════════════════
    # EXPORT
    # ═══════════════════════════════════════════════════════════════════

    @router.get("/export/csv")
    def export_csv(
        section: str = Query("overview", pattern="^(overview|evaluations|llm|metrics|regulatory|pipeline)$"),
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        workspace: str = "all",
        db: Session = Depends(get_db),
    ):
        """Export section data as CSV."""
        import csv
        import io
        from fastapi.responses import StreamingResponse

        output = io.StringIO()
        writer = csv.writer(output)

        if section == "overview":
            overview = get_overview(from_date, to_date, workspace, db)
            writer.writerow(["Metric", "Value"])
            for k, v in overview.items():
                if isinstance(v, dict):
                    for sk, sv in v.items():
                        writer.writerow([f"{k}.{sk}", sv])
                else:
                    writer.writerow([k, v])

        elif section == "evaluations":
            from core.models.db_models import Evaluation
            q = db.query(Evaluation)
            if workspace != "all":
                q = q.filter(Evaluation.workspace == workspace)
            q = _apply_date_filter(q, Evaluation, from_date, to_date, "created_at")
            evals = q.order_by(desc(Evaluation.created_at)).limit(500).all()

            writer.writerow(["ID", "Filename", "Score", "Status", "Workspace", "Domain", "Created"])
            for e in evals:
                writer.writerow([
                    e.id, e.filename, e.overall_score, e.status,
                    e.workspace, e.banking_domain,
                    e.created_at.isoformat() if e.created_at else "",
                ])

        elif section == "llm":
            perf = get_llm_performance(from_date, to_date, workspace, db)
            writer.writerow(["Metric", "Value"])
            for k, v in perf.items():
                writer.writerow([k, v])

        elif section == "metrics":
            avgs = get_metric_averages(from_date, to_date, workspace, db)
            writer.writerow(["Metric", "Category", "Avg Score", "Count", "Min", "Max"])
            for m in avgs:
                writer.writerow([m["name"], m["category"], m["avg_score"], m["count"], m["min_score"], m["max_score"]])

        elif section == "regulatory":
            rate = get_regulatory_compliance_rate(from_date, to_date, db)
            writer.writerow(["Metric", "Value"])
            for k, v in rate.items():
                writer.writerow([k, v])

        elif section == "pipeline":
            timings = get_pipeline_step_timings(from_date, to_date, workspace, db)
            writer.writerow(["Step", "Count", "Avg ms", "Min ms", "Max ms"])
            for t in timings:
                writer.writerow([t["step"], t["count"], t["avg_ms"], t["min_ms"], t["max_ms"]])

        output.seek(0)
        filename = f"docquality_monitor_{section}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    return router
