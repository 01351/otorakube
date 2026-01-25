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
ROOT_FOLDER_ID = "1c0JC6zLnipbJcP-2Dfe0QxXNQikSo3hm"

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
# ファイル名解析
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

@st.cache_resource
def get_drive_service():
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    return build("drive", "v3", credentials=credentials)

service = get_drive_service()

# =========================
# 親フォルダ配下の子フォルダ取得
# =========================

@st.cache_data(ttl=300)
def load_subfolders(parent_id):
    results = service.files().list(
        q=f"'{parent_id}' in parents and "
          f"mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id, name)"
    ).execute()

    return results.get("files", [])

# =========================
# PDF読み込み（フォルダ指定）
# =========================

@st.cache_data(ttl=60, show_spinner=False)
def load_from_drive(folder_id):
    results = service.files().list(
        q=f"'{folder_id}' in parents and "
          f"trashed=false and mimeType='application/pdf'",
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
# タブ生成（子フォルダ）
# =========================

subfolders = load_subfolders(ROOT_FOLDER_ID)

if not subfolders:
    st.warning("子フォルダが見つかりません")
    st.stop()

tabs = st.tabs([f["name"] for f in subfolders])
# =========================
# 各タブごとの検索・表示処理
# =========================

for tab, folder in zip(tabs, subfolders):
    with tab:
        df = load_from_drive(folder["id"])

        st.subheader(f"📁 {folder['name']}")

        if df.empty:
            st.info("このフォルダには表示可能な楽譜がありません")
            continue

        # =========================
        # 検索UI
        # =========================

        st.divider()
        st.subheader("検索")

        col1, col2 = st.columns([2, 1])
        with col1:
            title_input = st.text_input(
                "🎵 曲名（部分一致）",
                key=f"title_{folder['id']}"
            )
        with col2:
            composer_list = sorted(
                df["作曲・編曲者"].dropna().unique().tolist()
            )
            composer_input = st.selectbox(
                "👤 作曲・編曲者",
                ["指定しない"] + composer_list,
                key=f"composer_{folder['id']}"
            )

        # =========================
        # 検索処理
        # =========================

        filtered_df = df.copy()

        if title_input:
            filtered_df = filtered_df[
                filtered_df["曲名"].str.contains(
                    title_input, case=False, na=False
                )
            ]

        if composer_input != "指定しない":
            filtered_df = filtered_df[
                filtered_df["作曲・編曲者"] == composer_input
            ]

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
        # カード表示
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
                base_part = re.sub(
                    r"(二部|三部|四部)", "", r["声部"]
                )
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
<p style="margin:0 0 6px 0;">
作曲・編曲者：{r['作曲・編曲者']}
</p>

<p style="margin:0 0 6px 0;">
声部：
<span style="color:{color};">
{r['声部']}
</span>
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
