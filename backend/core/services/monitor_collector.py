"""
Monitor Collector — fire-and-forget event logger.

Instruments the main POC pipeline to capture telemetry data
for the monitoring dashboard. All writes are non-blocking
to avoid impacting evaluation performance.

Usage:
    from core.services.monitor_collector import monitor
    monitor.log_llm_call(workspace="banking", eval_id="...", ...)
"""

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MonitorCollector:
    """
    Non-blocking event logger for monitoring telemetry.

    Writes MonitorEvent rows to the database using a background thread
    to avoid blocking the evaluation pipeline.
    """

    def __init__(self):
        self._lock = threading.Lock()

    def _get_session(self):
        """Get a fresh DB session for writing monitor events.

        Uses the main POC's database since monitor_events table
        lives in the same SQLite file.
        """
        try:
            # Try compliance database first (it's the primary one)
            from compliance.database import SessionLocal
            return SessionLocal()
        except Exception:
            try:
                from banking.database import SessionLocal
                return SessionLocal()
            except Exception:
                logger.debug("Monitor: No database session available")
                return None

    def _write_event(self, **kwargs):
        """Write a monitor event in a background thread."""
        def _do_write():
            session = self._get_session()
            if not session:
                return
            try:
                from core.models.monitor_models import MonitorEvent
                event = MonitorEvent(**kwargs)
                session.add(event)
                session.commit()
            except Exception as e:
                logger.debug("Monitor event write failed: %s", e)
                try:
                    session.rollback()
                except Exception:
                    pass
            finally:
                try:
                    session.close()
                except Exception:
                    pass

        thread = threading.Thread(target=_do_write, daemon=True)
        thread.start()

    # ─── Public API ─────────────────────────────────────────────────────────

    def log_llm_call(
        self,
        workspace: str,
        eval_id: Optional[str] = None,
        step: str = "",
        model: str = "",
        latency_ms: int = 0,
        tokens_in: int = 0,
        tokens_out: int = 0,
        status_code: int = 200,
        error: Optional[str] = None,
    ):
        """Log an individual LLM API call."""
        self._write_event(
            timestamp=datetime.now(timezone.utc),
            workspace=workspace,
            event_type="llm_call",
            evaluation_id=eval_id,
            llm_model=model,
            llm_latency_ms=latency_ms,
            llm_input_tokens=tokens_in,
            llm_output_tokens=tokens_out,
            llm_status_code=status_code,
            llm_error=error,
            pipeline_step=step,
        )

    def log_eval_start(
        self,
        workspace: str,
        eval_id: Optional[str] = None,
        job_id: Optional[str] = None,
        filename: str = "",
        file_size: int = 0,
    ):
        """Log the start of an evaluation pipeline."""
        self._write_event(
            timestamp=datetime.now(timezone.utc),
            workspace=workspace,
            event_type="eval_start",
            evaluation_id=eval_id,
            job_id=job_id,
            filename=filename,
            file_size_bytes=file_size,
        )

    def log_eval_complete(
        self,
        workspace: str,
        eval_id: Optional[str] = None,
        overall_score: Optional[float] = None,
        domain: Optional[str] = None,
    ):
        """Log the successful completion of an evaluation."""
        self._write_event(
            timestamp=datetime.now(timezone.utc),
            workspace=workspace,
            event_type="eval_complete",
            evaluation_id=eval_id,
            overall_score=overall_score,
            banking_domain=domain,
        )

    def log_eval_error(
        self,
        workspace: str,
        eval_id: Optional[str] = None,
        job_id: Optional[str] = None,
        error_message: str = "",
    ):
        """Log a failed evaluation."""
        self._write_event(
            timestamp=datetime.now(timezone.utc),
            workspace=workspace,
            event_type="eval_error",
            evaluation_id=eval_id,
            job_id=job_id,
            llm_error=error_message,
        )

    def log_pipeline_step(
        self,
        workspace: str,
        eval_id: Optional[str] = None,
        step_name: str = "",
        latency_ms: int = 0,
    ):
        """Log the completion of a pipeline step with timing."""
        self._write_event(
            timestamp=datetime.now(timezone.utc),
            workspace=workspace,
            event_type="pipeline_step",
            evaluation_id=eval_id,
            pipeline_step=step_name,
            step_latency_ms=latency_ms,
        )

    def log_upload(
        self,
        workspace: str,
        job_id: Optional[str] = None,
        filename: str = "",
        file_size: int = 0,
    ):
        """Log a file upload event."""
        self._write_event(
            timestamp=datetime.now(timezone.utc),
            workspace=workspace,
            event_type="upload",
            job_id=job_id,
            filename=filename,
            file_size_bytes=file_size,
        )


# ─── Singleton Instance ────────────────────────────────────────────────────
# Import and use: `from core.services.monitor_collector import monitor`

monitor = MonitorCollector()
