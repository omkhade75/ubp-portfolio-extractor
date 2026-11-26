import os
import glob
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse

from app.services.job_manager import job_manager
from app.config import SAMPLE_PDFS_DIR, OUTPUT_DIR
from app.models.schemas import ExtractionJobStatus, JobLifecycleState

router = APIRouter(prefix="/api")

@router.get("/health")
@router.head("/health")
def health_check():
    return {"status": "ok", "app": "UBP Portfolio Statement Extraction System"}

@router.post("/jobs")
@router.post("/upload")
async def create_extraction_job(
    files: List[UploadFile] = File(...),
):
    """Uploads one or multiple PDFs or a ZIP file and begins deterministic extraction."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    job_id = job_manager.create_job()
    accepted = []

    for upload in files:
        content = await upload.read()
        err = job_manager.add_uploaded_file(job_id, upload.filename, content)
        if err:
            job_manager.delete_job(job_id)
            raise HTTPException(status_code=400, detail=err)
        accepted.append(upload.filename)

    job_manager.start_processing(job_id)
    return {
        "job_id": job_id,
        "status": JobLifecycleState.QUEUED.value,
        "stage": JobLifecycleState.QUEUED.value,
        "accepted_files": accepted,
        "total_files": len(accepted),
        "message": f"Processing queued for {len(accepted)} file(s)."
    }

@router.post("/jobs/load-samples")
def load_sample_files_job():
    """Autonomously loads the 5 original sample PDFs from the workspace for instant processing."""
    sample_files = sorted(glob.glob(str(SAMPLE_PDFS_DIR / "*.pdf")))
    if not sample_files:
        raise HTTPException(status_code=404, detail="Sample PDFs not found in workspace.")

    job_id = job_manager.create_job()
    for sf in sample_files:
        with open(sf, "rb") as f:
            content = f.read()
        err = job_manager.add_uploaded_file(job_id, os.path.basename(sf), content)
        if err:
            job_manager.delete_job(job_id)
            raise HTTPException(status_code=500, detail=err)

    job_manager.start_processing(job_id)
    filenames = [os.path.basename(f) for f in sample_files]
    return {
        "job_id": job_id,
        "status": JobLifecycleState.QUEUED.value,
        "stage": JobLifecycleState.QUEUED.value,
        "accepted_files": filenames,
        "total_files": len(filenames),
        "message": f"Loaded {len(sample_files)} sample PDFs.",
        "files": filenames
    }

@router.get("/jobs/{job_id}", response_model=ExtractionJobStatus)
def get_job_status(job_id: str):
    """Returns extraction phase, progress, and status."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return job

@router.get("/jobs/{job_id}/results")
def get_job_results(job_id: str):
    """Returns complete extraction summary, records, and validation checks."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    if job.status != "COMPLETED":
        return {"status": job.status, "message": "Extraction is not yet completed.", "results": []}
    return {"status": job.status, "results": job.results}

@router.get("/jobs/{job_id}/files")
def get_job_files(job_id: str):
    """Returns list of generated Excel workbooks."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    files_list = []
    for idx, r in enumerate(job.results):
        if r.excel_path and os.path.exists(r.excel_path):
            files_list.append({
                "file_id": idx,
                "filename": os.path.basename(r.excel_path),
                "portfolio_number": r.metadata.portfolio_number,
                "valuation_date": r.metadata.valuation_date,
                "pages": r.metadata.total_pages,
                "holdings_count": len(r.holdings),
                "download_url": f"/api/jobs/{job_id}/download/{idx}"
            })
    return {
        "job_id": job_id,
        "files": files_list,
        "zip_available": bool(job.zip_path and os.path.exists(job.zip_path)),
        "download_all_url": f"/api/jobs/{job_id}/download-all"
    }

@router.get("/jobs/{job_id}/download/{file_id}")
def download_individual_workbook(job_id: str, file_id: int):
    """Downloads an individual Excel workbook by file index."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    if file_id < 0 or file_id >= len(job.results):
        raise HTTPException(status_code=404, detail="File ID out of range.")

    res = job.results[file_id]
    if not res.excel_path or not os.path.exists(res.excel_path):
        raise HTTPException(status_code=404, detail="Excel workbook not found.")

    return FileResponse(
        path=res.excel_path,
        filename=os.path.basename(res.excel_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@router.get("/jobs/{job_id}/download-all")
def download_all_workbooks_zip(job_id: str):
    """Downloads a ZIP containing all generated workbooks and manifest."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    if not job.zip_path or not os.path.exists(job.zip_path):
        raise HTTPException(status_code=404, detail="Extraction ZIP not found.")

    return FileResponse(
        path=job.zip_path,
        filename=f"UBP_Portfolio_Extractions_{job_id[:8]}.zip",
        media_type="application/zip"
    )

@router.delete("/jobs/{job_id}")
def delete_extraction_job(job_id: str):
    """Clears extraction job and temporary files."""
    deleted = job_manager.delete_job(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return {"job_id": job_id, "deleted": True, "message": "Extraction job cleared."}
