import streamlit as st

st.set_page_config(layout="wide")

# -----------------------------
# ダミーデータ
# -----------------------------
data = [
    {
        "曲名": "いのちの名前",
        "作曲者": "西村翼",
        "声部": "混声三部",
        "区分": "合唱曲",
        "url": "https://example.com",
    },
    {
        "曲名": "群青",
        "作曲者": "西村翼",
        "声部": "男声四部",
        "区分": "男声合唱",
        "url": "https://example.com",
    },
]

# -----------------------------
# 色設定（明示）
# -----------------------------
VOICE_COLOR = {
    "混声": "#2563eb",  # 青
    "男声": "#16a34a",  # 緑
}

TEXT_MAIN = "#e5e7eb"    # ダークモード対応
TEXT_SUB = "#cbd5f5"
TEXT_MUTE = "#94a3b8"
CARD_BG = "#0f172a"
BUTTON_BG = "#475569"
BUTTON_HOVER = "#334155"

# -----------------------------
# 表示
# -----------------------------
cols = st.columns(2, gap="large")

for i, r in enumerate(data):
    col = cols[i % 2]

    voice_key = "混声" if "混声" in r["声部"] else "男声"
    color = VOICE_COLOR[voice_key]

    with col:
        st.markdown(
f"""
<div style="
background:{CARD_BG};
border-left:8px solid {color};
border-radius:14px;
padding:16px;
height:320px;
display:flex;
flex-direction:column;
justify-content:space-between;
">

<!-- 上部情報 -->
<div>

<!-- 曲名（高さ固定） -->
<div style="
min-height:56px;
display:flex;
align-items:center;
">
<h3 style="
margin:0;
font-size:20px;
font-weight:700;
color:{TEXT_MAIN};
line-height:1.3;
">
{r['曲名']}
</h3>
</div>

<p style="
margin:4px 0 6px 0;
font-size:13px;
color:{TEXT_MUTE};
">
作曲者：{r['作曲者']}
</p>

<p style="
margin:0 0 6px 0;
font-size:14px;
color:{TEXT_SUB};
">
声部：
<span style="color:{color};">
{r['声部']}
</span>
</p>

<span style="
display:inline-block;
padding:3px 10px;
border-radius:999px;
background:#1e293b;
font-size:12px;
color:{TEXT_SUB};
">
{r['区分']}
</span>

</div>

<!-- ボタン -->
<a href="{r['url']}" target="_blank"
style="
display:block;
text-align:center;
padding:9px;
border-radius:8px;
background:{BUTTON_BG};
color:{TEXT_MAIN};
text-decoration:none;
font-size:14px;
font-weight:500;
margin-top:8px;
"
onmouseover="this.style.background='{BUTTON_HOVER}'"
onmouseout="this.style.background='{BUTTON_BG}'"
>
楽譜を開く
</a>

</div>
""",
unsafe_allow_html=True
        )
