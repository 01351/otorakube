import streamlit as st
import pandas as pd

# =========================
# アプリの基本設定
# =========================

# ブラウザのタブに表示されるタイトル
st.set_page_config(page_title="楽譜管理アプリ", layout="wide")

# アプリの見出し
st.title("🎼 楽譜管理アプリ（OneDrive対応）")

# 説明文
st.write("""
OneDriveに保存している楽譜を  
**題名・作曲者・声部**で検索できます。
""")

# =========================
# データの読み込み
# =========================

# CSVファイルを読み込む
# scores.csv は app.py と同じフォルダに置いてください
@st.cache_data
def load_data():
    return pd.read_csv("scores.csv")

df = load_data()

# =========================
# 検索欄
# =========================

st.subheader("🔍 検索条件")

# 3列に分けて入力欄を配置
col1, col2, col3 = st.columns(3)

with col1:
    title_input = st.text_input("題名")

with col2:
    composer_input = st.text_input("作曲者")

with col3:
    part_input = st.text_input("声部（Soprano / Alto / Tenor など）")

# =========================
# 検索処理
# =========================

# 検索用のデータフレームをコピー
filtered_df = df.copy()

# 題名で検索（入力があれば）
if title_input:
    filtered_df = filtered_df[
        filtered_df["title"].str.contains(title_input, case=False, na=False)
    ]

# 作曲者で検索
if composer_input:
    filtered_df = filtered_df[
        filtered_df["composer"].str.contains(composer_input, case=False, na=False)
    ]

# 声部で検索
if part_input:
    filtered_df = filtered_df[
        filtered_df["part"].str.contains(part_input, case=False, na=False)
    ]

# =========================
# 検索結果表示
# =========================

st.subheader("📄 検索結果")

if filtered_df.empty:
    st.warning("該当する楽譜が見つかりませんでした。")
else:
    # 1件ずつ表示
    for _, row in filtered_df.iterrows():
        st.markdown(f"""
**🎵 題名**：{row['title']}  
**👤 作曲者**：{row['composer']}  
**🎶 声部**：{row['part']}  
🔗 [楽譜を開く]({row['url']})
---
""")
