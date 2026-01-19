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
st.caption("Google Drive 上の楽譜PDFを、曲名・作曲者・声部・区分で検索できます")

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

PART_ORDER = ["混声", "女声", "男声", "斉唱"]

PART_COLOR = {
    "混声": "#2563eb",
    "女声": "#db2777",
    "男声": "#16a34a",
    "斉唱": "#9333ea"
}

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
        "作曲者": composer,
        "声部": part,
        "区分": TYPE_MAP[t]
    }

# =========================
# Google Drive 読み込み
# =========================

@st.cache_data(ttl=60, show_spinner=False)
def load_from_drive():
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )

    service = build("drive", "v3", credentials=credentials)

    results = service.files().list(
        q=f"'{FOLDER_ID}' in parents and trashed=false and mimeType='application/pdf'",
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

df = load_from_drive()

# =========================
# 検索UI
# =========================

st.divider()
st.subheader("検索")

title_input = st.text_input("曲名（部分一致）")

composer_list = sorted(df["作曲者"].dropna().unique().tolist())
composer_input = st.selectbox("作曲者", ["指定しない"] + composer_list)

# 声部（横一列チェック）
st.markdown("**声部**")

existing_parts = sorted(
    df["声部"].dropna().unique().tolist(),
    key=lambda x: PART_ORDER.index(re.sub(r"(二部|三部|四部)", "", x))
)

part_cols = st.columns(len(existing_parts))
part_checks = {}

for col, part in zip(part_cols, existing_parts):
    with col:
        part_checks[part] = st.checkbox(part, value=True)

# 区分（横一列チェック）
st.markdown("**区分**")

type_cols = st.columns(len(TYPE_MAP))
type_checks = {}

for col, t in zip(type_cols, TYPE_MAP.values()):
    with col:
        type_checks[t] = st.checkbox(t, value=True)

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
        filtered_df["作曲者"] == composer_input
    ]

filtered_df = filtered_df[
    filtered_df["声部"].isin([p for p, v in part_checks.items() if v])
]

filtered_df = filtered_df[
    filtered_df["区分"].isin([t for t, v in type_checks.items() if v])
]

# =========================
# 検索結果（カード型）
# =========================

st.divider()
st.subheader("検索結果")
st.write(f"{len(filtered_df)} 件")

if filtered_df.empty:
    st.info("該当する楽譜がありません")
else:
    cards_per_row = 3
    rows = [
        filtered_df.iloc[i:i + cards_per_row]
        for i in range(0, len(filtered_df), cards_per_row)
    ]

    for row_df in rows:
        cols = st.columns(len(row_df))
        for col, (_, r) in zip(cols, row_df.iterrows()):
            base_part = re.sub(r"(二部|三部|四部)", "", r["声部"])
            color = PART_COLOR.get(base_part, "#666666")

            with col:
                st.markdown(
                    f"""
                    <div style="
                        border-left: 8px solid {color};
                        padding: 16px;
                        border-radius: 10px;
                        background-color: #ffffff;
                        color: #000000;
                        margin-bottom: 12px;
                    ">
                        <h3 style="margin-top:0; color:#000000;">
                            {r['曲名']}
                        </h3>
                        <p style="color:#000000;">
                            <strong>作曲者</strong>：{r['作曲者']}
                        </p>
                        <p>
                            <strong style="color:#000000;">声部</strong>：
                            <span style="color:{color}; font-weight:600;">
                                {r['声部']}
                            </span>
                        </p>
                        <p style="color:#000000;">
                            <strong>区分</strong>：{r['区分']}
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                st.link_button("楽譜を開く", r["url"])
