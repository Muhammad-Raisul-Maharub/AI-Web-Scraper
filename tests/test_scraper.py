# tests/test_scraper.py - Automated Unit & Integration Tests (unittest compatible)
import json
import zipfile
import io
import unittest
from fastapi.testclient import TestClient

from scrape import (
    extract_body_content,
    clean_body_content,
    extract_animation_assets,
    bundle_animations_zip
)
from tools import get_all_tools, execute_tool
from api import app

SAMPLE_ANIMATION_HTML = """
<!DOCTYPE html>
<html>
<head>
    <style>
        @keyframes fadeInOut {
            0% { opacity: 0; transform: scale(0.9); }
            50% { opacity: 1; transform: scale(1.05); }
            100% { opacity: 0; transform: scale(0.9); }
        }
        @keyframes slideIn {
            from { transform: translateX(-100%); }
            to { transform: translateX(0); }
        }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/gsap.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js"></script>
    <script src="https://assets.example.com/hero_lottie.json"></script>
</head>
<body>
    <div class="content">
        <h1>Animation Showcase</h1>
        <p>Interactive motion testing page.</p>
        
        <!-- Lottie Player -->
        <lottie-player src="https://assets.example.com/logo.json" loop autoplay></lottie-player>
        
        <!-- Rive Canvas -->
        <canvas data-rive-src="/animations/hero.riv"></canvas>
        
        <!-- Animated SVG (SMIL) -->
        <svg width="120" height="120" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="30" fill="#4f46e5">
                <animate attributeName="r" values="30;45;30" dur="2s" repeatCount="indefinite" />
            </circle>
        </svg>

        <!-- Motion Media -->
        <img src="/media/spinner.gif" alt="loading spinner" />
        <video src="/media/background_loop.mp4" autoplay loop muted></video>
    </div>
</body>
</html>
"""


class TestAnimationAndScraper(unittest.TestCase):

    def test_clean_body_content(self):
        body = extract_body_content(SAMPLE_ANIMATION_HTML)
        cleaned = clean_body_content(body)
        self.assertIn("Animation Showcase", cleaned)
        self.assertIn("Interactive motion testing page", cleaned)
        self.assertNotIn("script", cleaned.lower())
        self.assertNotIn("style", cleaned.lower())

    def test_extract_animation_assets(self):
        base_url = "https://example.com"
        assets = extract_animation_assets(SAMPLE_ANIMATION_HTML, base_url=base_url)

        self.assertGreaterEqual(assets["total_assets_count"], 7)
        
        # Lottie
        self.assertGreaterEqual(len(assets["lottie_files"]), 2)
        lottie_urls = [lf["url"] for lf in assets["lottie_files"]]
        self.assertIn("https://assets.example.com/logo.json", lottie_urls)
        self.assertIn("https://assets.example.com/hero_lottie.json", lottie_urls)

        # Rive
        self.assertEqual(len(assets["rive_files"]), 1)
        self.assertEqual(assets["rive_files"][0]["url"], "https://example.com/animations/hero.riv")

        # SVGs
        self.assertGreaterEqual(len(assets["svg_animations"]), 1)
        self.assertEqual(assets["svg_animations"][0]["type"], "inline-animated-svg")
        self.assertTrue(assets["svg_animations"][0]["has_smil_tags"])

        # Media
        media_urls = [m["url"] for m in assets["motion_media"]]
        self.assertIn("https://example.com/media/spinner.gif", media_urls)
        self.assertIn("https://example.com/media/background_loop.mp4", media_urls)

        # JS Libraries
        lib_names = [lib["library"] for lib in assets["animation_libraries"]]
        self.assertIn("gsap", lib_names)
        self.assertIn("three", lib_names)

        # CSS Keyframes
        kf_names = [kf["name"] for kf in assets["css_keyframes"]]
        self.assertIn("fadeInOut", kf_names)
        self.assertIn("slideIn", kf_names)

    def test_bundle_animations_zip(self):
        assets = extract_animation_assets(SAMPLE_ANIMATION_HTML, base_url="https://example.com")
        zip_bytes = bundle_animations_zip(assets, base_url="https://example.com")
        self.assertIsInstance(zip_bytes, bytes)
        self.assertGreater(len(zip_bytes), 0)

        # Verify ZIP contents
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            namelist = zf.namelist()
            self.assertIn("manifest.json", namelist)
            self.assertIn("css/keyframes.css", namelist)

            manifest_raw = zf.read("manifest.json").decode("utf-8")
            manifest_json = json.loads(manifest_raw)
            self.assertEqual(manifest_json["total_assets_count"], assets["total_assets_count"])

    def test_tool_extract_web_animations(self):
        tools = get_all_tools()
        self.assertIn("extract_web_animations", tools)
        t_def = tools["extract_web_animations"]
        self.assertIn("url", t_def["parameters"]["properties"])

    def test_api_scrape_animations_endpoint(self):
        client = TestClient(app)
        resp = client.post("/api/scrape/animations", json={"url": "https://quotes.toscrape.com", "mode": "fast"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total_assets_count", data)
        self.assertIn("lottie_files", data)
        self.assertIn("css_keyframes", data)


if __name__ == "__main__":
    unittest.main()
