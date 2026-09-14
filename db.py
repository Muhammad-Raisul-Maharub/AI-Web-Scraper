# db.py - SQLite Persistence, Scrape History, and Content Change Detection
import sqlite3
import hashlib
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_FILE = "scraper.db"


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database tables for history and change tracking."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scrapes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                mode TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                raw_length INTEGER,
                cleaned_length INTEGER,
                cleaned_text TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS extractions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scrape_id INTEGER,
                url TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                template TEXT,
                prompt TEXT,
                results_json TEXT,
                FOREIGN KEY (scrape_id) REFERENCES scrapes (id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tracked_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                item_name TEXT NOT NULL,
                price_text TEXT NOT NULL,
                price_numeric REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def compute_content_hash(text: str) -> str:
    """Compute SHA-256 hash for content change detection."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def save_scrape(url: str, mode: str, raw_html: str, cleaned_text: str) -> int:
    """Save a page scrape record."""
    init_db()
    c_hash = compute_content_hash(cleaned_text)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO scrapes (url, mode, content_hash, raw_length, cleaned_length, cleaned_text)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (url, mode, c_hash, len(raw_html), len(cleaned_text), cleaned_text))
        conn.commit()
        return cursor.lastrowid


def save_extraction(scrape_id: Optional[int], url: str, template: str, prompt: str, results_data: Any) -> int:
    """Save an AI extraction result."""
    init_db()
    json_str = json.dumps(results_data, ensure_ascii=False)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO extractions (scrape_id, url, template, prompt, results_json)
            VALUES (?, ?, ?, ?, ?)
        """, (scrape_id, url, template, prompt, json_str))
        conn.commit()
        return cursor.lastrowid


def get_recent_scrapes(limit: int = 15) -> List[Dict[str, Any]]:
    """Retrieve recent scrape history."""
    init_db()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, url, timestamp, mode, raw_length, cleaned_length, content_hash
            FROM scrapes
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]


def get_recent_extractions(limit: int = 15) -> List[Dict[str, Any]]:
    """Retrieve recent extraction history."""
    init_db()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, url, timestamp, template, prompt, results_json
            FROM extractions
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        rows = [dict(row) for row in cursor.fetchall()]
        for r in rows:
            try:
                r["results_parsed"] = json.loads(r["results_json"])
            except Exception:
                r["results_parsed"] = r["results_json"]
        return rows


def _parse_price_to_float(price_str: str) -> Optional[float]:
    """Extract numeric price value from string (e.g., '$19.99' -> 19.99)."""
    clean = re.sub(r"[^\d.]", "", price_str)
    try:
        return float(clean)
    except ValueError:
        return None


def detect_price_changes(url: str, extracted_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Compare newly extracted items with the latest recorded prices in the database.
    Logs new prices and returns a list of detected price changes.
    """
    init_db()
    changes = []

    with get_db() as conn:
        cursor = conn.cursor()

        for item in extracted_items:
            # Look for item name and price
            name = item.get("name") or item.get("product_name") or item.get("title")
            price = item.get("current_price") or item.get("price")

            if not name or not price:
                continue

            name = str(name).strip()
            price_text = str(price).strip()
            price_numeric = _parse_price_to_float(price_text)

            # Query the latest recorded price for this item on this URL
            cursor.execute("""
                SELECT price_text, price_numeric, timestamp
                FROM tracked_prices
                WHERE url = ? AND item_name = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (url, name))

            latest_record = cursor.fetchone()

            if latest_record:
                old_text = latest_record["price_text"]
                old_num = latest_record["price_numeric"]

                if old_text != price_text and old_num is not None and price_numeric is not None:
                    diff = price_numeric - old_num
                    changes.append({
                        "item": name,
                        "old_price": old_text,
                        "new_price": price_text,
                        "change_amount": round(diff, 2),
                        "direction": "increase" if diff > 0 else "decrease",
                        "previous_date": latest_record["timestamp"]
                    })

            # Record the new price measurement
            cursor.execute("""
                INSERT INTO tracked_prices (url, item_name, price_text, price_numeric)
                VALUES (?, ?, ?, ?)
            """, (url, name, price_text, price_numeric))

        conn.commit()

    return changes
