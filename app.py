import streamlit as st
import pandas as pd
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build

# =========================
# 基本設定
# =========================

st.set_page_config(
    page_title="楽譜管理アプリ（Google Drive）",
    layout="wide"
)

st.title("🎼 楽譜管理アプリ（Google Drive連携）")

st.write("""
Google Drive 上の楽譜PDFを  
**題名・作曲者・声部・区分**で検索できます。

📁 ファイル名形式  
`00題名-XYZ作曲者.pdf`
""")

# =========================
# Google Drive 設定
# =========================

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# 🔽 自分の Google Drive フォルダID
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

PART_OPTIONS = [
    "混声三部", "混声四部",
    "女声二部", "女声三部", "女声四部",
    "男声二部", "男声三部", "男声四部",
    "斉唱"
]

TYPE_OPTIONS = list(TYPE_MAP.values())

# =========================
# 作曲者名正規化（★を無視）
# =========================

def normalize_composer(name):
    if not isinstance(name, str):
        return ""

# ★ ☆ ＊ * ※ をすべて除去
    name = re.sub(r"[★☆＊*※]", "", name)

    return name.strip()

# =========================
# ファイル名解析
# =========================

def parse_filename(filename):
    """
    例:
    11AveMaria-AG4Bach.pdf
    """
    pattern = r"^(\d{2})(.+?)-([ABCD])([GFMU])([234])(.+)\.pdf$"
    match = re.match(pattern, filename)

    if not match:
        return None

    code, title, x, y, z, composer = match.groups()

    # 混声二部は存在しない
    if y == "G" and z == "2":
        return None

    work_type = TYPE_MAP[x]

    if y == "U":
        part = "斉唱"
    else:
        part = f"{PART_BASE_MAP[y]}{NUM_MAP[z]}"

    composer_clean = normalize_composer(composer)

    return {
        "code": code,                 # 並び順専用（非表示）
        "title": title.strip(),
        "composer": composer_clean,   # ★除去後
        "part": part,
        "type": work_type
    }

# =========================
# Google Drive 読み込み
# =========================

@st.cache_data(show_spinner=False)
def load_from_drive():

df, error_files = load_from_drive()

# =========================
# 検索UI
# =========================

st.subheader("🔍 検索条件")

# 作曲者一覧（★除去後・ユニーク）
composer_list = sorted(df["composer"].dropna().unique().tolist())

col1, col2, col3, col4 = st.columns(4)

with col1:
    title_input = st.text_input("題名（部分一致）")

with col2:
    composer_input = st.selectbox(
        "作曲者",
        [""] + composer_list
    )

with col3:
    part_inputs = st.multiselect(
        "声部（複数選択可）",
        PART_OPTIONS
    )

with col4:
    type_input = st.selectbox(
        "区分",
        [""] + TYPE_OPTIONS
    )

# =========================
# 検索処理
# =========================

filtered_df = df.copy()

if title_input:
    filtered_df = filtered_df[
        filtered_df["title"].str.contains(title_input, case=False, na=False)
    ]

if composer_input:
    filtered_df = filtered_df[
        filtered_df["composer"] == composer_input
    ]

if part_inputs:
    filtered_df = filtered_df[
        filtered_df["part"].isin(part_inputs)
    ]

if type_input:
    filtered_df = filtered_df[
        filtered_df["type"] == type_input
    ]

# =========================
# 検索結果表示
# =========================

st.subheader("📄 検索結果")
st.write(f"🔎 {len(filtered_df)} 件")

if filtered_df.empty:
    st.warning("該当する楽譜が見つかりませんでした。")
else:
    st.dataframe(
        filtered_df.drop(columns=["code"]),
        use_container_width=True,
        column_config={
            "url": st.column_config.LinkColumn(
                "楽譜リンク",
                display_text="開く"
            )
        }
    )

# =========================
# ファイル名エラー表示
# =========================

if error_files:
    with st.expander("⚠ ファイル名ルールに合っていないPDF"):
        for name in error_files:
            st.write(f"- {name}")
