"""
views/ui_components.py
Reusable Streamlit UI component helpers, modal dialogs, and stretch button adapters.
"""

import streamlit as st


def st_button_stretch(label: str, **kwargs) -> bool:
    kwargs.pop("use_container_width", None)
    try:
        return st.button(label, width="stretch", **kwargs)
    except TypeError:
        return st.button(label, use_container_width=True, **kwargs)


def st_sidebar_button_stretch(label: str, **kwargs) -> bool:
    kwargs.pop("use_container_width", None)
    try:
        return st.sidebar.button(label, width="stretch", **kwargs)
    except TypeError:
        return st.sidebar.button(label, use_container_width=True, **kwargs)


def st_download_button_stretch(label: str, data, **kwargs):
    kwargs.pop("use_container_width", None)
    try:
        return st.download_button(label, data, width="stretch", **kwargs)
    except TypeError:
        return st.download_button(label, data, use_container_width=True, **kwargs)


def st_form_submit_button_stretch(label: str, **kwargs):
    kwargs.pop("use_container_width", None)
    try:
        return st.form_submit_button(label, width="stretch", **kwargs)
    except TypeError:
        return st.form_submit_button(label, use_container_width=True, **kwargs)


def st_dataframe_stretch(df, **kwargs):
    kwargs.pop("use_container_width", None)
    try:
        return st.dataframe(df, width="stretch", **kwargs)
    except TypeError:
        return st.dataframe(df, use_container_width=True, **kwargs)


@st.dialog("📷 Verified Trade Execution Proof", width="large")
def show_screenshot_modal(title_text: str, img_source: str, file_bytes: bytes = None, filename: str = "trade_proof.jpeg"):
    st.markdown(f"""
    <div style="background: #0B1120; border: 1px solid #1E293B; border-radius: 8px; padding: 12px; margin-bottom: 12px;">
        <h4 style="margin: 0; color: #38BDF8; font-size: 1.1rem; font-weight: 800;">{title_text}</h4>
        <p style="margin: 4px 0 0 0; color: #94A3B8; font-size: 0.8rem;">Groww Broker Order Execution & Trade Proof Verification</p>
    </div>
    """, unsafe_allow_html=True)
    st.image(img_source, caption=title_text, use_container_width=True)
    m_c1, m_c2 = st.columns(2)
    with m_c1:
        if file_bytes:
            st.download_button(
                label="📥 Download Screenshot File",
                data=file_bytes,
                file_name=filename,
                mime="image/jpeg",
                use_container_width=True
            )
    with m_c2:
        if st.button("✖️ Close Dialog", key=f"close_dialog_{filename}", use_container_width=True):
            st.rerun()
