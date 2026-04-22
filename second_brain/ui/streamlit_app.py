import streamlit as st

from core.config import APP_NAME, VERSION

st.set_page_config(page_title=APP_NAME, page_icon="🧠", layout="wide")

st.title(f"🧠 {APP_NAME}")
st.caption(f"Version {VERSION}")
st.info("Willkommen im SecondBrain Agent. Seiten werden in ui/pages/ hinzugefügt.")
