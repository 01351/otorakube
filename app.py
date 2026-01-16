import streamlit as st
import pandas as pd
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build

# =========================
# 基本設定
# =========================
st.set_page_config(
    page_title="楽譜管理アプリ（Google Drive連携）",
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
    pattern = r"^(\d{2})(.+?)-([ABCD])([GFMU])([234]?)(.+)\.pdf$"
    match = re.match(pattern, filename)
    if not match:
        return None

    code, title, x, y, z, composer = match.groups()
    composer = composer.replace("★", "").strip()  # ★削除

    work_type = TYPE_MAP[x]
    if y == "U":
        part = "斉唱"
    else:
        part = f"{PART_BASE_MAP[y]}{NUM_MAP[z]}"

    return {
        "code": code,
        "title": title.strip(),
        "composer": composer,
        "part": part,
        "type": work_type
    }

# =========================
# Google Drive 読み込み（リアルタイム）
# =========================
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
    errors = []

    for f in results.get("files", []):
        parsed = parse_filename(f["name"])
        if parsed:
            rows.append({**parsed, "url": f["webViewLink"]})
        else:
            errors.append(f["name"])

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("code")

    return df, errors

df, error_files = load_from_drive()

# =========================
# 検索UI
# =========================
st.subheader("🔍 検索条件")

# 作曲者リスト
composer_list = sorted(df["composer"].dropna().unique().tolist())

# 存在する声部・区分のみ
existing_parts = sorted(df["part"].dropna().unique().tolist(),
                        key=lambda x: PART_ORDER.index(re.sub(r"[234]", "", x)))
existing_types = sorted(df["type"].dropna().unique().tolist())

# -------------------------
# 入力順: 題名 → 作曲者 → 声部 → 区分
# -------------------------
title_input = st.text_input("題名（部分一致）")

composer_input = st.selectbox("作曲者", ["指定しない"] + composer_list)

# 横一列チェックボックス（声部）
st.markdown("**声部**")
part_inputs = []
if existing_parts:
    part_cols = st.columns(len(existing_parts))
    for i, p in enumerate(existing_parts):
        if part_cols[i].checkbox(p, value=True, key=f"part_{p}"):
            part_inputs.append(p)

# 横一列チェックボックス（区分）
st.markdown("**区分**")
type_inputs = []
if existing_types:
    type_cols = st.columns(len(existing_types))
    for i, t in enumerate(existing_types):
        if type_cols[i].checkbox(t, value=True, key=f"type_{t}"):
            type_inputs.append(t)

# =========================
# 検索処理
# =========================
filtered_df = df.copy()

if title_input:
    filtered_df = filtered_df[
        filtered_df["title"].str.contains(title_input, case=False, na=False)
    ]

if composer_input != "指定しない":
    filtered_df = filtered_df[filtered_df["composer"] == composer_input]

if part_inputs:
    filtered_df = filtered_df[filtered_df["part"].isin(part_inputs)]

if type_inputs:
    filtered_df = filtered_df[filtered_df["type"].isin(type_inputs)]

# =========================
# 検索結果表示
# =========================
st.subheader("📄 検索結果")

if filtered_df.empty:
    st.warning("該当する楽譜が見つかりませんでした。")
else:
    st.dataframe(
        filtered_df.drop(columns=["code"]),
        use_container_width=True,
        column_config={
            "url": st.column_config.LinkColumn("楽譜リンク", display_text="開く")
        },
        hide_index=True
    )

# =========================
# ファイル名エラー表示
# =========================
if error_files:
    with st.expander("⚠ ファイル名ルールに合っていないPDF"):
        for name in error_files:
            st.write(f"- {name}")
