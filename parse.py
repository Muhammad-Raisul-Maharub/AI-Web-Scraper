# parse.py - Root Shim for omniscrape.engine.parse
import sys
import os

_src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from omniscrape.engine.parse import *
