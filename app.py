#Driveにファイルがないときは0件と表示できるように　確認
#区分がPの場合、区分名は「ピアノ」で声部は「なし」命名規則も声部は飛ばして作曲者を読みとる
#作曲者はサイト内にふりがなの入力リストを作って、新規の作曲者も追加できるように
#検索の作曲者は五十音順に並び替え、リストにない作曲者は上に表示

import streamlit as st
import re

# =========================
# 並び順定義
# =========================

PART_ORDER = {"混声": 0, "女声": 1, "男声": 2}
DIVISION_ORDER = {"二部": 0, "三部": 1, "四部": 2}
TYPE_ORDER = {
    "オリジナル(伴奏有)": 0,
    "オリジナル(無伴奏)": 1,
    "アレンジ": 2,
    "特殊": 3
}

def order_val(dic, key):
    return dic.get(key, 99)

# =========================
# session_state 初期化
# =========================

def init_state(keys, default=True):
    for k in keys:
        if k not in st.session_state:
            st.session_state[k] = default

# =========================
# ダミーデータ（Drive想定）
# =========================

files = [
    {"title": "Ave Maria", "part": "混声", "division": "四部", "type": "オリジナル(伴奏有)"},
    {"title": "Gloria", "part": "女声", "division": "三部", "type": "アレンジ"},
    {"title": "Kyrie", "part": "男声", "division": "二部", "type": "特殊"},
    {"title": "Sanctus", "part": "混声", "division": "二部", "type": "オリジナル(無伴奏)"},
]

# =========================
# UI
# =========================

st.set_page_config(page_title="楽譜管理", layout="wide")
st.title("楽譜管理アプリ")

view_mode = st.radio(
    "表示形式",
    ["カード表示", "一覧表示"],
    horizontal=True
)

# =========================
# 検索条件抽出
# =========================

parts = sorted({f["part"] for f in files}, key=lambda x: order_val(PART_ORDER, x))
types = sorted({f["type"] for f in files}, key=lambda x: order_val(TYPE_ORDER, x))

# =========================
# 検索UI（声部）
# =========================

if len(parts) > 1:
    init_state([f"part_{p}" for p in parts])
    st.markdown("### 声部")

    all_part = st.checkbox(
        "すべて選択（声部）",
        value=all(st.session_state[f"part_{p}"] for p in parts)
    )

    if all_part:
        for p in parts:
            st.session_state[f"part_{p}"] = True

    for p in parts:
        st.checkbox(p, key=f"part_{p}")

else:
    st.session_state[f"part_{parts[0]}"] = True

# =========================
# 検索UI（区分）
# =========================

if len(types) > 1:
    init_state([f"type_{t}" for t in types])
    st.markdown("### 区分")

    all_type = st.checkbox(
        "すべて選択（区分）",
        value=all(st.session_state[f"type_{t}"] for t in types)
    )

    if all_type:
        for t in types:
            st.session_state[f"type_{t}"] = True

    for t in types:
        st.checkbox(t, key=f"type_{t}")

else:
    st.session_state[f"type_{types[0]}"] = True

# =========================
# フィルタ
# =========================

filtered = [
    f for f in files
    if st.session_state.get(f"part_{f['part']}", True)
    and st.session_state.get(f"type_{f['type']}", True)
]

# =========================
# 並び替え（唯一の正解ルート）
# =========================

filtered.sort(
    key=lambda f: (
        order_val(PART_ORDER, f["part"]),
        order_val(DIVISION_ORDER, f["division"]),
        order_val(TYPE_ORDER, f["type"]),
        f["title"]
    )
)

# =========================
# 表示
# =========================

if view_mode == "カード表示":
    for i in range(0, len(filtered), 3):
        cols = st.columns(3)
        for col, f in zip(cols, filtered[i:i+3]):
            with col:
                st.markdown(
                    f"""
                    ### {f['title']}
                    **声部**：{f['part']}  
                    **編成**：{f['division']}  
                    **区分**：{f['type']}
                    """
                )
else:
    for f in filtered:
        st.write(
            f"{f['title']}｜{f['part']}｜{f['division']}｜{f['type']}"
        )
