# src/omniscrape/engine/scrape.py - Advanced Hybrid Web Scraping Engine
import os
import re
import time
import json
import logging
from typing import Optional, List, Dict, Any, Union
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
        src = str(img.get("src", "") or "")
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
        # If an individual paragraph exceeds max_length, split it into smaller segments
        if len(para) > max_length:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_length = 0
            for i in range(0, len(para), max_length - overlap):
                chunks.append(para[i:i + max_length])
            continue

        para_len = len(para) + 1
        if current_length + para_len > max_length:
            if current_chunk:
                chunk_text = "\n".join(current_chunk)
                chunks.append(chunk_text)
                # Keep last line as overlap
                current_chunk = [current_chunk[-1]] if len(current_chunk) > 1 else []
                current_length = len(current_chunk[0]) if current_chunk else 0

        current_chunk.append(para)
        current_length += para_len

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


def keyword_based_extraction(content: str, keywords: list) -> str:
    """
    Extracts lines of content containing any of the specified keywords.

    Parameters:
        content (str): The scraped content to search through.
        keywords (list): A list of keyword strings to search for.

    Returns:
        str: Filtered lines containing matching keywords.
    """
    if not content:
        return ""
    lines = content.split("\n")
    lower_keywords = [k.lower().strip() for k in keywords if k.strip()]
    extracted_lines = [line for line in lines if any(k in line.lower() for k in lower_keywords)]
    return "\n".join(extracted_lines)


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

            # Extract internal links
            soup = BeautifulSoup(html, "html.parser")
            for a_tag in soup.find_all("a", href=True):
                href = str(a_tag["href"])
                abs_url = urljoin(current_url, href)
                parsed_abs = urlparse(abs_url)

                if parsed_abs.netloc == root_domain and abs_url not in visited and abs_url not in queue:
                    queue.append(abs_url)

        except Exception as e:
            logging.error(f"Failed to crawl '{current_url}': {e}")

    return results


def capture_page_screenshot(url: str, output_path: Optional[str] = None, timeout: int = 30) -> str:
    """
    Capture a high-resolution full-page screenshot using Headless Chrome.
    """
    if not SELENIUM_AVAILABLE:
        raise RuntimeError("Selenium is required for screenshot capture.")

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

        if not output_path:
            # Save by default inside outputs/screenshots
            project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            ss_dir = os.path.join(project_dir, "outputs", "screenshots")
            os.makedirs(ss_dir, exist_ok=True)
            import hashlib
            filename = f"screenshot_{hashlib.md5(url.encode()).hexdigest()[:8]}.png"
            output_path = os.path.join(ss_dir, filename)
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


