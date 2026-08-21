"""Right column: the "Advanced settings" container (OpenAlex, Model, Agents, Raw YAML)."""

import httpx
import streamlit as st

from web_ui.core.config_io import DQ, dump_config_str


def render_advanced_panel(cfg: dict) -> str:
    """Render the Advanced settings container. Returns the selected `source`."""
    with st.container(border=True):
        st.subheader(":material/tune: Advanced settings")
        source = st.selectbox("Source", ["all", "journals"], key="run_source")

        _render_openalex(cfg)
        _render_model(cfg)
        _render_run_settings(cfg)
        _render_agents(cfg)

        with st.expander("Raw YAML", expanded=False, icon=":material/code:"):
            st.code(dump_config_str(cfg), language="yaml")

    return source


def _render_openalex(cfg: dict) -> None:
    with st.expander("OpenAlex", expanded=False, icon=":material/public:"):
        openalex_cfg = cfg.setdefault("openalex", {})
        openalex_cfg["mailto"] = DQ(
            st.text_input(
                "Mailto (polite pool)",
                value=openalex_cfg.get("mailto", ""),
                key="openalex_mailto",
            )
        )


def _render_model(cfg: dict) -> None:
    with st.expander("Model", expanded=False, icon=":material/smart_toy:"):
        model_cfg = cfg.setdefault("model", {})
        model_cfg["base_url"] = DQ(
            st.text_input(
                "Base URL", value=model_cfg.get("base_url", ""), key="model_base_url"
            )
        )
        model_cfg["model_name"] = DQ(
            st.text_input(
                "Model name", value=model_cfg.get("model_name", ""), key="model_name"
            )
        )
        model_cfg["api_key"] = DQ(
            st.text_input(
                "API key",
                value=model_cfg.get("api_key", ""),
                type="password",
                key="model_api_key",
            )
        )

        if st.button(
            "Test connection", key="test_connection", icon=":material/wifi_tethering:"
        ):
            base = model_cfg.get("base_url", "").rstrip("/")
            try:
                resp = httpx.get(
                    f"{base}/models",
                    headers={"Authorization": f"Bearer {model_cfg.get('api_key', '')}"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    st.success(f"Connected! HTTP {resp.status_code}")
                else:
                    st.error(f"HTTP {resp.status_code}: {resp.text[:300]}")
            except Exception as e:
                st.error(f"Connection failed: {e}")


def _render_run_settings(cfg: dict) -> None:
    with st.expander("Run settings", expanded=False, icon=":material/build:"):
        settings_cfg = cfg.setdefault("settings", {})
        settings_cfg["default_days"] = st.number_input(
            "Default days to look back",
            min_value=1,
            max_value=30,
            value=int(settings_cfg.get("default_days", 3)),
            key="default_days",
        )
        settings_cfg["data_dir"] = DQ(
            st.text_input(
                "Data directory", value=settings_cfg.get("data_dir", ""), key="data_dir"
            )
        )
        settings_cfg["paper_timeout_seconds"] = st.number_input(
            "Paper timeout (seconds)",
            min_value=5,
            max_value=600,
            value=int(settings_cfg.get("paper_timeout_seconds", 60)),
            key="paper_timeout",
        )
        settings_cfg["abstract_max_chars"] = st.number_input(
            "Abstract max chars sent to model",
            min_value=100,
            max_value=5000,
            value=int(settings_cfg.get("abstract_max_chars", 800)),
            key="abstract_max_chars",
        )
        settings_cfg["min_relevance_score"] = st.slider(
            "Minimum relevance score to keep",
            min_value=0.0,
            max_value=1.0,
            value=float(settings_cfg.get("min_relevance_score", 0.7)),
            step=0.05,
            key="min_relevance",
        )


def _render_agents(cfg: dict) -> None:
    with st.expander("Agents", expanded=False, icon=":material/psychology:"):
        agents_cfg = cfg.setdefault("agents", {})

        for name in list(agents_cfg.keys()):
            skill = agents_cfg[name]
            st.markdown(f"**{name}**")
            skill["instructions"] = st.text_area(
                "Instructions",
                value=skill.get("instructions", ""),
                height=200,
                key=f"{name}_instructions",
            )
            has_temp = st.checkbox(
                "Set temperature", value="temperature" in skill, key=f"{name}_has_temp"
            )
            if has_temp:
                skill["temperature"] = st.slider(
                    "Temperature",
                    0.0,
                    1.0,
                    float(skill.get("temperature", 0.5)),
                    0.05,
                    key=f"{name}_temp",
                )
            elif "temperature" in skill:
                del skill["temperature"]

            has_max_tok = st.checkbox(
                "Set max_tokens", value="max_tokens" in skill, key=f"{name}_has_maxtok"
            )
            if has_max_tok:
                skill["max_tokens"] = st.number_input(
                    "Max tokens",
                    min_value=1,
                    max_value=8192,
                    value=int(skill.get("max_tokens", 512)),
                    key=f"{name}_maxtok",
                )
            elif "max_tokens" in skill:
                del skill["max_tokens"]

            if st.button(
                f"Delete '{name}'", key=f"{name}_delete", icon=":material/delete:"
            ):
                del agents_cfg[name]
                st.rerun()
