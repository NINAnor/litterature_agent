"""Middle column: highlights box + the list of paper summary cards."""

from datetime import date

import streamlit as st


def render_summaries_panel(
    summaries_df, highlights_df, selected: str, data_dir: str
) -> None:
    if summaries_df is None or summaries_df.empty:
        st.subheader(":material/inbox: No summaries yet")
        st.caption(f"Run the agent to populate `{data_dir}/summaries.parquet`.")
        return

    if selected == "All":
        day_df = summaries_df
        selected_day = None
        st.subheader(f":material/description: All summaries ({len(day_df)})")
    else:
        selected_day = date.fromisoformat(selected)
        day_df = summaries_df[summaries_df["run_day"] == selected_day]
        st.subheader(
            f":material/description: {selected_day.strftime('%d/%m/%Y')} ({len(day_df)} papers)"
        )

    _render_highlights(highlights_df, selected, selected_day)

    search = st.text_input(
        "Search title or summary",
        key="search_query",
        placeholder="Filter by keyword...",
    )
    if search:
        mask = day_df["title"].str.contains(search, case=False, na=False) | day_df[
            "summary"
        ].str.contains(search, case=False, na=False)
        day_df = day_df[mask]

    for _, row in day_df.iterrows():
        _render_paper_card(row)


def _render_highlights(highlights_df, selected: str, selected_day) -> None:
    if highlights_df is None or highlights_df.empty:
        return

    if selected == "All":
        day_highlights = highlights_df
    else:
        day_highlights = highlights_df[
            highlights_df["run_date"].dt.date == selected_day
        ]

    if day_highlights.empty:
        return

    with st.container(border=True, key="highlights_box"):
        st.markdown("##### :material/star: Highlights")
        for h in day_highlights["highlight"]:
            st.markdown(f"- {h}")


def _render_paper_card(row) -> None:
    with st.container(border=True):
        if row.get("url"):
            st.markdown(f"#### [{row['title']}]({row['url']})")
        else:
            st.markdown(f"#### {row['title']}")

        meta_bits = [f":material/target: Relevance: {row['relevance_score']:.2f}"]
        if row.get("source"):
            meta_bits.append(f":material/public: Journal: {row['source']}")
        st.caption("  •  ".join(meta_bits))

        second_row = []
        if row.get("published_date") is not None:
            pub_date = row["published_date"]
            pub_date_str = (
                pub_date.strftime("%d/%m/%Y")
                if hasattr(pub_date, "strftime")
                else str(pub_date)
            )
            second_row.append(f":material/calendar_month: Date: {pub_date_str}")

        authors = row.get("authors")
        if authors is not None and len(authors) > 0:
            authors_str = ", ".join(authors[:5])
            if len(authors) > 5:
                authors_str += " et al."
            second_row.append(f":material/group: {authors_str}")

        if second_row:
            st.caption("  •  ".join(second_row))

        st.write(row["summary"])

        if row.get("methods") is not None and len(row["methods"]) > 0:
            st.caption(f":material/build: **Methods:** {', '.join(row['methods'])}")
        if row.get("topics") is not None and len(row["topics"]) > 0:
            st.caption(f":material/sell: **Topics:** {', '.join(row['topics'])}")
