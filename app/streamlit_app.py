"""Streamlit demo UI for the multi-agent compliance and troubleshooting system."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from agents.synthesizer import answer_query

st.set_page_config(
    page_title="Hydraulic Press Assistant",
    page_icon=":wrench:",
    layout="wide",
)

st.title("Hydraulic Press Maintenance Assistant")
st.caption(
    "Multi-agent RAG system for manuals, safety compliance, and repair troubleshooting."
)

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.header("About")
    st.markdown(
        """
This demo routes your question through:
- **Researcher** → equipment manuals
- **Auditor** → safety/compliance docs
- **Troubleshooter** → past repair logs

The orchestrator picks the relevant agents, then the synthesizer combines their outputs.
"""
    )
    show_debug = st.checkbox("Show agent debug output", value=False)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("debug") and show_debug:
            with st.expander("Agent debug output"):
                st.code(message["debug"], language="json")

prompt = st.chat_input("Ask about operation, safety, or troubleshooting...")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Routing query and consulting specialist agents..."):
            try:
                result = answer_query(prompt)
                st.markdown(result.final_answer)

                debug_payload = {
                    "agents_used": result.agents_used,
                    "orchestrator": result.orchestrator,
                }
                if show_debug:
                    with st.expander("Agent debug output"):
                        st.code(
                            json.dumps(debug_payload, indent=2),
                            language="json",
                        )

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": result.final_answer,
                        "debug": json.dumps(debug_payload, indent=2),
                    }
                )
            except Exception as exc:
                error_text = f"Error: {exc}"
                st.error(error_text)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_text}
                )
