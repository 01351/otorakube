import streamlit as st
import pandas as pd
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build

# =========================
# 基本設定
# =========================

st.set_page_config(
    page_title="楽譜管理アプリ",
    layout="wide"
)

st.title("楽譜管理アプリ")
st.caption("Google Drive 上の楽譜PDFを検索できます")

# =========================
# Google Drive 設定
# =========================

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
FOLDER_ID = "1c0JC6zLnipbJcP-2Dfe0QxXNQikSo3hm"

# =========================
# 定義マップ
# =========================

TYPE_MAP = {
    "A": "オリジナル（伴奏有）",
    "B": "オリジナル（無伴奏）",
    "C": "アレンジ",
    "D": "特殊"
}

PART_BASE_MAP = {
    "G": "混声",
    "F": "女声",
    "M": "男声",
    "U": "斉唱"
}

NUM_MAP = {
    "2": "二部",
    "3": "三部",
    "4": "四部"
}

PART_ORDER = ["混声", "女声", "男声", "斉唱"]

PART_COLOR = {
    "混声": "#16a34a",
    "女声": "#db2777",
    "男声": "#2563eb",
    "斉唱": "#9333ea"
}

TEXT_COLOR = "#0f172a"

# =========================
# ファイル名解析
# =========================

def parse_filename(filename):
    pattern = r"^(\d{2})(.+?)-([ABCD])([GFMU])([234]?)(.+)\.pdf$"
    m = re.match(pattern, filename)
    if not m:
        return None

    code, title, t, p, n, composer = m.groups()
    composer = composer.replace("★", "").strip()

    if p == "U":
        part = "斉唱"
    else:
        part = f"{PART_BASE_MAP[p]}{NUM_MAP.get(n, '')}"

    return {
        "code": code,
        "曲名": title.strip(),
        "作曲者": composer,
        "声部": part,
        "区分": TYPE_MAP[t]
    }

# =========================
# Google Drive 読み込み
# =========================

@st.cache_data(ttl=60, show_spinner=False)
def load_from_drive():
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )

    service = build("drive", "v3", credentials=credentials)

    results = service.files().list(
        q=f"'{FOLDER_ID}' in parents and trashed=false and mimeType='application/pdf'",
        fields="files(name, webViewLink)"
    ).execute()

    rows = []
    for f in results.get("files", []):
        parsed = parse_filename(f["name"])
        if parsed:
            rows.append({**parsed, "url": f["webViewLink"]})

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("code")

    return df

df = load_from_drive()

# =========================
# 検索結果
# =========================

st.divider()
st.subheader("検索結果")
st.write(f"{len(df)} 件")

# =========================
# カード表示（幅固定・色統一版）
# =========================

cards_per_row = 3
rows = [
    df.iloc[i:i + cards_per_row]
    for i in range(0, len(df), cards_per_row)
]

for row_df in rows:
    cols = st.columns(cards_per_row)

    for i in range(cards_per_row):
        if i >= len(row_df):
            with cols[i]:
                st.empty()
            continue

        r = row_df.iloc[i]
        base_part = re.sub(r"(二部|三部|四部)", "", r["声部"])
        color = PART_COLOR.get(base_part, "#64748b")

        with cols[i]:
            st.markdown(
f"""
<div style="
border-left:8px solid {color};
padding:14px;
border-radius:12px;
background:#ffffff;
height:260px;
display:grid;
grid-template-rows:64px 1fr;
row-gap:6px;
margin-bottom:24px;
color:{TEXT_COLOR};
">

<h3 style="
margin:0;
font-size:20px;
font-weight:700;
line-height:1.2;
overflow:hidden;
">
{r['曲名']}
</h3>

<div style="display:flex;flex-direction:column;">

<p style="font-size:16px;margin:0 0 6px 0;">
作曲者：{r['作曲者']}
</p>

<p style="margin:0 0 6px 0;font-size:16px;">
声　部：
<span style="color:{color};">
{r['声部']}
</span>
</p>

<span style="
align-self:flex-start;
padding:3px 9px;
border-radius:999px;
background:#f1f5f9;
font-size:13px;
">
{r['区分']}
</span>

<a href="{r['url']}" target="_blank"
style="
display:block;
width:90%;
margin:14px auto 0 auto;
text-align:center;
padding:9px;
border-radius:8px;
background:#e5e7eb;
color:{TEXT_COLOR};
text-decoration:none;
font-weight:600;
"
onmousedown="this.style.background='#c7d2fe'"
onmouseup="this.style.background='#e5e7eb'"
>
楽譜を開く
</a>

</div>
</div>
""",
unsafe_allow_html=True
            )
