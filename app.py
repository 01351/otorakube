import streamlit as st
import pandas as pd
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build

# =====================
# 基本設定
# =====================
st.set_page_config(
    page_title="楽譜検索",
    layout="wide"
)

DRIVE_FOLDER_ID = "1c0JC6zLnipbJcP-2Dfe0QxXNQikSo3hm"

# =====================
# Google Drive 接続
# =====================
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=["https://www.googleapis.com/auth/drive.readonly"],
)

drive_service = build("drive", "v3", credentials=credentials)

# =====================
# Drive からファイル取得（リアルタイム）
# =====================
def fetch_drive_files():
    results = drive_service.files().list(
        q=f"'{DRIVE_FOLDER_ID}' in parents and trashed=false and mimeType='application/pdf'",
        fields="files(id, name)"
    ).execute()

    rows = []

    for f in results.get("files", []):
        name = f["name"]

        # 命名規則：曲名__作曲者__声部__区分.pdf
        parts = name.replace(".pdf", "").split("__")
        if len(parts) < 4:
            continue

        title, composer, part, category = parts[:4]

        composer = re.sub(r"[★☆]", "", composer)

        if part.startswith("斉唱"):
            part_display = "斉唱"
            part_type = "斉唱"
        else:
            part_display = part
            part_type = re.sub(r"[二三四1234]部?", "", part)

        rows.append({
            "曲名": title,
            "作曲者": composer,
            "声部": part_display,
            "声部種別": part_type,
            "区分": category,
            "url": f"https://drive.google.com/file/d/{f['id']}/view"
        })

    return pd.DataFrame(
        rows,
        columns=["曲名", "作曲者", "声部", "声部種別", "区分", "url"]
    )

df = fetch_drive_files()

st.markdown("## 🛠 デバッグ情報（Drive 取得結果）")

st.write("総ファイル数:", len(df))

st.write("### カラム一覧")
st.write(df.columns.tolist())

st.write("### 声部（表示用）一覧")
st.write(df["声部"].value_counts(dropna=False))

st.write("### 声部種別（フィルタ用）一覧")
st.write(df["声部種別"].value_counts(dropna=False))

st.write("### 区分一覧")
st.write(df["区分"].value_counts(dropna=False))

st.write("### 作曲者一覧（上位20）")
st.write(df["作曲者"].value_counts().head(20))

st.write("### DataFrame 先頭10行")
st.dataframe(df.head(10), use_container_width=True)


# =====================
# 選択肢生成
# =====================
PART_ORDER = ["混声", "女声", "男声", "斉唱"]

existing_parts = [
    p for p in PART_ORDER
    if p in df["声部種別"].dropna().unique()
]

existing_categories = sorted(df["区分"].dropna().unique())
existing_composers = sorted(df["作曲者"].dropna().unique())

# =====================
# UI
# =====================
st.markdown("### 🔍 検索条件")

col1, col2, col3, col4 = st.columns([2, 2, 3, 3])

with col1:
    keyword = st.text_input("曲名", "")

with col2:
    composer_input = st.selectbox(
        "作曲者",
        ["指定しない"] + existing_composers
    )

with col3:
    st.markdown("**声部（複数選択可）**")
    part_inputs = []
    if existing_parts:
        part_cols = st.columns(len(existing_parts))
        for c, p in zip(part_cols, existing_parts):
            with c:
                if st.checkbox(p, value=True):
                    part_inputs.append(p)

with col4:
    st.markdown("**区分（複数選択可）**")
    cat_inputs = []
    if existing_categories:
        cat_cols = st.columns(len(existing_categories))
        for c, k in zip(cat_cols, existing_categories):
            with c:
                if st.checkbox(k, value=True):
                    cat_inputs.append(k)

# =====================
# フィルタ処理
# =====================
filtered = df.copy()

if keyword:
    filtered = filtered[
        filtered["曲名"].str.contains(keyword, case=False, na=False)
    ]

if composer_input != "指定しない":
    filtered = filtered[filtered["作曲者"] == composer_input]

if part_inputs:
    filtered = filtered[filtered["声部種別"].isin(part_inputs)]

if cat_inputs:
    filtered = filtered[filtered["区分"].isin(cat_inputs)]

# =====================
# 結果表示
# =====================
st.markdown(f"### 📄 検索結果（{len(filtered)} 件）")

PART_COLOR = {
    "混声": "#2563eb",   # 青
    "女声": "#db2777",   # ピンク
    "男声": "#16a34a",   # 緑
    "斉唱": "#9333ea"    # 紫
}

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
                height:240px;
                display:flex;
                flex-direction:column;
                justify-content:space-between;
            ">
                <div>
                    <div style="font-size:16px;font-weight:700;color:#000;min-height:48px;">
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
