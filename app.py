#区分もDriveのファイル情報から直接読み取れるように　確認
#Driveにファイルがないときは0件と表示できるように　確認
#区分がPの場合、区分名は「ピアノ」で声部は「なし」命名規則も声部は飛ばして作曲者を読みとる
#作曲者はサイト内にふりがなの入力リストを作って、新規の作曲者も追加できるように
#検索の作曲者は五十音順に並び替え、リストにない作曲者は上に表示

import streamlit as st
import pandas as pd
import re
import io

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

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
# 定数
# =========================

ADMIN_PASSWORD = "0000"

SCOPES = ["https://www.googleapis.com/auth/drive"]

FOLDER_ID = "1c0JC6zLnipbJcP-2Dfe0QxXNQikSo3hm"
PRIVATE_FOLDER_ID = "1q8mfqK5Kc-QXOLe-9oJZTEFj3A8UO4hX"

TEXT_COLOR = "#0f172a"

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

# =========================
# 管理者ログイン
# =========================

if "is_admin" not in st.session_state:
    st.session_state["is_admin"] = False

with st.expander("🔐 管理者ログイン"):
    pwd = st.text_input("管理者パスワード", type="password")
    if pwd:
        if pwd == ADMIN_PASSWORD:
            st.session_state["is_admin"] = True
            st.success("管理者ログイン中")
        else:
            st.error("パスワードが違います")

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

@st.cache_data(ttl=60)
def get_service():
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    return build("drive", "v3", credentials=credentials)

service = get_service()

# =========================
# 同名ファイル存在チェック
# =========================

