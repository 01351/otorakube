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
    st.radio(
        "表示形式",
        ["カード", "一覧"],
        horizontal=True,
        key="global_view"
    )

with c_sort:
    st.selectbox(
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
# =========================
# タブ内：検索・並び替え・表示処理
# =========================

tab_labels = ["すべて", "混声", "女声", "男声"]

for tab, label in zip(tabs, tab_labels):
    with tab:
        # -------------------------
        # 対象データ抽出
        # -------------------------
        df_f = df.copy()

        if label != "すべて":
            df_f = df_f[df_f["声部区分"] == label]

        # -------------------------
        # 検索フィルタ
        # -------------------------
        if keyword:
            df_f = df_f[
                df_f["曲名"].str.contains(keyword, na=False)
                | df_f["作曲・編曲者"].str.contains(keyword, na=False)
            ]

        if part_filter:
            df_f = df_f[df_f["声部区分"].isin(part_filter)]

        if type_filter:
            df_f = df_f[df_f["区分"].isin(type_filter)]

        # -------------------------
        # 並び替え
        # -------------------------
        sort_key = st.session_state["global_sort"]

        if sort_key == "声部順（標準）":
            df_f = df_f.sort_values(
                ["_pb", "_pn", "_to", "code"],
                ascending=[True, True, True, True]
            )

        elif sort_key == "曲名（昇順）":
            df_f = df_f.sort_values("曲名", ascending=True)

        elif sort_key == "曲名（降順）":
            df_f = df_f.sort_values("曲名", ascending=False)

        elif sort_key == "作曲・編曲者（昇順）":
            df_f = df_f.sort_values("作曲・編曲者", ascending=True)

        elif sort_key == "作曲・編曲者（降順）":
            df_f = df_f.sort_values("作曲・編曲者", ascending=False)

        elif sort_key == "コード（昇順）":
            df_f = df_f.sort_values("code", ascending=True)

        elif sort_key == "コード（降順）":
            df_f = df_f.sort_values("code", ascending=False)

        # -------------------------
        # 件数表示
        # -------------------------
        st.markdown(f"### 🔍 検索結果：{len(df_f)} 件")

        if df_f.empty:
            st.info("条件に一致する楽譜がありません")
            continue

        # -------------------------
        # 表示切り替え
        # -------------------------
        view_mode = st.session_state["global_view"]

        # ===== 一覧表示 =====
        if view_mode == "一覧":
            st.dataframe(
                df_f[
                    ["code", "曲名", "作曲・編曲者", "声部区分", "声部", "区分", "link"]
                ].rename(columns={"link": "楽譜リンク"}),
                use_container_width=True,
                hide_index=True,
            )

        # ===== カード表示 =====
        else:
            cards_per_row = 3

            for start in range(0, len(df_f), cards_per_row):
                row_df = df_f.iloc[start:start + cards_per_row]
                cols = st.columns(len(row_df))

                for col, (_, r) in zip(cols, row_df.iterrows()):
                    with col:
                        st.markdown(
                            f"""
<div style="
    border:1px solid #e5e7eb;
    border-radius:14px;
    padding:16px;
    margin-bottom:24px;
    background:#ffffff;
    min-height:260px;
">
    <h3 style="margin-top:0;">{r["曲名"]}</h3>
    <p>作曲・編曲者：{r["作曲・編曲者"] or "―"}</p>
    <p>声部：<strong>{r["声部区分"]} {r["声部"]}</strong></p>
    <span style="
        display:inline-block;
        padding:4px 10px;
        border-radius:999px;
        background:#f1f5f9;
        font-size:13px;
        margin-bottom:8px;
    ">
        {r["区分"]}
    </span>
    <a href="{r["link"]}" target="_blank"
       style="
           display:block;
           margin-top:14px;
           text-align:center;
           padding:10px;
           border-radius:10px;
           background:#e5e7eb;
           font-weight:600;
           text-decoration:none;
           color:#0f172a;
       ">
       楽譜を開く
    </a>
</div>
""",
                            unsafe_allow_html=True
                        )
