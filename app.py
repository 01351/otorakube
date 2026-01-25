#区分もDriveのファイル情報から直接読み取れるように　確認
#Driveにファイルがないときは0件と表示できるように　確認
#区分がPの場合、区分名は「ピアノ」で声部は「なし」命名規則も声部は飛ばして作曲者を読みとる
#作曲者はサイト内にふりがなの入力リストを作って、新規の作曲者も追加できるように
#検索の作曲者は五十音順に並び替え、リストにない作曲者は上に表示

# ==================================================
# 楽譜管理アプリ（Google Drive / 子フォルダ対応）
# KeyError対策・全文表示・堅牢版
# ==================================================

import streamlit as st
import pandas as pd
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build
from typing import List, Dict

# ==================================================
# Streamlit 基本設定
# ==================================================

st.set_page_config(
    page_title="🎼 楽譜管理アプリ",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🎼 楽譜管理アプリ")
st.caption("Google Drive 上の楽譜PDFを検索できます（子フォルダ対応 / KeyError対策済）")

# ==================================================
# Google Drive API 設定
# ==================================================

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# 親フォルダID（楽譜をまとめているフォルダ）
PARENT_FOLDER_ID = "1c0JC6zLnipbJcP-2Dfe0QxXNQikSo3hm"

# ==================================================
# Google Drive API 初期化
# ==================================================

def init_drive_service():
    credentials = service_account.Credentials.from_service_account_file(
        "service_account.json",
        scopes=SCOPES
    )
    return build("drive", "v3", credentials=credentials)

service = init_drive_service()

# ==================================================
# Drive操作ユーティリティ
# ==================================================

def list_subfolders(parent_id: str) -> List[Dict]:
    """
    親フォルダ直下の子フォルダ一覧を取得
    """
    results = service.files().list(
        q=(
            f"'{parent_id}' in parents "
            "and mimeType='application/vnd.google-apps.folder' "
            "and trashed=false"
        ),
        fields="files(id, name)",
        pageSize=1000
    ).execute()

    return results.get("files", [])


def list_pdfs(folder_id: str) -> List[Dict]:
    """
    指定フォルダ内のPDFファイル一覧を取得
    """
    results = service.files().list(
        q=(
            f"'{folder_id}' in parents "
            "and mimeType='application/pdf' "
            "and trashed=false"
        ),
        fields="files(id, name, webViewLink)",
        pageSize=1000
    ).execute()

    return results.get("files", [])

# ==================================================
# ファイル名解析ロジック
# ==================================================

def parse_filename(filename: str) -> Dict:
    """
    ファイル名を解析して情報を抽出
    想定形式：
      作曲者_曲名_声部.pdf
      作曲者＿曲名＿声部.pdf（全角対応）
    """

    name = filename.replace(".pdf", "")

    # 半角・全角アンダースコア両対応
    parts = re.split(r"[_＿]", name)

    composer = parts[0] if len(parts) >= 1 else ""
    title = parts[1] if len(parts) >= 2 else ""
    part = parts[2] if len(parts) >= 3 else ""

    return {
        "作曲・編曲者": composer.strip(),
        "曲名": title.strip(),
        "声部": part.strip(),
        "ファイル名": filename
    }

# ==================================================
# データロード（子フォルダ対応）
# ==================================================

@st.cache_data(show_spinner=True)
def load_scores() -> pd.DataFrame:
    records: List[Dict] = []

    subfolders = list_subfolders(PARENT_FOLDER_ID)

    for folder in subfolders:
        folder_id = folder.get("id")
        folder_name = folder.get("name")

        pdf_files = list_pdfs(folder_id)

        for pdf in pdf_files:
            parsed = parse_filename(pdf.get("name", ""))

            parsed.update({
                "フォルダ名": folder_name,
                "Driveリンク": pdf.get("webViewLink", "")
            })

            records.append(parsed)

    # ★ ここが超重要：必ず列名を明示する
    columns = [
        "フォルダ名",
        "作曲・編曲者",
        "曲名",
        "声部",
        "ファイル名",
        "Driveリンク"
    ]

    df = pd.DataFrame(records, columns=columns)

    return df

# ==================================================
# データ読み込み実行
# ==================================================

df = load_scores()

# ==================================================
# 空データ対策
# ==================================================

if df.empty:
    st.warning("PDFが見つかりませんでした。フォルダ構成を確認してください。")
    st.stop()

# ==================================================
# カラム存在チェック（KeyError完全防止）
# ==================================================

REQUIRED_COLUMNS = [
    "フォルダ名",
    "作曲・編曲者",
    "曲名",
    "声部",
    "ファイル名",
    "Driveリンク"
]

missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]

if missing_cols:
    st.error(f"必要な列が存在しません: {missing_cols}")
    st.write("現在の列一覧:")
    st.write(df.columns.tolist())
    st.stop()

# ==================================================
# サイドバー：検索UI
# ==================================================

st.sidebar.header("🔎 検索条件")

# フォルダ絞り込み
folder_list = sorted(df["フォルダ名"].dropna().unique().tolist())
selected_folder = st.sidebar.selectbox(
    "📁 フォルダ",
    ["すべて"] + folder_list
)

# 作曲・編曲者（★KeyErrorが出ていた箇所）
composer_list = sorted(
    df["作曲・編曲者"].dropna().unique().tolist()
)

selected_composer = st.sidebar.selectbox(
    "🎵 作曲・編曲者",
    ["すべて"] + composer_list
)

# 声部
part_list = sorted(df["声部"].dropna().unique().tolist())
selected_part = st.sidebar.selectbox(
    "🎤 声部",
    ["すべて"] + part_list
)

# キーワード検索
keyword = st.sidebar.text_input("🔤 曲名キーワード")

# ==================================================
# フィルタ処理
# ==================================================

filtered_df = df.copy()

if selected_folder != "すべて":
    filtered_df = filtered_df[
        filtered_df["フォルダ名"] == selected_folder
    ]

if selected_composer != "すべて":
    filtered_df = filtered_df[
        filtered_df["作曲・編曲者"] == selected_composer
    ]

if selected_part != "すべて":
    filtered_df = filtered_df[
        filtered_df["声部"] == selected_part
    ]

if keyword:
    filtered_df = filtered_df[
        filtered_df["曲名"].str.contains(keyword, case=False, na=False)
    ]

# ==================================================
# 表示用整形
# ==================================================

# 表示順を整理
filtered_df = filtered_df[[
    "フォルダ名",
    "作曲・編曲者",
    "曲名",
    "声部",
    "ファイル名",
    "Driveリンク"
]]

# ==================================================
# 結果表示（全文表示）
# ==================================================

st.subheader(f"📄 検索結果：{len(filtered_df)} 件")

st.dataframe(
    filtered_df,
    use_container_width=True,
    hide_index=True
)

# ==================================================
# Driveリンク補助表示
# ==================================================

with st.expander("🔗 Driveで開く"):
    for _, row in filtered_df.iterrows():
        if row["Driveリンク"]:
            st.markdown(f"- [{row['ファイル名']}]({row['Driveリンク']})")

# ==================================================
# デバッグ用（必要なときだけON）
# ==================================================

if st.sidebar.checkbox("🛠 デバッグ表示"):
    st.write("### DataFrame 全体")
    st.write(df)
    st.write("### 列一覧")
    st.write(df.columns.tolist())
