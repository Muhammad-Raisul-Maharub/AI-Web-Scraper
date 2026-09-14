# scheduler.py - Background Scraping Job Scheduler & Autonomous Monitor
import time
import json
import logging
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from db import get_db, save_scrape, save_extraction, detect_price_changes
from scrape import (
    scrape_website,
    extract_body_content,
    clean_body_content,
    extract_animation_assets
)
from parse import extract_with_ai
from schemas import EXTRACTION_TEMPLATES
from webhook import send_webhook

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def init_scheduler_tables():
    """Create database tables for scheduled recurring scrape jobs and run logs."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                mode TEXT DEFAULT 'fast',
                scrape_type TEXT DEFAULT 'text',
                template TEXT,
                prompt TEXT,
                interval_minutes INTEGER DEFAULT 60,
                webhook_url TEXT,
                alert_on_change_only INTEGER DEFAULT 1,
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_run_at DATETIME,
                next_run_at DATETIME,
                last_status TEXT DEFAULT 'pending'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_run_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                run_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL,
                summary TEXT,
                diff_detected INTEGER DEFAULT 0,
                details_json TEXT,
                FOREIGN KEY (job_id) REFERENCES scheduled_jobs (id) ON DELETE CASCADE
            )
        """)
        conn.commit()


# Initialize tables on import
init_scheduler_tables()


# ==============================================================================
# JOB CRUD OPERATIONS
# ==============================================================================

