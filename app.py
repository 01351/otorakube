import streamlit as st
import pandas as pd
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build

# =========================
# 基本設定
# =========================

st.set_page_config(
    page_title="楽譜管理アプリ",
    layout="wide"
)

st.title("楽譜管理アプリ")

# =========================
# Google Drive 設定
# =========================

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
FOLDER_ID = "1c0JC6zLnipbJcP-2Dfe0QxXNQikSo3hm"

# =========================
# 定義
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
    """
    例:
    11AveMaria-AG4Bach★.pdf
    """
    pattern = r"^(\d{2})(.+?)-([ABCD])([GFMU])([234]?)(.+)\.pdf$"
    m = re.match(pattern, filename)
    if not m:
        return None

    code, title, t, p, n, composer = m.groups()

    composer = composer.replace("★", "").strip()
    title = title.strip()

    work_type = TYPE_MAP.get(t)

    if p == "U":
        part = "斉唱"
        part_base = "斉唱"
    else:
        part_base = PART_BASE_MAP[p]
        part = f"{part_base}{NUM_MAP.get(n, '')}"

    return {
        "code": code,
        "曲名": title,
        "作曲者": composer,
        "声部": part,
        "声部種別": part_base,
        "区分": work_type
    }

# =========================
# Google Drive 読み込み
# =========================

def load_from_drive():
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )

    service = build("drive", "v3", credentials=credentials)

    res = service.files().list(
        q=f"'{FOLDER_ID}' in parents and trashed=false and mimeType='application/pdf'",
        fields="files(name, webViewLink)"
    ).execute()

    rows = []

    for f in res.get("files", []):
        parsed = parse_filename(f["name"])
        if parsed:
            rows.append({**parsed, "url": f["webViewLink"]})

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df = df.sort_values("code")
    return df

# =========================
# キャッシュ制御
# =========================

if "reload" not in st.session_state:
    st.session_state.reload = 0

if st.button("🔄 Drive を再読み込み"):
    st.session_state.reload += 1

df = load_from_drive()

# =========================
# 検索UI
# =========================

st.subheader("検索")

# --- 曲名 ---
title_input = st.text_input("曲名（部分一致）")

# --- 作曲者 ---
composer_list = sorted(df["作曲者"].dropna().unique().tolist())
composer_input = st.selectbox("作曲者", ["指定しない"] + composer_list)

# --- 声部（横一列チェックボックス） ---
st.markdown("**声部**")
existing_parts = [
    p for p in PART_ORDER
    if p in df["声部種別"].unique()
]

part_cols = st.columns(len(existing_parts))
part_checks = {}

for col, part in zip(part_cols, existing_parts):
    with col:
        part_checks[part] = st.checkbox(part, value=True)

# --- 区分（横一列チェックボックス） ---
st.markdown("**区分**")
type_list = df["区分"].dropna().unique().tolist()
type_cols = st.columns(len(type_list))
type_checks = {}

for col, t in zip(type_cols, type_list):
    with col:
        type_checks[t] = st.checkbox(t, value=True)

# =========================
# 検索処理
# =========================

filtered = df.copy()

if title_input:
    filtered = filtered[
        filtered["曲名"].str.contains(title_input, case=False, na=False)
    ]

if composer_input != "指定しない":
    filtered = filtered[filtered["作曲者"] == composer_input]

selected_parts = [k for k, v in part_checks.items() if v]
filtered = filtered[filtered["声部種別"].isin(selected_parts)]

selected_types = [k for k, v in type_checks.items() if v]
filtered = filtered[filtered["区分"].isin(selected_types)]

# =========================
# 検索結果
# =========================

st.subheader(f"検索結果：{len(filtered)} 件")

if filtered.empty:
    st.info("該当する楽譜はありません")
else:
    for _, r in filtered.iterrows():
        with st.container(border=True):
            st.markdown(f"### {r['曲名']}")
            st.write(f"作曲者：{r['作曲者']}")
            st.write(f"声部：{r['声部']}")
            st.write(f"区分：{r['区分']}")

            st.markdown(
                f"""
                <a href="{r['url']}" target="_blank"
                   style="
                   display:inline-block;
                   padding:8px 16px;
                   background:#2563eb;
                   color:white;
                   border-radius:6px;
                   text-decoration:none;
                   font-weight:600;
                   ">
                   楽譜を開く
                </a>
                """,
                unsafe_allow_html=True
            )
