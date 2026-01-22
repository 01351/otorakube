#区分もDriveのファイル情報から直接読み取れるように
#Driveにファイルがないときは0件と表示できるように
#カードの「声　部」を「声部」に
#検索の区分の並びを二部→三部→四部の順に
#すべて選択を反映させる
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

st.set_page_config(page_title="楽譜管理アプリ", layout="wide")
st.title("楽譜管理アプリ")
st.caption("Google Drive 上の楽譜PDFを検索できます")

# =========================
# URL クエリ取得
# =========================

query_params = st.query_params
qp_part = query_params.get("part", None)
qp_type = query_params.get("type", None)

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

PART_BASE_MAP = {"G": "混声", "F": "女声", "M": "男声", "U": "斉唱"}
NUM_MAP = {"2": "二部", "3": "三部", "4": "四部"}
PART_ORDER = ["混声", "女声", "男声", "斉唱"]

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

    part = "斉唱" if p == "U" else f"{PART_BASE_MAP[p]}{NUM_MAP.get(n, '')}"

    return {
        "code": code,
        "曲名": title.strip(),
        "作曲・編曲者": composer,
        "声部": part,
        "区分": TYPE_MAP.get(t, "不明")
    }

# =========================
# Drive 読み込み
# =========================

@st.cache_data(ttl=60, show_spinner=False)
def load_from_drive():
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
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

title_input = st.text_input("🎵 曲名（部分一致）")

composer_list = sorted(df["作曲・編曲者"].dropna().unique().tolist())
composer_input = st.selectbox("👤 作曲・編曲者", ["指定しない"] + composer_list)

# 声部
st.markdown("**声部**")
existing_parts = sorted(
    df["声部"].dropna().unique().tolist(),
    key=lambda x: PART_ORDER.index(re.sub(r"(二部|三部|四部)", "", x))
)

part_checks = {}
cols = st.columns(len(existing_parts))
for col, part in zip(cols, existing_parts):
    with col:
        part_checks[part] = st.checkbox(
            part,
            value=(qp_part == part) if qp_part else True
        )

# 区分
st.markdown("**区分**")
type_checks = {}
cols = st.columns(len(TYPE_MAP))
for col, t in zip(cols, TYPE_MAP.values()):
    with col:
        type_checks[t] = st.checkbox(
            t,
            value=(qp_type == t) if qp_type else True
        )

# =========================
# 検索処理
# =========================

filtered_df = df.copy()

if title_input:
    filtered_df = filtered_df[filtered_df["曲名"].str.contains(title_input, case=False)]

if composer_input != "指定しない":
    filtered_df = filtered_df[filtered_df["作曲・編曲者"] == composer_input]

filtered_df = filtered_df[
    filtered_df["声部"].isin([p for p, v in part_checks.items() if v])
]

filtered_df = filtered_df[
    filtered_df["区分"].isin([t for t, v in type_checks.items() if v])
]

# =========================
# 結果表示
# =========================

st.divider()
st.subheader("検索結果")
st.write(f"{len(filtered_df)} 件")

if filtered_df.empty:
    st.info("Drive に楽譜ファイルがありません")

# =========================
# カード表示（声部リンク化）
# =========================

for row in filtered_df.itertuples():
    base = re.sub(r"(二部|三部|四部)", "", row.声部)
    color = PART_COLOR.get(base, "#64748b")

    part_link = f"?part={row.声部}"
    type_link = f"?type={row.区分}"

    st.markdown(
f"""
<div style="border-left:8px solid {color};padding:14px;margin-bottom:16px;
border-radius:12px;background:#fff;color:{TEXT_COLOR};">

<h3 style="margin:0 0 8px 0;">{row.曲名}</h3>

<p style="margin:0 0 4px 0;">作曲・編曲者：{row.作曲・編曲者}</p>

<p style="margin:0 0 4px 0;">
声部：
<a href="{part_link}" style="color:{color};font-weight:700;text-decoration:none;">
{row.声部}
</a>
</p>

<p style="margin:0 0 8px 0;">
区分：
<a href="{type_link}" style="text-decoration:none;">
{row.区分}
</a>
</p>

<a href="{row.url}" target="_blank"
style="display:inline-block;padding:6px 12px;
border-radius:8px;background:#e5e7eb;text-decoration:none;">
楽譜を開く
</a>

</div>
""",
unsafe_allow_html=True
    )
