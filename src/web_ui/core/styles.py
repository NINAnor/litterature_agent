"""Custom CSS for the web UI, matching the NINA brand palette (teal + orange)."""

CUSTOM_CSS = """
<style>
a { color: #87BFC4; }
a:hover { color: #5FB1BA; }

div[data-testid="stMetric"] {
    background-color: #ffffff;
    border: 1px solid rgba(38, 39, 48, 0.2);
    padding: 15px;
    border-radius: 0.5rem;
}

.footer {
    width: 100%;
    background-color: #f5f5f5;
    color: #666;
    text-align: center;
    padding: 10px 0;
    margin-top: 20px;
    font-size: 0.85em;
    border-top: 1px solid #ddd;
}

.footer a {
    color: #87BFC4;
    text-decoration: none;
}

.footer a:hover {
    text-decoration: underline;
}

/* Left-align the sidebar nav buttons (Runs menu) and keep padding
   consistent between selected (primary) and unselected (tertiary) items,
   so text doesn't shift horizontally depending on selection state. */
[data-testid="stSidebar"] div[data-testid="stButton"] button {
    justify-content: flex-start !important;
    text-align: left !important;
    padding: 0.25rem 0.75rem !important;
    border-radius: 0.4rem !important;
}
[data-testid="stSidebar"] div[data-testid="stButton"] button > div {
    justify-content: flex-start !important;
}
[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="tertiary"]:hover {
    background-color: rgba(0, 0, 0, 0.05) !important;
}

/* Highlight the Highlights box in NINA teal */
.st-key-highlights_box {
    background-color: rgba(135, 191, 196, 0.15) !important;
    border: 1px solid rgba(135, 191, 196, 0.6) !important;
}
</style>
"""
