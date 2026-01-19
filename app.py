import streamlit as st
import pandas as pd
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build

# =====================
# 基本設定
# =====================
st.set_page_config(page_title="楽譜検索", layout="wide")

DRIVE_FOLDER_ID = "1c0JC6zLnipbJcP-2Dfe0QxXNQikSo3hm"

# =====================
# 定義
# =====================
TYPE_MAP = {
    "A": "オリジナル（伴奏有）",
    "B": "オリジナル（無伴奏）",
    "C": "アレンジ",
    "D": "特殊"
}

PART_MAP = {
    "G": "混声",
    "F": "女声",
    "M": "男声",
    "U": "斉唱"
}

PART_ORDER = ["混声", "女声", "男声", "斉唱"]

# 🎨 声部カラー（最新版）
PART_COLOR = {
    "混声": "#16a34a",   # 緑
    "女声": "#db2777",   # ピンク
    "男声": "#2563eb",   # 青
    "斉唱": "#9333ea"    # 紫
}

# =====================
# Google Drive 接続
# =====================
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=["https://www.googleapis.com/auth/drive.readonly"],
)
drive = build("drive", "v3", credentials=credentials)

# =====================
# Drive 読み込み（リアルタイム）
# =====================
def load_drive_files():
    res = drive.files().list(
        q=f"'{DRIVE_FOLDER_ID}' in parents and trashed=false and mimeType='application/pdf'",
        fields="files(id,name)"
    ).execute()

    rows = []

    for f in res.get("files", []):
        m = re.match(
            r"^(\d{2})(.+?)-([ABCD])([GFMU])([234]?)(.+)\.pdf$",
            f["name"]
        )
        if not m:
            continue

        _, title, t, p, num, composer = m.groups()
        composer = re.sub(r"[★☆]", "", composer).strip()

        part_base = PART_MAP[p]
        part = "斉唱" if p == "U" else f"{part_base}{num}部"

        rows.append({
            "曲名": title.strip(),
            "作曲者": composer,
            "声部": part,
            "声部種別": part_base,
            "区分": TYPE_MAP[t],
            "url": f"https://drive.google.com/file/d/{f['id']}/view"
        })

    return pd.DataFrame(
        rows,
        columns=["曲名", "作曲者", "声部", "声部種別", "区分", "url"]
    )

df = load_drive_files()

# =====================
# 検索UI
# =====================
st.markdown("### 🔍 検索条件")

col1, col2, col3, col4 = st.columns([2, 2, 3, 3])

with col1:
    keyword = st.text_input("曲名", "")

with col2:
    composers = sorted(df["作曲者"].dropna().unique())
    composer_input = st.selectbox("作曲者", ["指定しない"] + composers)

with col3:
    st.markdown("**声部**")
    part_inputs = []
    existing_parts = [
        p for p in PART_ORDER
        if p in df["声部種別"].unique()
    ]
    cols = st.columns(len(existing_parts))
    for c, p in zip(cols, existing_parts):
        with c:
            if st.checkbox(p, value=True):
                part_inputs.append(p)

with col4:
    st.markdown("**区分**")
    cat_inputs = []
    categories = sorted(df["区分"].dropna().unique())
    cols = st.columns(len(categories))
    for c, k in zip(cols, categories):
        with c:
            if st.checkbox(k, value=True):
                cat_inputs.append(k)

# =====================
# フィルタ処理
# =====================
filtered = df.copy()

if keyword:
    filtered = filtered[filtered["曲名"].str.contains(keyword, case=False)]

if composer_input != "指定しない":
    filtered = filtered[filtered["作曲者"] == composer_input]

if part_inputs:
    filtered = filtered[filtered["声部種別"].isin(part_inputs)]

if cat_inputs:
    filtered = filtered[filtered["区分"].isin(cat_inputs)]

# =====================
# 検索結果
# =====================
st.markdown(f"### 📄 検索結果（{len(filtered)} 件）")

cols = st.columns(3)

for i, (_, r) in enumerate(filtered.iterrows()):
    with cols[i % 3]:
        color = PART_COLOR.get(r["声部種別"], "#999999")

        st.markdown(
            f"""
            <div style="
                border-left:6px solid {color};
                padding:16px;
                border-radius:12px;
                background:#f8fafc;
                height:220px;
                display:flex;
                flex-direction:column;
                justify-content:space-between;
            ">
                <div>
                    <div style="font-size:16px;font-weight:700;color:#000;">
                        {r['曲名']}
                    </div>
                    <div style="font-size:13px;color:#000;">
                        {r['作曲者']}
                    </div>
                    <div style="margin-top:6px;font-weight:600;color:{color};">
                        {r['声部']}
                    </div>
                    <div style="font-size:12px;color:#000;">
                        {r['区分']}
                    </div>
                </div>

                <a href="{r['url']}" target="_blank"
                   style="
                   display:block;
                   text-align:center;
                   padding:10px;
                   border-radius:8px;
                   background:#2563eb;
                   color:white;
                   text-decoration:none;
                   font-weight:600;
                   ">
                   楽譜を開く
                </a>
            </div>
            """,
            unsafe_allow_html=True
        )
