"""Load/save each user's config.yaml (in S3) while preserving comments and
formatting (ruamel.yaml)."""

import io

from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString as DQ

from paper_agent.s3_storage import join, read_text, user_prefix, write_text
from web_ui.core.constants import REPO_ROOT

__all__ = [
    "DQ",
    "dump_config_str",
    "load_user_config",
    "save_user_config",
    "user_data_dir",
]

_yaml = YAML()
_yaml.preserve_quotes = True
_yaml.indent(mapping=2, sequence=4, offset=2)
_yaml.width = 4096  # avoid wrapping long instruction strings


def dump_config_str(cfg: dict) -> str:
    buf = io.StringIO()
    _yaml.dump(cfg, buf)
    return buf.getvalue()


def user_data_dir(user_id: str) -> str:
    """Canonical S3 location for a given user's papers/summaries/highlights."""
    return join(user_prefix(user_id), "paper_summaries")


def _user_config_uri(user_id: str) -> str:
    return join(user_prefix(user_id), "config.yaml")


def load_user_config(user_id: str) -> dict:
    """Load a user's config.yaml from S3, seeding it from config.example.yaml
    on first use. The `settings.data_dir` field is always forced to that
    user's canonical S3 path, so summaries/papers stay isolated per user.
    """
    uri = _user_config_uri(user_id)
    text = read_text(uri)

    if text is not None:
        cfg = _yaml.load(text)
    else:
        example_path = REPO_ROOT / "config.example.yaml"
        with open(example_path) as f:
            cfg = _yaml.load(f)

    cfg.setdefault("settings", {})["data_dir"] = DQ(user_data_dir(user_id))

    if text is None:
        save_user_config(user_id, cfg)

    return cfg


def save_user_config(user_id: str, cfg: dict) -> None:
    """Persist a user's config.yaml to S3 (always pinning their data_dir)."""
    cfg.setdefault("settings", {})["data_dir"] = DQ(user_data_dir(user_id))
    write_text(_user_config_uri(user_id), dump_config_str(cfg))
