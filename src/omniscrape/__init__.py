# src/omniscrape/__init__.py - OmniScrape AI Package
"""
OmniScrape AI - Advanced Hybrid Web Scraping, Animation Extraction, and Background Monitoring Platform.
"""

from .engine import (
    scrape_website,
    extract_body_content,
    clean_body_content,
    split_dom_content,
    keyword_based_extraction,
    dive_deep,
    capture_page_screenshot,
    scrape_with_infinite_scroll,
    scrape_with_pagination,
    extract_animation_assets,
    scrape_animations,
    bundle_animations_zip,
    extract_with_ai,
    extract_with_vision
)
from .storage import (
    get_db,
    init_db,
    save_scrape,
    save_extraction,
    get_recent_scrapes,
    get_recent_extractions,
    detect_price_changes,
    RunOutputManager,
    default_output_manager
)
from .copilot import (
    run_copilot_turn,
    register_tool,
    get_all_tools,
    execute_tool
)
from .automation import (
    create_job,
    list_jobs,
    get_job,
    get_scheduler,
    send_webhook
)

__version__ = "1.0.0"
__all__ = [
    "scrape_website",
    "extract_body_content",
    "clean_body_content",
    "split_dom_content",
    "dive_deep",
    "capture_page_screenshot",
    "scrape_with_infinite_scroll",
    "scrape_with_pagination",
    "extract_animation_assets",
    "scrape_animations",
    "bundle_animations_zip",
    "extract_with_ai",
    "extract_with_vision",
    "get_db",
    "init_db",
    "save_scrape",
    "save_extraction",
    "get_recent_scrapes",
    "get_recent_extractions",
    "detect_price_changes",
    "RunOutputManager",
    "default_output_manager",
    "run_copilot_turn",
    "register_tool",
    "get_all_tools",
    "execute_tool",
    "create_job",
    "list_jobs",
    "get_job",
    "get_scheduler",
    "send_webhook"
]
