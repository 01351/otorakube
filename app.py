#区分もDriveのファイル情報から直接読み取れるように　確認
#Driveにファイルがないときは0件と表示できるように　確認
#区分がPの場合、区分名は「ピアノ」で声部は「なし」命名規則も声部は飛ばして作曲者を読みとる
#作曲者はサイト内にふりがなの入力リストを作って、新規の作曲者も追加できるように
#検索の作曲者は五十音順に並び替え、リストにない作曲者は上に表示

# =========================
# Part 1
# Drive 構造取得 & データ構築
# =========================

import streamlit as st
import pandas as pd
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build

# =========================
# 定数（既存コードと同じ）
# =========================

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

ROOT_FOLDER_ID = "1c0JC6zLnipbJcP-2Dfe0QxXNQikSo3hm"

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
# ファイル名解析（既存ロジック）
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
        "作曲・編曲者": composer,
        "声部": part,
        "区分": TYPE_MAP.get(t, "不明")
    }

# =========================
# Google Drive Service
# =========================

@st.cache_data(ttl=300)
def get_drive_service():
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    return build("drive", "v3", credentials=credentials)

service = get_drive_service()

# =========================
# 子フォルダ取得（可変対応）
# =========================

@st.cache_data(ttl=300)
def get_child_folders(root_folder_id):
    query = (
        f"'{root_folder_id}' in parents and "
        "mimeType = 'application/vnd.google-apps.folder' and "
        "trashed = false"
    )

    res = service.files().list(
        q=query,
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()

    return res.get("files", [])

# =========================
# フォルダ内PDF取得
# =========================

def load_pdfs_from_folder(folder_id):
    query = (
        f"'{folder_id}' in parents and "
        "mimeType='application/pdf' and "
        "trashed = false"
    )

    res = service.files().list(
        q=query,
        fields="files(id, name, webViewLink)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()

    rows = []

    for f in res.get("files", []):
        parsed = parse_filename(f["name"])
        if parsed:
            rows.append({
                **parsed,
                "url": f["webViewLink"]
            })

    df = pd.DataFrame(rows)

    if not df.empty:
        df = df.sort_values("code")

    return df

# =========================
# 全フォルダ分のDataFrame構築
# =========================

@st.cache_data(ttl=300)
def build_folder_dataframe_map():
    folder_map = {}

    child_folders = get_child_folders(ROOT_FOLDER_ID)

    all_dfs = []

    for folder in child_folders:
        folder_id = folder["id"]
        folder_name = folder["name"]

        df = load_pdfs_from_folder(folder_id)

        folder_map[folder_name] = df

        if not df.empty:
            all_dfs.append(df)

    # 「すべての楽譜」用
    if all_dfs:
        df_all = pd.concat(all_dfs, ignore_index=True)
        df_all = df_all.sort_values("code")
    else:
        df_all = pd.DataFrame()

    return folder_map, df_all

# =========================
# 実行
# =========================

folder_df_map, df_all_scores = build_folder_dataframe_map()

# folder_df_map:
# {
#   "フォルダA": DataFrame,
#   "フォルダB": DataFrame,
#   ...
# }
#
# df_all_scores:
#   全フォルダ横断 DataFrame
