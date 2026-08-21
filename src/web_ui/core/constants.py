"""Shared paths and constants for the web UI."""

from pathlib import Path

CORE_DIR = Path(__file__).parent
WEB_UI_DIR = CORE_DIR.parent
REPO_ROOT = WEB_UI_DIR.parent.parent
CONFIG_PATH = REPO_ROOT / "config.yaml"
LOGO_PATH = WEB_UI_DIR / "assets" / "nina-logo.svg"

OPENALEX_BASE_URL = "https://api.openalex.org"
