# src/omniscrape/copilot/tools.py - Extensible Tool Registry and Plugin System
import os
import sys
import json
import logging
import importlib.util
from typing import Callable, Dict, Any, List, Optional
from pydantic import BaseModel

from ..engine.scrape import (
    scrape_website,
    extract_body_content,
    clean_body_content,
    capture_page_screenshot,
    extract_animation_assets
)
from ..engine.parse import extract_with_ai
from ..models.schemas import EXTRACTION_TEMPLATES, create_dynamic_model
from ..storage.db import (
    save_scrape,
    save_extraction,
    get_recent_scrapes,
    get_recent_extractions,
    detect_price_changes
)
from ..storage.outputs import default_output_manager
from ..automation.webhook import send_webhook
from ..automation import scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Global Tool Registry
REGISTERED_TOOLS: Dict[str, Dict[str, Any]] = {}


def register_tool(name: str, description: str, parameters: Dict[str, Any]):
    """
    Decorator to register a function as an AI tool for the Assistant and MCP Server.
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

    # Record output in isolated run folder
    run_info = default_output_manager.create_run(url=url, task_type="scrape_page", mode=mode)
    default_output_manager.save_text(run_info["run_dir"], "cleaned_dom.txt", cleaned, category="text")
    default_output_manager.finalize_run(run_info["run_dir"], status="success")

    return {
        "scrape_id": scrape_id,
        "run_id": run_info["run_id"],
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
def tool_extract_structured_data(
    url: str,
    prompt: str,
    template: Optional[str] = None,
    provider: str = "gemini"
) -> Dict[str, Any]:
    raw_html = scrape_website(url, mode="fast")
    body = extract_body_content(raw_html)
    cleaned = clean_body_content(body)
    scrape_id = save_scrape(url, "fast", raw_html, cleaned)

    schema_class = None
    template_key = None
    if template:
        template_map = {
            "ecommerce": "🛍️ E-Commerce Products",
            "jobs": "💼 Job Postings",
            "realestate": "🏡 Real Estate Listings",
            "articles": "📰 Article & News Summaries",
            "quotes": "💬 Quotes & Testimonials"
        }
        template_key = template_map.get(template.lower())
        if template_key and template_key in EXTRACTION_TEMPLATES:
            schema_class = EXTRACTION_TEMPLATES[template_key]["model"]

    extracted = extract_with_ai(
        dom_content=cleaned,
        parse_description=prompt,
        provider=provider,
        output_format="json",
        schema_class=schema_class
    )

    save_extraction(scrape_id, url, template or "custom", prompt, extracted)

    # Detect price shifts if structured records are returned
    price_changes = []
    if isinstance(extracted, list):
        price_changes = detect_price_changes(url, extracted)

    # Record output in isolated run folder
    run_info = default_output_manager.create_run(
        url=url,
        task_type="extract_structured_data",
        mode="fast",
        template=template,
        prompt=prompt
    )
    run_dir = run_info["run_dir"]
    default_output_manager.save_text(run_dir, "cleaned_dom.txt", cleaned, category="text")
    default_output_manager.save_json(run_dir, "extracted_data.json", extracted, category="json")
    if isinstance(extracted, list) and extracted:
        try:
            default_output_manager.save_csv(run_dir, "extracted_data.csv", extracted, category="tabular")
        except Exception:
            pass
    default_output_manager.finalize_run(run_dir, status="success")

    return {
        "url": url,
        "run_id": run_info["run_id"],
        "template": template or "freeform",
        "data": extracted,
        "price_changes": price_changes
    }


@register_tool(
    name="extract_web_animations",
    description="Detect and extract motion and animation assets (Lottie, Rive, SVGs, GIFs, JS libs, and CSS keyframes) from a webpage.",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The webpage URL to inspect for animation assets."}
        },
        "required": ["url"]
    }
)
def tool_extract_web_animations(url: str) -> Dict[str, Any]:
    raw_html = scrape_website(url, mode="fast")
    assets = extract_animation_assets(raw_html, base_url=url)

    # Record output in isolated run folder
    run_info = default_output_manager.create_run(url=url, task_type="extract_web_animations", mode="fast")
    default_output_manager.save_json(run_info["run_dir"], "animation_assets.json", assets, category="json")
    default_output_manager.finalize_run(run_info["run_dir"], status="success")

    return {
        "url": url,
        "run_id": run_info["run_id"],
        "total_assets_count": assets.get("total_assets_count", 0),
        "lottie_files_count": len(assets.get("lottie_files", [])),
        "rive_files_count": len(assets.get("rive_files", [])),
        "svg_animations_count": len(assets.get("svg_animations", [])),
        "motion_media_count": len(assets.get("motion_media", [])),
        "animation_libraries": [lib["library"] for lib in assets.get("animation_libraries", [])],
        "css_keyframes_count": len(assets.get("css_keyframes", [])),
        "details": assets
    }


@register_tool(
    name="take_screenshot",
    description="Capture a high-resolution full-page screenshot of any webpage using Headless Chrome.",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Target webpage URL to capture."}
        },
        "required": ["url"]
    }
)
def tool_take_screenshot(url: str) -> Dict[str, Any]:
    run_info = default_output_manager.create_run(url=url, task_type="take_screenshot", mode="local")
    run_dir = run_info["run_dir"]
    ss_target = os.path.join(run_dir, "screenshot.png")
    ss_path = capture_page_screenshot(url, output_path=ss_target)
    default_output_manager.save_image(run_dir, "screenshot.png", ss_path, category="image")
    default_output_manager.finalize_run(run_dir, status="success")

    return {
        "url": url,
        "run_id": run_info["run_id"],
        "screenshot_path": ss_path,
        "status": "success"
    }


@register_tool(
    name="query_scrape_history",
    description="Query past scrape and extraction logs from the SQLite database.",
    parameters={
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Number of recent records to retrieve (default: 5)."}
        }
    }
)
def tool_query_scrape_history(limit: int = 5) -> Dict[str, Any]:
    scrapes = get_recent_scrapes(limit=limit)
    extractions = get_recent_extractions(limit=limit)
    return {
        "recent_scrapes": scrapes,
        "recent_extractions": extractions
    }


@register_tool(
    name="list_runs",
    description="List all past scraper execution runs and artifacts saved in the outputs folder.",
    parameters={
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Number of runs to retrieve (default: 10)."}
        }
    }
)
def tool_list_runs(limit: int = 10) -> Dict[str, Any]:
    runs = default_output_manager.list_runs(limit=limit)
    return {
        "total_runs": len(runs),
        "runs": runs
    }


@register_tool(
    name="get_run_output",
    description="Get full metadata, file manifest, and contents for a specific execution run ID.",
    parameters={
        "type": "object",
        "properties": {
            "run_id": {"type": "string", "description": "The unique ID of the run folder."}
        },
        "required": ["run_id"]
    }
)
def tool_get_run_output(run_id: str) -> Dict[str, Any]:
    run = default_output_manager.get_run(run_id)
    if not run:
        return {"error": f"Run '{run_id}' not found."}
    return run


@register_tool(
    name="send_webhook_alert",
    description="Dispatch an instant alert payload to Discord, Slack, or generic webhook URLs.",
    parameters={
        "type": "object",
        "properties": {
            "webhook_url": {"type": "string", "description": "The destination webhook URL."},
            "title": {"type": "string", "description": "Alert title or subject."},
            "content": {"type": "string", "description": "Alert body text or JSON string."}
        },
        "required": ["webhook_url", "title", "content"]
    }
)
def tool_send_webhook_alert(webhook_url: str, title: str, content: str) -> Dict[str, Any]:
    return send_webhook(webhook_url, title, content)


# Backward-compatible tool function aliases
tool_extract_data = tool_extract_structured_data
tool_query_history = tool_query_scrape_history
tool_send_webhook = tool_send_webhook_alert


@register_tool(
    name="schedule_scrape_job",
    description="Schedule a recurring background scrape task with optional price diff tracking and webhook alerts.",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Friendly label for this recurring monitor."},
            "url": {"type": "string", "description": "Target webpage URL to monitor."},
            "interval_minutes": {"type": "integer", "description": "Frequency in minutes between scrapes (default: 60)."},
            "scrape_type": {
                "type": "string",
                "enum": ["text", "animations"],
                "description": "What to extract: 'text' or 'animations'."
            },
            "webhook_url": {"type": "string", "description": "Optional webhook endpoint for change notifications."}
        },
        "required": ["name", "url"]
    }
)
def tool_schedule_scrape_job(
    name: str,
    url: str,
    interval_minutes: int = 60,
    scrape_type: str = "text",
    webhook_url: Optional[str] = None
) -> Dict[str, Any]:
    job_id = scheduler.create_job(
        name=name,
        url=url,
        interval_minutes=interval_minutes,
        scrape_type=scrape_type,
        webhook_url=webhook_url
    )
    return {
        "job_id": job_id,
        "name": name,
        "url": url,
        "interval_minutes": interval_minutes,
        "status": "scheduled"
    }


@register_tool(
    name="list_scrape_jobs",
    description="List all scheduled recurring scrape and monitor jobs.",
    parameters={
        "type": "object",
        "properties": {}
    }
)
def tool_list_scrape_jobs() -> Dict[str, Any]:
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


def load_plugins(plugins_dir: Optional[str] = None):
    """
    Dynamically load custom Python plugins from a directory.
    Any Python file with functions decorated by @register_tool will be automatically added.
    """
    if not plugins_dir:
        # Determine project root plugins directory
        tools_dir = os.path.dirname(os.path.abspath(__file__))
        copilot_dir = os.path.dirname(tools_dir)
        src_dir = os.path.dirname(copilot_dir)
        proj_root = os.path.dirname(src_dir)
        plugins_dir = os.path.join(proj_root, "plugins")

    if not os.path.exists(plugins_dir):
        os.makedirs(plugins_dir, exist_ok=True)
        return

    for filename in os.listdir(plugins_dir):
        if filename.endswith(".py") and not filename.startswith("__"):
            module_name = f"plugins.{filename[:-3]}"
            file_path = os.path.join(plugins_dir, filename)
            try:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = mod
                    spec.loader.exec_module(mod)
                    logging.info(f"Loaded custom plugin: {filename}")
            except Exception as e:
                logging.error(f"Failed to load plugin {filename}: {e}")
