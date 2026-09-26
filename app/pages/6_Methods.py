"""Methods and changelog (spec S9, page 7)."""

from __future__ import annotations

import re

import streamlit as st

import lib

lib.setup("Methods")
changelog = lib.doc_text("docs/MODEL_CHANGELOG.md")
pending = [line for line in changelog.splitlines()
           if line.startswith("|") and re.search(r"awaiting Lang", line, re.IGNORECASE)]
if pending:
    st.warning(f"{len(pending)} model change(s) awaiting Lang's approval. See the Changelog tab.")

learn, card, log = st.tabs(["How it works", "Model card", "Changelog"])
with learn:
    st.markdown(lib.doc_text("docs/LEARN.md") or "docs/LEARN.md not found.")
with card:
    st.markdown(lib.doc_text("docs/MODEL_CARD.md") or "docs/MODEL_CARD.md not found.")
with log:
    if pending:
        st.markdown("**Awaiting Lang's approval:**")
        for line in pending:
            cells = [c.strip() for c in line.strip("|").split("|")]
            st.markdown(f"- {cells[0]}: {cells[3] if len(cells) > 3 else ''}")
    st.markdown(re.sub(r"awaiting Lang", "**awaiting Lang's approval**", changelog))
