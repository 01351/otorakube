#すべて選択を実装
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

        with tab:
            df = df_all[df_all["folder_name"] == current_folder].copy()

            # =========================
            # 検索
            # =========================

            st.divider()
            st.subheader(f"検索（{current_folder}）")

            c1, c2 = st.columns([2, 1])
            with c1:
                title_input = st.text_input("🎵 曲名（部分一致）", key=f"title_{current_folder}")
            with c2:
                composers = sorted(df["作曲・編曲者"].dropna().unique())
                composer_input = st.selectbox(
                    "👤 作曲・編曲者",
                    ["指定しない"] + composers,
                    key=f"composer_{current_folder}"
                )

            # =========================
            # 声部
            # =========================

            st.markdown("**声部**")

            def part_sort_key(p):
                base = re.sub(r"(二部|三部|四部)", "", p)
                num = re.search(r"(二部|三部|四部)", p)
                return (
                    ["混声", "女声", "男声", "斉唱"].index(base),
                    ["二部", "三部", "四部"].index(num.group()) if num else 99
                )

            existing_parts = sorted(df["声部"].dropna().unique(), key=part_sort_key)

            master_part = f"all_part_{current_folder}"
            st.session_state.setdefault(master_part, True)

            for p in existing_parts:
                st.session_state.setdefault(f"part_{current_folder}_{p}", True)

            def cb_part_all():
                v = st.session_state.get(master_part, False)
                for p in existing_parts:
                    st.session_state[f"part_{current_folder}_{p}"] = v

            def cb_part_sync():
                st.session_state[master_part] = all(
                    st.session_state.get(f"part_{current_folder}_{p}", False)
                    for p in existing_parts
                )

            st.checkbox("すべて選択", key=master_part, on_change=cb_part_all)

            cols = st.columns(len(existing_parts))
            selected_parts = []
            for col, p in zip(cols, existing_parts):
                with col:
                    st.checkbox(p, key=f"part_{current_folder}_{p}", on_change=cb_part_sync)
                    if st.session_state[f"part_{current_folder}_{p}"]:
                        selected_parts.append(p)

            # =========================
            # 区分
            # =========================

            st.markdown("**区分**")

            existing_types = sorted(df["区分"].dropna().unique())
            master_type = f"all_type_{current_folder}"
            st.session_state.setdefault(master_type, True)

            for t in existing_types:
                st.session_state.setdefault(f"type_{current_folder}_{t}", True)

            def cb_type_all():
                v = st.session_state.get(master_type, False)
                for t in existing_types:
                    st.session_state[f"type_{current_folder}_{t}"] = v

            def cb_type_sync():
                st.session_state[master_type] = all(
                    st.session_state.get(f"type_{current_folder}_{t}", False)
                    for t in existing_types
                )

            st.checkbox("すべて選択", key=master_type, on_change=cb_type_all)

            cols = st.columns(len(existing_types))
            selected_types = []
            for col, t in zip(cols, existing_types):
                with col:
                    st.checkbox(t, key=f"type_{current_folder}_{t}", on_change=cb_type_sync)
                    if st.session_state[f"type_{current_folder}_{t}"]:
                        selected_types.append(t)

            # =========================
            # 並び替え（← 復活）
            # =========================

            st.divider()
            st.markdown("### 🔃 並び替え")

            s1, s2 = st.columns([3, 2])
            with s1:
                sort_key = st.selectbox(
                    "並び替え項目",
                    ["曲名（五十音順）", "声部", "区分"],
                    key=f"sort_key_{current_folder}"
                )
            with s2:
                sort_order = st.radio(
                    "順序",
                    ["昇順", "降順"],
                    horizontal=True,
                    key=f"sort_order_{current_folder}"
                )

            # =========================
            # フィルタ処理
            # =========================

            filtered_df = df.copy()

            if title_input:
                filtered_df = filtered_df[filtered_df["曲名"].str.contains(title_input, na=False)]
            if composer_input != "指定しない":
                filtered_df = filtered_df[filtered_df["作曲・編曲者"] == composer_input]

            filtered_df = filtered_df[
                filtered_df["声部"].isin(selected_parts)
                & filtered_df["区分"].isin(selected_types)
            ]

            ascending = sort_order == "昇順"
            PART_ORDER = {p: i for i, p in enumerate(existing_parts)}
            TYPE_ORDER = {t: i for i, t in enumerate(existing_types)}

            if sort_key == "曲名（五十音順）":
                filtered_df = filtered_df.sort_values("code", ascending=ascending)
            elif sort_key == "声部":
                filtered_df = (
                    filtered_df
                    .assign(_o=filtered_df["声部"].map(PART_ORDER))
                    .sort_values("_o", ascending=ascending)
                    .drop(columns="_o")
                )
            elif sort_key == "区分":
                filtered_df = (
                    filtered_df
                    .assign(_o=filtered_df["区分"].map(TYPE_ORDER))
                    .sort_values("_o", ascending=ascending)
                    .drop(columns="_o")
                )

            # =========================
            # カード表示
            # =========================

            st.divider()
            st.markdown(
                f'<div style="font-size:22px; font-weight:800; border-bottom:3px solid #6366f1; padding-bottom:6px; margin-bottom:12px;">検索結果： {len(filtered_df)} 件</div>',
                unsafe_allow_html=True
            )

            if filtered_df.empty:
                st.info("条件に一致する楽譜がありません")
            else:
                cards_per_row = 3
                for i in range(0, len(filtered_df), cards_per_row):
                    row = filtered_df.iloc[i:i + cards_per_row]
                    cols = st.columns(cards_per_row)

                    for j, r in enumerate(row.itertuples()):
                        base = re.sub(r"(二部|三部|四部)", "", r.声部)
                        color = PART_COLOR.get(base, "#64748b")

                        with cols[j]:
                            st.markdown(f"""
<div style="border-left:8px solid {color}; padding:14px; border-radius:12px; background:#ffffff; height:260px; display:grid; grid-template-rows:72px 1fr; row-gap:6px; margin-bottom:24px; color:{TEXT_COLOR};">
<h3 style="margin:0; font-size:20px; font-weight:700; line-height:1.2; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;">{r.曲名}</h3>
<div>
<p style="margin:0 0 6px 0;">作曲・編曲者：{r.作曲・編曲者}</p>
<p style="margin:0 0 6px 0;">声部：<span style="color:{color};">{r.声部}</span></p>
<span style="display:inline-block; padding:3px 9px; border-radius:999px; background:#f1f5f9; font-size:13px;">{r.区分}</span>
<a href="{r.url}" target="_blank" style="display:block; margin-top:12px; text-align:center; padding:9px; border-radius:8px; background:#e5e7eb; color:{TEXT_COLOR}; text-decoration:none; font-weight:600;">楽譜を開く</a>
</div>
</div>
""", unsafe_allow_html=True)
