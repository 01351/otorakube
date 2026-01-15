import streamlit as st
import pandas as pd

# =========================
# アプリの基本設定
# =========================

st.set_page_config(page_title="楽譜管理アプリ", layout="wide")

st.title("🎼 楽譜管理アプリ（OneDrive対応）")

st.write("""
OneDriveに保存している楽譜を  
**題名・作曲者・声部**で検索できます。
""")

# =========================
# データの読み込み
# =========================

@st.cache_data
def load_data():
    return pd.read_csv("scores.csv")

df = load_data()

# =========================
# 検索欄
# =========================

st.subheader("🔍 検索条件")

col1, col2, col3 = st.columns(3)

with col1:
    title_input = st.text_input("題名")

with col2:
    composer_input = st.text_input("作曲者")

with col3:
    part_input = st.selectbox(
        "声部",
        ["", "Soprano", "Alto", "Tenor", "Bass", "SATB", "女声", "混声"]
    )

# =========================
# 検索処理
# =========================

filtered_df = df.copy()

if title_input:
    filtered_df = filtered_df[
        filtered_df["title"].str.contains(title_input, case=False, na=False)
    ]

if composer_input:
    filtered_df = filtered_df[
        filtered_df["composer"].str.contains(composer_input, case=False, na=False)
    ]

if part_input:
    filtered_df = filtered_df[
        filtered_df["part"].str.contains(part_input, case=False, na=False)
    ]

# =========================
# 検索結果表示
# =========================

st.subheader("📄 検索結果")

# 件数表示（改善③）
st.write(f"🔎 {len(filtered_df)} 件の楽譜が見つかりました")

if filtered_df.empty:
    st.warning("該当する楽譜が見つかりませんでした。")
else:
    # テーブル表示（改善②）
    st.dataframe(
        filtered_df[["title", "composer", "part", "url"]],
        use_container_width=True
    )