def create_job(
    name: str,
    url: str,
    mode: str = "fast",
    scrape_type: str = "text",
    template: Optional[str] = None,
    prompt: Optional[str] = None,
    interval_minutes: int = 60,
    webhook_url: Optional[str] = None,
    alert_on_change_only: bool = True
) -> int:
    """Register a new recurring scrape job in the database."""
    next_run = (datetime.now() + timedelta(minutes=interval_minutes)).strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO scheduled_jobs (
                name, url, mode, scrape_type, template, prompt,
                interval_minutes, webhook_url, alert_on_change_only,
                is_active, next_run_at, last_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 'pending')
        """, (
            name, url, mode, scrape_type, template, prompt,
            interval_minutes, webhook_url, 1 if alert_on_change_only else 0,
            next_run
        ))
        conn.commit()
        return cursor.lastrowid


def list_jobs() -> List[Dict[str, Any]]:
    """Retrieve all scheduled jobs from SQLite."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, url, mode, scrape_type, template, prompt,
                   interval_minutes, webhook_url, alert_on_change_only,
                   is_active, created_at, last_run_at, next_run_at, last_status
            FROM scheduled_jobs
            ORDER BY id DESC
        """)
        return [dict(row) for row in cursor.fetchall()]


def get_job(job_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a single scheduled job by ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM scheduled_jobs WHERE id = ?
        """, (job_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def delete_job(job_id: int) -> bool:
    """Delete a scheduled job and its execution logs."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM job_run_logs WHERE job_id = ?", (job_id,))
        cursor.execute("DELETE FROM scheduled_jobs WHERE id = ?", (job_id,))
        conn.commit()
        return cursor.rowcount > 0


def toggle_job(job_id: int) -> bool:
    """Toggle active/paused state for a job."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_active, interval_minutes FROM scheduled_jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        if not row:
            return False

        new_state = 0 if row["is_active"] else 1
        next_run = (datetime.now() + timedelta(minutes=row["interval_minutes"])).strftime("%Y-%m-%d %H:%M:%S") if new_state else None
        cursor.execute("""
            UPDATE scheduled_jobs
            SET is_active = ?, next_run_at = ?
            WHERE id = ?
        """, (new_state, next_run, job_id))
        conn.commit()
        return True


def get_job_logs(job_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieve execution logs for a specific scheduled job."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, job_id, run_at, status, summary, diff_detected, details_json
            FROM job_run_logs
            WHERE job_id = ?
            ORDER BY run_at DESC
            LIMIT ?
        """, (job_id, limit))
        return [dict(row) for row in cursor.fetchall()]


# ==============================================================================
# JOB PIPELINE EXECUTION
# ==============================================================================

def execute_job_pipeline(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a scheduled scrape job pipeline:
    1. Scrape URL with chosen engine
    2. Extract content (Cleaned Text / AI Extraction / Animations)
    3. Detect price/content changes
    4. Fire webhook alerts if triggered
    5. Record execution log & schedule next run
    """
    job_id = job["id"]
    url = job["url"]
    mode = job.get("mode", "fast")
    scrape_type = job.get("scrape_type", "text")
    template = job.get("template")
    prompt = job.get("prompt")
    webhook_url = job.get("webhook_url")
    alert_on_change_only = bool(job.get("alert_on_change_only", 1))

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary = ""
    diff_detected = False
    details: Dict[str, Any] = {}

    try:
        logging.info(f"🕒 Executing scheduled job #{job_id} ('{job['name']}') on {url}...")
        raw_html = scrape_website(url, mode=mode)

        if scrape_type == "animations":
            # Animation inspection
            assets = extract_animation_assets(raw_html, base_url=url)
            total_assets = assets.get("total_assets_count", 0)
            summary = f"Scraped {total_assets} animation assets (Lottie: {len(assets['lottie_files'])}, SVGs: {len(assets['svg_animations'])}, Media: {len(assets['motion_media'])})."
            details = {
                "total_assets": total_assets,
                "lottie_count": len(assets["lottie_files"]),
                "svg_count": len(assets["svg_animations"]),
                "media_count": len(assets["motion_media"]),
                "keyframes_count": len(assets["css_keyframes"])
            }

            # Simple diff check against previous run
            prev_logs = get_job_logs(job_id, limit=1)
            if prev_logs and prev_logs[0].get("details_json"):
                try:
                    prev_details = json.loads(prev_logs[0]["details_json"])
                    if prev_details.get("total_assets") != total_assets:
                        diff_detected = True
                        summary += f" [Asset count changed from {prev_details.get('total_assets')} to {total_assets}]"
                except Exception:
                    pass

        else:
            # Clean text & structured extraction
            body = extract_body_content(raw_html)
            cleaned = clean_body_content(body)
            scrape_id = save_scrape(url, mode, raw_html, cleaned)

            extracted_items = None
            price_changes = []

            # Determine if structured AI extraction is configured
            if template or prompt:
                schema_class = None
                instruction = prompt or ""
                if template and template in EXTRACTION_TEMPLATES:
                    schema_class = EXTRACTION_TEMPLATES[template]["model"]
                    instruction = instruction or EXTRACTION_TEMPLATES[template]["default_prompt"]

                extracted_items = extract_with_ai(
                    dom_content=cleaned,
                    parse_description=instruction or "Extract key data items.",
                    provider="gemini",
                    output_format="json",
                    schema_class=schema_class
                )
                save_extraction(scrape_id, url, template or "custom", instruction, extracted_items)

                if isinstance(extracted_items, list):
                    price_changes = detect_price_changes(url, extracted_items)
                    if price_changes:
                        diff_detected = True
                        summary = f"Detected {len(price_changes)} price shift(s) across {len(extracted_items)} items."
                    else:
                        summary = f"Extracted {len(extracted_items)} items (no price changes)."
                else:
                    summary = "Extraction completed."
            else:
                summary = f"Scraped {len(cleaned):,} cleaned characters."

            details = {
                "scrape_id": scrape_id,
                "cleaned_length": len(cleaned),
                "price_changes": price_changes,
                "item_count": len(extracted_items) if isinstance(extracted_items, list) else 0
            }

        # Check webhook alert trigger
        should_alert = webhook_url and (diff_detected or not alert_on_change_only)
        if should_alert:
            alert_title = f"🔔 Scraping Monitor Alert: {job['name']}"
            alert_payload = {
                "job": job["name"],
                "url": url,
                "summary": summary,
                "diff_detected": diff_detected,
                "timestamp": now_str,
                "details": details
            }
            send_webhook(webhook_url, alert_title, json.dumps(alert_payload, indent=2))
            summary += " [Webhook Alert Dispatched]"

        status = "success"

    except Exception as e:
        logging.error(f"Scheduled job #{job_id} failed: {e}")
        status = "failed"
        summary = f"Execution failed: {str(e)}"
        details = {"error": str(e)}

    # Update database log and next run
    interval = job.get("interval_minutes", 60)
    next_run = (datetime.now() + timedelta(minutes=interval)).strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        cursor = conn.cursor()
        # Record run log
        cursor.execute("""
            INSERT INTO job_run_logs (job_id, run_at, status, summary, diff_detected, details_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (job_id, now_str, status, summary, 1 if diff_detected else 0, json.dumps(details)))

        # Update job record
        cursor.execute("""
            UPDATE scheduled_jobs
            SET last_run_at = ?, next_run_at = ?, last_status = ?
            WHERE id = ?
        """, (now_str, next_run, status, job_id))
        conn.commit()

    return {
        "job_id": job_id,
        "status": status,
        "summary": summary,
        "diff_detected": diff_detected,
        "next_run_at": next_run
    }


def trigger_job_now(job_id: int) -> Dict[str, Any]:
    """Manually trigger immediate execution of a scheduled job."""
    job = get_job(job_id)
    if not job:
        raise ValueError(f"Job #{job_id} not found.")
    return execute_job_pipeline(job)


# ==============================================================================
# BACKGROUND DAEMON SCHEDULER
# ==============================================================================

class BackgroundScheduler:
    """
    Lightweight, thread-safe background scheduler that monitors due jobs in SQLite
    and executes them on their configured intervals.
    """
    def __init__(self, check_interval_seconds: int = 10):
        self.check_interval = check_interval_seconds
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="ScraperSchedulerDaemon")
            self._thread.start()
            logging.info("🕒 Background Scraper Scheduler Daemon started.")

    def stop(self):
        with self._lock:
            self._running = False
            logging.info("🕒 Background Scraper Scheduler Daemon stopped.")

    def is_running(self) -> bool:
        return self._running

    def _worker_loop(self):
        while self._running:
            try:
                self._check_and_run_due_jobs()
            except Exception as e:
                logging.error(f"Error in scheduler loop: {e}")
            time.sleep(self.check_interval)

    def _check_and_run_due_jobs(self):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM scheduled_jobs
                WHERE is_active = 1
                  AND next_run_at IS NOT NULL
                  AND next_run_at <= ?
            """, (now_str,))
            due_jobs = [dict(r) for r in cursor.fetchall()]

        for job in due_jobs:
            try:
                execute_job_pipeline(job)
            except Exception as e:
                logging.error(f"Failed to execute due job #{job['id']}: {e}")


# Singleton instance
_scheduler_instance: Optional[BackgroundScheduler] = None
_instance_lock = threading.Lock()


def get_scheduler() -> BackgroundScheduler:
    """Get or initialize the global BackgroundScheduler daemon."""
    global _scheduler_instance
    with _instance_lock:
        if _scheduler_instance is None:
            _scheduler_instance = BackgroundScheduler(check_interval_seconds=10)
            _scheduler_instance.start()
        return _scheduler_instance
