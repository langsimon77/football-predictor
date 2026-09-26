"""Questions (spec S9, page 6). Read-only: answers are ticked in the GitHub Issue
(PRD Q3), so no write token ever sits in this public app."""

from __future__ import annotations

import re

import pandas as pd
import streamlit as st

import lib

lib.setup("Questions")
lib.updated_line()
st.write("Answer by ticking boxes in the GitHub Issue: open the link, tick, and you are done. "
         "This page only shows the questions.")
questions = lib.document("questions.json")
if not questions:
    st.info("No open questions. A new Issue opens with the daily run when matches lock "
            "within the next 48 to 72 hours.")
    st.stop()

MARKER = re.compile(r"\s*<!--.*?-->")
for q in questions:  # type: ignore[union-attr]
    st.subheader(q["title"])
    if q.get("number"):
        st.link_button("Answer on GitHub", f"{lib.ISSUES}/{q['number']}")
    deadline = q.get("deadline_utc")
    if not deadline and q.get("created_utc"):
        deadline = pd.Timestamp(q["created_utc"]) + pd.Timedelta(days=1)
    if deadline:
        when = lib.juba(pd.Timestamp(deadline))
        st.caption(f"Deadline: the next daily run, {when:%a %d %b, %H:%M} Juba time. "
                   "Unticked clubs count as \"don't know\".")
    body = MARKER.sub("", q.get("body") or "").replace("- [x]", "- ✅").replace("- [ ]", "- ⬜")
    with st.expander("Show the questions", expanded=len(questions) == 1):  # type: ignore[arg-type]
        st.markdown(body)
