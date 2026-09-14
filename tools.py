# tools.py - Extensible Tool Registry and Plugin System for AI Web Scraper
import os
import sys
import json
import logging
import importlib.util
from typing import Callable, Dict, Any, List, Optional
from pydantic import BaseModel

from scrape import scrape_website, extract_body_content, clean_body_content, capture_page_screenshot, extract_animation_assets
from parse import extract_with_ai
from schemas import EXTRACTION_TEMPLATES, create_dynamic_model
from db import save_scrape, save_extraction, get_recent_scrapes, get_recent_extractions, detect_price_changes
from webhook import send_webhook

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Global Tool Registry
REGISTERED_TOOLS: Dict[str, Dict[str, Any]] = {}


def register_tool(name: str, description: str, parameters: Dict[str, Any]):
    """
    Decorator to register a function as an AI tool for the Assistant and MCP Server.

    parameters should be a JSON Schema dict:
    {
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "..."}
        },
        "required": ["param1"]
    }
    """
    def decorator(func: Callable):
        REGISTERED_TOOLS[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "func": func
        }
        return func
    return decorator


# ==============================================================================
# BUILT-IN CORE TOOLS
# ==============================================================================

@register_tool(
    name="scrape_page",
    description="Fetch and clean the text content of any website URL. Returns cleaned readable text and metadata.",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Target webpage URL to scrape."},
            "mode": {
                "type": "string",
                "enum": ["fast", "local", "bright_data"],
                "description": "Scraping engine: 'fast' (HTTP), 'local' (Headless Chrome), or 'bright_data' (Proxy)."
            }
        },
        "required": ["url"]
    }
)
def tool_scrape_page(url: str, mode: str = "fast") -> Dict[str, Any]:
    raw_html = scrape_website(url, mode=mode)
    body = extract_body_content(raw_html)
    cleaned = clean_body_content(body)
    scrape_id = save_scrape(url, mode, raw_html, cleaned)
    return {
        "scrape_id": scrape_id,
        "url": url,
        "raw_characters": len(raw_html),
        "cleaned_characters": len(cleaned),
        "content": cleaned[:4000] + ("\n...[truncated for context]" if len(cleaned) > 4000 else "")
    }


@register_tool(
    name="extract_structured_data",
    description="Scrape a webpage and extract structured information using AI and Pydantic schemas (e.g. products, jobs, articles, quotes).",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The webpage URL to scrape."},
            "prompt": {"type": "string", "description": "Instructions for what information to extract."},
            "template": {
                "type": "string",
                "enum": ["ecommerce", "jobs", "realestate", "articles", "quotes"],
                "description": "Optional domain schema template to enforce structured fields."
            },
            "provider": {
                "type": "string",
                "enum": ["gemini", "ollama", "openai"],
                "description": "AI provider for extraction (default: gemini)."
            }
        },
        "required": ["url", "prompt"]
    }
)
def tool_extract_data(url: str, prompt: str, template: str = None, provider: str = "gemini") -> Dict[str, Any]:
    raw_html = scrape_website(url, mode="fast")
    cleaned = clean_body_content(extract_body_content(raw_html))
    scrape_id = save_scrape(url, "fast", raw_html, cleaned)

    schema_class = None
    template_mapping = {
        "ecommerce": "🛍️ E-Commerce Products",
        "jobs": "💼 Job Postings",
        "realestate": "🏡 Real Estate Listings",
        "articles": "📰 Article & News Summaries",
        "quotes": "💬 Quotes & Testimonials"
    }

    if template and template in template_mapping:
        schema_class = EXTRACTION_TEMPLATES[template_mapping[template]]["model"]

    result = extract_with_ai(
        dom_content=cleaned,
        parse_description=prompt,
        provider=provider,
        output_format="json",
        schema_class=schema_class
    )

    save_extraction(scrape_id, url, template or "custom", prompt, result)

    price_changes = []
    if isinstance(result, list):
        price_changes = detect_price_changes(url, result)

    return {
        "url": url,
        "items_extracted": len(result) if isinstance(result, list) else 1,
        "price_changes_detected": price_changes,
        "data": result
    }


@register_tool(
    name="take_screenshot",
    description="Capture a high-resolution full-page screenshot of a webpage using Headless Chrome.",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Target webpage URL to capture."}
        },
        "required": ["url"]
    }
)
def tool_take_screenshot(url: str) -> Dict[str, Any]:
    path = capture_page_screenshot(url)
    size = os.path.getsize(path) if os.path.exists(path) else 0
    return {
        "url": url,
        "screenshot_path": path,
        "file_size_bytes": size,
        "status": "success"
    }


@register_tool(
    name="query_scrape_history",
    description="Query the local SQLite database for recent scrape logs, URLs, and extraction history.",
    parameters={
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Number of recent records to retrieve (default: 5)."}
        }
    }
)
def tool_query_history(limit: int = 5) -> Dict[str, Any]:
    scrapes = get_recent_scrapes(limit=limit)
    extractions = get_recent_extractions(limit=limit)
    return {
        "recent_scrapes": scrapes,
        "recent_extractions": extractions
    }


@register_tool(
    name="send_webhook_alert",
    description="Dispatch an alert or notification containing extracted data to Discord, Slack, or generic webhook.",
    parameters={
        "type": "object",
        "properties": {
            "webhook_url": {"type": "string", "description": "Destination webhook URL."},
            "title": {"type": "string", "description": "Title or header of the notification."},
            "content": {"type": "string", "description": "Message content or stringified JSON payload."}
        },
        "required": ["webhook_url", "title", "content"]
    }
)
def tool_send_webhook(webhook_url: str, title: str, content: str) -> Dict[str, Any]:
    return send_webhook(webhook_url, title, content)


