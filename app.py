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
# 並び替えキー（★追加）
# =========================

def part_sort_key(part):
    base = re.sub(r"(二部|三部|四部)", "", part)
    num_match = re.search(r"(二部|三部|四部)", part)

    base_i = PART_BASE_ORDER.index(base) if base in PART_BASE_ORDER else 99
    num_i = (
        PART_NUM_ORDER.index(num_match.group())
        if num_match and num_match.group() in PART_NUM_ORDER
        else 99
    )
    return (base_i, num_i)

def type_sort_key(t):
    return TYPE_ORDER.index(t) if t in TYPE_ORDER else 99

# =========================
# Google Drive 読み込み
# =========================

@st.cache_data(ttl=60, show_spinner=False)
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

    all_rows = []
    folder_names = []

    for folder in sub_folders:
        results = service.files().list(
            q=f"'{folder['id']}' in parents and trashed=false and mimeType='application/pdf'",
            fields="files(name, webViewLink)"
        ).execute()

        files = results.get("files", [])
        if files:
            folder_names.append(folder["name"])
            for f in files:
                parsed = parse_filename(f["name"])
                if parsed:
                    all_rows.append({
                        **parsed,
                        "url": f["webViewLink"],
                        "folder_name": folder["name"]
                    })

    df = pd.DataFrame(all_rows)
    if not df.empty:
        df = df.sort_values("code")

    return df, folder_names

df_all, folder_names = load_all_from_drive()

# =========================
# メイン処理
# =========================

if df_all.empty:
    st.info("条件に一致する楽譜がありません")
else:
    tabs = st.tabs(folder_names)

    for i, tab in enumerate(tabs):
        current_folder = folder_names[i]
        safe_folder = re.sub(r"\W+", "_", current_folder)

        with tab:
            df = df_all[df_all["folder_name"] == current_folder].copy()

            # =========================
            # 検索 & 表示切替
            # =========================

            st.divider()
            st.subheader(f"検索（{current_folder}）")

            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                title_input = st.text_input("🎵 曲名（部分一致）", key=f"title_{safe_folder}")
            with c2:
                composers = sorted(df["作曲・編曲者"].dropna().unique())
                composer_input = st.selectbox(
                    "👤 作曲・編曲者",
                    ["指定しない"] + composers,
                    key=f"composer_{safe_folder}"
                )
            with c3:
                view_mode = st.radio(
                    "表示形式",
                    ["カード", "一覧"],
                    horizontal=True,
                    key=f"view_{safe_folder}"
                )

            # =========================
            # 声部・区分抽出（★必ず df から）
            # =========================

            existing_parts = sorted(
                df["声部"].dropna().unique(),
                key=part_sort_key
            )
            existing_types = sorted(
                df["区分"].dropna().unique(),
                key=type_sort_key
            )

            selected_parts = existing_parts.copy()
            selected_types = existing_types.copy()

            # =========================
            # フィルタ処理
            # =========================

            filtered_df = df.copy()

            if title_input:
                filtered_df = filtered_df[
                    filtered_df["曲名"].str.contains(title_input, na=False)
                ]

            if composer_input != "指定しない":
                filtered_df = filtered_df[
                    filtered_df["作曲・編曲者"] == composer_input
                ]

            filtered_df = filtered_df[
                filtered_df["声部"].isin(selected_parts)
                & filtered_df["区分"].isin(selected_types)
            ]

            # =========================
            # 並び替え（★意味順固定）
            # =========================

            filtered_df["_p"] = filtered_df["声部"].apply(part_sort_key)
            filtered_df["_t"] = filtered_df["区分"].apply(type_sort_key)

            filtered_df = (
                filtered_df
                .sort_values(["_p", "_t", "code"])
                .drop(columns=["_p", "_t"])
            )

            # =========================
            # 表示
            # =========================

            st.divider()
            st.markdown(
                f'<div style="font-size:22px;font-weight:800;border-bottom:3px solid #6366f1;padding-bottom:6px;">検索結果： {len(filtered_df)} 件</div>',
                unsafe_allow_html=True
            )

            if filtered_df.empty:
                st.info("条件に一致する楽譜がありません")
                continue

            if view_mode == "一覧":
                st.dataframe(
                    filtered_df[["曲名", "作曲・編曲者", "声部", "区分", "url"]],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                cards_per_row = 3
                for start in range(0, len(filtered_df), cards_per_row):
                    row_df = filtered_df.iloc[start:start + cards_per_row]
                    cols = st.columns(cards_per_row)

                    for idx, (_, r) in enumerate(row_df.iterrows()):
                        base = re.sub(r"(二部|三部|四部)", "", r["声部"])
                        color = PART_COLOR.get(base, "#64748b")

                        with cols[idx]:
                            st.markdown(
                                f"""
<div style="border-left:8px solid {color};padding:14px;border-radius:12px;background:#ffffff;min-height:260px;margin-bottom:24px;color:{TEXT_COLOR};">
<h3>{r["曲名"]}</h3>
<p>作曲・編曲者：{r["作曲・編曲者"]}</p>
<p>声部：<span style="color:{color};">{r["声部"]}</span></p>
<span>{r["区分"]}</span>
<a href="{r["url"]}" target="_blank">楽譜を開く</a>
</div>
""",
                                unsafe_allow_html=True
                            )
