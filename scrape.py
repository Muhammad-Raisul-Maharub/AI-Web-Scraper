# scrape.py - Advanced Hybrid Web Scraping Engine
import os
import re
import time
import logging
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Optional Selenium imports with graceful fallbacks
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _scrape_with_requests(url: str, timeout: int = 20) -> str:
    """Fetch website HTML using fast HTTP requests."""
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.text


def _scrape_with_local_chrome(url: str, timeout: int = 30) -> str:
    """Fetch website HTML using local Headless Chrome via Selenium."""
    if not SELENIUM_AVAILABLE:
        raise RuntimeError("Selenium or webdriver-manager is not installed.")

    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(f"user-agent={DEFAULT_HEADERS['User-Agent']}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        logging.warning(f"Could not use ChromeDriverManager: {e}. Falling back to default PATH.")
        driver = webdriver.Chrome(options=options)

    try:
        driver.set_page_load_timeout(timeout)
        driver.get(url)
        time.sleep(2)  # Allow dynamic JS to settle
        return driver.page_source
    finally:
        driver.quit()


def _scrape_with_bright_data(url: str, timeout: int = 45) -> str:
    """Fetch website HTML using Bright Data remote Scraping Browser."""
    if not SELENIUM_AVAILABLE:
        raise RuntimeError("Selenium is required for remote Bright Data scraping.")

    sbr_url = os.getenv("SBR_WEBDRIVER")
    if not sbr_url:
        raise ValueError("SBR_WEBDRIVER is not defined in your environment or .env file.")

    options = ChromeOptions()
    driver = webdriver.Remote(command_executor=sbr_url, options=options)

    try:
        driver.set_page_load_timeout(timeout)
        driver.get(url)

        # Basic Cloudflare / Captcha check
        title = driver.title.lower() if driver.title else ""
        if "just a moment" in title or "attention required" in title:
            logging.warning("Cloudflare challenge detected, waiting for automated solver...")
            time.sleep(5)

        return driver.page_source
    finally:
        driver.quit()


def scrape_website(website: str, mode: str = "fast", timeout: int = 30) -> str:
    """
    Scrape website content using the specified engine mode.

    Parameters:
        website (str): The target URL.
        mode (str): 'fast' (HTTP requests), 'local' (Headless Chrome), or 'bright_data' (Remote Proxy).
        timeout (int): Page load timeout in seconds.

    Returns:
        str: Raw HTML content.
    """
    if not website.startswith("http://") and not website.startswith("https://"):
        website = "https://" + website

    logging.info(f"Scraping '{website}' using mode='{mode}'...")

    if mode == "fast":
        try:
            return _scrape_with_requests(website, timeout=timeout)
        except Exception as e:
            logging.warning(f"Fast HTTP request failed: {e}. Falling back to local headless browser...")
            if SELENIUM_AVAILABLE:
                return _scrape_with_local_chrome(website, timeout=timeout)
            raise

    elif mode == "local":
        return _scrape_with_local_chrome(website, timeout=timeout)

    elif mode == "bright_data":
        return _scrape_with_bright_data(website, timeout=timeout)

    else:
        raise ValueError(f"Unknown scraping mode: {mode}")


def extract_body_content(html_content: str) -> str:
    """Extract <body> from raw HTML."""
    soup = BeautifulSoup(html_content, "html.parser")
    body = soup.body
    return str(body) if body else html_content


def clean_body_content(body_content: str) -> str:
    """
    Clean HTML by stripping non-content elements (scripts, styles, ads, SVGs)
    and base64 image data to optimize token usage.
    """
    soup = BeautifulSoup(body_content, "html.parser")

    # Remove irrelevant tags
    for tag in soup(["script", "style", "iframe", "noscript", "svg", "canvas", "nav", "footer"]):
        tag.decompose()

    # Strip base64 inline images
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if src.startswith("data:"):
            img.decompose()

    text = soup.get_text(separator="\n")
    # Clean redundant whitespace while preserving paragraph structure
    cleaned_lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    non_empty = [line for line in cleaned_lines if line]
    return "\n".join(non_empty)


def split_dom_content(dom_content: str, max_length: int = 5000, overlap: int = 200) -> list[str]:
    """
    Semantically split text into chunks on newline/paragraph boundaries
    instead of slicing arbitrarily mid-word.
    """
    if len(dom_content) <= max_length:
        return [dom_content]

    paragraphs = dom_content.split("\n")
    chunks = []
    current_chunk = []
    current_length = 0

    for para in paragraphs:
        para_len = len(para) + 1
        if current_length + para_len > max_length:
            if current_chunk:
                chunk_text = "\n".join(current_chunk)
                chunks.append(chunk_text)
                # Keep last few lines as overlap
                current_chunk = [current_chunk[-1]] if len(current_chunk) > 1 else []
                current_length = len(current_chunk[0]) if current_chunk else 0

        current_chunk.append(para)
        current_length += para_len

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


def dive_deep(
    start_url: str,
    max_pages: int = 5,
    mode: str = "fast",
    progress_callback=None
) -> list[dict]:
    """
    Polite, domain-restricted crawler. Only follows links on the same root domain
    and strictly enforces max_pages to prevent runaway crawler loops.
    """
    if not start_url.startswith("http://") and not start_url.startswith("https://"):
        start_url = "https://" + start_url

    parsed_start = urlparse(start_url)
    root_domain = parsed_start.netloc

    queue = [start_url]
    visited = set()
    results = []

    while queue and len(results) < max_pages:
        current_url = queue.pop(0)
        if current_url in visited:
            continue

        visited.add(current_url)
        if progress_callback:
            progress_callback(len(results) + 1, max_pages, current_url)

        try:
            html = scrape_website(current_url, mode=mode)
            body = extract_body_content(html)
            cleaned = clean_body_content(body)

            results.append({
                "url": current_url,
                "html": html,
                "cleaned": cleaned
            })

            # Extract same-domain links for queue
            soup = BeautifulSoup(html, "html.parser")
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                abs_url = urljoin(current_url, href)
                parsed_href = urlparse(abs_url)

                # Keep only same domain and http/https schemes
                if (
                    parsed_href.netloc == root_domain
                    and parsed_href.scheme in ("http", "https")
                    and abs_url not in visited
                    and abs_url not in queue
                    and not any(abs_url.endswith(ext) for ext in [".pdf", ".jpg", ".png", ".zip", ".exe"])
                ):
                    queue.append(abs_url)

        except Exception as e:
            logging.error(f"Error crawling {current_url}: {e}")

    return results


def keyword_based_extraction(content: str, keywords: list[str]) -> str:
    """Extract lines and paragraphs containing any user-specified keywords."""
    lines = content.split("\n")
    matches = []
    keywords_lower = [k.lower().strip() for k in keywords if k.strip()]

    for line in lines:
        if any(kw in line.lower() for kw in keywords_lower):
            matches.append(line)

    return "\n".join(matches)


def capture_page_screenshot(url: str, output_path: str = None, timeout: int = 30) -> str:
    """
    Capture a high-resolution screenshot of the target page using Headless Chrome.
    Returns the file path of the saved PNG screenshot.
    """
    if not SELENIUM_AVAILABLE:
        raise RuntimeError("Selenium is required for screenshot capture.")

    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1600,1200")
    options.add_argument(f"user-agent={DEFAULT_HEADERS['User-Agent']}")
    options.add_argument("--disable-blink-features=AutomationControlled")

    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception:
        driver = webdriver.Chrome(options=options)

    try:
        driver.set_page_load_timeout(timeout)
        driver.get(url)
        time.sleep(2)

        if not output_path:
            os.makedirs("screenshots", exist_ok=True)
            import hashlib
            filename = f"screenshot_{hashlib.md5(url.encode()).hexdigest()[:8]}.png"
            output_path = os.path.join("screenshots", filename)
        else:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        driver.save_screenshot(output_path)
        return output_path
    finally:
        driver.quit()


def scrape_with_infinite_scroll(url: str, max_scrolls: int = 5, pause_time: float = 1.5, timeout: int = 30) -> str:
    """
    Scrape dynamic pages that load more content via infinite scrolling.
    """
    if not SELENIUM_AVAILABLE:
        raise RuntimeError("Selenium is required for infinite scroll scraping.")

    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(f"user-agent={DEFAULT_HEADERS['User-Agent']}")
    options.add_argument("--disable-blink-features=AutomationControlled")

    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception:
        driver = webdriver.Chrome(options=options)

    try:
        driver.set_page_load_timeout(timeout)
        driver.get(url)
        time.sleep(2)

        last_height = driver.execute_script("return document.body.scrollHeight")

        for scroll_i in range(max_scrolls):
            logging.info(f"Scrolling page down ({scroll_i + 1}/{max_scrolls})...")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(pause_time)

            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                logging.info("Reached bottom of dynamic content feed.")
                break
            last_height = new_height

        return driver.page_source
    finally:
        driver.quit()


def scrape_with_pagination(
    start_url: str,
    next_button_css: str = "li.next a, a.next, a[rel='next']",
    max_pages: int = 3,
    timeout: int = 30
) -> list[dict]:
    """
    Automate multi-page scraping by following pagination buttons.
    """
    if not SELENIUM_AVAILABLE:
        raise RuntimeError("Selenium is required for pagination automation.")

    from selenium.webdriver.common.by import By

    if not start_url.startswith("http://") and not start_url.startswith("https://"):
        start_url = "https://" + start_url

    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(f"user-agent={DEFAULT_HEADERS['User-Agent']}")
    options.add_argument("--disable-blink-features=AutomationControlled")

    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception:
        driver = webdriver.Chrome(options=options)

    pages = []
    current_page = 1

    try:
        driver.set_page_load_timeout(timeout)
        driver.get(start_url)

        while current_page <= max_pages:
            time.sleep(2)
            page_url = driver.current_url
            html = driver.page_source
            body = extract_body_content(html)
            cleaned = clean_body_content(body)

            pages.append({
                "page": current_page,
                "url": page_url,
                "html": html,
                "cleaned": cleaned
            })

            if current_page >= max_pages:
                break

            # Locate Next button
            try:
                next_btns = driver.find_elements(By.CSS_SELECTOR, next_button_css)
                if not next_btns or not next_btns[0].is_displayed():
                    logging.info("No visible 'Next' button found; ending pagination.")
                    break
                next_btn = next_btns[0]
                driver.execute_script("arguments[0].click();", next_btn)
                current_page += 1
            except Exception as e:
                logging.info(f"Could not click next button: {e}")
                break

        return pages
    finally:
        driver.quit()