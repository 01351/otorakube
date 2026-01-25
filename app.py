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
# =========================
# Part 2
# タブUI & 検索UI
# =========================

# ※ Part1 で生成された以下を使う前提
# folder_df_map : dict[str, DataFrame]
# df_all_scores : DataFrame

st.subheader("🔍 楽譜検索")

# =========================
# 検索UI（共通）
# =========================

col1, col2, col3, col4 = st.columns(4)

with col1:
    keyword_title = st.text_input("曲名")

with col2:
    keyword_composer = st.text_input("作曲・編曲者")

with col3:
    part_filter = st.selectbox(
        "声部",
        ["すべて"] + sorted(df_all_scores["声部"].dropna().unique().tolist())
        if not df_all_scores.empty else ["すべて"]
    )

with col4:
    type_filter = st.selectbox(
        "区分",
        ["すべて"] + sorted(df_all_scores["区分"].dropna().unique().tolist())
        if not df_all_scores.empty else ["すべて"]
    )

# =========================
# 検索処理関数（共通）
# =========================

def apply_filter(df):
    if df.empty:
        return df

    filtered = df.copy()

    if keyword_title:
        filtered = filtered[
            filtered["曲名"].str.contains(keyword_title, case=False, na=False)
        ]

    if keyword_composer:
        filtered = filtered[
            filtered["作曲・編曲者"].str.contains(keyword_composer, case=False, na=False)
        ]

    if part_filter != "すべて":
        filtered = filtered[filtered["声部"] == part_filter]

    if type_filter != "すべて":
        filtered = filtered[filtered["区分"] == type_filter]

    return filtered

# =========================
# タブ構成
# =========================

tab_names = ["すべての楽譜"] + list(folder_df_map.keys())
tabs = st.tabs(tab_names)

# =========================
# すべての楽譜 タブ
# =========================

with tabs[0]:
    st.markdown("### 📚 すべての楽譜")

    df_filtered = apply_filter(df_all_scores)

    st.caption(f"{len(df_filtered)} 件")

    if df_filtered.empty:
        st.info("該当する楽譜がありません")
    else:
        st.dataframe(
            df_filtered[["曲名", "作曲・編曲者", "声部", "区分"]],
            use_container_width=True,
            hide_index=True
        )

# =========================
# 各子フォルダタブ
# =========================

for i, folder_name in enumerate(folder_df_map.keys(), start=1):
    with tabs[i]:
        st.markdown(f"### 📁 {folder_name}")

        df_folder = folder_df_map[folder_name]
        df_filtered = apply_filter(df_folder)

        st.caption(f"{len(df_filtered)} 件")

        if df_filtered.empty:
            st.info("このフォルダに該当する楽譜はありません")
        else:
            st.dataframe(
                df_filtered[["曲名", "作曲・編曲者", "声部", "区分"]],
                use_container_width=True,
                hide_index=True
            )
# =========================
# Part 3
# カードUI表示
# =========================

def render_cards(df):
    if df.empty:
        st.info("該当する楽譜がありません")
        return

    cards_per_row = 3
    rows = [
        df.iloc[i:i + cards_per_row]
        for i in range(0, len(df), cards_per_row)
    ]

    for row_df in rows:
        cols = st.columns(cards_per_row)

        for i in range(cards_per_row):
            if i >= len(row_df):
                with cols[i]:
                    st.empty()
                continue

            r = row_df.iloc[i]

            base_part = re.sub(r"(二部|三部|四部)", "", r["声部"])
            color = PART_COLOR.get(base_part, "#64748b")

            with cols[i]:
                st.markdown(
f"""
<div style="
border-left:8px solid {color};
padding:14px;
border-radius:14px;
background:#ffffff;
height:270px;
display:grid;
grid-template-rows:72px 1fr;
row-gap:8px;
margin-bottom:24px;
box-shadow:0 8px 20px rgba(0,0,0,0.06);
color:{TEXT_COLOR};
">

<h3 style="
margin:0;
font-size:20px;
font-weight:700;
line-height:1.25;
display:-webkit-box;
-webkit-line-clamp:2;
-webkit-box-orient:vertical;
overflow:hidden;
">
{r['曲名']}
</h3>

<div>
<p style="margin:0 0 6px 0;">作曲・編曲者：{r['作曲・編曲者']}</p>

<p style="margin:0 0 6px 0;">
声部：
<span style="color:{color}; font-weight:600;">
{r['声部']}
</span>
</p>

<span style="
display:inline-block;
padding:4px 10px;
border-radius:999px;
background:#f1f5f9;
font-size:13px;
margin-bottom:8px;
">
{r['区分']}
</span>

<a href="{r['url']}" target="_blank"
style="
display:block;
margin-top:10px;
text-align:center;
padding:10px;
border-radius:10px;
background:#6366f1;
color:#ffffff;
text-decoration:none;
font-weight:700;
">
📄 楽譜を開く
</a>
</div>
</div>
""",
                    unsafe_allow_html=True
                )

# =========================
# タブごとのカード表示
# =========================

# tabs, apply_filter, folder_df_map, df_all_scores は Part2 のものを使用

with tabs[0]:
    st.markdown("### 📚 すべての楽譜")
    df_filtered = apply_filter(df_all_scores)
    st.caption(f"{len(df_filtered)} 件")
    render_cards(df_filtered)

for i, folder_name in enumerate(folder_df_map.keys(), start=1):
    with tabs[i]:
        st.markdown(f"### 📁 {folder_name}")
        df_filtered = apply_filter(folder_df_map[folder_name])
        st.caption(f"{len(df_filtered)} 件")
        render_cards(df_filtered)