def extract_animation_assets(html_content: str, base_url: str) -> dict:
    """
    Extract animation and motion assets from webpage HTML.
    Detects Lottie JSON, Rive (.riv), animated SVGs, GIFs/WebM, animation JS libraries, and CSS keyframes.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    base_url = base_url.rstrip("/")

    results = {
        "url": base_url,
        "lottie_files": [],
        "rive_files": [],
        "svg_animations": [],
        "motion_media": [],
        "animation_libraries": [],
        "css_keyframes": [],
        "total_assets_count": 0
    }

    # 1. Lottie Animations
    for tag in soup.find_all(["lottie-player", "dotlottie-player"]):
        src = str(tag.get("src") or tag.get("data-src") or "")
        if src:
            abs_src = urljoin(base_url, src)
            results["lottie_files"].append({
                "type": "lottie-player",
                "url": abs_src,
                "loop": str(tag.get("loop", "false")),
                "autoplay": str(tag.get("autoplay", "false"))
            })

    # Search script tags and attributes for .json lottie or bodymovin links
    for script in soup.find_all("script"):
        src = str(script.get("src", "") or "")
        if src and (".json" in src.lower() or "lottie" in src.lower()):
            abs_src = urljoin(base_url, src)
            if abs_src not in [item["url"] for item in results["lottie_files"]]:
                results["lottie_files"].append({"type": "script-lottie", "url": abs_src})

        # Inline JSON Lottie detection
        script_text = script.string or ""
        if '"v":' in script_text and '"fr":' in script_text and '"ip":' in script_text and '"op":' in script_text:
            match = re.search(r"(\{[^{}]*\"v\"\s*:\s*\"[^\"]+\"[^{}]*\"layers\"\s*:\s*\[.*?\]\s*\})", script_text, re.DOTALL)
            if match:
                results["lottie_files"].append({
                    "type": "inline-lottie-json",
                    "url": "inline_data",
                    "preview": match.group(1)[:300] + "..."
                })

    # 2. Rive Animations (.riv)
    for canvas in soup.find_all(["canvas", "div"]):
        rive_src = str(canvas.get("data-rive-src") or canvas.get("data-src") or canvas.get("src") or "")
        if rive_src and rive_src.endswith(".riv"):
            results["rive_files"].append({"url": urljoin(base_url, rive_src), "type": "rive-canvas"})

    for a_tag in soup.find_all("a", href=True):
        href = str(a_tag.get("href", "") or "")
        if href.endswith(".riv"):
            results["rive_files"].append({"url": urljoin(base_url, href), "type": "rive-link"})

    # 3. Animated SVGs & Vector Motion
    for svg in soup.find_all("svg"):
        has_animate = bool(svg.find_all(["animate", "animateTransform", "animateMotion", "set"]))
        svg_str = str(svg)
        if has_animate or "keyframes" in svg_str or "animation" in svg_str:
            results["svg_animations"].append({
                "type": "inline-animated-svg",
                "html": svg_str[:1500],
                "has_smil_tags": has_animate
            })

    for img in soup.find_all(["img", "object", "embed"]):
        src = str(img.get("src") or img.get("data") or "")
        if src.lower().endswith(".svg"):
            abs_src = urljoin(base_url, src)
            results["svg_animations"].append({"type": "svg-file", "url": abs_src})

    # 4. Animated Media (GIF, WebP animations, MP4, WebM clips)
    for img in soup.find_all("img"):
        src = str(img.get("src") or img.get("data-src") or "")
        if src.lower().endswith((".gif", ".apng")):
            results["motion_media"].append({"type": "gif", "url": urljoin(base_url, src)})

    for video in soup.find_all(["video", "source"]):
        src = str(video.get("src") or "")
        if src.lower().endswith((".mp4", ".webm", ".ogg")):
            abs_src = urljoin(base_url, src)
            if abs_src not in [m["url"] for m in results["motion_media"]]:
                results["motion_media"].append({"type": "video-loop", "url": abs_src})

    # 5. Animation Libraries & Scripts
    known_anim_libs = [
        "gsap", "three", "anime", "lottie", "framer-motion",
        "scrollmagic", "pixi", "locomotive-scroll", "barba", "typed", "particles"
    ]
    for script in soup.find_all("script", src=True):
        src = str(script.get("src", "") or "")
        src_lower = src.lower()
        for lib in known_anim_libs:
            if lib in src_lower:
                results["animation_libraries"].append({
                    "library": lib,
                    "url": urljoin(base_url, src)
                })
                break

    # 6. CSS Keyframe Animations
    for style in soup.find_all("style"):
        css_text = style.string or ""
        keyframes = re.findall(r"@keyframes\s+([a-zA-Z0-9_-]+)\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}", css_text)
        for name, rules in keyframes:
            results["css_keyframes"].append({
                "name": name,
                "css": f"@keyframes {name} {{{rules[:400]}}}"
            })

    # Calculate total count
    results["total_assets_count"] = (
        len(results["lottie_files"]) +
        len(results["rive_files"]) +
        len(results["svg_animations"]) +
        len(results["motion_media"]) +
        len(results["animation_libraries"]) +
        len(results["css_keyframes"])
    )

    return results


# Backward-compatible alias
scrape_animations = extract_animation_assets


def scrape_animations_from_driver(driver, base_url: str = "") -> dict:
    """
    Extract animations dynamically from an active Selenium WebDriver session.
    Combines static HTML parsing with runtime CSSOM extraction to capture
    cross-origin keyframes, dynamically injected animations, and media loops.
    """
    if not base_url:
        try:
            base_url = driver.current_url
        except Exception:
            base_url = ""

    # 1. Base extraction from DOM source
    try:
        html = driver.page_source
    except Exception:
        html = ""

    results = extract_animation_assets(html, base_url=base_url)

    # 2. Dynamic runtime CSSOM keyframe extraction
    cssom_script = """
    const keyframes = [];
    for (let i = 0; i < document.styleSheets.length; i++) {
        try {
            const sheet = document.styleSheets[i];
            const rules = sheet.cssRules || sheet.rules;
            if (!rules) continue;
            for (let j = 0; j < rules.length; j++) {
                const rule = rules[j];
                if (rule.type === CSSRule.KEYFRAMES_RULE || rule.type === 7) {
                    keyframes.push({
                        name: rule.name,
                        css: rule.cssText.slice(0, 400)
                    });
                }
            }
        } catch (e) {
            // Bypass cross-origin stylesheet errors
            continue;
        }
    }
    return keyframes;
    """
    try:
        dynamic_keyframes = driver.execute_script(cssom_script) or []
        existing_names = {kf["name"] for kf in results["css_keyframes"]}
        for kf in dynamic_keyframes:
            if kf.get("name") and kf["name"] not in existing_names:
                results["css_keyframes"].append(kf)
                existing_names.add(kf["name"])
    except Exception as e:
        logging.debug(f"CSSOM keyframe extraction exception: {e}")

    # 3. Dynamic runtime video loop extraction
    video_script = """
    const videos = [];
    document.querySelectorAll('video').forEach(v => {
        const src = v.currentSrc || v.src;
        if (src) videos.push(src);
        v.querySelectorAll('source').forEach(s => {
            if (s.src) videos.push(s.src);
        });
    });
    return Array.from(new Set(videos));
    """
    try:
        dynamic_videos = driver.execute_script(video_script) or []
        existing_media_urls = {m["url"] for m in results["motion_media"]}
        for vurl in dynamic_videos:
            if vurl not in existing_media_urls:
                results["motion_media"].append({"type": "video-loop", "url": vurl})
                existing_media_urls.add(vurl)
    except Exception as e:
        logging.debug(f"Dynamic video extraction exception: {e}")

    # Recalculate total count
    results["total_assets_count"] = (
        len(results["lottie_files"]) +
        len(results["rive_files"]) +
        len(results["svg_animations"]) +
        len(results["motion_media"]) +
        len(results["animation_libraries"]) +
        len(results["css_keyframes"])
    )

    return results


def bundle_animations_zip(assets_dict: dict, base_url: Optional[str] = None) -> bytes:
    """
    Download discovered animation assets and package them into an in-memory ZIP archive.
    """
    import zipfile
    import io

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # Write Manifest JSON
        manifest_data = json.dumps(assets_dict, indent=2, ensure_ascii=False)
        zip_file.writestr("manifest.json", manifest_data)

        # Download Lottie and Media files
        url_items = []
        for lottie in assets_dict.get("lottie_files", []):
            if lottie.get("url") and lottie["url"].startswith("http"):
                url_items.append(("lottie", lottie["url"]))

        for rive in assets_dict.get("rive_files", []):
            if rive.get("url") and rive["url"].startswith("http"):
                url_items.append(("rive", rive["url"]))

        for media in assets_dict.get("motion_media", []):
            if media.get("url") and media["url"].startswith("http"):
                url_items.append(("media", media["url"]))

        for svg in assets_dict.get("svg_animations", []):
            if svg.get("url") and svg["url"].startswith("http"):
                url_items.append(("svgs", svg["url"]))

        # Download remote assets with timeout
        for folder, url in url_items:
            try:
                fname = os.path.basename(urlparse(url).path) or f"asset_{hash(url)}.bin"
                resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
                if resp.status_code == 200:
                    zip_file.writestr(f"{folder}/{fname}", resp.content)
            except Exception as e:
                logging.warning(f"Could not bundle asset {url}: {e}")

        # Save CSS Keyframes to keyframes.css
        keyframes_list = assets_dict.get("css_keyframes", [])
        if keyframes_list:
            css_content = "\n\n".join([kf["css"] for kf in keyframes_list])
            zip_file.writestr("css/keyframes.css", css_content)

    zip_buffer.seek(0)
    return zip_buffer.getvalue()
