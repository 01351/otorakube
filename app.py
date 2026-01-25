#区分もDriveのファイル情報から直接読み取れるように　確認
#Driveにファイルがないときは0件と表示できるように　確認
#区分がPの場合、区分名は「ピアノ」で声部は「なし」命名規則も声部は飛ばして作曲者を読みとる
#作曲者はサイト内にふりがなの入力リストを作って、新規の作曲者も追加できるように
#検索の作曲者は五十音順に並び替え、リストにない作曲者は上に表示

import streamlit as st
import pandas as pd
import re

from google.oauth2 import service_account
from googleapiclient.discovery import build

# =========================
# Streamlit 基本設定
# =========================
st.set_page_config(
    page_title="楽譜管理アプリ",
    layout="wide"
)

st.title("🎼 楽譜管理アプリ")
st.caption("Google Drive 上の楽譜PDFを検索できます（DEBUG付き）")

# =========================
# Google Drive 設定
# =========================
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

SERVICE_ACCOUNT_INFO = {
    # ここは既存の service account 情報をそのまま
}

ROOT_FOLDER_ID = "ここに親フォルダID"

credentials = service_account.Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO,
    scopes=SCOPES
)

service = build("drive", "v3", credentials=credentials)

# =========================
# ファイル名解析
# =========================
def parse_filename(filename: str):
    """
    想定例:
    曲名_作曲者_編曲者_SA.pdf
    """
    name = filename.replace(".pdf", "")
    parts = name.split("_")

    if len(parts) < 2:
        return None

    return {
        "曲名": parts[0],
        "作曲・編曲者": parts[1] if len(parts) > 1 else "",
        "声部": parts[2] if len(parts) > 2 else "",
        "ファイル名": filename,
    }

# =========================
# Google Drive から取得
# =========================
@st.cache_data(ttl=60)
def load_from_drive():
    rows = []

    query = (
        f"'{ROOT_FOLDER_ID}' in parents "
        "and mimeType='application/pdf' "
        "and trashed=false"
    )

    results = service.files().list(
        q=query,
        fields="files(id, name, webViewLink)",
        pageSize=1000,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()

    files = results.get("files", [])

    # ===== DEBUG =====
    st.subheader("🧪 DEBUG: Drive Files")
    st.write("取得ファイル数:", len(files))
    st.write(files)

    for f in files:
        parsed = parse_filename(f["name"])
        if parsed:
            rows.append({
                **parsed,
                "URL": f["webViewLink"]
            })

    # ===== DEBUG =====
    st.subheader("🧪 DEBUG: rows")
    st.write("rows 件数:", len(rows))
    st.write(rows)

    if not rows:
        st.error("⚠️ rows が空です。parse_filename が一致していません。")

    df = pd.DataFrame(rows)

    # ===== DEBUG =====
    st.subheader("🧪 DEBUG: DataFrame")
    st.write("df shape:", df.shape)
    st.write("df columns:", df.columns.tolist())
    st.dataframe(df)

    if df.empty:
        st.error("⚠️ DataFrame が空です。")

    return df

# =========================
# データ取得
# =========================
df = load_from_drive()

# =========================
# 検索 UI
# =========================
st.divider()
st.subheader("🔍 検索")

if df.empty:
    st.warning("表示できる楽譜がありません")
    st.stop()

title_keyword = st.text_input("曲名で検索")
composer_list = sorted(df["作曲・編曲者"].dropna().unique().tolist())
composer_filter = st.multiselect("作曲・編曲者", composer_list)

filtered_df = df.copy()

if title_keyword:
    filtered_df = filtered_df[
        filtered_df["曲名"].str.contains(title_keyword, case=False, na=False)
    ]

if composer_filter:
    filtered_df = filtered_df[
        filtered_df["作曲・編曲者"].isin(composer_filter)
    ]

# =========================
# 結果表示
# =========================
st.divider()
st.subheader("📄 検索結果")

st.write("表示件数:", len(filtered_df))

for _, row in filtered_df.iterrows():
    with st.container(border=True):
        st.markdown(f"### {row['曲名']}")
        st.write("作曲・編曲者:", row["作曲・編曲者"])
        st.write("声部:", row["声部"])
        st.link_button("📄 PDF を開く", row["URL"])
