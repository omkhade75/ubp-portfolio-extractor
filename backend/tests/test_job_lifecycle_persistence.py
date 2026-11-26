import os
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.job_manager import job_manager
from app.services.job_store import job_store
from app.models.schemas import JobLifecycleState

client = TestClient(app)

def test_health_get_and_head():
    """Verify /api/health supports both GET and HEAD methods."""
    res_get = client.get("/api/health")
    assert res_get.status_code == 200
    assert res_get.json()["status"] == "ok"

    res_head = client.head("/api/health")
    assert res_head.status_code == 200

def test_job_persistence_survives_memory_wipe():
    """Verify jobs persist in SQLite and survive complete RAM clearance."""
    job_id = job_manager.create_job()
    assert job_id is not None

    # Verify initial state in memory and database
    job = job_manager.get_job(job_id)
    assert job is not None
    assert job.status == JobLifecycleState.QUEUED.value
    assert job.stage == JobLifecycleState.QUEUED.value

    # Simulate container restart or multi-worker switch by wiping RAM cache
    job_manager.jobs.clear()
    assert job_id not in job_manager.jobs

    # Retrieval must query SQLite store and recover the job
    recovered_job = job_manager.get_job(job_id)
    assert recovered_job is not None
    assert recovered_job.job_id == job_id
    assert recovered_job.status == JobLifecycleState.QUEUED.value

    # Clean up
    job_manager.delete_job(job_id)
    assert job_manager.get_job(job_id) is None

def test_upload_endpoint_and_aliases():
    """Verify both /api/upload and /api/jobs work identically with standard response."""
    test_pdf_content = b"%PDF-1.4\n%mock pdf\n%%EOF"
    
    # 1. Test /api/upload alias
    res_upload = client.post(
        "/api/upload",
        files={"files": ("test_upload.pdf", test_pdf_content, "application/pdf")}
    )
    assert res_upload.status_code == 200
    data_upload = res_upload.json()
    assert "job_id" in data_upload
    assert data_upload["status"] == JobLifecycleState.QUEUED.value
    assert data_upload["stage"] == JobLifecycleState.QUEUED.value
    assert "test_upload.pdf" in data_upload["accepted_files"]
    assert data_upload["total_files"] == 1

    job_id_1 = data_upload["job_id"]
    status_res = client.get(f"/api/jobs/{job_id_1}")
    assert status_res.status_code == 200

    # 2. Test /api/jobs endpoint
    res_jobs = client.post(
        "/api/jobs",
        files={"files": ("test_jobs.pdf", test_pdf_content, "application/pdf")}
    )
    assert res_jobs.status_code == 200
    data_jobs = res_jobs.json()
    assert "job_id" in data_jobs
    assert data_jobs["status"] == JobLifecycleState.QUEUED.value
    assert "test_jobs.pdf" in data_jobs["accepted_files"]

    # 3. Test non-existent job returns 404
    fake_id = "00000000-0000-0000-0000-000000000000"
    res_404 = client.get(f"/api/jobs/{fake_id}")
    assert res_404.status_code == 404
    assert f"Job {fake_id} not found" in res_404.json()["detail"]

    # Cleanup
    job_manager.delete_job(job_id_1)
    job_manager.delete_job(data_jobs["job_id"])
