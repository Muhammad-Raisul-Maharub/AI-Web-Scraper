# mcp_server.py - Model Context Protocol (MCP) Server for OmniScrape AI
import json
import logging
from typing import Optional
from mcp.server.mcpserver import MCPServer
from tools import (
    tool_scrape_page,
    tool_extract_data,
    tool_take_screenshot,
    tool_query_history,
    tool_send_webhook,
    tool_extract_web_animations,
    tool_schedule_scrape_job,
    tool_list_scrape_jobs,
    load_plugins
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Initialize MCP Server
server = MCPServer(
    name="omniscrape-ai",
    version="2.1.0",
    description="OmniScrape AI: Autonomous multi-modal web scraping, Pydantic structured data extraction, animation inspection, and price tracking."
)

# Load optional plugins
load_plugins()


@server.tool()
def scrape_page(url: str, mode: str = "fast") -> str:
    """
    Fetch and clean the text content of any website URL. Strips HTML noise and returns clean readable text.

    Parameters:
        url: Target webpage URL (e.g. 'https://news.ycombinator.com').
        mode: Scraping engine: 'fast' (HTTP requests), 'local' (Headless Chrome), or 'bright_data' (Proxy).
    """
    try:
        result = tool_scrape_page(url=url, mode=mode)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "url": url})


@server.tool()
def extract_structured_data(
    url: str,
    prompt: str,
    template: Optional[str] = None,
    provider: str = "gemini"
) -> str:
    """
    Scrape a webpage and extract structured information using AI and Pydantic schemas.

    Parameters:
        url: The webpage URL to scrape.
        prompt: Instructions for what information to extract (e.g. 'Extract all products and prices').
        template: Optional domain schema: 'ecommerce', 'jobs', 'realestate', 'articles', or 'quotes'.
        provider: AI provider to use: 'gemini', 'ollama', or 'openai'.
    """
    try:
        result = tool_extract_data(url=url, prompt=prompt, template=template, provider=provider)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "url": url})


@server.tool()
def take_screenshot(url: str) -> str:
    """
    Capture a high-resolution screenshot of a webpage using Headless Chrome.

    Parameters:
        url: Target webpage URL to capture.
    """
    try:
        result = tool_take_screenshot(url=url)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "url": url})


@server.tool()
def query_scrape_history(limit: int = 5) -> str:
    """
    Query the local SQLite database for recent scrape logs and extractions.

    Parameters:
        limit: Number of recent records to retrieve (default: 5).
    """
    try:
        result = tool_query_history(limit=limit)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@server.tool()
def send_webhook_alert(webhook_url: str, title: str, content: str) -> str:
    """
    Dispatch an alert containing extracted data or price shift notifications to Discord or Slack.

    Parameters:
        webhook_url: Target webhook URL.
        title: Notification header/title.
        content: Message body or JSON string.
    """
    try:
        result = tool_send_webhook(webhook_url=webhook_url, title=title, content=content)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@server.tool()
def extract_web_animations(url: str, mode: str = "fast") -> str:
    """
    Extract animation and motion assets (Lottie JSON, Rive .riv, animated SVGs, GIF/WebM loops, GSAP/Three.js libraries, and CSS @keyframes) from a webpage.

    Parameters:
        url: Target webpage URL to inspect.
        mode: Scraping engine: 'fast', 'local', or 'bright_data' (default: 'fast').
    """
    try:
        result = tool_extract_web_animations(url=url, mode=mode)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "url": url})


@server.tool()
def schedule_scrape_job(
    name: str,
    url: str,
    interval_minutes: int = 60,
    scrape_type: str = "text",
    template: Optional[str] = None,
    prompt: Optional[str] = None,
    webhook_url: Optional[str] = None,
    alert_on_change_only: bool = True
) -> str:
    """
    Schedule an automated recurring background scrape job that monitors a website and sends alerts on changes.

    Parameters:
        name: Descriptive job name (e.g. 'Daily GPU Price Watcher').
        url: Webpage URL to monitor.
        interval_minutes: Execution frequency in minutes (e.g. 15, 60, 360, 1440).
        scrape_type: 'text' (default) or 'animations'.
        template: Optional schema template ('ecommerce', 'jobs', 'realestate', 'articles', 'quotes').
        prompt: Optional extraction prompt.
        webhook_url: Optional Discord or Slack webhook URL for alerts.
        alert_on_change_only: Only send notifications when diffs or price shifts are detected.
    """
    try:
        result = tool_schedule_scrape_job(
            name=name,
            url=url,
            interval_minutes=interval_minutes,
            scrape_type=scrape_type,
            template=template,
            prompt=prompt,
            webhook_url=webhook_url,
            alert_on_change_only=alert_on_change_only
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@server.tool()
def list_scrape_jobs() -> str:
    """
    List all active and paused recurring scrape jobs with their status and next run times.
    """
    try:
        result = tool_list_scrape_jobs()
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    # Runs the MCP server over standard input/output (stdio)
    server.run()