def file_exists_in_folder(service, filename, folder_id):
    query = (
        f"name = '{filename}' and "
        f"'{folder_id}' in parents and "
        "trashed = false"
    )
    res = service.files().list(
        q=query,
        fields="files(id)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()
    return len(res.get("files", [])) > 0

# =========================
# Drive 読み込み
# =========================

@st.cache_data(ttl=60)
def load_from_drive(folder_id):
    results = service.files().list(
        q=f"'{folder_id}' in parents and trashed=false and mimeType='application/pdf'",
        fields="files(id,name,webViewLink)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()

    rows = []
    errors = []

    for f in results.get("files", []):
        parsed = parse_filename(f["name"])
        if parsed:
            rows.append({**parsed, "url": f["webViewLink"]})
        else:
            errors.append(f["name"])

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("code")

    return df, errors

df, filename_errors = load_from_drive(FOLDER_ID)

# =========================
# 検索UI
# =========================

st.divider()
st.subheader("検索")

col1, col2 = st.columns([2, 1])
with col1:
    title_input = st.text_input("🎵 曲名（部分一致）")
with col2:
    composer_list = sorted(df["作曲・編曲者"].dropna().unique().tolist())
    composer_input = st.selectbox("👤 作曲・編曲者", ["指定しない"] + composer_list)

st.caption("▼ 詳細条件")

# =========================
# 声部
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

if "initialized_part" not in st.session_state:
    st.session_state["all_part"] = True
    for p in existing_parts:
        st.session_state[f"part_{p}"] = True
    st.session_state["initialized_part"] = True

def toggle_all_part():
    for p in existing_parts:
        st.session_state[f"part_{p}"] = st.session_state["all_part"]

def sync_all_part():
    st.session_state["all_part"] = all(
        st.session_state.get(f"part_{p}", False) for p in existing_parts
    )

st.checkbox("すべて選択", key="all_part", on_change=toggle_all_part)

part_cols = st.columns(len(existing_parts))
part_checks = {}

for col, part in zip(part_cols, existing_parts):
    with col:
        part_checks[part] = st.checkbox(
            part,
            key=f"part_{part}",
            on_change=sync_all_part
        )

PART_ORDER = {p: i for i, p in enumerate(existing_parts)}

# =========================
# 区分
# =========================

st.markdown("**区分**")
type_labels = list(TYPE_MAP.values())

if "initialized_type" not in st.session_state:
    st.session_state["all_type"] = True
    for t in type_labels:
        st.session_state[f"type_{t}"] = True
    st.session_state["initialized_type"] = True

def toggle_all_type():
    for t in type_labels:
        st.session_state[f"type_{t}"] = st.session_state["all_type"]

def sync_all_type():
    st.session_state["all_type"] = all(
        st.session_state.get(f"type_{t}", False) for t in type_labels
    )

st.checkbox("すべて選択", key="all_type", on_change=toggle_all_type)

type_cols = st.columns(len(type_labels))
type_checks = {}

for col, t in zip(type_cols, type_labels):
    with col:
        type_checks[t] = st.checkbox(
            t,
            key=f"type_{t}",
            on_change=sync_all_type
        )

TYPE_ORDER = {t: i for i, t in enumerate(type_labels)}

# =========================
# 並び替え
# =========================

st.markdown("**並び替え**")

sort_key = st.selectbox(
    "項目",
    ["曲名（五十音順）", "声部", "区分"],
    index=0
)

sort_order = st.radio(
    "順序",
    ["昇順", "降順"],
    index=0,
    horizontal=True
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
# 検索結果
# =========================

st.divider()
st.subheader("検索結果")

st.markdown(
    f"""
<div style="font-size:22px;font-weight:800;border-bottom:3px solid #6366f1;
padding-bottom:6px;margin-bottom:12px;">
検索結果： {len(filtered_df)} 件
</div>
""",
    unsafe_allow_html=True
)

if filtered_df.empty:
    st.info("条件に一致する楽譜がありません")

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
        base_part = re.sub(r"(二部|三部|四部)", "", r["声部"])
        color = PART_COLOR.get(base_part, "#64748b")

        with cols[i]:
            st.markdown(
f"""
<div style="border-left:8px solid {color};padding:14px;border-radius:12px;
background:#ffffff;height:260px;display:grid;
grid-template-rows:72px 1fr;row-gap:6px;margin-bottom:24px;
color:{TEXT_COLOR};">

<h3 style="margin:0;font-size:20px;font-weight:700;
line-height:1.2;display:-webkit-box;-webkit-line-clamp:2;
-webkit-box-orient:vertical;overflow:hidden;">
{r['曲名']}
</h3>

<div>
<p>作曲・編曲者：{r['作曲・編曲者']}</p>
<p>声部：<span style="color:{color};">{r['声部']}</span></p>

<span style="padding:3px 9px;border-radius:999px;
background:#f1f5f9;font-size:13px;">
{r['区分']}
</span>

<a href="{r['url']}" target="_blank"
style="display:block;margin-top:12px;text-align:center;
padding:9px;border-radius:8px;background:#e5e7eb;
color:{TEXT_COLOR};text-decoration:none;font-weight:600;">
楽譜を開く
</a>
</div>
</div>
""",
                unsafe_allow_html=True
            )

# =========================
# 管理者メニュー
# =========================

if st.session_state.get("is_admin"):
    st.divider()
    st.header("🔧 管理者メニュー")

    st.subheader("🧪 ファイル名チェック")
    if filename_errors:
        st.error(f"{len(filename_errors)} 件のルール違反")
        for n in filename_errors:
            st.write("・", n)
    else:
        st.success("すべて正しい形式です")

    st.subheader("📤 PDFアップロード")
    uploaded = st.file_uploader("PDFを選択", type="pdf")
    is_private = st.checkbox("非公開としてアップロード")

    if uploaded:
        target = PRIVATE_FOLDER_ID if is_private else FOLDER_ID

        if file_exists_in_folder(service, uploaded.name, target):
            st.error("⚠️ 同じ名前のPDFがすでに存在します。")
        else:
            media = MediaIoBaseUpload(
                io.BytesIO(uploaded.read()),
                mimetype="application/pdf",
                resumable=True
            )

            service.files().create(
                body={"name": uploaded.name, "parents": [target]},
                media_body=media,
                supportsAllDrives=True
            ).execute()

            st.success("✅ アップロード完了（再読み込みで反映）")
