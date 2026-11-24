import os
import shutil
import uuid
import zipfile
import threading
import json
from typing import Dict, List, Optional
from pathlib import Path

from app.config import INPUT_DIR, OUTPUT_DIR
from app.models.schemas import ExtractionJobStatus, StatementExtractionResult
from app.extraction.table_reconstructor import extract_ubp_statement
from app.excel.workbook_generator import generate_ubp_excel_workbook

class JobManager:
    """
    Manages asynchronous background extraction jobs with isolated directories,
    progress tracking, ZIP path-traversal safeguards, and manifest generation.
    """
    def __init__(self):
        self.jobs: Dict[str, ExtractionJobStatus] = {}
        self.job_files: Dict[str, List[Path]] = {}
        self.lock = threading.Lock()

    def create_job(self) -> str:
        job_id = str(uuid.uuid4())
        job_in_dir = INPUT_DIR / job_id
        job_out_dir = OUTPUT_DIR / job_id
        job_in_dir.mkdir(parents=True, exist_ok=True)
        job_out_dir.mkdir(parents=True, exist_ok=True)

        status = ExtractionJobStatus(
            job_id=job_id,
            status="PENDING",
            phase="File validation",
            progress_percentage=0,
            total_files=0,
            processed_files=0,
            results=[]
        )
        with self.lock:
            self.jobs[job_id] = status
            self.job_files[job_id] = []
        return job_id

    def add_uploaded_file(self, job_id: str, filename: str, content: bytes) -> Optional[str]:
        """
        Validates content magic bytes and safely stores PDF or unpacks ZIP.
        Safeguards against ZIP path traversal.
        """
        job_in_dir = INPUT_DIR / job_id
        
        # Check ZIP
        if content.startswith(b"PK\x03\x04") or filename.lower().endswith(".zip"):
            temp_zip = job_in_dir / "uploaded.zip"
            with open(temp_zip, "wb") as f:
                f.write(content)

            try:
                with zipfile.ZipFile(temp_zip, "r") as z:
                    for member in z.infolist():
                        # Path traversal guard
                        target = (job_in_dir / member.filename).resolve()
                        if not str(target).startswith(str(job_in_dir.resolve())):
                            continue
                        if member.is_dir():
                            continue
                        if member.filename.lower().endswith(".pdf"):
                            target.parent.mkdir(parents=True, exist_ok=True)
                            with z.open(member) as source, open(target, "wb") as dest:
                                shutil.copyfileobj(source, dest)
                            with self.lock:
                                self.job_files[job_id].append(target)
            except Exception as e:
                return f"Corrupt or invalid ZIP archive: {str(e)}"
            finally:
                if temp_zip.exists():
                    temp_zip.unlink()

        # Check PDF
        elif content.startswith(b"%PDF-") or filename.lower().endswith(".pdf"):
            safe_name = os.path.basename(filename)
            target = job_in_dir / safe_name
            with open(target, "wb") as f:
                f.write(content)
            with self.lock:
                self.job_files[job_id].append(target)
        else:
            return f"Unsupported file type for {filename}. Only PDF and ZIP are accepted."

        with self.lock:
            self.jobs[job_id].total_files = len(self.job_files[job_id])
        return None

    def start_processing(self, job_id: str):
        thread = threading.Thread(target=self._process_job_worker, args=(job_id,), daemon=True)
        thread.start()

    def _process_job_worker(self, job_id: str):
        job = self.jobs.get(job_id)
        if not job:
            return

        files = self.job_files.get(job_id, [])
        if not files:
            with self.lock:
                job.status = "FAILED"
                job.error_message = "No valid PDF statements found in upload."
            return

        with self.lock:
            job.status = "PROCESSING"
            job.total_files = len(files)
            job.progress_percentage = 5

        job_out_dir = OUTPUT_DIR / job_id
        results: List[StatementExtractionResult] = []

        total = len(files)
        for idx, pdf_path in enumerate(files):
            fname = pdf_path.name
            with self.lock:
                job.current_file = fname
                job.phase = f"Processing {fname} (PDF inspection)"
                base_pct = 5 + int((idx / total) * 85)
                job.progress_percentage = base_pct

            try:
                # Phases 2-7
                res = extract_ubp_statement(str(pdf_path))
                
                # Phase 8: Excel generation
                with self.lock:
                    job.phase = f"Generating Excel for {fname}"
                excel_path = generate_ubp_excel_workbook(res, str(job_out_dir))
                res.excel_path = excel_path

                results.append(res)

                with self.lock:
                    job.processed_files = idx + 1
                    job.progress_percentage = 5 + int(((idx + 1) / total) * 85)

            except Exception as e:
                # Error on single file
                with self.lock:
                    job.status = "FAILED"
                    job.error_message = f"Failed extracting {fname}: {str(e)}"
                return

        # Package ZIP containing all workbooks and processing manifest
        zip_path = job_out_dir / f"UBP_Extractions_{job_id[:8]}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for r in results:
                if r.excel_path and os.path.exists(r.excel_path):
                    z.write(r.excel_path, arcname=os.path.basename(r.excel_path))
            # Also write processing manifest
            manifest_content = self._generate_manifest_text(results)
            z.writestr("processing_manifest.txt", manifest_content)

            # Write word-level coordinates audit JSON
            coords_manifest = {
                r.metadata.filename: [
                    {
                        "page": rp.page_number,
                        "section": rp.section_name,
                        "word_count": len(rp.word_coordinates),
                        "words": rp.word_coordinates
                    }
                    for rp in r.raw_pages
                ]
                for r in results
            }
            z.writestr("audit_word_coordinates.json", json.dumps(coords_manifest, indent=2))

        # Determine overall status: COMPLETED, REVIEW_REQUIRED, or INCOMPLETE
        has_any_fail = any(any(c.level == "FAIL" for c in r.validation_checks) for r in results)
        has_missing_sections = any(
            (len(r.holdings) == 0 and "HOLDINGS" in r.metadata.detected_sections)
            for r in results
        )
        if has_any_fail:
            final_status = "REVIEW_REQUIRED"
            final_phase = "Extraction complete - Review required due to validation discrepancies"
        elif has_missing_sections:
            final_status = "INCOMPLETE"
            final_phase = "Extraction incomplete - Core financial sections missing"
        else:
            final_status = "COMPLETED"
            final_phase = "Extraction & Excel generation complete"

        with self.lock:
            job.status = final_status
            job.phase = final_phase
            job.progress_percentage = 100
            job.results = results
            job.zip_path = str(zip_path)

    def _generate_manifest_text(self, results: List[StatementExtractionResult]) -> str:
        lines = [
            "=================================================",
            "UBP PORTFOLIO STATEMENT EXTRACTION MANIFEST",
            "=================================================",
            f"Total Statements Processed: {len(results)}",
            ""
        ]
        for r in results:
            meta = r.metadata
            lines.append(f"File: {meta.filename}")
            lines.append(f"  Portfolio Number: {meta.portfolio_number}")
            lines.append(f"  Valuation Date: {meta.valuation_date}")
            lines.append(f"  Pages: {meta.total_pages}")
            lines.append(f"  Holdings Extracted: {len(r.holdings)}")
            lines.append(f"  Current Accounts: {len(r.current_accounts)}")
            lines.append(f"  Loans: {len(r.loans)}")
            lines.append(f"  Validation Checks: {len(r.validation_checks)} (Passed: {sum(1 for c in r.validation_checks if c.level == 'PASS')})")
            lines.append("-------------------------------------------------")
        return "\n".join(lines)

    def get_job(self, job_id: str) -> Optional[ExtractionJobStatus]:
        with self.lock:
            return self.jobs.get(job_id)

    def delete_job(self, job_id: str) -> bool:
        with self.lock:
            if job_id not in self.jobs:
                return False
            del self.jobs[job_id]
            if job_id in self.job_files:
                del self.job_files[job_id]

        # Clean disk
        for base in [INPUT_DIR, OUTPUT_DIR]:
            d = base / job_id
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
        return True

job_manager = JobManager()
