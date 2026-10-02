"""config.py - every tunable parameter of the bench, overridable by environment variables."""
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.environ.get("FLORA_OUT", os.path.join(ROOT, "outputs"))
SEED = int(os.environ.get("FLORA_SEED", "2026"))
QUICK = os.environ.get("FLORA_QUICK", "0") == "1"
