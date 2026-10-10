"""Standalone detailed lab; shared controls also appear in Advanced options."""
import streamlit as st
from advanced import render_advanced_lab

st.set_page_config(page_title="Audio Watermark Lab",page_icon="〰️",layout="wide")
render_advanced_lab()
