import os
import requests
import streamlit as st

st.set_page_config(page_title="KW Categorizer", layout="wide")

st.title("Keyword Categorizer (Bucket-first + GPT fallback)")
st.caption("Upload a CSV/XLSX → get back an Excel with bucket, intent, stage, negatives, and summaries.")

# ---- Config ----
DEFAULT_API_BASE = os.environ.get("API_BASE_URL", "").strip()  # e.g., https://kw-categorizer.onrender.com
api_base = st.text_input(
    "FastAPI base URL (Render)",
    value=DEFAULT_API_BASE or "https://YOUR-FASTAPI-SERVICE.onrender.com",
    help="This should be the Render URL where FastAPI is deployed."
).rstrip("/")

col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    gpt_fallback = st.toggle("Enable GPT fallback", value=True)
with col2:
    gpt_batch_size = st.number_input("GPT batch size", min_value=20, max_value=200, value=80, step=10)
with col3:
    timeout_s = st.number_input("Request timeout (seconds)", min_value=30, max_value=900, value=300, step=30)

uploaded = st.file_uploader("Upload keyword file (.csv or .xlsx)", type=["csv", "xlsx"])

st.divider()

def ping_health(base_url: str):
    try:
        r = requests.get(f"{base_url}/health", timeout=10)
        return r.status_code == 200, (r.json() if r.headers.get("content-type","").startswith("application/json") else r.text)
    except Exception as e:
        return False, str(e)

if st.button("Test connection"):
    ok, info = ping_health(api_base)
    if ok:
        st.success(f"Connected ✅  {info}")
    else:
        st.error(f"Failed to connect ❌  {info}")

# ---- Run classification ----
if uploaded is not None:
    st.write("File:", uploaded.name, f"({uploaded.size/1024:.1f} KB)")

    run = st.button("Classify & Download Excel", type="primary")
    if run:
        if not api_base.startswith("http"):
            st.error("Please enter a valid FastAPI base URL (must start with http/https).")
            st.stop()

        endpoint = f"{api_base}/classify"
        params = {
            "gpt_fallback": "true" if gpt_fallback else "false",
            "gpt_batch_size": int(gpt_batch_size),
        }

        files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type or "application/octet-stream")}

        with st.spinner("Running classification..."):
            try:
                resp = requests.post(endpoint, params=params, files=files, timeout=int(timeout_s))
            except requests.Timeout:
                st.error("Timed out. Try disabling GPT fallback or increasing timeout.")
                st.stop()
            except Exception as e:
                st.error(f"Request failed: {e}")
                st.stop()

        if resp.status_code != 200:
            # FastAPI returns JSON error typically
            content_type = resp.headers.get("content-type", "")
            if "application/json" in content_type:
                st.error(resp.json())
            else:
                st.error(resp.text[:2000])
            st.stop()

        out_bytes = resp.content
        st.success("Done ✅ Your Excel is ready.")
        st.download_button(
            "Download categorized Excel",
            data=out_bytes,
            file_name="categorized_output.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

st.markdown("---")
st.caption(
    "Tip: For very large files (10k+ keywords), run once with GPT fallback OFF, then re-run only the unclassified rows with GPT fallback ON."
)
