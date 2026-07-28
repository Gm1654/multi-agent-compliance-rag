"""Streamlit demo UI for the multi-agent compliance and troubleshooting system.

Theming is handled entirely by Streamlit's native engine via .streamlit/config.toml,
which defines separate [theme.light] and [theme.dark] palettes. Streamlit switches
between them automatically based on OS/browser preference (and its own Settings UI
if available).

The SVG routing diagram lives in an iframe (st.components.v1.html) which is outside
Streamlit's theme engine. It uses st.context.theme.type to detect the active theme
and renders matching colours on every script re-run.

NOTE: st.context.theme.type may lag by one interaction on initial load or immediately
after a theme switch (known Streamlit issue #11920). The diagram auto-corrects on
the next user action.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
import streamlit.components.v1 as components

from agents.synthesizer import answer_query

# ── Palettes — must match .streamlit/config.toml ─────────────────────────────
_PALETTES = {
    "dark": {
        "bg":         "#0E1117",
        "bg2":        "#262730",
        "text":       "#FAFAFA",
        "text_muted": "#9BA3AF",
        "border":     "#3D3F4E",
        "shadow":     "rgba(0,0,0,0.40)",
    },
    "light": {
        "bg":         "#FFFFFF",
        "bg2":        "#F0F2F6",
        "text":       "#262730",
        "text_muted": "#6B7280",
        "border":     "#D9DDE8",
        "shadow":     "rgba(0,0,0,0.06)",
    },
}


def _palette() -> dict:
    """Return the colour palette matching the user's active Streamlit theme."""
    try:
        theme_type = st.context.theme.type  # "light" or "dark"
    except Exception:
        theme_type = "light"
    return _PALETTES.get(theme_type, _PALETTES["light"])


# ── SVG routing diagram ───────────────────────────────────────────────────────

def get_routing_html(agents_used: list[str], p: dict) -> str:
    """Return a self-contained HTML/SVG diagram styled to palette p."""
    agents_lower = [a.lower() for a in agents_used]

    res_on = "researcher"     in agents_lower
    aud_on = "auditor"        in agents_lower
    tro_on = "troubleshooter" in agents_lower

    p_res = "M 300 72 C 220 108, 150 122, 100 148"
    p_aud = "M 300 72 L 300 148"
    p_tro = "M 300 72 C 380 108, 450 122, 500 148"

    def _dot(path: str, on: bool) -> str:
        if not on:
            return ""
        return (
            f'<circle r="5.5" fill="#FACC15">'
            f'<animateMotion path="{path}" dur="1.3s" repeatCount="indefinite"/>'
            f'</circle>'
        )

    def _conn(path: str, on: bool, color: str, arrow: str) -> str:
        return (
            f'<path d="{path}" fill="none" '
            f'stroke="{ color if on else p["border"] }" '
            f'stroke-width="{ "2.8" if on else "1.8" }" '
            f'stroke-dasharray="5,4" '
            f'opacity="{ "1.0" if on else "0.30" }" '
            f'marker-end="url(#{ arrow if on else "arrow-neutral" })"/>'
        )

    def _dim(on: bool) -> str:
        return "1.0" if on else "0.25"

    def _lbl(on: bool, active_color: str) -> str:
        return active_color if on else p["text_muted"]

    badges = []
    if res_on:
        badges.append(
            '<span style="background:#581C87;color:#E9D5FF;border:1px solid #7E22CE;'
            'padding:3px 10px;border-radius:12px;font-weight:600;font-size:13px;margin:0 3px;">'
            "🤖 Researcher</span>"
        )
    if aud_on:
        badges.append(
            '<span style="background:#134E4A;color:#CCFBF1;border:1px solid #0F766E;'
            'padding:3px 10px;border-radius:12px;font-weight:600;font-size:13px;margin:0 3px;">'
            "🤖 Auditor</span>"
        )
    if tro_on:
        badges.append(
            '<span style="background:#7C2D12;color:#FFEDD5;border:1px solid #C2410C;'
            'padding:3px 10px;border-radius:12px;font-weight:600;font-size:13px;margin:0 3px;">'
            "🤖 Troubleshooter</span>"
        )

    status = (
        " ".join(badges)
        if badges
        else f'<span style="color:{p["text_muted"]};font-style:italic;">None</span>'
    )

    rs = p["text"]   # robot stroke
    re = p["bg"]     # robot eye fill
    sb = p["bg"]     # screen background

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body{{margin:0;padding:0;font-family:'Segoe UI',system-ui,sans-serif;
       background:transparent;display:flex;flex-direction:column;align-items:center;}}
  .card{{width:98%;max-width:640px;background:{p["bg2"]};border:1px solid {p["border"]};
         border-radius:14px;padding:16px 14px 14px;box-shadow:0 4px 16px {p["shadow"]};}}
  .status{{margin-top:8px;text-align:center;font-size:13px;color:{p["text"]};font-weight:500;}}
