# src/omniscrape/storage/outputs.py - Centralized Run & Output Management
import os
import json
import time
import shutil
import zipfile
import io
import re
from datetime import datetime
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional, Union

# Derive project root dynamically
STORAGE_DIR = os.path.dirname(os.path.abspath(__file__))
OMNISCRAPE_DIR = os.path.dirname(STORAGE_DIR)
SRC_DIR = os.path.dirname(OMNISCRAPE_DIR)
PROJECT_ROOT = os.path.dirname(SRC_DIR)

DEFAULT_OUTPUTS_DIR = os.path.join(PROJECT_ROOT, "outputs")
OUTPUTS_DIR = os.getenv("OMNISCRAPE_OUTPUTS_DIR", DEFAULT_OUTPUTS_DIR)
RUNS_DIR = os.path.join(OUTPUTS_DIR, "runs")


def _sanitize_slug(text: str) -> str:
    """Create a filesystem-safe slug from URL or text."""
    if not text:
        return "scrape"
    parsed = urlparse(text)
    host = parsed.netloc or parsed.path or text
    cleaned = re.sub(r"[^\w\-_]", "_", host)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned[:35] if cleaned else "scrape"


def _resolve_run_dir(run_target: Union[str, Dict[str, Any]]) -> str:
    """Helper to resolve a run directory path from either a string or a run dict."""
    if isinstance(run_target, dict):
        return run_target.get("run_dir", "")
    return str(run_target)


