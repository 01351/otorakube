#フォルダ横断タブ
#並び替え
#表示形式は並び替えに
#検索の声部は混声→女声→男声→斉唱、二部→三部→四部
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

PART_BASE_ORDER = ["混声", "女声", "男声", "斉唱"]
NUM_ORDER = ["二部", "三部", "四部"]
TYPE_ORDER = [
    "オリジナル（伴奏有）",
    "オリジナル（無伴奏）",
    "アレンジ",
    "特殊"
]

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
    part = base + NUM_MAP.get(n, "")

    return {
        "code": code,
        "曲名": title.strip(),
        "作曲・編曲者": composer,
        "声部": part,
        "区分": TYPE_MAP.get(t, "不明"),
        "声部_base": base,
        "声部_num": NUM_MAP.get(n, "")
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

    rows = []
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
                    rows.append({
                        **parsed,
                        "url": f["webViewLink"],
                        "folder_name": folder["name"]
                    })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("code")

    return df, folder_names

df_all, folder_names = load_all_from_drive()

# =========================
# メイン処理
# =========================

if df_all.empty:
    st.info("条件に一致する楽譜がありません")
    st.stop()

tabs = st.tabs(folder_names)

for i, tab in enumerate(tabs):
    folder = folder_names[i]
    safe = re.sub(r"\W+", "_", folder)

    with tab:
        df = df_all[df_all["folder_name"] == folder].copy()

        st.divider()
        st.subheader(f"検索（{folder}）")

        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            title_input = st.text_input("🎵 曲名", key=f"title_{safe}")
        with c2:
            composers = sorted(df["作曲・編曲者"].dropna().unique())
            composer_input = st.selectbox(
                "👤 作曲・編曲者",
                ["指定しない"] + composers,
                key=f"composer_{safe}"
            )
        with c3:
            view_mode = st.radio(
                "表示形式",
                ["カード", "一覧"],
                horizontal=True,
                key=f"view_{safe}"
            )

        # =========================
        # 声部フィルタ
        # =========================

        st.markdown("**声部**")
        parts = sorted(df["声部"].unique())
        selected_parts = parts.copy()

        if len(parts) == 1:
            st.info(parts[0])
        else:
            key_all = f"all_part_{safe}"
            st.session_state.setdefault(key_all, True)

            for p in parts:
                st.session_state.setdefault(f"part_{safe}_{p}", True)

            def sync_part_all():
                checked = st.session_state.get(key_all, False)
                for p in parts:
                    st.session_state[f"part_{safe}_{p}"] = checked

            def sync_part_each():
                st.session_state[key_all] = all(
                    st.session_state.get(f"part_{safe}_{p}", False)
                    for p in parts
                )

            st.checkbox("すべて選択", key=key_all, on_change=sync_part_all)

            cols = st.columns(len(parts))
            selected_parts = []
            for col, p in zip(cols, parts):
                with col:
                    st.checkbox(p, key=f"part_{safe}_{p}", on_change=sync_part_each)
                    if st.session_state[f"part_{safe}_{p}"]:
                        selected_parts.append(p)

        # =========================
        # 区分フィルタ
        # =========================

        st.markdown("**区分**")
        types = sorted(df["区分"].unique())
        selected_types = types.copy()

        if len(types) == 1:
            st.info(types[0])
        else:
            key_all = f"all_type_{safe}"
            st.session_state.setdefault(key_all, True)

            for t in types:
                st.session_state.setdefault(f"type_{safe}_{t}", True)

            def sync_type_all():
                checked = st.session_state.get(key_all, False)
                for t in types:
                    st.session_state[f"type_{safe}_{t}"] = checked

            def sync_type_each():
                st.session_state[key_all] = all(
                    st.session_state.get(f"type_{safe}_{t}", False)
                    for t in types
                )

            st.checkbox("すべて選択", key=key_all, on_change=sync_type_all)

            cols = st.columns(len(types))
            selected_types = []
            for col, t in zip(cols, types):
                with col:
                    st.checkbox(t, key=f"type_{safe}_{t}", on_change=sync_type_each)
                    if st.session_state[f"type_{safe}_{t}"]:
                        selected_types.append(t)

        # =========================
        # フィルタ & 並び替え
        # =========================

        filtered = df.copy()

        if title_input:
            filtered = filtered[filtered["曲名"].str.contains(title_input, na=False)]

        if composer_input != "指定しない":
            filtered = filtered[filtered["作曲・編曲者"] == composer_input]

        filtered = filtered[
            filtered["声部"].isin(selected_parts)
            & filtered["区分"].isin(selected_types)
        ]

        filtered["_pb"] = filtered["声部_base"].apply(
            lambda x: PART_BASE_ORDER.index(x) if x in PART_BASE_ORDER else 99
        )
        filtered["_pn"] = filtered["声部_num"].apply(
            lambda x: NUM_ORDER.index(x) if x in NUM_ORDER else 99
        )
        filtered["_to"] = filtered["区分"].apply(
            lambda x: TYPE_ORDER.index(x) if x in TYPE_ORDER else 99
        )

        filtered = filtered.sort_values(["_pb", "_pn", "_to", "code"])

        st.divider()
        st.markdown(f"### 🔍 検索結果：{len(filtered)} 件")

        if filtered.empty:
            st.info("条件に一致する楽譜がありません")
            continue

        # =========================
        # 表示
        # =========================

        if view_mode == "一覧":
            st.dataframe(
                filtered[["曲名", "作曲・編曲者", "声部", "区分", "url"]]
                .rename(columns={"url": "楽譜リンク"}),
                use_container_width=True,
                hide_index=True
            )
        else:
            cards_per_row = 3
            for start in range(0, len(filtered), cards_per_row):
                row_df = filtered.iloc[start:start + cards_per_row]
                cols = st.columns(len(row_df))  # ★並び替えが崩れないポイント

                for idx, (_, r) in enumerate(row_df.iterrows()):
                    base = re.sub(r"(二部|三部|四部)", "", r["声部"])
                    color = PART_COLOR.get(base, "#64748b")

                    with cols[idx]:
                        st.markdown(
                            f"""
<div style="border-left:8px solid {color};padding:14px;border-radius:12px;background:#ffffff;min-height:260px;margin-bottom:24px;color:{TEXT_COLOR};">
<h3 style="margin:0;font-size:20px;font-weight:700;">{r["曲名"]}</h3>
<p>作曲・編曲者：{r["作曲・編曲者"]}</p>
<p>声部：<span style="color:{color};font-weight:600;">{r["声部"]}</span></p>
<span style="padding:3px 9px;border-radius:999px;background:#f1f5f9;font-size:13px;">{r["区分"]}</span>
<a href="{r["url"]}" target="_blank"
   style="display:block;margin-top:12px;text-align:center;padding:9px;border-radius:8px;background:#e5e7eb;color:{TEXT_COLOR};font-weight:600;text-decoration:none;">
楽譜を開く
</a>
</div>
""",
                            unsafe_allow_html=True
                        )
