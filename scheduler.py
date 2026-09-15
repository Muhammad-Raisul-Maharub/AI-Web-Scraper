# scheduler.py - Root Shim for omniscrape.automation.scheduler
import sys
import os

_src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from omniscrape.automation.scheduler import *

if __name__ == "__main__":
    import time
    scheduler = get_scheduler()
    print("🕒 Background Scraper Scheduler running. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.stop()
        print("Scheduler stopped.")
