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

# =========================
# 定義マップ
# =========================

TYPE_MAP = {
    "A": "オリジナル（伴奏有）",
    "B": "オリジナル（無伴奏）",
    "C": "アレンジ",
    "D": "特殊"
}

PART_COLOR = {
    "混声": "#16a34a",
    "女声": "#db2777",
    "男声": "#2563eb",
    "斉唱": "#9333ea"
}

PART_ORDER = ["混声", "女声", "男声", "斉唱"]

TEXT_COLOR = "#0f172a"

# =========================
# ファイル名解析（フォールバック用）
# =========================

def parse_filename(filename):
    pattern = r"^(\d{2})(.+?)-([ABCD])([GFMU])([234]?)(.+)\.pdf$"
    m = re.match(pattern, filename)
    if not m:
        return None

    code, title, t, p, n, composer = m.groups()
    composer = composer.replace("★", "").strip()

    base_map = {"G": "混声", "F": "女声", "M": "男声", "U": "斉唱"}
    num_map = {"2": "二部", "3": "三部", "4": "四部"}

    part = base_map.get(p, "") + num_map.get(n, "")

    return {
        "code": code,
        "曲名": title.strip(),
        "作曲・編曲者": composer,
        "声部": part,
        "区分": TYPE_MAP.get(t, "不明")
    }

# =========================
# Drive description 解析
# =========================

def parse_description(desc: str):
    """
    description から 区分 / 声部 を取得
    """
    result = {}
    if not desc:
        return result

    for line in desc.splitlines():
        if "区分=" in line:
            code = line.replace("区分=", "").strip()
            result["区分"] = TYPE_MAP.get(code, code)
        if "声部=" in line:
            result["声部"] = line.replace("声部=", "").strip()

    return result

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
        fields="files(name, description, webViewLink)"
    ).execute()

    rows = []
    for f in results.get("files", []):
        base = parse_filename(f["name"])
        if not base:
            continue

        desc_data = parse_description(f.get("description", ""))

        rows.append({
            "code": base["code"],
            "曲名": base["曲名"],
            "作曲・編曲者": base["作曲・編曲者"],
            "声部": desc_data.get("声部", base["声部"]),
            "区分": desc_data.get("区分", base["区分"]),
            "url": f["webViewLink"]
        })

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

col1, col2 = st.columns([2, 1])
with col1:
    title_input = st.text_input("🎵 曲名（部分一致）")
with col2:
    composer_list = sorted(df["作曲・編曲者"].dropna().unique().tolist())
    composer_input = st.selectbox("👤 作曲・編曲者", ["指定しない"] + composer_list)

st.caption("▼ 詳細条件")

# 声部
st.markdown("**声部**")
existing_parts = sorted(
    df["声部"].dropna().unique().tolist(),
    key=lambda x: PART_ORDER.index(re.sub(r"(二部|三部|四部)", "", x))
)

all_part = st.checkbox("すべて選択", value=True)
part_cols = st.columns(len(existing_parts))
part_checks = {
    part: part_cols[i].checkbox(part, value=all_part)
    for i, part in enumerate(existing_parts)
}

# 区分
st.markdown("**区分**")
all_type = st.checkbox("すべて選択", value=True)
type_values = sorted(df["区分"].dropna().unique().tolist())
type_cols = st.columns(len(type_values))
type_checks = {
    t: type_cols[i].checkbox(t, value=all_type)
    for i, t in enumerate(type_values)
}

# =========================
# 検索処理
# =========================

filtered_df = df.copy()

if title_input:
    filtered_df = filtered_df[filtered_df["曲名"].str.contains(title_input, case=False)]

if composer_input != "指定しない":
    filtered_df = filtered_df[filtered_df["作曲・編曲者"] == composer_input]

filtered_df = filtered_df[
    filtered_df["声部"].isin([k for k, v in part_checks.items() if v])
]

filtered_df = filtered_df[
    filtered_df["区分"].isin([k for k, v in type_checks.items() if v])
]

# =========================
# 検索結果
# =========================

st.divider()
st.subheader("検索結果")
st.write(f"{len(filtered_df)} 件")

if filtered_df.empty:
    st.info("該当する楽譜がありません")

# =========================
# カード表示
# =========================

cards_per_row = 3
rows = [filtered_df.iloc[i:i + cards_per_row] for i in range(0, len(filtered_df), cards_per_row)]

for row_df in rows:
    cols = st.columns(cards_per_row)

    for i in range(cards_per_row):
        if i >= len(row_df):
            cols[i].empty()
            continue

        r = row_df.iloc[i]
        base_part = re.sub(r"(二部|三部|四部)", "", r["声部"])
        color = PART_COLOR.get(base_part, "#64748b")

        with cols[i]:
            st.markdown(
f"""
<style>
.score-btn:active {{ background:#c7d2fe !important; }}
</style>

<div style="
border-left:8px solid {color};
padding:14px;
border-radius:12px;
background:#ffffff;
height:260px;
display:grid;
grid-template-rows:72px 1fr;
row-gap:6px;
margin-bottom:24px;
color:{TEXT_COLOR};
">

<div style="display:flex;align-items:center;">
<h3 style="
margin:0;
font-size:20px;
font-weight:700;
line-height:1.2;
display:-webkit-box;
-webkit-line-clamp:2;
-webkit-box-orient:vertical;
overflow:hidden;
">
{r['曲名']}
</h3>
</div>

<p style="font-size:16px;margin:0;">作曲・編曲者：{r['作曲・編曲者']}</p>
<p style="font-size:16px;margin:0;">声　部：<span style="color:{color};">{r['声部']}</span></p>
<span style="font-size:13px;margin:4px 0;">{r['区分']}</span>

<a href="{r['url']}" target="_blank"
class="score-btn"
style="
display:block;
width:90%;
margin:12px auto 0;
text-align:center;
padding:9px;
border-radius:8px;
background:#e5e7eb;
color:{TEXT_COLOR};
text-decoration:none;
font-weight:600;
">
楽譜を開く
</a>
</div>
""",
unsafe_allow_html=True
            )
