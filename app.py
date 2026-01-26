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
st.caption("Google Drive 上のフォルダ別に楽譜PDFを検索できます")

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

TYPE_ORDER = [
    "オリジナル（伴奏有）",
    "オリジナル（無伴奏）",
    "アレンジ",
    "特殊"
]

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

PART_BASE_ORDER = ["混声", "女声", "男声", "斉唱"]
PART_NUM_ORDER = ["二部", "三部", "四部"]

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

    base = PART_BASE_MAP.get(p, "不明")
    num = NUM_MAP.get(n, "")
    part = base + num

    section = TYPE_MAP.get(t, "不明")

    return {
        "code": code,
        "曲名": title.strip(),
        "作曲・編曲者": composer,
        "声部": part,
        "区分": section
    }

# =========================
# 並び替えキー
# =========================

def part_sort_key(p):
    base = re.sub(r"(二部|三部|四部)", "", p)
    num_match = re.search(r"(二部|三部|四部)", p)

    base_i = PART_BASE_ORDER.index(base) if base in PART_BASE_ORDER else 99
    num_i = PART_NUM_ORDER.index(num_match.group()) if num_match and num_match.group() in PART_NUM_ORDER else 99

    return (base_i, num_i)

def type_sort_key(t):
    return TYPE_ORDER.index(t) if t in TYPE_ORDER else 99

# =========================
# Google Drive 読み込み
# =========================

@st.cache_data(ttl=60)
def load_all_from_drive():
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )

    service = build("drive", "v3", credentials=credentials)

    folder_results = service.files().list(
        q=f"'{FOLDER_ID}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id, name)"
    ).execute()

    sub_folders = folder_results.get("files", [])
    if not sub_folders:
        sub_folders = [{"id": FOLDER_ID, "name": "楽譜一覧"}]

    rows = []
    folder_names = []

    for folder in sub_folders:
        results = service.files().list(
            q=f"'{folder['id']}' in parents and trashed=false and mimeType='application/pdf'",
            fields="files(name, webViewLink)"
        ).execute()

        files = results.get("files", [])
        if not files:
            continue

        folder_names.append(folder["name"])

        for f in files:
            parsed = parse_filename(f["name"])
            if parsed:
                rows.append({
                    **parsed,
                    "url": f["webViewLink"],
                    "folder_name": folder["name"]
                })

    return pd.DataFrame(rows), folder_names

df_all, folder_names = load_all_from_drive()

# =========================
# メイン処理
# =========================

if df_all.empty:
    st.info("楽譜が見つかりません")
    st.stop()

tabs = st.tabs(folder_names)

for i, tab in enumerate(tabs):
    folder = folder_names[i]

    with tab:
        df = df_all[df_all["folder_name"] == folder].copy()

        # --- 検索UI ---
        st.subheader(f"検索（{folder}）")

        title_input = st.text_input("🎵 曲名（部分一致）", key=f"title_{folder}")

        parts = sorted(df["声部"].unique(), key=part_sort_key)
        types = sorted(df["区分"].unique(), key=type_sort_key)

        selected_parts = st.multiselect(
            "声部",
            parts,
            default=parts,
            key=f"parts_{folder}"
        )

        selected_types = st.multiselect(
            "区分",
            types,
            default=types,
            key=f"types_{folder}"
        )

        # --- フィルタ ---
        filtered = df.copy()

        if title_input:
            filtered = filtered[
                filtered["曲名"].str.contains(title_input, na=False)
            ]

        filtered = filtered[
            filtered["声部"].isin(selected_parts)
            & filtered["区分"].isin(selected_types)
        ]

        # --- 並び替え（固定） ---
        filtered["_p"] = filtered["声部"].apply(part_sort_key)
        filtered["_t"] = filtered["区分"].apply(type_sort_key)

        filtered = (
            filtered
            .sort_values(["_p", "_t", "code"])
            .drop(columns=["_p", "_t"])
        )

        # =========================
        # 表示
        # =========================

        st.divider()
        st.markdown(f"### 検索結果：{len(filtered)} 件")

        if filtered.empty:
            st.info("条件に一致する楽譜がありません")
            continue

        cards_per_row = 3

        for start in range(0, len(filtered), cards_per_row):
            row_df = filtered.iloc[start:start + cards_per_row]
            cols = st.columns(cards_per_row)

            for idx, (_, r) in enumerate(row_df.iterrows()):
                base = re.sub(r"(二部|三部|四部)", "", r["声部"])
                color = PART_COLOR.get(base, "#64748b")

                with cols[idx]:
                    st.markdown(
                        f"""
<div style="
    border-left:8px solid {color};
    padding:14px;
    border-radius:12px;
    background:#ffffff;
    min-height:240px;
    margin-bottom:20px;
    color:{TEXT_COLOR};
">
<h3 style="margin-top:0;">{r["曲名"]}</h3>
<p>作曲・編曲者：{r["作曲・編曲者"]}</p>
<p>声部：<span style="color:{color}; font-weight:600;">{r["声部"]}</span></p>
<p>{r["区分"]}</p>
<a href="{r["url"]}" target="_blank">▶ 楽譜を開く</a>
</div>
""",
                        unsafe_allow_html=True
                    )