class RunOutputManager:
    """
    Manages dedicated output folders for every scraping, extraction,
    animation bundling, or copilot execution.
    """

    def __init__(self, base_runs_dir: Optional[str] = None, base_dir: Optional[str] = None):
        self.runs_dir = base_runs_dir or base_dir or RUNS_DIR
        os.makedirs(self.runs_dir, exist_ok=True)

    def create_run(
        self,
        url: str,
        task_type: str = "scrape",
        mode: str = "fast",
        template: Optional[str] = None,
        prompt: Optional[str] = None,
        custom_id: Optional[str] = None,
        metadata_extra: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Initializes an isolated run directory under outputs/runs/<run_id>/
        with an initial metadata.json manifest.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = _sanitize_slug(url)
        run_id = custom_id or f"{timestamp}_{slug}"
        run_dir = os.path.join(self.runs_dir, run_id)
        os.makedirs(run_dir, exist_ok=True)

        meta = {
            "run_id": run_id,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": datetime.now().isoformat(),
            "url": url,
            "task_type": task_type,
            "mode": mode,
            "template": template or "",
            "prompt": prompt or "",
            "status": "in_progress",
            "duration_seconds": None,
            "files": [],
            "file_details": {},
            "metrics": {},
            "error": None
        }
        if metadata_extra:
            meta.update(metadata_extra)

        meta_path = os.path.join(run_dir, "metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        return {
            "run_id": run_id,
            "run_dir": run_dir,
            "metadata_path": meta_path,
            "metadata": meta
        }

    def _update_manifest(self, run_dir: Union[str, Dict[str, Any]], filename: str, category: str, size_bytes: int):
        """Update metadata.json with file record."""
        rdir = _resolve_run_dir(run_dir)
        meta_path = os.path.join(rdir, "metadata.json")
        if not os.path.exists(meta_path):
            return

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

            if filename not in meta["files"]:
                meta["files"].append(filename)

            meta.setdefault("file_details", {})[filename] = {
                "category": category,
                "size_bytes": size_bytes,
                "recorded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
        except Exception:
            pass

    def save_text(self, run_dir: Union[str, Dict[str, Any]], filename: str, content: str, category: str = "text") -> str:
        """Saves text, HTML, or Markdown content into the run directory."""
        rdir = _resolve_run_dir(run_dir)
        target_path = os.path.join(rdir, filename)
        with open(target_path, "w", encoding="utf-8", errors="replace") as f:
            f.write(content)

        size = os.path.getsize(target_path)
        self._update_manifest(rdir, filename, category, size)
        return target_path

    def save_json(self, run_dir: Union[str, Dict[str, Any]], filename: str, data: Any, category: str = "json") -> str:
        """Saves a Python data structure as formatted JSON."""
        rdir = _resolve_run_dir(run_dir)
        target_path = os.path.join(rdir, filename)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        size = os.path.getsize(target_path)
        self._update_manifest(rdir, filename, category, size)
        return target_path

    def save_csv(self, run_dir: Union[str, Dict[str, Any]], filename: str, data: Any, category: str = "tabular") -> str:
        """
        Saves tabular data (pandas DataFrame, list of dicts, or CSV string) to CSV.
        """
        rdir = _resolve_run_dir(run_dir)
        target_path = os.path.join(rdir, filename)
        if hasattr(data, "to_csv"):
            data.to_csv(target_path, index=False)
        elif isinstance(data, list) and data and isinstance(data[0], dict):
            import pandas as pd
            pd.DataFrame(data).to_csv(target_path, index=False)
        elif isinstance(data, str):
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(data)
        else:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(str(data))

        size = os.path.getsize(target_path)
        self._update_manifest(rdir, filename, category, size)
        return target_path

    def save_image(self, run_dir: Union[str, Dict[str, Any]], filename: str, image_source: Union[str, bytes], category: str = "image") -> str:
        """
        Saves an image by either copying an existing image file or writing raw bytes.
        """
        rdir = _resolve_run_dir(run_dir)
        target_path = os.path.join(rdir, filename)
        if isinstance(image_source, str) and os.path.exists(image_source):
            shutil.copyfile(image_source, target_path)
        elif isinstance(image_source, bytes):
            with open(target_path, "wb") as f:
                f.write(image_source)
        else:
            raise ValueError("image_source must be a valid existing file path or bytes")

        size = os.path.getsize(target_path)
        self._update_manifest(rdir, filename, category, size)
        return target_path

    def save_zip(self, run_dir: Union[str, Dict[str, Any]], filename: str, zip_source: Union[str, bytes], category: str = "archive") -> str:
        """Saves a ZIP file into the run directory."""
        rdir = _resolve_run_dir(run_dir)
        target_path = os.path.join(rdir, filename)
        if isinstance(zip_source, str) and os.path.exists(zip_source):
            shutil.copyfile(zip_source, target_path)
        elif isinstance(zip_source, bytes):
            with open(target_path, "wb") as f:
                f.write(zip_source)
        else:
            raise ValueError("zip_source must be an existing file path or bytes")

        size = os.path.getsize(target_path)
        self._update_manifest(rdir, filename, category, size)
        return target_path

    def save_binary(self, run_dir: Union[str, Dict[str, Any]], filename: str, data: bytes, category: str = "binary") -> str:
        """Saves arbitrary binary bytes into the run directory."""
        rdir = _resolve_run_dir(run_dir)
        target_path = os.path.join(rdir, filename)
        with open(target_path, "wb") as f:
            f.write(data)

        size = os.path.getsize(target_path)
        self._update_manifest(rdir, filename, category, size)
        return target_path

    def finalize_run(
        self,
        run_dir: Union[str, Dict[str, Any]],
        status: str = "success",
        duration_seconds: Optional[float] = None,
        metrics: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        extra_meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Finalizes run metadata with status, duration, metrics, and completion state."""
        rdir = _resolve_run_dir(run_dir)
        meta_path = os.path.join(rdir, "metadata.json")
        meta = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                pass

        meta["status"] = status
        if duration_seconds is not None:
            meta["duration_seconds"] = round(duration_seconds, 3)
        if metrics:
            meta.setdefault("metrics", {}).update(metrics)
        if extra_meta:
            meta.update(extra_meta)
        if error:
            meta["error"] = error
        meta["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        return meta

    def list_runs(self, limit: int = 100, reverse: bool = True) -> List[Dict[str, Any]]:
        """Lists all previous run records sorted chronologically."""
        if not os.path.exists(self.runs_dir):
            return []

        runs = []
        for name in os.listdir(self.runs_dir):
            run_path = os.path.join(self.runs_dir, name)
            if not os.path.isdir(run_path):
                continue

            meta_file = os.path.join(run_path, "metadata.json")
            if os.path.exists(meta_file):
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                        meta["run_dir"] = run_path
                        meta["id"] = meta.get("run_id") or name
                        meta["metadata"] = dict(meta)
                        runs.append(meta)
                except Exception:
                    rec = {
                        "run_id": name,
                        "id": name,
                        "run_dir": run_path,
                        "created_at": "Unknown",
                        "status": "unreadable",
                        "files": os.listdir(run_path)
                    }
                    rec["metadata"] = dict(rec)
                    runs.append(rec)
            else:
                rec = {
                    "run_id": name,
                    "id": name,
                    "run_dir": run_path,
                    "created_at": "Unknown",
                    "status": "legacy",
                    "files": os.listdir(run_path)
                }
                rec["metadata"] = dict(rec)
                runs.append(rec)

        runs.sort(key=lambda x: x.get("created_at") or x.get("run_id", ""), reverse=reverse)
        return runs[:limit]

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves full details, metadata, and file map for a specific run ID."""
        run_dir = os.path.join(self.runs_dir, run_id)
        if not os.path.isdir(run_dir):
            return None

        meta_file = os.path.join(run_dir, "metadata.json")
        meta = {}
        if os.path.exists(meta_file):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                pass

        files_map = {}
        for fname in os.listdir(run_dir):
            fpath = os.path.join(run_dir, fname)
            if os.path.isfile(fpath):
                files_map[fname] = {
                    "path": fpath,
                    "size_bytes": os.path.getsize(fpath),
                    "modified": datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M:%S")
                }

        meta["run_dir"] = run_dir
        meta["run_id"] = run_id
        meta["id"] = run_id
        meta["available_files"] = files_map
        meta["metadata"] = dict(meta)
        return meta

    def export_run_zip(self, run_id: str) -> Optional[io.BytesIO]:
        """Bundles the entire contents of a run folder into an in-memory ZIP archive."""
        run_dir = os.path.join(self.runs_dir, run_id)
        if not os.path.isdir(run_dir):
            return None

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(run_dir):
                for f in files:
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, run_dir)
                    zf.write(full_p, arcname=rel_p)

        buf.seek(0)
        return buf

    def delete_run(self, run_id: str) -> bool:
        """Safely removes a run directory."""
        run_dir = os.path.join(self.runs_dir, run_id)
        if os.path.isdir(run_dir):
            shutil.rmtree(run_dir, ignore_errors=True)
            return True
        return False


# Global default instance
default_output_manager = RunOutputManager()
