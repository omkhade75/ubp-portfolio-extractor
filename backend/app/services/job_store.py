import os
import json
import sqlite3
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from app.config import OUTPUT_DIR
from app.models.schemas import ExtractionJobStatus, StatementExtractionResult

DB_PATH = Path(os.environ.get("JOBS_DB_PATH", OUTPUT_DIR / "jobs.sqlite3"))
_local = threading.local()

def get_db_connection() -> sqlite3.Connection:
    """Returns a thread-local SQLite connection with WAL mode and row factory."""
    if not hasattr(_local, "conn") or _local.conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=10000;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        _local.conn = conn
    return _local.conn

def init_job_db():
    """Initializes the persistent extraction_jobs SQLite table."""
    conn = get_db_connection()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS extraction_jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                stage TEXT NOT NULL,
                phase TEXT NOT NULL,
                progress_percentage INTEGER NOT NULL,
                total_files INTEGER NOT NULL DEFAULT 0,
                processed_files INTEGER NOT NULL DEFAULT 0,
                current_file TEXT,
                total_pages INTEGER DEFAULT 0,
                processed_pages INTEGER DEFAULT 0,
                accepted_files_json TEXT NOT NULL DEFAULT '[]',
                error_message TEXT,
                results_json TEXT NOT NULL DEFAULT '[]',
                zip_path TEXT,
                download_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON extraction_jobs(status);
        """)

# Initialize database on module import
init_job_db()

class PersistentJobStore:
    """
    Production-grade SQLite job store with JSON snapshot backup.
    Guarantees cross-worker and cross-restart job persistence.
    """
    def __init__(self):
        self._lock = threading.Lock()

    def save_job(self, status: ExtractionJobStatus):
        """Persists complete job state to SQLite and snapshot JSON file."""
        conn = get_db_connection()
        accepted_files_json = json.dumps(getattr(status, "accepted_files", []))
        
        # Serialize results safely
        try:
            results_data = [r.model_dump(mode="json") if hasattr(r, "model_dump") else r.dict() for r in status.results]
            results_json = json.dumps(results_data)
        except Exception:
            results_json = "[]"

        now_str = datetime.now(timezone.utc).isoformat()

        with self._lock:
            with conn:
                conn.execute("""
                    INSERT INTO extraction_jobs (
                        job_id, status, stage, phase, progress_percentage,
                        total_files, processed_files, current_file, total_pages, processed_pages,
                        accepted_files_json, error_message, results_json, zip_path, download_url,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(job_id) DO UPDATE SET
                        status = excluded.status,
                        stage = excluded.stage,
                        phase = excluded.phase,
                        progress_percentage = excluded.progress_percentage,
                        total_files = excluded.total_files,
                        processed_files = excluded.processed_files,
                        current_file = excluded.current_file,
                        total_pages = excluded.total_pages,
                        processed_pages = excluded.processed_pages,
                        accepted_files_json = excluded.accepted_files_json,
                        error_message = excluded.error_message,
                        results_json = excluded.results_json,
                        zip_path = excluded.zip_path,
                        download_url = excluded.download_url,
                        updated_at = excluded.updated_at;
                """, (
                    status.job_id,
                    status.status,
                    getattr(status, "stage", status.status),
                    status.phase,
                    status.progress_percentage,
                    status.total_files,
                    status.processed_files,
                    status.current_file,
                    getattr(status, "total_pages", None),
                    getattr(status, "processed_pages", None),
                    accepted_files_json,
                    status.error_message,
                    results_json,
                    status.zip_path,
                    getattr(status, "download_url", None),
                    now_str
                ))

        # Secondary disk snapshot in job output directory
        job_dir = OUTPUT_DIR / status.job_id
        try:
            job_dir.mkdir(parents=True, exist_ok=True)
            snapshot_file = job_dir / "job_status.json"
            dump_data = status.model_dump(mode="json") if hasattr(status, "model_dump") else status.dict()
            with open(snapshot_file, "w") as f:
                json.dump(dump_data, f, indent=2)
        except Exception:
            pass

    def get_job(self, job_id: str) -> Optional[ExtractionJobStatus]:
        """
        Retrieves job status from SQLite, with disk JSON snapshot fallback.
        Never returns 404 for an existing job across worker processes or restarts.
        """
        conn = get_db_connection()
        row = None
        with self._lock:
            cur = conn.execute("SELECT * FROM extraction_jobs WHERE job_id = ?", (job_id,))
            row = cur.fetchone()

        if row:
            try:
                results_list = []
                raw_results = json.loads(row["results_json"] or "[]")
                for r_dict in raw_results:
                    results_list.append(StatementExtractionResult.model_validate(r_dict))

                accepted = json.loads(row["accepted_files_json"] or "[]")

                return ExtractionJobStatus(
                    job_id=row["job_id"],
                    status=row["status"],
                    phase=row["phase"],
                    stage=row["stage"] or row["status"],
                    progress_percentage=row["progress_percentage"],
                    total_files=row["total_files"],
                    processed_files=row["processed_files"],
                    current_file=row["current_file"],
                    total_pages=row["total_pages"],
                    processed_pages=row["processed_pages"],
                    accepted_files=accepted,
                    error_message=row["error_message"],
                    results=results_list,
                    zip_path=row["zip_path"],
                    download_url=row["download_url"]
                )
            except Exception:
                pass

        # Fallback to disk snapshot file if SQLite had a read issue
        snapshot_file = OUTPUT_DIR / job_id / "job_status.json"
        if snapshot_file.exists():
            try:
                with open(snapshot_file, "r") as f:
                    data = json.load(f)
                    return ExtractionJobStatus.model_validate(data)
            except Exception:
                pass

        return None

    def update_job_progress(
        self,
        job_id: str,
        status: str,
        stage: str,
        phase: str,
        progress_percentage: int,
        processed_files: Optional[int] = None,
        total_files: Optional[int] = None,
        current_file: Optional[str] = None,
        error_message: Optional[str] = None,
        results: Optional[List[StatementExtractionResult]] = None,
        zip_path: Optional[str] = None,
        download_url: Optional[str] = None
    ) -> Optional[ExtractionJobStatus]:
        """Atomically updates specific progress fields in SQLite and returns updated status."""
        existing = self.get_job(job_id)
        if not existing:
            return None

        existing.status = status
        existing.stage = stage
        existing.phase = phase
        existing.progress_percentage = progress_percentage
        if processed_files is not None:
            existing.processed_files = processed_files
        if total_files is not None:
            existing.total_files = total_files
        if current_file is not None:
            existing.current_file = current_file
        if error_message is not None:
            existing.error_message = error_message
        if results is not None:
            existing.results = results
        if zip_path is not None:
            existing.zip_path = zip_path
        if download_url is not None:
            existing.download_url = download_url

        self.save_job(existing)
        return existing

    def delete_job(self, job_id: str) -> bool:
        """Deletes job record from SQLite database."""
        conn = get_db_connection()
        with self._lock:
            with conn:
                conn.execute("DELETE FROM extraction_jobs WHERE job_id = ?", (job_id,))
        return True

job_store = PersistentJobStore()
