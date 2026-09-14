# mcp_server.py - Model Context Protocol (MCP) Server for AI Web Scraper
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
    load_plugins
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Initialize MCP Server
server = MCPServer(
    name="ai-web-scraper",
    version="2.0.0",
    description="Live web scraping, Pydantic structured data extraction, screenshot capture, and price tracking."
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


if __name__ == "__main__":
    # Runs the MCP server over standard input/output (stdio)
    server.run()
