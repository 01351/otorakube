#区分もDriveのファイル情報から直接読み取れるように　確認
#Driveにファイルがないときは0件と表示できるように　確認
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
    page_title="楽譜管理システム",
    layout="wide"
)

st.title("楽譜管理システム")
st.caption("Google Drive 上の各フォルダから楽譜を検索できます")

# =========================
# Google Drive 設定
# =========================
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
# 親フォルダのID
PARENT_FOLDER_ID = "1c0JC6zLnipbJcP-2Dfe0QxXNQikSo3hm"

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

TEXT_COLOR = "#0f172a"

# =========================
# ファイル名解析
# =========================
def parse_filename(filename):
    # 例: 01合唱曲名-AG4作曲者.pdf
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
# Google Drive 読み込み（子フォルダ対応）
# =========================
@st.cache_data(ttl=60, show_spinner="Google Driveからデータを取得中...")
def load_all_data_from_drive():
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    service = build("drive", "v3", credentials=credentials)

    # 1. 親フォルダ内の「フォルダ」一覧を取得
    folder_results = service.files().list(
        q=f"'{PARENT_FOLDER_ID}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        fields="files(id, name)"
    ).execute()
    
    folders = folder_results.get("files", [])
    
    # フォルダが見つからない場合は空のリストを返す
    if not folders:
        # 親フォルダ直下にファイルがある可能性を考慮して親フォルダ自身をリストに入れる
        folders = [{"id": PARENT_FOLDER_ID, "name": "全楽譜"}]

    all_rows = []
    
    # 2. 各フォルダ内のPDFをスキャン
    for folder in folders:
        f_id = folder["id"]
        f_name = folder["name"]
        
        file_results = service.files().list(
            q=f"'{f_id}' in parents and trashed=false and mimeType='application/pdf'",
            fields="files(name, webViewLink)"
        ).execute()

        for f in file_results.get("files", []):
            parsed = parse_filename(f["name"])
            if parsed:
                parsed.update({
                    "url": f["webViewLink"],
                    "folder_name": f_name
                })
                all_rows.append(parsed)

    df = pd.DataFrame(all_rows)
    if not df.empty:
        df = df.sort_values("code")
    
    return df, [f["name"] for f in folders]

# データ読み込み実行
df_all, folder_names = load_all_data_from_drive()

if df_all.empty:
    st.warning("楽譜ファイルが見つかりませんでした。Google DriveのフォルダIDやファイル名規則を確認してください。")
    st.stop()

# =========================
# メイン表示（タブ分け）
# =========================
st.markdown("### 📂 カテゴリ選択")
tabs = st.tabs(folder_names)

for i, tab in enumerate(tabs):
    current_folder = folder_names[i]
    
    with tab:
        # このタブ（フォルダ）に属するデータのみ抽出
        df = df_all[df_all["folder_name"] == current_folder].copy()
        
        if df.empty:
            st.info(f"「{current_folder}」内に対象のPDFはありません。")
            continue

        # --- 検索UI ---
        col1, col2 = st.columns([2, 1])
        with col1:
            title_input = st.text_input("🎵 曲名（部分一致）", key=f"search_{current_folder}")
        with col2:
            composer_list = sorted(df["作曲・編曲者"].dropna().unique().tolist())
            composer_input = st.selectbox("👤 作曲・編曲者", ["指定しない"] + composer_list, key=f"comp_{current_folder}")

        # --- フィルタリング ---
        filtered_df = df.copy()
        if title_input:
            filtered_df = filtered_df[filtered_df["曲名"].str.contains(title_input, case=False, na=False)]
        if composer_input != "指定しない":
            filtered_df = filtered_df[filtered_df["作曲・編曲者"] == composer_input]

        # --- 結果表示 ---
        st.markdown(f"**検索結果： {len(filtered_df)} 件**")
        st.divider()

        # --- カード表示（3列グリッド） ---
        cards_per_row = 3
        for row_idx in range(0, len(filtered_df), cards_per_row):
            row_df = filtered_df.iloc[row_idx:row_idx + cards_per_row]
            cols = st.columns(cards_per_row)

            for col_idx, (_, r) in enumerate(row_df.iterrows()):
                base_part = re.sub(r"(二部|三部|四部)", "", r["声部"])
                color = PART_COLOR.get(base_part, "#64748b")
                
                with cols[col_idx]:
                    st.markdown(f"""
                        <div style="
                            border-left:8px solid {color};
                            padding:16px;
                            border-radius:12px;
                            background:#ffffff;
                            border:1px solid #e2e8f0;
                            height:260px;
                            display:flex;
                            flex-direction:column;
                            justify-content:space-between;
                            margin-bottom:20px;
                            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                        ">
                            <div>
                                <h3 style="margin:0; font-size:18px; color:{TEXT_COLOR}; font-weight:700;">{r['曲名']}</h3>
                                <p style="margin:8px 0; font-size:14px; color:#475569;">
                                    👤 {r['作曲・編曲者']}<br>
                                    🎤 声部：<span style="color:{color}; font-weight:bold;">{r['声部']}</span>
                                </p>
                                <span style="display:inline-block; padding:2px 10px; border-radius:12px; background:#f1f5f9; font-size:12px; color:#64748b;">
                                    {r['区分']}
                                </span>
                            </div>
                            <a href="{r['url']}" target="_blank" style="
                                display:block;
                                width:100%;
                                padding:10px 0;
                                text-align:center;
                                background:#f8fafc;
                                border:1px solid #cbd5e1;
                                border-radius:8px;
                                color:{TEXT_COLOR};
                                text-decoration:none;
                                font-weight:600;
                                font-size:14px;
                            ">
                                📄 楽譜を開く
                            </a>
                        </div>
                    """, unsafe_allow_html=True)
