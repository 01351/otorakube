import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# =====================
# Google 認証
# =====================
def get_gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes,
    )
    return gspread.authorize(credentials)

# =====================
# データ読み込み
# =====================
@st.cache_data
def load_data():
    gc = get_gspread_client()
    sh = gc.open_by_key(st.secrets["SPREADSHEET_KEY"])
    ws = sh.sheet1
    records = ws.get_all_records()
    return pd.DataFrame(records)

# =====================
# 作曲者名の ★ を除去
# =====================
def normalize_composer(name):
    if not isinstance(name, str):
        return ""
    return name.replace("★", "").strip()

# =====================
# 画面
# =====================
st.title("楽曲一覧")

df = load_data()

# 作曲者正規化列を作る
df["作曲者_正規化"] = df["作曲者"].apply(normalize_composer)

# =====================
# フィルタUI
# =====================

# ②：一覧から選択
no2_list = sorted(df["②"].astype(str).unique())
selected_no2 = st.selectbox("② を選択", no2_list)

# 作曲者：★除去後一覧から選択
composer_list = sorted(df["作曲者_正規化"].unique())
selected_composer = st.selectbox("作曲者を選択", composer_list)

# =====================
# フィルタ処理
# =====================
filtered_df = df[
    (df["②"].astype(str) == selected_no2) &
    (df["作曲者_正規化"] == selected_composer)
]

# =====================
# 表示
# =====================
st.subheader("検索結果")
st.dataframe(filtered_df.drop(columns=["作曲者_正規化"]))
