# api.py - FastAPI Headless REST API for OmniScrape AI
import os
import sys
import time
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Ensure src/ is on sys.path
_src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from omniscrape.engine.scrape import (
    scrape_website,
    extract_body_content,
    clean_body_content,
    extract_animation_assets,
    bundle_animations_zip,
    capture_page_screenshot
)
from omniscrape.engine.parse import extract_with_ai
from omniscrape.models.schemas import EXTRACTION_TEMPLATES, create_dynamic_model
from omniscrape.storage.db import save_scrape, save_extraction, get_recent_scrapes, get_recent_extractions, detect_price_changes
from omniscrape.storage.outputs import default_output_manager
from omniscrape.automation.webhook import send_webhook
import scheduler

app = FastAPI(
    title="OmniScrape AI REST API",
    description="Headless API for autonomous multi-modal web scraping, structured data extraction, animation inspection, and recurring background monitors.",
    version="2.2.0"
)


class ScrapeRequest(BaseModel):
    url: str = Field(..., description="Target webpage URL")
    mode: str = Field("fast", description="Scraper mode: 'fast', 'local', or 'bright_data'")
    timeout: int = Field(30, description="Page load timeout in seconds")


class ExtractRequest(BaseModel):
    url: str = Field(..., description="Target webpage URL")
    mode: str = Field("fast", description="Scraper mode: 'fast', 'local', or 'bright_data'")
    prompt: Optional[str] = Field(None, description="Custom natural language extraction instructions")
    template: Optional[str] = Field(None, description="Pre-defined template name (e.g. '🛍️ E-Commerce Products')")
    custom_fields: Optional[List[str]] = Field(None, description="Custom field names if creating dynamic schema")
    provider: str = Field("gemini", description="AI provider: 'gemini', 'ollama', or 'openai'")
    model: Optional[str] = Field(None, description="Model identifier (e.g. 'gemini-2.5-flash', 'llama3.1')")
    api_key: Optional[str] = Field(None, description="Provider API key (if not configured in .env)")
    output_format: str = Field("json", description="'json' or 'markdown'")
    webhook_url: Optional[str] = Field(None, description="Optional webhook URL to receive extracted results")


@app.get("/")
def root():
    return {
        "status": "online",
        "service": "OmniScrape AI REST API",
        "version": "2.2.0",
        "endpoints": {
            "templates": "/api/templates",
            "scrape": "/api/scrape",
            "scrape_animations": "/api/scrape/animations",
            "extract": "/api/extract",
            "history": "/api/history",
            "runs": "/api/runs",
            "jobs": "/api/jobs"
        }
    }


@app.get("/api/templates")
def list_templates():
    """List all available pre-defined schema templates."""
    results = {}
    for name, data in EXTRACTION_TEMPLATES.items():
        results[name] = {
            "description": data["description"],
            "default_prompt": data["default_prompt"],
            "fields": list(data["model"].model_fields.keys())
        }
    return {"templates": results}


