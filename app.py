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

# DriveフォルダID
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

# =========================
# ファイル名解析
# =========================
def parse_filename(filename):
    """
    U(斉唱)は数字無視、一律斉唱
    """
    pattern = r"^(\d{2})(.+?)-([ABCD])([GFMU])([234]?)(.+)\.pdf$"
    match = re.match(pattern, filename)
    if not match:
        return None

    code, title, x, y, z, composer = match.groups()
    composer = composer.replace("★", "").strip()
    work_type = TYPE_MAP.get(x, "不明")

    if y == "U":
        part = "斉唱"
    else:
        part_number = NUM_MAP.get(z, "")
        part = f"{PART_BASE_MAP.get(y, '')}{part_number}"

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
@st.cache_data(show_spinner=False)
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

# 作曲者一覧（★除去済み・ユニーク）
composer_list = sorted(df["composer"].dropna().unique().tolist())

# 声部・区分一覧はデータに存在するもののみ
part_list = sorted(df["part"].dropna().unique().tolist())
type_list = sorted(df["type"].dropna().unique().tolist())

# ---- UI配置 ----
title_input = st.text_input("題名（部分一致）")

# 作曲者はプルダウン（単一選択）
composer_input = st.selectbox(
    "作曲者",
    options=["指定しない"] + composer_list
)

# 声部はチェックボックス横一列表示
st.write("声部")
cols = st.columns(len(part_list))
part_input = []
for i, part in enumerate(part_list):
    if cols[i].checkbox(part, value=True):
        part_input.append(part)

# 区分もチェックボックス横一列表示
st.write("区分")
cols = st.columns(len(type_list))
type_input = []
for i, t in enumerate(type_list):
    if cols[i].checkbox(t, value=True):
        type_input.append(t)

# =========================
# 検索処理
# =========================
filtered_df = df.copy()

if title_input:
    filtered_df = filtered_df[
        filtered_df["title"].str.contains(title_input, case=False, na=False)
    ]

if composer_input and composer_input != "指定しない":
    filtered_df = filtered_df[
        filtered_df["composer"] == composer_input
    ]

if part_input:
    filtered_df = filtered_df[
        filtered_df["part"].isin(part_input)
    ]

if type_input:
    filtered_df = filtered_df[
        filtered_df["type"].isin(type_input)
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
