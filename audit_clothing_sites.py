# audit_clothing_sites.py
import os
import sys
import json
import time
import shutil
import logging
from urllib.parse import urlparse
import requests

from scrape import (
    scrape_website,
    extract_animation_assets,
    capture_page_screenshot,
    DEFAULT_HEADERS,
    SELENIUM_AVAILABLE
)

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

CLOTHING_SITES = [
    {
        "brand": "Nike",
        "url": "https://www.nike.com",
        "category": "Sportswear / Performance Athletic"
    },
    {
        "brand": "H&M",
        "url": "https://www2.hm.com/en_us/index.html",
        "category": "Fast Fashion / Contemporary Everyday"
    },
    {
        "brand": "Zara",
        "url": "https://www.zara.com",
        "category": "High-Street Runway / Editorial Fashion"
    },
    {
        "brand": "Uniqlo",
        "url": "https://www.uniqlo.com/us/en/",
        "category": "Modern Japanese LifeWear & Basics"
    },
    {
        "brand": "ASOS",
        "url": "https://www.asos.com",
        "category": "Youth Trend & Multi-brand E-Commerce"
    },
    {
        "brand": "Gymshark",
        "url": "https://www.gymshark.com",
        "category": "Athletic Conditioning & Activewear"
    },
    {
        "brand": "Levi's",
        "url": "https://www.levi.com/US/en_US/",
        "category": "Heritage Denim & Casual Wear"
    },
    {
        "brand": "Gap",
        "url": "https://www.gap.com",
        "category": "American Casual & Family Wardrobe"
    },
    {
        "brand": "Mango",
        "url": "https://shop.mango.com",
        "category": "Mediterranean Chic & Smart Casual"
    },
    {
        "brand": "Lululemon",
        "url": "https://shop.lululemon.com",
        "category": "Technical Athletic & Yoga Apparel"
    }
]

ARTIFACT_DIR = r"C:\Users\rmaha\.gemini\antigravity-ide\brain\249a91b7-20ba-43dc-a754-567de3a4be88"
IMAGES_OUT_DIR = os.path.join(ARTIFACT_DIR, "images", "clothing")
LOCAL_SCREENSHOTS_DIR = os.path.join("screenshots", "clothing")
RESULTS_JSON = os.path.join("screenshots", "clothing_audit_results.json")

os.makedirs(IMAGES_OUT_DIR, exist_ok=True)
os.makedirs(LOCAL_SCREENSHOTS_DIR, exist_ok=True)


def process_site(site_info):
    brand = site_info["brand"]
    url = site_info["url"]
    slug = brand.lower().replace("'", "").replace("&", "and").replace(" ", "_")
    
    print(f"\n=======================================================")
    print(f"👕 [{brand}] - {url}")
    print(f"=======================================================")
    
    result = {
        "brand": brand,
        "url": url,
        "category": site_info["category"],
        "screenshot_local": None,
        "screenshot_artifact": None,
        "status": "pending",
        "animation_data": {},
        "notes": ""
    }

    # 1. Capture Screenshot with Headless Chrome
    local_ss_path = os.path.join(LOCAL_SCREENSHOTS_DIR, f"{slug}.png")
    artifact_ss_path = os.path.join(IMAGES_OUT_DIR, f"{slug}.png")
    
    print(f"📸 Capturing screenshot for {brand}...")
    try:
        ss_path = capture_page_screenshot(url, output_path=local_ss_path, timeout=30)
        shutil.copy2(ss_path, artifact_ss_path)
        result["screenshot_local"] = ss_path
        result["screenshot_artifact"] = artifact_ss_path
        print(f"✅ Screenshot saved: {local_ss_path} -> copied to artifact dir")
    except Exception as e:
        print(f"⚠️ Screenshot capture error for {brand}: {e}")
        result["notes"] += f"Screenshot error: {e}. "

    # 2. Scrape HTML Content
    html_content = ""
    print(f"🕷️ Fetching HTML content for {brand}...")
    # First try local headless Chrome (more resilient against JS render & Cloudflare challenges)
    if SELENIUM_AVAILABLE:
        try:
            print(f"  Attempting Chrome headless render...")
            html_content = scrape_website(url, mode="local", timeout=25)
        except Exception as e:
            print(f"  Local Chrome failed: {e}. Falling back to Fast HTTP...")
    
    if not html_content:
        try:
            html_content = scrape_website(url, mode="fast", timeout=25)
        except Exception as e:
            print(f"⚠️ Scraping HTML failed for {brand}: {e}")
            result["notes"] += f"Scrape error: {e}. "

    # 3. Extract Animations & Motion Assets
    if html_content:
        print(f"🎬 Analyzing animation assets for {brand} ({len(html_content):,} chars)...")
        try:
            anim_assets = extract_animation_assets(html_content, base_url=url)
            result["animation_data"] = anim_assets
            result["status"] = "success"
            print(f"✨ Found {anim_assets['total_assets_count']} animation assets:")
            print(f"   • Lottie: {len(anim_assets['lottie_files'])}")
            print(f"   • Rive: {len(anim_assets['rive_files'])}")
            print(f"   • SVGs: {len(anim_assets['svg_animations'])}")
            print(f"   • Motion Media: {len(anim_assets['motion_media'])}")
            print(f"   • JS Libraries: {len(anim_assets['animation_libraries'])}")
            print(f"   • CSS Keyframes: {len(anim_assets['css_keyframes'])}")
        except Exception as e:
            print(f"⚠️ Animation extraction error for {brand}: {e}")
            result["notes"] += f"Animation extraction error: {e}. "
    else:
        result["status"] = "failed"

    return result


def main():
    all_results = []
    
    for site in CLOTHING_SITES:
        res = process_site(site)
        all_results.append(res)
        time.sleep(1)

    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
        
    print(f"\n🎉 Finished processing all {len(all_results)} clothing websites!")
    print(f"📄 Audit results saved to: {RESULTS_JSON}")


if __name__ == "__main__":
    main()
