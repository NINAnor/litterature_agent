"""S3 helpers shared by the CLI and web UI — DuckDB-only, no extra SDKs.

Per-user data (config + parquet summaries) is stored in a single S3 bucket,
one prefix per user: `s3://<bucket>/<prefix>/<user_id>/...`. Everything is
read/written through DuckDB's `httpfs` extension using plain `s3://` URIs:
- Parquet files (papers/summaries/highlights) via `COPY ... (FORMAT PARQUET)`.
- Small text files (config.yaml, markdown reports) are round-tripped through
  DuckDB's CSV reader/writer as a single-column blob (see `read_text` /
  `write_text` below) — this avoids needing a separate S3 SDK like boto3.

Credentials are resolved in this order:
1. Environment variables: S3_ENDPOINT_URL, S3_ACCESS_KEY_ID,
   S3_SECRET_ACCESS_KEY, S3_REGION, S3_FORCE_PATH_STYLE.
2. A local `rclone.conf` remote (for convenient local development), selected
   via the S3_RCLONE_REMOTE env var (default: "miljodata-test").
"""

from __future__ import annotations

import configparser
import os
from functools import lru_cache
from pathlib import Path

import duckdb

S3_BUCKET = os.environ.get("S3_BUCKET", "miljodata-test")
S3_PREFIX = os.environ.get("S3_PREFIX", "paper-agent").strip("/")
RCLONE_REMOTE = os.environ.get("S3_RCLONE_REMOTE", "miljodata-test")
RCLONE_CONFIG_PATH = Path(
    os.environ.get("RCLONE_CONFIG_PATH", "~/.config/rclone/rclone.conf")
).expanduser()


def is_s3_uri(path: str) -> bool:
    return str(path).startswith("s3://")


def user_prefix(user_id: str) -> str:
    """Return the `s3://bucket/prefix/user_id` base URI for a given user."""
    return f"s3://{S3_BUCKET}/{S3_PREFIX}/{sanitize_user_id(user_id)}"


def sanitize_user_id(user_id: str) -> str:
    """Make a raw username safe to use as an S3 key segment."""
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in user_id.strip())
    return safe.strip("-").lower() or "anonymous"


def join(base: str, *parts: str) -> str:
    """Join path segments with `/`, working for both local paths and s3:// URIs
    (unlike `pathlib.Path`, which collapses the `//` after the `s3:` scheme).
    """
    segments = [base.rstrip("/")] + [p.strip("/") for p in parts]
    return "/".join(segments)


@lru_cache(maxsize=1)
def _rclone_credentials() -> dict | None:
    """Best-effort parse of a local rclone.conf for the configured remote."""
    if not RCLONE_CONFIG_PATH.exists():
        return None

    parser = configparser.ConfigParser()
    parser.read(RCLONE_CONFIG_PATH)
    if RCLONE_REMOTE not in parser:
        return None

    section = parser[RCLONE_REMOTE]
    if section.get("type") != "s3":
        return None

    return {
        "endpoint_url": section.get("endpoint"),
        "access_key_id": section.get("access_key_id"),
        "secret_access_key": section.get("secret_access_key"),
        "region": section.get("region") or "us-east-1",
        "force_path_style": section.getboolean("force_path_style", fallback=True),
    }


def get_s3_settings() -> dict:
    """Resolve S3 connection settings from env vars, falling back to rclone.conf."""
    endpoint = os.environ.get("S3_ENDPOINT_URL")
    access_key = os.environ.get("S3_ACCESS_KEY_ID")
    secret_key = os.environ.get("S3_SECRET_ACCESS_KEY")

    if endpoint and access_key and secret_key:
        return {
            "endpoint_url": endpoint,
            "access_key_id": access_key,
            "secret_access_key": secret_key,
            "region": os.environ.get("S3_REGION", "us-east-1"),
            "force_path_style": os.environ.get("S3_FORCE_PATH_STYLE", "true").lower()
            in ("1", "true", "yes"),
        }

    creds = _rclone_credentials()
    if creds:
        return creds

    raise RuntimeError(
        "No S3 credentials found. Set S3_ENDPOINT_URL, S3_ACCESS_KEY_ID and "
        "S3_SECRET_ACCESS_KEY (see .env.example), or make sure "
        f"~/.config/rclone/rclone.conf has a '[{RCLONE_REMOTE}]' remote."
    )


def configure_duckdb_httpfs(con: duckdb.DuckDBPyConnection) -> None:
    """Install/load the httpfs extension and point it at our S3 endpoint."""
    settings = get_s3_settings()
    endpoint = settings["endpoint_url"].removeprefix("https://").removeprefix("http://")
    use_ssl = settings["endpoint_url"].startswith("https://")

    con.execute("INSTALL httpfs")
    con.execute("LOAD httpfs")
    con.execute(f"SET s3_endpoint='{endpoint}'")
    con.execute(f"SET s3_access_key_id='{settings['access_key_id']}'")
    con.execute(f"SET s3_secret_access_key='{settings['secret_access_key']}'")
    con.execute(f"SET s3_region='{settings.get('region', 'us-east-1')}'")
    con.execute(f"SET s3_use_ssl={'true' if use_ssl else 'false'}")
    con.execute(
        f"SET s3_url_style='{'path' if settings.get('force_path_style', True) else 'vhost'}'"
    )


def connect(*paths: str) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection, configuring the `httpfs` extension if any of
    the given paths point at S3. Shared by `PaperStorage` and the web UI's
    data loaders so there's a single place that decides "does this need S3".
    """
    con = duckdb.connect()
    if any(is_s3_uri(p) for p in paths):
        configure_duckdb_httpfs(con)
    return con


def object_exists(uri: str) -> bool:
    """Check whether a single object exists, local or s3://.

    Note: DuckDB's `glob()` doesn't hit the network for literal (non-wildcard)
    S3 paths, so it can't be used for existence checks — instead we try an
    actual (zero-row) read and treat any error as "doesn't exist".
    """
    if not is_s3_uri(uri):
        return Path(uri).exists()

    con = connect(uri)
    try:
        if uri.endswith(".parquet"):
            con.execute(f"SELECT 1 FROM read_parquet('{uri}') LIMIT 0")
        else:
            con.execute(
                f"SELECT 1 FROM read_csv('{uri}', columns={{'content': 'VARCHAR'}}, "
                "header=false, quote='\"', escape='\"') LIMIT 0"
            )
        return True
    except Exception:
        return False
    finally:
        con.close()


def read_text(uri: str) -> str | None:
    """Read a small text object (local path or s3:// URI), or None if missing.

    Written objects are round-tripped through DuckDB's CSV format (see
    `write_text`), so we must read them back with `read_csv`, not the raw
    `read_text` table function (which would return the still-quoted bytes).
    """
    con = connect(uri)
    try:
        row = con.execute(
            "SELECT content FROM read_csv(?, columns={'content': 'VARCHAR'}, "
            "header=false, quote='\"', escape='\"')",
            [uri],
        ).fetchone()
        return row[0] if row else None
    except Exception:
        return None
    finally:
        con.close()


def write_text(uri: str, content: str) -> None:
    """Write a small text blob (local path or s3:// URI) via DuckDB's CSV
    reader/writer, used as a raw single-column text container (round-trips
    exactly, including newlines/quotes/unicode — see module tests).
    """
    con = connect(uri)
    try:
        con.execute("CREATE TEMP TABLE _write_text AS SELECT ? AS content", [content])
        con.execute(f"COPY _write_text TO '{uri}' (FORMAT CSV, HEADER false)")
    finally:
        con.execute("DROP TABLE IF EXISTS _write_text")
        con.close()
