# tests/test_scraper.py - Automated Unit & Integration Tests (unittest compatible)
import json
import zipfile
import io
import unittest
import os
import shutil
import tempfile
from fastapi.testclient import TestClient

from scrape import (
    extract_body_content,
    clean_body_content,
    split_dom_content,
    extract_animation_assets,
    scrape_animations,
    bundle_animations_zip
)
from tools import get_all_tools, execute_tool
from outputs import RunOutputManager, default_output_manager
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

    def test_split_dom_content(self):
        # Test normal chunking
        short_text = "Paragraph 1\nParagraph 2\nParagraph 3"
        chunks = split_dom_content(short_text, max_length=100)
        self.assertEqual(len(chunks), 1)

        # Test chunking with long content
        long_para = "Word " * 1500  # ~7500 chars, exceeds 2000
        chunks = split_dom_content(long_para, max_length=2000, overlap=100)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertLessEqual(len(c), 2000)

    def test_scrape_animations_alias(self):
        assets = scrape_animations(SAMPLE_ANIMATION_HTML, base_url="https://example.com")
        self.assertGreaterEqual(assets["total_assets_count"], 7)

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

    def test_scheduler_crud_and_execution(self):
        import scheduler
        # Create
        job_id = scheduler.create_job(
            name="Unit Test Job",
            url="https://quotes.toscrape.com",
            mode="fast",
            interval_minutes=30
        )
        self.assertIsInstance(job_id, int)

        # Get
        job = scheduler.get_job(job_id)
        self.assertIsNotNone(job)
        self.assertEqual(job["name"], "Unit Test Job")

        # Run Now
        run_res = scheduler.trigger_job_now(job_id)
        self.assertEqual(run_res["status"], "success")

        # Check logs
        logs = scheduler.get_job_logs(job_id)
        self.assertGreaterEqual(len(logs), 1)

        # Toggle
        toggled = scheduler.toggle_job(job_id)
        self.assertTrue(toggled)
        updated_job = scheduler.get_job(job_id)
        self.assertEqual(updated_job["is_active"], 0)

        # Delete
        deleted = scheduler.delete_job(job_id)
        self.assertTrue(deleted)
        self.assertIsNone(scheduler.get_job(job_id))

    def test_scheduler_tools_registered(self):
        tools = get_all_tools()
        self.assertIn("schedule_scrape_job", tools)
        self.assertIn("list_scrape_jobs", tools)
        self.assertIn("trigger_scrape_job", tools)

    def test_api_jobs_endpoints(self):
        client = TestClient(app)
        # 1. Create job via API
        create_resp = client.post("/api/jobs", json={
            "name": "API Test Job",
            "url": "https://quotes.toscrape.com",
            "mode": "fast",
            "scrape_type": "text",
            "interval_minutes": 45
        })
        self.assertEqual(create_resp.status_code, 200)
        create_data = create_resp.json()
        self.assertTrue(create_data["success"])
        job_id = create_data["job"]["id"]

        # 2. List jobs via API
        list_resp = client.get("/api/jobs")
        self.assertEqual(list_resp.status_code, 200)
        jobs = list_resp.json()["jobs"]
        self.assertTrue(any(j["id"] == job_id for j in jobs))

        # 3. Toggle job
        patch_resp = client.patch(f"/api/jobs/{job_id}/toggle")
        self.assertEqual(patch_resp.status_code, 200)

        # 4. Delete job
        del_resp = client.delete(f"/api/jobs/{job_id}")
        self.assertEqual(del_resp.status_code, 200)

    def test_run_output_manager_lifecycle(self):
        temp_dir = tempfile.mkdtemp(prefix="test_runs_")
        try:
            mgr = RunOutputManager(base_dir=temp_dir)

            # 1. Create run
            run_info = mgr.create_run("https://example.com/test", task_type="scrape_and_extract")
            run_dir = run_info["run_dir"]
            run_id = run_info["run_id"]
            self.assertTrue(os.path.exists(run_dir))

            # 2. Save artifacts
            mgr.save_text(run_dir, "cleaned_dom.txt", "Sample clean DOM text")
            mgr.save_json(run_dir, "extracted_data.json", [{"title": "Item 1", "price": 10.99}])
            mgr.save_csv(run_dir, "extracted_data.csv", [{"title": "Item 1", "price": 10.99}])
            mgr.save_binary(run_dir, "test.bin", b"\x00\x01\x02\x03")

            # 3. Finalize run
            mgr.finalize_run(run_dir, status="success", duration_seconds=1.23, extra_meta={"source": "unittest"})

            # 4. Read metadata
            run_record = mgr.get_run(run_id)
            self.assertIsNotNone(run_record)
            self.assertEqual(run_record["metadata"]["status"], "success")
            self.assertEqual(run_record["metadata"]["url"], "https://example.com/test")
            self.assertIn("cleaned_dom.txt", run_record["metadata"]["files"])
            self.assertIn("extracted_data.json", run_record["metadata"]["files"])

            # 5. List runs
            runs = mgr.list_runs()
            self.assertGreaterEqual(len(runs), 1)
            self.assertEqual(runs[0]["id"], run_id)

            # 6. Export zip
            zip_buf = mgr.export_run_zip(run_id)
            self.assertIsNotNone(zip_buf)
            with zipfile.ZipFile(zip_buf, "r") as zf:
                names = zf.namelist()
                self.assertIn("metadata.json", names)
                self.assertIn("cleaned_dom.txt", names)
                self.assertIn("extracted_data.json", names)

            # 7. Delete run
            deleted = mgr.delete_run(run_id)
            self.assertTrue(deleted)
            self.assertIsNone(mgr.get_run(run_id))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_api_runs_endpoints(self):
        client = TestClient(app)
        # Create a test run using default_output_manager
        run_info = default_output_manager.create_run("https://quotes.toscrape.com/api-test", task_type="test")
        run_dir = run_info["run_dir"]
        run_id = run_info["run_id"]
        default_output_manager.save_text(run_dir, "test.txt", "Hello API test")
        default_output_manager.finalize_run(run_dir, status="success", duration_seconds=0.5)

        # 1. List runs
        resp = client.get("/api/runs")
        self.assertEqual(resp.status_code, 200)
        runs = resp.json()["runs"]
        self.assertTrue(any(r["id"] == run_id for r in runs))

        # 2. Get run details
        detail_resp = client.get(f"/api/runs/{run_id}")
        self.assertEqual(detail_resp.status_code, 200)
        detail_data = detail_resp.json()
        self.assertEqual(detail_data["id"], run_id)
        self.assertEqual(detail_data["metadata"]["url"], "https://quotes.toscrape.com/api-test")

        # 3. Download zip
        download_resp = client.get(f"/api/runs/{run_id}/download")
        self.assertEqual(download_resp.status_code, 200)
        self.assertEqual(download_resp.headers["content-type"], "application/zip")

        # 4. Delete run
        del_resp = client.delete(f"/api/runs/{run_id}")
        self.assertEqual(del_resp.status_code, 200)

    def test_run_tools_registered_and_executable(self):
        tools = get_all_tools()
        self.assertIn("list_runs", tools)
        self.assertIn("get_run_output", tools)

        # Execute list_runs tool
        res = execute_tool("list_runs", {"limit": 5})
        self.assertIsInstance(res, dict)
        self.assertIn("runs", res)
        self.assertIsInstance(res["runs"], list)


if __name__ == "__main__":
    unittest.main()

