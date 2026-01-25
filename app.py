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
# =========================
# 共通：検索UI
# =========================

with st.sidebar:
    st.subheader("🔍 検索条件")

    keyword = st.text_input("曲名キーワード", "")

    # 全タブ共通で使うため、列が存在する前提を守る
    all_df_for_filter = tabs_data["すべての楽譜"]

    composer_list = (
        sorted(all_df_for_filter["作曲・編曲者"].dropna().unique().tolist())
        if "作曲・編曲者" in all_df_for_filter.columns
        else []
    )
    composer = st.multiselect("作曲・編曲者", composer_list)

    part_list = (
        sorted(all_df_for_filter["声部"].dropna().unique().tolist())
        if "声部" in all_df_for_filter.columns
        else []
    )
    part = st.multiselect("声部", part_list)

    type_list = (
        sorted(all_df_for_filter["区分"].dropna().unique().tolist())
        if "区分" in all_df_for_filter.columns
        else []
    )
    score_type = st.multiselect("区分", type_list)

# =========================
# 検索関数
# =========================

def apply_filter(df):
    if df.empty:
        return df

    filtered = df.copy()

    if keyword:
        filtered = filtered[filtered["曲名"].str.contains(keyword, case=False, na=False)]

    if composer:
        filtered = filtered[filtered["作曲・編曲者"].isin(composer)]

    if part:
        filtered = filtered[filtered["声部"].isin(part)]

    if score_type:
        filtered = filtered[filtered["区分"].isin(score_type)]

    return filtered

# =========================
# カード表示
# =========================

def render_cards(df):
    if df.empty:
        st.info("該当する楽譜がありません")
        return

    cols = st.columns(4)

    for i, (_, row) in enumerate(df.iterrows()):
        with cols[i % 4]:
            color = PART_COLOR.get(row["声部"].replace("二部", "").replace("三部", "").replace("四部", ""), "#64748b")

            st.markdown(
                f"""
                <div style="
                    border:1px solid #e5e7eb;
                    border-radius:10px;
                    padding:12px;
                    margin-bottom:12px;
                ">
                    <div style="font-size:14px; color:#475569;">
                        {row["区分"]}
                    </div>
                    <div style="font-size:18px; font-weight:700; color:{TEXT_COLOR};">
                        {row["曲名"]}
                    </div>
                    <div style="margin-top:4px; font-size:14px;">
                        {row["作曲・編曲者"]}
                    </div>
                    <div style="
                        display:inline-block;
                        margin-top:6px;
                        padding:2px 8px;
                        border-radius:999px;
                        background:{color};
                        color:white;
                        font-size:12px;
                    ">
                        {row["声部"]}
                    </div>
                    <div style="margin-top:10px;">
                        <a href="{row["url"]}" target="_blank">📄 PDFを開く</a>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

# =========================
# タブごとの描画
# =========================

for tab, label in zip(tabs, tab_labels):
    with tab:
        df = tabs_data[label]
        filtered_df = apply_filter(df)
        render_cards(filtered_df)
