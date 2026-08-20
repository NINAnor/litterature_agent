"""Entrypoint that launches the Streamlit config UI (see app.py)."""

import sys
from pathlib import Path

import streamlit.web.cli as stcli


def main() -> None:
    app_path = Path(__file__).parent / "app.py"
    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--server.address=0.0.0.0",
        "--server.port=8501",
    ]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
