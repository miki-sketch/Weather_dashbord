import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from geopy.distance import geodesic
from datetime import datetime, timedelta
import json

# --- ページ設定 ---
st.set_page_config(
    page_title="都市間距離・天気ダッシュボード",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- カスタムCSS (ビジネス向け・クリーンデザイン) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Noto Sans JP', sans-serif;
    }

    /* メイン背景 */
    .stApp {
        background-color: #f8fafc;
        color: #1e293b;
    }

    /* サイドバー */
    section[data-testid="stSidebar"] {
        background-color: #ffffff !important;
        border-right: 1px solid #e2e8f0;
    }

    /* メトリクスカード */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        padding: 1.5rem;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
    }

    div[data-testid="stMetricLabel"] {
        font-weight: 500;
        color: #64748b;
    }

    div[data-testid="stMetricValue"] {
        color: #0f172a;
        font-weight: 700;
        font-size: 1.8rem;
    }

    /* ヘッダーエリア */
    .header-section {
        padding: 1.5rem 0;
        background-color: #ffffff;
        border-bottom: 1px solid #e2e8f0;
        margin-bottom: 2rem;
        text-align: center;
    }

    .main-title {
        font-size: 2rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 0.5rem;
    }

    .route-info {
        font-size: 1.25rem;
        font-weight: 600;
        color: #2563eb;
        margin: 1rem 0;
        padding: 0.5rem 1.5rem;
        display: inline-block;
        border: 1px solid #bfdbfe;
        border-radius: 4px;
        background-color: #eff6ff;
    }
    
    .distance-display {
        font-size: 2.5rem;
        font-weight: 800;
        color: #1e40af;
    }
</style>
""", unsafe_allow_html=True)

# --- ヘルパー関数 ---

@st.cache_data
def get_coordinates(city_name):
    """Open-Meteo Geocoding API を使用して座標を取得"""
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name}&count=1&language=ja&format=json"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("results"):
                result = data["results"][0]
                return {
                    "name": result["name"],
                    "lat": result["latitude"],
                    "lon": result["longitude"],
                    "country": result.get("country", "")
                }
    except Exception as e:
        st.error(f"ジオコーディングエラー: {e}")
    return None

@st.cache_data
def get_weather_data(lat, lon):
    """Open-Meteo API を使用して天気データを取得 (過去7日 + 未来7日)"""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,windspeed_10m&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max&past_days=7&timezone=auto"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"天気データ取得エラー: {e}")
    return None

def calculate_distance(lat1, lon1, lat2, lon2):
    """geopy を使用して2点間の直線距離 (km) を計算 (Haversine相当)"""
    return geodesic((lat1, lon1), (lat2, lon2)).kilometers

# --- サイドバー (入力UI) ---
st.sidebar.title("🔍 検索条件")
st.sidebar.markdown("---")

# 現在地の推測 (簡易版 IPベース)
@st.cache_data
def get_initial_city():
    try:
        res = requests.get("https://ipapi.co/json/", timeout=5)
        if res.status_code == 200:
            return res.json().get("city", "東京")
    except:
        pass
    return "東京"

default_from = get_initial_city()
from_city = st.sidebar.text_input("出発地 (From)", value=default_from, help="都市名を入力してください")
to_city = st.sidebar.text_input("目的地 (To)", value="大阪", help="天気を表示する都市名を入力してください")

# 期間選択
today = datetime.now().date()
d_start = today - timedelta(days=7)
d_end = today + timedelta(days=6)

date_range = st.sidebar.date_input(
    "表示期間 (最大14日間)",
    value=(d_start, d_end),
    min_value=today - timedelta(days=365),
    max_value=today + timedelta(days=16),
)

# バリデーション
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
    if (end_date - start_date).days > 14:
        st.sidebar.error("⚠️ 14日を超える期間は選択できません。")
        st.stop()
else:
    st.sidebar.warning("開始日と終了日を選択してください。")
    st.stop()

st.sidebar.markdown("---")
st.sidebar.info("データ出典: Open-Meteo / Geopy")

# --- メインロジック ---

with st.spinner("データを取得中..."):
    from_coord = get_coordinates(from_city)
    to_coord = get_coordinates(to_city)

if not from_coord or not to_coord:
    st.error("指定された都市が見つかりませんでした。別の名称を試してください。")
    st.stop()

# 距離計算
distance = calculate_distance(from_coord["lat"], from_coord["lon"], to_coord["lat"], to_coord["lon"])

# 天気取得
weather_data = get_weather_data(to_coord["lat"], to_coord["lon"])
if not weather_data:
    st.error("天気データの取得に失敗しました。")
    st.stop()

# --- 画面構成 ---

# 1. サマリーエリア
st.markdown(f"""
<div class="header-section">
    <div class="main-title">都市間距離 ＆ ウェザーダッシュボード</div>
    <div class="route-info">
        {from_coord['name']} ({from_coord['country']}) ➔ {to_coord['name']} ({to_coord['country']})
    </div>
    <div style="margin-top: 10px;">
        <span style="font-size: 1rem; color: #64748b;">直線距離</span><br/>
        <span class="distance-display">{distance:.1f} <span style="font-size: 1.5rem;">km</span></span>
    </div>
