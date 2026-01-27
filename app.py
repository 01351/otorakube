#並び替え
#表示形式は並び替えに
#カードは3分割の見た目で
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
    page_title="楽譜管理アプリ",
    layout="wide"
)

st.title("楽譜管理アプリ")
st.caption("Google Drive 上の楽譜PDFを検索できます")

# =========================
# Google Drive 設定
# =========================
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
FOLDER_ID = "1c0JC6zLnipbJcP-2Dfe0QxXNQikSo3hm"

credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=SCOPES,
)
service = build("drive", "v3", credentials=credentials)

# =========================
# 定義マップ
# =========================
TYPE_MAP = {
    "A": "オリジナル（伴奏あり）",
    "B": "オリジナル（無伴奏）",
    "C": "編曲",
}

PART_ORDER = {
    "混声": 0,
    "女声": 1,
    "男声": 2,
}

PART_NAME_ORDER = {
    "S": 0,
    "A": 1,
    "T": 2,
    "B": 3,
}

# =========================
# Drive ファイル取得
# =========================
@st.cache_data
def fetch_files():
    results = service.files().list(
        q=f"'{FOLDER_ID}' in parents and mimeType='application/pdf'",
        fields="files(id, name, webViewLink)",
        pageSize=1000,
    ).execute()
    return results.get("files", [])

files = fetch_files()

# =========================
# ファイル名解析
# =========================
rows = []

pattern = re.compile(
    r"""
    ^(?P<code>\d+)
    _(?P<part>混声|女声|男声)
    _(?P<voice>[SATB]+)?
    _(?P<type>[ABC])
    _(?P<title>.+?)
    (?:（(?P<composer>.+?)）)?
    \.pdf$
    """,
    re.VERBOSE,
)

for f in files:
    m = pattern.match(f["name"])
    if not m:
        continue

    rows.append({
        "code": m.group("code"),
        "声部区分": m.group("part"),
        "声部": m.group("voice") or "",
        "区分": TYPE_MAP.get(m.group("type"), ""),
        "曲名": m.group("title"),
        "作曲・編曲者": m.group("composer") or "",
        "link": f["webViewLink"],
    })

df = pd.DataFrame(rows)

# =========================
# 並び替え用内部カラム
# =========================
if not df.empty:
    df["_pb"] = df["声部区分"].map(PART_ORDER).fillna(99)
    df["_pn"] = df["声部"].map(lambda x: PART_NAME_ORDER.get(x[:1], 99))
    df["_to"] = df["区分"].map(lambda x: list(TYPE_MAP.values()).index(x) if x in TYPE_MAP.values() else 99)

# =========================
# 検索条件UI
# =========================
st.subheader("検索")

c1, c2, c3 = st.columns(3)

with c1:
    keyword = st.text_input("曲名・作曲者検索")

with c2:
    part_filter = st.multiselect(
        "声部区分",
        ["混声", "女声", "男声"],
        default=["混声", "女声", "男声"]
    )

with c3:
    type_filter = st.multiselect(
        "区分",
        list(TYPE_MAP.values()),
        default=list(TYPE_MAP.values())
    )

# =========================
# グローバル表示・並び替え（★修正点）
# =========================
c_view, c_sort = st.columns([1, 2])

with c_view:
    st.session_state["global_view"] = st.radio(
        "表示形式",
        ["カード", "一覧"],
        horizontal=True,
        key="global_view"
    )

with c_sort:
    st.session_state["global_sort"] = st.selectbox(
        "↕ 並び替え",
        [
            "声部順（標準）",
            "曲名（昇順）",
            "曲名（降順）",
            "作曲・編曲者（昇順）",
            "作曲・編曲者（降順）",
            "コード（昇順）",
            "コード（降順）",
        ],
        key="global_sort"
    )

st.divider()

# =========================
# タブ定義
# =========================
tabs = st.tabs(["すべて", "混声", "女声", "男声"])
