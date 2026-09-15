# src/omniscrape/storage/__init__.py
from .db import (
    get_db,
    init_db,
    compute_content_hash,
    save_scrape,
    save_extraction,
    get_recent_scrapes,
    get_recent_extractions,
    detect_price_changes,
    DB_FILE,
    DATA_DIR
)
from .outputs import (
    RunOutputManager,
    default_output_manager,
    OUTPUTS_DIR,
    RUNS_DIR
)

__all__ = [
    "get_db",
    "init_db",
    "compute_content_hash",
    "save_scrape",
    "save_extraction",
    "get_recent_scrapes",
    "get_recent_extractions",
    "detect_price_changes",
    "DB_FILE",
    "DATA_DIR",
    "RunOutputManager",
    "default_output_manager",
    "OUTPUTS_DIR",
    "RUNS_DIR"
]
