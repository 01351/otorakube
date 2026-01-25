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

# 親フォルダ（この中に子フォルダが3つある想定）
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

@st.cache_data(ttl=300, show_spinner=False)
def get_drive_service():
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    return build("drive", "v3", credentials=credentials)

service = get_drive_service()

# =========================
# 子フォルダ一覧取得
# =========================

@st.cache_data(ttl=300, show_spinner=False)
def get_child_folders(parent_id):
    res = service.files().list(
        q=f"'{parent_id}' in parents and trashed=false and mimeType='application/vnd.google-apps.folder'",
        fields="files(id, name)",
        orderBy="name",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()

    return res.get("files", [])

child_folders = get_child_folders(ROOT_FOLDER_ID)

if not child_folders:
    st.error("子フォルダが見つかりません")
    st.stop()

# =========================
# フォルダごとのPDF読み込み
# =========================

@st.cache_data(ttl=300, show_spinner=False)
def load_from_drive(folder_id):
    results = service.files().list(
        q=f"'{folder_id}' in parents and trashed=false and mimeType='application/pdf'",
        fields="files(name, webViewLink)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
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
# タブ作成（子フォルダ）
# =========================

tab_labels = [f["name"] for f in child_folders]
tabs = st.tabs(tab_labels)
# =========================
# タブ内表示処理
# =========================

for tab, folder in zip(tabs, child_folders):
    with tab:
        df = load_from_drive(folder["id"])

        if df.empty:
            st.info("このフォルダには表示できるPDFがありません")
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

        st.caption("▼ 詳細条件")

        # =========================
        # 声部（チェックボックス）
        # =========================

        st.markdown("**声部**")

        def part_sort_key(part):
            base = re.sub(r"(二部|三部|四部)", "", part)
            num = re.search(r"(二部|三部|四部)", part)

            base_order = ["混声", "女声", "男声", "斉唱"]
            num_order = ["二部", "三部", "四部"]

            return (
                base_order.index(base) if base in base_order else 99,
                num_order.index(num.group()) if num else 99
            )

        existing_parts = sorted(
            df["声部"].dropna().unique().tolist(),
            key=part_sort_key
        )

        part_state_key = f"initialized_part_{folder['id']}"
        if part_state_key not in st.session_state:
            st.session_state[f"all_part_{folder['id']}"] = True
            for p in existing_parts:
                st.session_state[f"part_{folder['id']}_{p}"] = True
            st.session_state[part_state_key] = True

        def toggle_all_part(fid):
            for p in existing_parts:
                st.session_state[f"part_{fid}_{p}"] = st.session_state[f"all_part_{fid}"]

        def sync_all_part(fid):
            st.session_state[f"all_part_{fid}"] = all(
                st.session_state.get(f"part_{fid}_{p}", False)
                for p in existing_parts
            )

        st.checkbox(
            "すべて選択",
            key=f"all_part_{folder['id']}",
            on_change=toggle_all_part,
            args=(folder["id"],)
        )

        part_cols = st.columns(len(existing_parts))
        part_checks = {}

        for col, part in zip(part_cols, existing_parts):
            with col:
                part_checks[part] = st.checkbox(
                    part,
                    key=f"part_{folder['id']}_{part}",
                    on_change=sync_all_part,
                    args=(folder["id"],)
                )

        PART_ORDER = {p: i for i, p in enumerate(existing_parts)}

        # =========================
        # 区分（チェックボックス）
        # =========================

        st.markdown("**区分**")
        type_labels = list(TYPE_MAP.values())

        type_state_key = f"initialized_type_{folder['id']}"
        if type_state_key not in st.session_state:
            st.session_state[f"all_type_{folder['id']}"] = True
            for t in type_labels:
                st.session_state[f"type_{folder['id']}_{t}"] = True
            st.session_state[type_state_key] = True

        def toggle_all_type(fid):
            for t in type_labels:
                st.session_state[f"type_{fid}_{t}"] = st.session_state[f"all_type_{fid}"]

        def sync_all_type(fid):
            st.session_state[f"all_type_{fid}"] = all(
                st.session_state.get(f"type_{fid}_{t}", False)
                for t in type_labels
            )

        st.checkbox(
            "すべて選択",
            key=f"all_type_{folder['id']}",
            on_change=toggle_all_type,
            args=(folder["id"],)
        )

        type_cols = st.columns(len(type_labels))
        type_checks = {}

        for col, t in zip(type_cols, type_labels):
            with col:
                type_checks[t] = st.checkbox(
                    t,
                    key=f"type_{folder['id']}_{t}",
                    on_change=sync_all_type,
                    args=(folder["id"],)
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
                index=0,
                key=f"sort_key_{folder['id']}"
            )

        with sort_col2:
            sort_order = st.radio(
                "順序",
                ["昇順", "降順"],
                horizontal=True,
                index=0,
                key=f"sort_order_{folder['id']}"
            )

        # =========================
        # 検索処理
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
        # 検索結果件数
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
