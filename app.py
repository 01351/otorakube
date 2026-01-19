import streamlit as st
import pandas as pd
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build

# =====================
# 基本設定
# =====================
st.set_page_config(
    page_title="楽譜検索（デバッグ）",
    layout="wide"
)

DRIVE_FOLDER_ID = "1c0JC6zLnipbJcP-2Dfe0QxXNQikSo3hm"

# =====================
# Google Drive 接続
# =====================
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=["https://www.googleapis.com/auth/drive.readonly"],
)

drive_service = build("drive", "v3", credentials=credentials)

# =====================
# Drive からファイル取得（リアルタイム）
# =====================
def fetch_drive_files():
    try:
        results = drive_service.files().list(
            q=f"'{DRIVE_FOLDER_ID}' in parents and trashed = false",
            fields="files(id, name)"
        ).execute()
    except Exception as e:
        st.error("Drive API エラー")
        st.exception(e)
        return pd.DataFrame(
            columns=["曲名", "作曲者", "声部", "声部種別", "区分", "url"]
        )

    files = results.get("files", [])

    # 🔍 ファイル一覧（最重要デバッグ）
    st.markdown("## 📂 Driveから取得した生ファイル一覧")
    st.write(files)
    st.write("取得ファイル数:", len(files))

    rows = []

    for f in files:
        name = f.get("name", "")

        # 命名規則：曲名__作曲者__声部__区分.pdf
        base = name.replace(".pdf", "")
        parts = base.split("__")

        if len(parts) < 4:
            continue

        title, composer, part, category = parts[:4]

        composer = re.sub(r"[★☆]", "", composer)

        if part.startswith("斉唱"):
            part_display = "斉唱"
            part_type = "斉唱"
        else:
            part_display = part
            part_type = re.sub(r"[二三四1234]部?", "", part)

        rows.append({
            "曲名": title,
            "作曲者": composer,
            "声部": part_display,
            "声部種別": part_type,
            "区分": category,
            "url": f"https://drive.google.com/file/d/{f['id']}/view"
        })

    # 🔴 0件でもカラム保証
    return pd.DataFrame(
        rows,
        columns=["曲名", "作曲者", "声部", "声部種別", "区分", "url"]
    )

# =====================
# データ取得
# =====================
df = fetch_drive_files()

# =====================
# DataFrame デバッグ表示
# =====================
st.markdown("## 🧪 DataFrame デバッグ確認")

st.write("件数:", len(df))
st.write("カラム一覧:", df.columns.tolist())
st.write("DataFrame中身:")
st.write(df)

# =====================
# 声部・区分・作曲者のユニーク値確認
# =====================
st.markdown("## 🔎 カラム別ユニーク値確認")

if not df.empty:
    st.write("声部種別:", df["声部種別"].dropna().unique().tolist())
    st.write("区分:", df["区分"].dropna().unique().tolist())
    st.write("作曲者:", df["作曲者"].dropna().unique().tolist())
else:
    st.warning("DataFrame が空です。Drive から 0 件です。")

st.markdown("---")
st.info("ここまでがデバッグ確認用コードです。UIはまだ有効化していません。")
