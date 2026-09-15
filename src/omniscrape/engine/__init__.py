# src/omniscrape/engine/__init__.py
from .scrape import (
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
    scrape_animations_from_driver,
    bundle_animations_zip,
    DEFAULT_HEADERS,
    SELENIUM_AVAILABLE
)
from .parse import (
    parse_with_gemini,
    parse_with_openai,
    parse_with_ollama,
    extract_with_ai,
    extract_with_vision
)

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
    "scrape_animations_from_driver",
    "bundle_animations_zip",
    "DEFAULT_HEADERS",
    "SELENIUM_AVAILABLE",
    "parse_with_gemini",
    "parse_with_openai",
    "parse_with_ollama",
    "extract_with_ai",
    "extract_with_vision"
]