</style></head><body>
<div class="card">
  <svg viewBox="0 0 600 225" width="100%" height="215" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <marker id="arrow-neutral" viewBox="0 0 10 10" refX="6" refY="5"
              markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 1 L 10 5 L 0 9 z" fill="{p["border"]}"/>
      </marker>
      <marker id="arrow-purple" viewBox="0 0 10 10" refX="6" refY="5"
              markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 1 L 10 5 L 0 9 z" fill="#A855F7"/>
      </marker>
      <marker id="arrow-teal" viewBox="0 0 10 10" refX="6" refY="5"
              markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 1 L 10 5 L 0 9 z" fill="#14B8A6"/>
      </marker>
      <marker id="arrow-coral" viewBox="0 0 10 10" refX="6" refY="5"
              markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 1 L 10 5 L 0 9 z" fill="#F97316"/>
      </marker>
      <g id="robot">
        <line x1="-9" y1="-26" x2="-9" y2="-36" stroke="{rs}" stroke-width="2.5" stroke-linecap="round"/>
        <circle cx="-9" cy="-39" r="3" stroke="{rs}" stroke-width="2" fill="none"/>
        <line x1="9"  y1="-26" x2="9"  y2="-36" stroke="{rs}" stroke-width="2.5" stroke-linecap="round"/>
        <circle cx="9"  cy="-39" r="3" stroke="{rs}" stroke-width="2" fill="none"/>
        <rect x="-20" y="-26" width="40" height="20" rx="5" stroke="{rs}" stroke-width="2.5" fill="none"/>
        <circle cx="-8" cy="-18" r="2.5" fill="{re}"/>
        <circle cx="8"  cy="-18" r="2.5" fill="{re}"/>
        <line x1="-6" y1="-11" x2="6" y2="-11" stroke="{rs}" stroke-width="2" stroke-linecap="round"/>
        <rect x="-30" y="-2" width="8"  height="18" rx="2.5" stroke="{rs}" stroke-width="2.5" fill="none"/>
        <rect x="22"  y="-2" width="8"  height="18" rx="2.5" stroke="{rs}" stroke-width="2.5" fill="none"/>
        <rect x="-22" y="-6" width="44" height="26" rx="5"   stroke="{rs}" stroke-width="2.5" fill="none"/>
        <rect x="-11" y="-1" width="22" height="14" rx="2.5"
              fill="{sb}" fill-opacity="0.85" stroke="{rs}" stroke-width="1.8"/>
        <line x1="-5" y1="3" x2="5" y2="3" stroke="{rs}" stroke-width="1.8" stroke-linecap="round"/>
        <line x1="-3" y1="8" x2="3" y2="8" stroke="{rs}" stroke-width="1.8" stroke-linecap="round"/>
      </g>
    </defs>

    {_conn(p_res, res_on, "#A855F7", "arrow-purple")}
    {_conn(p_aud, aud_on, "#14B8A6", "arrow-teal")}
    {_conn(p_tro, tro_on, "#F97316", "arrow-coral")}

    {_dot(p_res, res_on)}
    {_dot(p_aud, aud_on)}
    {_dot(p_tro, tro_on)}

    <g transform="translate(300,44)">
      <g fill="#94A3B8"><use href="#robot"/></g>
      <text x="0" y="32" text-anchor="middle" font-size="11" font-weight="700"
            fill="{p["text"]}">Orchestrator</text>
    </g>
    <g transform="translate(100,164)" opacity="{_dim(res_on)}">
      <g fill="#C084FC"><use href="#robot"/></g>
      <text x="0" y="32" text-anchor="middle" font-size="11" font-weight="700"
            fill="{_lbl(res_on, '#E9D5FF')}">Researcher</text>
      <text x="0" y="44" text-anchor="middle" font-size="9.5" fill="{p["text_muted"]}">Equipment Manuals</text>
    </g>
    <g transform="translate(300,164)" opacity="{_dim(aud_on)}">
      <g fill="#2DD4BF"><use href="#robot"/></g>
      <text x="0" y="32" text-anchor="middle" font-size="11" font-weight="700"
            fill="{_lbl(aud_on, '#99F6E4')}">Auditor</text>
      <text x="0" y="44" text-anchor="middle" font-size="9.5" fill="{p["text_muted"]}">Safety &amp; Compliance</text>
    </g>
    <g transform="translate(500,164)" opacity="{_dim(tro_on)}">
      <g fill="#FB923C"><use href="#robot"/></g>
      <text x="0" y="32" text-anchor="middle" font-size="11" font-weight="700"
            fill="{_lbl(tro_on, '#FFEDD5')}">Troubleshooter</text>
      <text x="0" y="44" text-anchor="middle" font-size="9.5" fill="{p["text_muted"]}">Repair Logs</text>
    </g>
  </svg>
  <div class="status">⚡ Query routed to: {status}</div>
</div>
</body></html>"""


# ── Page setup ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Hydraulic Press Assistant",
    page_icon=":wrench:",
    layout="wide",
)

# Resolve active palette once per run (responds to native theme switching)
palette = _palette()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    show_debug = st.checkbox("Show agent debug output", value=False)

    st.divider()
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

# ── Main content ──────────────────────────────────────────────────────────────
st.title("Hydraulic Press Maintenance Assistant")
st.caption(
    "Multi-agent RAG system for manuals, safety compliance, and repair troubleshooting."
)

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant" and "agents_used" in message:
            components.html(
                get_routing_html(message["agents_used"], palette), height=285
            )
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
                components.html(
                    get_routing_html(result.agents_used, palette), height=285
                )
                st.markdown(result.final_answer)

                debug_payload = {
                    "agents_used": result.agents_used,
                    "orchestrator": result.orchestrator,
                }
                if show_debug:
                    with st.expander("Agent debug output"):
                        st.code(json.dumps(debug_payload, indent=2), language="json")

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": result.final_answer,
                        "agents_used": result.agents_used,
                        "debug": json.dumps(debug_payload, indent=2),
                    }
                )
            except Exception as exc:
                error_text = f"Error: {exc}"
                st.error(error_text)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_text}
                )