@app.post("/api/scrape")
def scrape_endpoint(req: ScrapeRequest):
    """Scrape and clean a web page and record an isolated run in outputs/runs/."""
    start_time = time.time()
    run_info = default_output_manager.create_run(url=req.url, task_type="scrape", mode=req.mode)
    run_dir = run_info["run_dir"]

    try:
        raw_html = scrape_website(req.url, mode=req.mode, timeout=req.timeout)
        default_output_manager.save_text(run_dir, "raw_page.html", raw_html, category="html")

        body = extract_body_content(raw_html)
        cleaned = clean_body_content(body)
        scrape_id = save_scrape(req.url, req.mode, raw_html, cleaned)
        default_output_manager.save_text(run_dir, "cleaned_dom.txt", cleaned, category="text")
        default_output_manager.finalize_run(run_dir, status="success", duration_seconds=time.time() - start_time)

        return {
            "scrape_id": scrape_id,
            "run_id": run_info["run_id"],
            "output_dir": run_dir,
            "url": req.url,
            "raw_characters": len(raw_html),
            "cleaned_characters": len(cleaned),
            "cleaned_preview": cleaned[:500] + ("..." if len(cleaned) > 500 else "")
        }
    except Exception as e:
        default_output_manager.finalize_run(run_dir, status="failed", duration_seconds=time.time() - start_time, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scrape/animations")
def scrape_animations_endpoint(req: ScrapeRequest):
    """
    Inspect webpage HTML and extract all animation/motion assets:
    Lottie JSON, Rive .riv, animated SVGs, GIFs/videos, animation JS libraries, and CSS keyframes.
    """
    start_time = time.time()
    run_info = default_output_manager.create_run(url=req.url, task_type="animations", mode=req.mode)
    run_dir = run_info["run_dir"]

    try:
        raw_html = scrape_website(req.url, mode=req.mode, timeout=req.timeout)
        default_output_manager.save_text(run_dir, "raw_page.html", raw_html, category="html")

        assets = extract_animation_assets(raw_html, base_url=req.url)
        default_output_manager.save_json(run_dir, "animation_assets.json", assets, category="json")

        zip_bytes = bundle_animations_zip(assets, base_url=req.url)
        default_output_manager.save_zip(run_dir, "animations.zip", zip_bytes, category="archive")
        default_output_manager.finalize_run(run_dir, status="success", duration_seconds=time.time() - start_time)

        assets["run_id"] = run_info["run_id"]
        assets["output_dir"] = run_dir
        return assets
    except Exception as e:
        default_output_manager.finalize_run(run_dir, status="failed", duration_seconds=time.time() - start_time, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/extract")
def extract_endpoint(req: ExtractRequest, background_tasks: BackgroundTasks):
    """End-to-end web scraping and structured AI extraction."""
    start_time = time.time()
    run_info = default_output_manager.create_run(
        url=req.url,
        task_type="extract",
        mode=req.mode,
        template=req.template,
        prompt=req.prompt
    )
    run_dir = run_info["run_dir"]

    try:
        # 1. Scrape & clean DOM
        raw_html = scrape_website(req.url, mode=req.mode)
        default_output_manager.save_text(run_dir, "raw_page.html", raw_html, category="html")

        body = extract_body_content(raw_html)
        cleaned = clean_body_content(body)
        scrape_id = save_scrape(req.url, req.mode, raw_html, cleaned)
        default_output_manager.save_text(run_dir, "cleaned_dom.txt", cleaned, category="text")

        # 2. Determine schema
        schema_class = None
        instruction = req.prompt or ""

        if req.template and req.template in EXTRACTION_TEMPLATES:
            t_data = EXTRACTION_TEMPLATES[req.template]
            schema_class = t_data["model"]
            instruction = instruction or t_data["default_prompt"]
        elif req.custom_fields:
            schema_class = create_dynamic_model(req.custom_fields)
            instruction = instruction or f"Extract all items with fields: {', '.join(req.custom_fields)}"

        if not instruction:
            instruction = "Extract all key information from this webpage."

        # 3. AI Extraction
        result = extract_with_ai(
            dom_content=cleaned,
            parse_description=instruction,
            provider=req.provider,
            model_name=req.model,
            api_key=req.api_key,
            output_format=req.output_format,
            schema_class=schema_class
        )

        # 4. Save extraction and detect price changes if applicable
        save_extraction(scrape_id, req.url, req.template or "custom", instruction, result)
        default_output_manager.save_json(run_dir, "extracted_data.json", result, category="json")
        if isinstance(result, list) and result:
            try:
                default_output_manager.save_csv(run_dir, "extracted_data.csv", result, category="tabular")
            except Exception:
                pass

        price_changes = []
        if isinstance(result, list):
            price_changes = detect_price_changes(req.url, result)

        # 5. Dispatch webhook in background if requested
        if req.webhook_url:
            background_tasks.add_task(
                send_webhook,
                req.webhook_url,
                f"AI Scrape Result: {req.url}",
                result
            )

        default_output_manager.finalize_run(run_dir, status="success", duration_seconds=time.time() - start_time)

        return {
            "scrape_id": scrape_id,
            "run_id": run_info["run_id"],
            "output_dir": run_dir,
            "url": req.url,
            "provider": req.provider,
            "model": req.model,
            "extracted_items_count": len(result) if isinstance(result, list) else 1,
            "price_changes_detected": price_changes,
            "results": result
        }

    except Exception as e:
        default_output_manager.finalize_run(run_dir, status="failed", duration_seconds=time.time() - start_time, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history")
def history_endpoint(limit: int = Query(10, ge=1, le=50)):
    """Retrieve recent scrape and extraction database records."""
    return {
        "recent_scrapes": get_recent_scrapes(limit=limit),
        "recent_extractions": get_recent_extractions(limit=limit)
    }


# ==============================================================================
# RUN OUTPUT EXPLORER ENDPOINTS
# ==============================================================================

@app.get("/api/runs")
def list_runs_endpoint(limit: int = Query(20, ge=1, le=100)):
    """List all saved execution runs in the outputs directory."""
    runs = default_output_manager.list_runs(limit=limit)
    return {
        "total_runs": len(runs),
        "runs": runs
    }


@app.get("/api/runs/{run_id}")
def get_run_endpoint(run_id: str):
    """Retrieve detailed manifest and file map for a specific run ID."""
    run = default_output_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    return run


@app.get("/api/runs/{run_id}/download")
def download_run_zip_endpoint(run_id: str):
    """Download the full run output folder as a ZIP file."""
    buf = default_output_manager.export_run_zip(run_id)
    if not buf:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={run_id}.zip"}
    )


@app.delete("/api/runs/{run_id}")
def delete_run_endpoint(run_id: str):
    """Delete a run folder and its contents."""
    success = default_output_manager.delete_run(run_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    return {"success": True, "message": f"Run '{run_id}' deleted."}


# ==============================================================================
# SCHEDULED RECURRING SCRAPE JOBS & AUTONOMOUS MONITOR
# ==============================================================================

class CreateJobRequest(BaseModel):
    name: str = Field(..., description="Descriptive job title")
    url: str = Field(..., description="Target website URL")
    mode: str = Field("fast", description="'fast', 'local', or 'bright_data'")
    scrape_type: str = Field("text", description="'text' or 'animations'")
    template: Optional[str] = Field(None, description="Schema template (e.g. 'ecommerce')")
    prompt: Optional[str] = Field(None, description="Custom extraction instructions")
    interval_minutes: int = Field(60, ge=1, description="Interval in minutes")
    webhook_url: Optional[str] = Field(None, description="Discord/Slack/Zapier webhook URL")
    alert_on_change_only: bool = Field(True, description="Only trigger alerts when price/content shifts occur")


@app.get("/api/jobs")
def list_jobs_endpoint():
    """List all scheduled recurring scrape jobs with their status and next run times."""
    return {"jobs": scheduler.list_jobs()}


@app.post("/api/jobs")
def create_job_endpoint(req: CreateJobRequest):
    """Register a new recurring scrape job for background execution."""
    try:
        job_id = scheduler.create_job(
            name=req.name,
            url=req.url,
            mode=req.mode,
            scrape_type=req.scrape_type,
            template=req.template,
            prompt=req.prompt,
            interval_minutes=req.interval_minutes,
            webhook_url=req.webhook_url,
            alert_on_change_only=req.alert_on_change_only
        )
        return {
            "success": True,
            "message": f"Job #{job_id} ('{req.name}') scheduled successfully.",
            "job": scheduler.get_job(job_id)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs/{job_id}/logs")
def get_job_logs_endpoint(job_id: int, limit: int = Query(20, ge=1, le=100)):
    """Retrieve execution history logs for a specific scheduled job."""
    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job #{job_id} not found.")
    return {
        "job": job,
        "logs": scheduler.get_job_logs(job_id, limit=limit)
    }


@app.post("/api/jobs/{job_id}/run")
def trigger_job_endpoint(job_id: int):
    """Manually trigger immediate execution of a scheduled scrape job."""
    try:
        result = scheduler.trigger_job_now(job_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/jobs/{job_id}/toggle")
def toggle_job_endpoint(job_id: int):
    """Pause or resume a scheduled job."""
    success = scheduler.toggle_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Job #{job_id} not found.")
    job = scheduler.get_job(job_id)
    return {
        "success": True,
        "is_active": bool(job["is_active"]),
        "status": "active" if job["is_active"] else "paused"
    }


@app.delete("/api/jobs/{job_id}")
def delete_job_endpoint(job_id: int):
    """Delete a scheduled job and its execution history."""
    success = scheduler.delete_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Job #{job_id} not found.")
    return {"success": True, "message": f"Job #{job_id} deleted."}
