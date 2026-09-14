# api.py - FastAPI Headless REST API for AI Web Scraper
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

from scrape import scrape_website, extract_body_content, clean_body_content
from parse import extract_with_ai
from schemas import EXTRACTION_TEMPLATES, create_dynamic_model
from db import save_scrape, save_extraction, get_recent_scrapes, get_recent_extractions, detect_price_changes
from webhook import send_webhook

app = FastAPI(
    title="AI Web Scraper REST API",
    description="Headless API for scraping websites and extracting structured data with AI models.",
    version="2.0.0"
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
        "service": "AI Web Scraper REST API",
        "version": "2.0.0",
        "endpoints": {
            "templates": "/api/templates",
            "scrape": "/api/scrape",
            "extract": "/api/extract",
            "history": "/api/history"
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
    """Scrape and clean a web page without running AI extraction."""
    try:
        raw_html = scrape_website(req.url, mode=req.mode, timeout=req.timeout)
        body = extract_body_content(raw_html)
        cleaned = clean_body_content(body)
        scrape_id = save_scrape(req.url, req.mode, raw_html, cleaned)

        return {
            "scrape_id": scrape_id,
            "url": req.url,
            "raw_characters": len(raw_html),
            "cleaned_characters": len(cleaned),
            "cleaned_preview": cleaned[:500] + ("..." if len(cleaned) > 500 else "")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/extract")
def extract_endpoint(req: ExtractRequest, background_tasks: BackgroundTasks):
    """End-to-end web scraping and structured AI extraction."""
    try:
        # 1. Scrape & clean DOM
        raw_html = scrape_website(req.url, mode=req.mode)
        body = extract_body_content(raw_html)
        cleaned = clean_body_content(body)
        scrape_id = save_scrape(req.url, req.mode, raw_html, cleaned)

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

        return {
            "scrape_id": scrape_id,
            "url": req.url,
            "provider": req.provider,
            "model": req.model,
            "extracted_items_count": len(result) if isinstance(result, list) else 1,
            "price_changes_detected": price_changes,
            "results": result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history")
def history_endpoint(limit: int = Query(10, ge=1, le=50)):
    """Retrieve recent scrape and extraction records."""
    return {
        "recent_scrapes": get_recent_scrapes(limit=limit),
        "recent_extractions": get_recent_extractions(limit=limit)
    }