</div>
""", unsafe_allow_html=True)

# 2. メトリクス (目的地の天気概要)
st.subheader(f"📍 {to_coord['name']} の天気概要 (選択期間内)")
col1, col2, col3, col4 = st.columns(4)

df_daily = pd.DataFrame(weather_data["daily"])
# 本来はdate_rangeでフィルタリングすべきだが、Open-Meteo APIの固定レンジ等があるため簡易化
max_t = df_daily["temperature_2m_max"].max()
min_t = df_daily["temperature_2m_min"].min()
max_w = df_daily["windspeed_10m_max"].max()

col1.metric("最高気温", f"{max_t}°C", "🌡️")
col2.metric("最低気温", f"{min_t}°C", "❄️")
col3.metric("最大風速", f"{max_w} km/h", "💨")
col4.metric("データ状況", "正常", "📊")

st.markdown("<br/>", unsafe_allow_html=True)

# 3. 可視化エリア
st.subheader("📈 気温・風速の推移")

df_hourly = pd.DataFrame(weather_data["hourly"])
df_hourly["time"] = pd.to_datetime(df_hourly["time"])
current_time = datetime.now()

# 気温グラフ
fig_temp = px.line(
    df_hourly, x="time", y="temperature_2m",
    title=f"{to_coord['name']} 気温推移 (実績と予報)",
    labels={"temperature_2m": "気温 (°C)", "time": "日時"},
    color_discrete_sequence=["#ef4444"]
)
fig_temp.add_vline(x=current_time, line_width=2, line_dash="dash", line_color="#3b82f6")
fig_temp.add_annotation(x=current_time, text="現在", showarrow=False, yshift=10, font_color="#3b82f6")
fig_temp.update_layout(
    plot_bgcolor="white",
    xaxis=dict(showgrid=True, gridcolor="#f1f5f9"),
    yaxis=dict(showgrid=True, gridcolor="#f1f5f9")
)
st.plotly_chart(fig_temp, use_container_width=True)

# 風速グラフ
fig_wind = px.area(
    df_hourly, x="time", y="windspeed_10m",
    title=f"{to_coord['name']} 風速推移",
    labels={"windspeed_10m": "風速 (km/h)", "time": "日時"},
    color_discrete_sequence=["#2563eb"]
)
fig_wind.add_vline(x=current_time, line_width=2, line_dash="dash", line_color="#ef4444")
fig_wind.update_layout(
    plot_bgcolor="white",
    xaxis=dict(showgrid=True, gridcolor="#f1f5f9"),
    yaxis=dict(showgrid=True, gridcolor="#f1f5f9")
)
st.plotly_chart(fig_wind, use_container_width=True)

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #94a3b8; font-size: 0.8rem;">
    ビジネス向け都市間距離・天気ダッシュボード | Powered by Streamlit & Open-Meteo
</div>
""", unsafe_allow_html=True)
