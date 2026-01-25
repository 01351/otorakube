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
# 基本設定
# =========================

st.set_page_config(
    page_title="楽譜管理システム",
    layout="wide"
)

st.title("楽譜管理システム")
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

PART_COLOR = {
    "混声": "#16a34a",
    "女声": "#db2777",
    "男声": "#2563eb",
    "斉唱": "#9333ea"
}

TEXT_COLOR = "#0f172a"

# =========================
# ファイル名解析（※一切変更なし）
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
# Google Drive 接続
# =========================

@st.cache_data(ttl=60, show_spinner=False)
def get_drive_service():
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    return build("drive", "v3", credentials=credentials)

service = get_drive_service()

# =========================
# 子フォルダ一覧取得（何個でも対応）
# =========================

def get_child_folders(service, parent_id):
    res = service.files().list(
        q=f"'{parent_id}' in parents and trashed=false and mimeType='application/vnd.google-apps.folder'",
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()
    return res.get("files", [])

# =========================
# フォルダ内PDF取得
# =========================

def get_pdfs_in_folder(service, folder_id):
    res = service.files().list(
        q=f"'{folder_id}' in parents and trashed=false and mimeType='application/pdf'",
        fields="files(name, webViewLink)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()
    return res.get("files", [])

# =========================
# Drive 読み込み（子フォルダ対応・防御込み）
# =========================

@st.cache_data(ttl=60, show_spinner=False)
def load_from_drive_with_children():
    tabs_data = {}

    # すべての楽譜（全子フォルダ合算）
    all_rows = []

    child_folders = get_child_folders(service, FOLDER_ID)

    for folder in child_folders:
        folder_name = folder["name"]
        folder_id = folder["id"]

        rows = []
        pdfs = get_pdfs_in_folder(service, folder_id)

        for f in pdfs:
            parsed = parse_filename(f["name"])
            if parsed:
                rows.append({**parsed, "url": f["webViewLink"]})

        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("code")

        # 空でも列は保証
        if df.empty:
            df = pd.DataFrame(
                columns=["code", "曲名", "作曲・編曲者", "声部", "区分", "url"]
            )

        tabs_data[folder_name] = df
        all_rows.extend(rows)

    # 「すべての楽譜」タブ
    all_df = pd.DataFrame(all_rows)
    if not all_df.empty:
        all_df = all_df.sort_values("code")
    else:
        all_df = pd.DataFrame(
            columns=["code", "曲名", "作曲・編曲者", "声部", "区分", "url"]
        )

    tabs_data["すべての楽譜"] = all_df

    return tabs_data

tabs_data = load_from_drive_with_children()

# =========================
# タブ生成
# =========================

tab_labels = list(tabs_data.keys())
tabs = st.tabs(tab_labels)

# ====== ここから先は part2 ======
