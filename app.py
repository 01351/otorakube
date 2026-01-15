import streamlit as st
import pandas as pd

# =========================
# アプリの基本設定
# =========================

st.set_page_config(page_title="楽譜管理アプリ", layout="wide")
st.title("🎼 楽譜管理アプリ（OneDrive対応）")

st.write("""
OneDriveに保存している楽譜を  
**題名・作曲者・声部**で検索・管理できます。
""")

CSV_PATH = "scores.csv"

# =========================
# データ読み込み・保存
# =========================

@st.cache_data
def load_data():
    return pd.read_csv(CSV_PATH)

def save_data(df):
    df.to_csv(CSV_PATH, index=False)
    st.cache_data.clear()

df = load_data()

# =========================
# 楽譜の追加画面
# =========================

st.subheader("➕ 楽譜を追加")

with st.form("add_score_form"):
    col1, col2 = st.columns(2)

    with col1:
        new_title = st.text_input("題名")
        new_composer = st.text_input("作曲者")

    with col2:
        new_part = st.selectbox(
            "声部",
            ["混声四部", "混声三部", "女声", "男声", "斉唱"]
        )
        new_url = st.text_input("OneDriveリンク")

    submitted = st.form_submit_button("追加")

    if submitted:
        if new_title and new_composer and new_url:
            new_row = pd.DataFrame([{
                "title": new_title,
                "composer": new_composer,
                "part": new_part,
                "url": new_url
            }])
            df = pd.concat([df, new_row], ignore_index=True)
            save_data(df)
            st.success("楽譜を追加しました")
            st.rerun()
        else:
            st.error("すべての項目を入力してください")

# =========================
# 検索欄
# =========================

st.subheader("🔍 検索条件")

col1, col2, col3 = st.columns(3)

with col1:
    title_input = st.text_input("題名で検索")

with col2:
    composer_input = st.text_input("作曲者で検索")

with col3:
    part_input = st.selectbox(
        "声部",
        ["", "混声四部", "混声三部", "女声", "男声", "斉唱"]
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
# 検索結果 & 編集画面
# =========================

st.subheader("📄 検索結果")

st.write(f"🔎 {len(filtered_df)} 件の楽譜が見つかりました")

if filtered_df.empty:
    st.warning("該当する楽譜が見つかりませんでした。")
else:
    edited_df = st.data_editor(
        filtered_df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "url": st.column_config.LinkColumn(
                "楽譜リンク",
                display_text="開く"
            ),
            "part": st.column_config.SelectboxColumn(
                "声部",
                options=["混声四部", "混声三部", "女声", "男声", "斉唱"]
            )
        }
    )

    if st.button("💾 編集内容を保存"):
        save_data(edited_df)
        st.success("保存しました")
        st.rerun()
