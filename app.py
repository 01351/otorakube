import streamlit as st
import pandas as pd
import unicodedata
import gspread
from google.oauth2.service_account import Credentials

# ======================
# 基本設定
# ======================
st.set_page_config(page_title="合唱楽譜検索", layout="wide")
st.title("🎶 合唱楽譜データベース")

# ======================
# 定数
# ======================
PART_OPTIONS = ["混声四部", "女声三部", "男声四部", "児童合唱"]

# ======================
# 文字正規化（検索用）
# ======================
def normalize(text):
    if pd.isna(text):
        return ""
    return unicodedata.normalize("NFKC", str(text)).lower()

# ======================
# Google Drive / Sheets 読み込み
# ======================
def load_from_drive():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]

    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes,
    )

    gc = gspread.authorize(credentials)

    # ← あなたが Secrets に入れた FOLDERID
    folder_id = st.secrets["1c0JC6zLnipbJcP-2Dfe0QxXNQikSo3hm"]

    sh = gc.open_by_key(folder_id)
    worksheet = sh.sheet1
    data = worksheet.get_all_records()

    df = pd.DataFrame(data)
    return df

# ======================
# データ読み込み
# ======================
@st.cache_data
def load_data():
    return load_from_drive()

df = load_data()

# ======================
# 検索UI
# ======================
st.subheader("🔍 検索")

col1, col2, col3 = st.columns(3)

with col1:
    title_input = st.text_input("曲名")

with col2:
    composer_input = st.text_input("作曲者")

with col3:
    part_input = st.multiselect("声部", PART_OPTIONS)

# 並び替え
sort_option = st.radio(
    "並び替え",
    ["五十音順", "題名順", "作曲者順"],
    horizontal=True
)

# ======================
# フィルタ処理
# ======================
filtered_df = df.copy()

if title_input:
    key = normalize(title_input)
    filtered_df = filtered_df[
        filtered_df["title"].apply(lambda x: key in normalize(x))
    ]

if composer_input:
    key = normalize(composer_input)
    filtered_df = filtered_df[
        filtered_df["composer"].apply(lambda x: key in normalize(x))
    ]

if part_input:
    filtered_df = filtered_df[
        filtered_df["part"].isin(part_input)
    ]

# 並び替え
if not filtered_df.empty:
    if sort_option == "五十音順":
        filtered_df = filtered_df.sort_values("code")
    elif sort_option == "題名順":
        filtered_df = filtered_df.sort_values("title")
    elif sort_option == "作曲者順":
        filtered_df = filtered_df.sort_values("composer")

# ======================
# 結果表示
# ======================
st.subheader("📄 検索結果")

if filtered_df.empty:
    st.info("該当する楽譜がありません")
else:
    st.dataframe(
        filtered_df[["title", "composer", "part"]],
        use_container_width=True
    )

# ======================
# 楽譜プレビュー
# ======================
st.subheader("👀 楽譜プレビュー")

if not filtered_df.empty:
    selected_title = st.selectbox(
        "プレビューする楽譜を選択",
        filtered_df["title"]
    )

    selected_row = filtered_df[
        filtered_df["title"] == selected_title
    ].iloc[0]

    st.components.v1.iframe(
        selected_row["url"],
        height=650
    )