@register_tool(
    name="extract_web_animations",
    description="Inspect any webpage HTML and extract all animation/motion assets including Lottie JSON files, Rive (.riv) assets, animated SVG graphics, GIF/WebM loops, animation JS libraries (GSAP, Three.js), and CSS @keyframes.",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Webpage URL to inspect for animation and motion assets."},
            "mode": {
                "type": "string",
                "enum": ["fast", "local", "bright_data"],
                "description": "Scraping engine: 'fast', 'local', or 'bright_data' (default: 'fast')."
            }
        },
        "required": ["url"]
    }
)
def tool_extract_web_animations(url: str, mode: str = "fast") -> Dict[str, Any]:
    raw_html = scrape_website(url, mode=mode)
    assets = extract_animation_assets(raw_html, base_url=url)
    return assets


@register_tool(
    name="schedule_scrape_job",
    description="Schedule an automated recurring background scrape job for a URL with interval, optional template or prompt, and webhook alert.",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Descriptive title for the scheduled monitor job."},
            "url": {"type": "string", "description": "Target webpage URL to monitor."},
            "interval_minutes": {"type": "integer", "description": "Run frequency in minutes (e.g. 15, 60, 360)."},
            "scrape_type": {
                "type": "string",
                "enum": ["text", "animations"],
                "description": "Whether to extract structured text or monitor animation assets (default: 'text')."
            },
            "template": {
                "type": "string",
                "enum": ["ecommerce", "jobs", "realestate", "articles", "quotes"],
                "description": "Optional schema template for structured data extraction."
            },
            "prompt": {"type": "string", "description": "Custom extraction instructions for the AI model."},
            "webhook_url": {"type": "string", "description": "Discord or Slack webhook URL to receive change alerts."},
            "alert_on_change_only": {"type": "boolean", "description": "Only send webhook alert when content/price shifts are detected (default: true)."}
        },
        "required": ["name", "url", "interval_minutes"]
    }
)
def tool_schedule_scrape_job(
    name: str,
    url: str,
    interval_minutes: int = 60,
    scrape_type: str = "text",
    template: Optional[str] = None,
    prompt: Optional[str] = None,
    webhook_url: Optional[str] = None,
    alert_on_change_only: bool = True
) -> Dict[str, Any]:
    import scheduler
    job_id = scheduler.create_job(
        name=name,
        url=url,
        mode="fast",
        scrape_type=scrape_type,
        template=template,
        prompt=prompt,
        interval_minutes=interval_minutes,
        webhook_url=webhook_url,
        alert_on_change_only=alert_on_change_only
    )
    job = scheduler.get_job(job_id)
    return {
        "success": True,
        "message": f"Successfully scheduled monitor job #{job_id} ('{name}') every {interval_minutes} minutes.",
        "job": job
    }


@register_tool(
    name="list_scrape_jobs",
    description="List all active and paused recurring scrape jobs and their next scheduled execution times.",
    parameters={
        "type": "object",
        "properties": {}
    }
)
def tool_list_scrape_jobs() -> Dict[str, Any]:
    import scheduler
    jobs = scheduler.list_jobs()
    return {
        "total_jobs": len(jobs),
        "jobs": jobs
    }


@register_tool(
    name="trigger_scrape_job",
    description="Manually trigger immediate execution of a scheduled recurring scrape job.",
    parameters={
        "type": "object",
        "properties": {
            "job_id": {"type": "integer", "description": "The ID of the scheduled job to run."}
        },
        "required": ["job_id"]
    }
)
def tool_trigger_scrape_job(job_id: int) -> Dict[str, Any]:
    import scheduler
    return scheduler.trigger_job_now(job_id)


# ==============================================================================
# TOOL REGISTRY MANAGEMENT & EXPORTS
# ==============================================================================

def get_all_tools() -> Dict[str, Dict[str, Any]]:
    """Return all registered tools."""
    return REGISTERED_TOOLS


def execute_tool(name: str, arguments: Dict[str, Any]) -> Any:
    """Execute a registered tool by name with arguments."""
    if name not in REGISTERED_TOOLS:
        raise ValueError(f"Tool '{name}' is not registered. Available tools: {list(REGISTERED_TOOLS.keys())}")
    func = REGISTERED_TOOLS[name]["func"]
    return func(**arguments)


def get_openai_tool_definitions() -> List[Dict[str, Any]]:
    """Export tool definitions in OpenAI function-calling format."""
    defs = []
    for name, t in REGISTERED_TOOLS.items():
        defs.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"]
            }
        })
    return defs


def get_gemini_tool_declarations() -> List[Dict[str, Any]]:
    """Export function declarations for Google Gemini SDK."""
    declarations = []
    for name, t in REGISTERED_TOOLS.items():
        declarations.append({
            "name": t["name"],
            "description": t["description"],
            "parameters": t["parameters"]
        })
    return declarations


def load_plugins(plugins_dir: str = "plugins"):
    """
    Dynamically load custom Python plugins from a directory.
    Any Python file with functions decorated by @register_tool will be automatically added.
    """
    if not os.path.exists(plugins_dir):
        os.makedirs(plugins_dir, exist_ok=True)
        return

    for filename in os.listdir(plugins_dir):
        if filename.endswith(".py") and not filename.startswith("__"):
            module_name = f"plugins.{filename[:-3]}"
            file_path = os.path.join(plugins_dir, filename)
            try:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                mod = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = mod
                spec.loader.exec_module(mod)
                logging.info(f"Loaded custom plugin: {filename}")
            except Exception as e:
                logging.error(f"Failed to load plugin {filename}: {e}")
