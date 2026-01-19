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

st.title("🎼 楽譜管理アプリ")

st.caption(
    "Google Drive 上の楽譜PDFを、題名・作曲者・声部・区分で検索できます"
)

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

# =========================
# ファイル名解析
# =========================

def parse_filename(filename):
    """
    新命名規則対応
    例:
    11AveMaria-AG4Bach★.pdf
    12Song-UCComposer.pdf
    """
    pattern = r"^(\d{2})(.+?)-([ABCD])([GFMU])([234]?)(.+)\.pdf$"
    m = re.match(pattern, filename)
    if not m:
        return None

    code, title, t, p, n, composer = m.groups()
    composer = composer.replace("★", "").strip()

    work_type = TYPE_MAP[t]

    if p == "U":
        part = "斉唱"
    else:
        part = f"{PART_BASE_MAP[p]}{NUM_MAP.get(n, '')}"

    return {
        "code": code,
        "title": title.strip(),
        "composer": composer,
        "part": part,
        "type": work_type
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
# 検索UI
# =========================

st.divider()
st.subheader("🔍 検索")

# 題名
title_input = st.text_input("題名（部分一致）", placeholder="Ave Maria など")

# 作曲者
composer_list = sorted(df["composer"].dropna().unique().tolist())
composer_input = st.selectbox(
    "作曲者",
    ["指定しない"] + composer_list
)

# 声部（横一列）
st.markdown("**声部**")
existing_parts = sorted(
    df["part"].dropna().unique().tolist(),
    key=lambda x: PART_ORDER.index(re.sub(r"(二部|三部|四部)", "", x))
)

part_cols = st.columns(len(existing_parts))
part_checks = {}

for col, part in zip(part_cols, existing_parts):
    with col:
        part_checks[part] = st.checkbox(part, value=True)

# 区分（横一列）
st.markdown("**区分**")
type_cols = st.columns(len(TYPE_MAP))
type_checks = {}

for col, t in zip(type_cols, TYPE_MAP.values()):
    with col:
        type_checks[t] = st.checkbox(t, value=True)

# =========================
# 検索処理
# =========================

filtered_df = df.copy()

if title_input:
    filtered_df = filtered_df[
        filtered_df["title"].str.contains(title_input, case=False, na=False)
    ]

if composer_input != "指定しない":
    filtered_df = filtered_df[
        filtered_df["composer"] == composer_input
    ]

selected_parts = [p for p, v in part_checks.items() if v]
filtered_df = filtered_df[filtered_df["part"].isin(selected_parts)]

selected_types = [t for t, v in type_checks.items() if v]
filtered_df = filtered_df[filtered_df["type"].isin(selected_types)]

# =========================
# 検索結果
# =========================

st.divider()
st.subheader("📄 検索結果")

if filtered_df.empty:
    st.info("該当する楽譜がありません")
else:
    st.dataframe(
        filtered_df.drop(columns=["code"]),
        use_container_width=True,
        column_config={
            "url": st.column_config.LinkColumn("楽譜", display_text="開く")
        }
    )
