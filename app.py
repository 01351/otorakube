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
# ファイル名解析（元コードそのまま）
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
# 【追加】子フォルダ一覧取得
# =========================

def get_child_folders(service, parent_id):
    results = service.files().list(
        q=f"'{parent_id}' in parents and trashed=false and mimeType='application/vnd.google-apps.folder'",
        fields="files(id, name)"
    ).execute()
    return results.get("files", [])

# =========================
# 【追加】指定フォルダ内PDF取得
# =========================

def load_pdfs_from_folder(service, folder_id):
    results = service.files().list(
        q=f"'{folder_id}' in parents and trashed=false and mimeType='application/pdf'",
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

# =========================
# 【追加】全フォルダ読み込み（タブ用データ）
# =========================

@st.cache_data(ttl=60, show_spinner=False)
def load_all_tabs_data():
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    service = build("drive", "v3", credentials=credentials)

    tabs_data = {}

    # すべての楽譜（親直下＋全子フォルダ）
    all_rows = []

    child_folders = get_child_folders(service, FOLDER_ID)

    for folder in child_folders:
        df = load_pdfs_from_folder(service, folder["id"])
        tabs_data[folder["name"]] = df
        if not df.empty:
            all_rows.append(df)

    if all_rows:
        tabs_data["すべての楽譜"] = pd.concat(all_rows).sort_values("code")
    else:
        tabs_data["すべての楽譜"] = pd.DataFrame()

    return tabs_data
# =========================
# 【追加】タブ生成
# =========================

tabs_data = load_all_tabs_data()
tab_labels = list(tabs_data.keys())

tabs = st.tabs(tab_labels)

# =========================
# タブごとに既存UI・検索・表示を適用
# =========================

for tab, tab_name in zip(tabs, tab_labels):
    with tab:
        df = tabs_data[tab_name].copy()

        if df.empty:
            st.info("このフォルダには該当する楽譜がありません")
            continue

        # =========================
        # 検索UI（元コードそのまま）
        # =========================

        st.divider()
        st.subheader("検索")

        col1, col2 = st.columns([2, 1])
        with col1:
            title_input = st.text_input(
                "🎵 曲名（部分一致）",
                key=f"title_{tab_name}"
            )
        with col2:
            composer_list = sorted(df["作曲・編曲者"].dropna().unique().tolist())
            composer_input = st.selectbox(
                "👤 作曲・編曲者",
                ["指定しない"] + composer_list,
                key=f"composer_{tab_name}"
            )

        st.caption("▼ 詳細条件")

        # =========================
        # 声部（チェックボックス）
        # =========================

        st.markdown("**声部**")

        existing_parts = sorted(
            df["声部"].dropna().unique().tolist(),
            key=part_sort_key
        )

        part_checks = {}
        for p in existing_parts:
            part_checks[p] = st.checkbox(
                p,
                value=True,
                key=f"part_{tab_name}_{p}"
            )

        PART_ORDER = {p: i for i, p in enumerate(existing_parts)}

        # =========================
        # 区分（チェックボックス）
        # =========================

        st.markdown("**区分**")
        type_labels = list(TYPE_MAP.values())

        type_checks = {}
        for t in type_labels:
            type_checks[t] = st.checkbox(
                t,
                value=True,
                key=f"type_{tab_name}_{t}"
            )

        TYPE_ORDER = {t: i for i, t in enumerate(type_labels)}

        # =========================
        # 並び替えUI
        # =========================

        st.divider()
        st.markdown("### 🔃 並び替え")

        sort_col1, sort_col2 = st.columns([3, 2])

        with sort_col1:
            sort_key = st.selectbox(
                "並び替え項目",
                ["曲名（五十音順）", "声部", "区分"],
                key=f"sortkey_{tab_name}"
            )

        with sort_col2:
            sort_order = st.radio(
                "順序",
                ["昇順", "降順"],
                horizontal=True,
                key=f"sortorder_{tab_name}"
            )

        # =========================
        # 検索処理（元コード準拠）
        # =========================

        filtered_df = df.copy()

        if title_input:
            filtered_df = filtered_df[
                filtered_df["曲名"].str.contains(title_input, case=False, na=False)
            ]

        if composer_input != "指定しない":
            filtered_df = filtered_df[
                filtered_df["作曲・編曲者"] == composer_input
            ]

        filtered_df = filtered_df[
            filtered_df["声部"].isin([p for p, v in part_checks.items() if v])
        ]

        filtered_df = filtered_df[
            filtered_df["区分"].isin([t for t, v in type_checks.items() if v])
        ]

        ascending = sort_order == "昇順"

        if sort_key == "曲名（五十音順）":
            filtered_df = filtered_df.sort_values("code", ascending=ascending)

        elif sort_key == "声部":
            filtered_df = (
                filtered_df
                .assign(_order=filtered_df["声部"].map(PART_ORDER))
                .sort_values("_order", ascending=ascending)
                .drop(columns="_order")
            )

        elif sort_key == "区分":
            filtered_df = (
                filtered_df
                .assign(_order=filtered_df["区分"].map(TYPE_ORDER))
                .sort_values("_order", ascending=ascending)
                .drop(columns="_order")
            )

        # =========================
        # 検索結果表示
        # =========================

        st.divider()
        st.subheader("検索結果")

        st.markdown(
            f"""
            <div style="
            font-size:22px;
            font-weight:800;
            border-bottom:3px solid #6366f1;
            padding-bottom:6px;
            margin-bottom:12px;
            ">
            検索結果： {len(filtered_df)} 件
            </div>
            """,
            unsafe_allow_html=True
        )

        if filtered_df.empty:
            st.info("条件に一致する楽譜がありません")
            continue

        # =========================
        # カード表示（元コード準拠）
        # =========================

        cards_per_row = 3
        rows = [
            filtered_df.iloc[i:i + cards_per_row]
            for i in range(0, len(filtered_df), cards_per_row)
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
border-radius:12px;
background:#ffffff;
height:260px;
display:grid;
grid-template-rows:72px 1fr;
row-gap:6px;
margin-bottom:24px;
color:{TEXT_COLOR};
">

<h3 style="
margin:0;
font-size:20px;
font-weight:700;
line-height:1.2;
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
声部：<span style="color:{color};">{r['声部']}</span>
</p>

<span style="
display:inline-block;
padding:3px 9px;
border-radius:999px;
background:#f1f5f9;
font-size:13px;
">
{r['区分']}
</span>

<a href="{r['url']}" target="_blank"
style="
display:block;
margin-top:12px;
text-align:center;
padding:9px;
border-radius:8px;
background:#e5e7eb;
color:{TEXT_COLOR};
text-decoration:none;
font-weight:600;
">
楽譜を開く
</a>
</div>
</div>
""",
                        unsafe_allow_html=True
                    )
