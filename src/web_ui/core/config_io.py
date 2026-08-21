"""Load/save config.yaml while preserving comments and formatting (ruamel.yaml)."""

import io

from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString as DQ

from web_ui.core.constants import CONFIG_PATH

__all__ = ["DQ", "load_config", "save_config", "dump_config_str"]

_yaml = YAML()
_yaml.preserve_quotes = True
_yaml.indent(mapping=2, sequence=4, offset=2)
_yaml.width = 4096  # avoid wrapping long instruction strings


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return _yaml.load(f)


def save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        _yaml.dump(cfg, f)


def dump_config_str(cfg: dict) -> str:
    buf = io.StringIO()
    _yaml.dump(cfg, buf)
    return buf.getvalue()
