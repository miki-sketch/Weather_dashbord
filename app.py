import streamlit as st
import yaml
import os
import json
import re
import requests
import gspread
import datetime  # [追加]
from google.oauth2.service_account import Credentials
from typing import Optional

# ============================================================
# ページ設定 (必ず最初に呼ぶ)
# ============================================================
st.set_page_config(
    page_title="富士ミネラル向けタリフ",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# 起点住所（変更時はここを修正）
# ============================================================
ORIGIN_ADDRESS = "〒409-3611 山梨県西八代郡市川三郷町大塚1125"

# ============================================================
# ログシート名定数  [追加]
# ============================================================
LOG_SHEET_NAME = "検索結果"
LOG_HEADERS = [
    "検索日時", "参照タリフ年度", "行先", "マッチ種別",
    "入力重量(kg)", "適用重量(kg)",
    "実走行距離(km)", "適用タリフ距離(km)", "運賃(円)"
]

# ============================================================
# カスタム CSS (スマホ・PC 両対応)
# ============================================================
st.markdown("""
<style>
.block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
.fare-result-box {
    font-size: 3.5rem;
    font-weight: bold;
    color: #0d6efd;
    text-align: center;
    padding: 28px 20px;
    background: linear-gradient(135deg, #e8f4fd, #f0f8ff);
    border-radius: 16px;
    border: 2px solid #0d6efd;
    margin: 16px 0;
    box-shadow: 0 4px 12px rgba(13,110,253,0.15);
    letter-spacing: 0.04em;
}
.ref-box {
    background-color: #f8f9fa;
    padding: 14px 18px;
    border-radius: 10px;
    border-left: 5px solid #20c997;
    margin: 6px 0;
    font-size: 1rem;
}
.ref-box b { color: #495057; font-size: 0.85rem; display: block; margin-bottom: 4px; }
.ref-value { font-size: 1.25rem; font-weight: 600; color: #212529; }
.year-badge {
    display: inline-block;
    background-color: #0d6efd;
    color: white;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 0.9rem;
    font-weight: 600;
    margin-bottom: 8px;
}
.maps-badge {
    display: inline-block;
    background-color: #198754;
    color: white;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
    margin-left: 6px;
    vertical-align: middle;
}
.log-badge {
    display: inline-block;
    background-color: #fd7e14;
    color: white;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
    margin-left: 6px;
    vertical-align: middle;
}
@media (max-width: 768px) {
    .fare-result-box { font-size: 2.4rem; padding: 20px 12px; }
    .ref-value { font-size: 1.1rem; }
    h1 { font-size: 1.5rem !important; }
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# 設定読み込み
# ============================================================
@st.cache_data(show_spinner=False)
def load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# ============================================================
# Google Sheets 認証 (st.cache_resource でシングルトン)
# ============================================================
@st.cache_resource(show_spinner=False)
def get_gspread_client() -> gspread.Client:
    scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds_json_str = os.environ.get("GOOGLE_CREDENTIALS", "")
    if creds_json_str:
        try:
            creds_dict = json.loads(creds_json_str)
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            return gspread.authorize(creds)
        except json.JSONDecodeError as e:
            st.error(f"GOOGLE_CREDENTIALS の JSON パースに失敗しました: {e}")
            st.stop()

    creds_file = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    if os.path.exists(creds_file):
        creds = Credentials.from_service_account_file(creds_file, scopes=scopes)
        return gspread.authorize(creds)

    st.error(
        "Google API 認証情報が見つかりません。\n\n"
        "以下のいずれかを設定してください:\n"
        "- 環境変数 `GOOGLE_CREDENTIALS` にサービスアカウントJSONを文字列で設定\n"
        "- 環境変数 `GOOGLE_CREDENTIALS_FILE` にJSONファイルのパスを設定\n"
        "- プロジェクトルートに `credentials.json` を配置"
    )
    st.stop()

# ============================================================
# ユーティリティ
# ============================================================
def _normalize_city(name: str) -> str:
    return name.replace(" ", "").replace("　", "")

def _parse_number(text: str) -> Optional[float]:
    if not text or not text.strip():
        return None
    normalized = text.strip().translate(
        str.maketrans("０１２３４５６７８９，．", "0123456789,.")
    )
    match = re.search(r"-?[\d,]+\.?\d*", normalized)
    if not match:
        return None
    try:
        return float(match.group().replace(",", ""))
    except ValueError:
        return None

# ============================================================
# データ取得 (OKTable)
# ============================================================
@st.cache_data(ttl=3600, show_spinner="スプレッドシートからデータを取得しています...")
def load_fare_data(spreadsheet_id: str, sheet_name: str) -> tuple:
    gc = get_gspread_client()
    try:
        ss = gc.open_by_key(spreadsheet_id)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"スプレッドシートが見つかりません。\nID: `{spreadsheet_id}`")
        st.stop()

    try:
        ws = ss.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        available = [w.title for w in ss.worksheets()]
        st.error(f"シート「{sheet_name}」が見つかりません。\n利用可能なシート: {', '.join(available)}")
        st.stop()

    all_rows = ws.get_all_values()
    if not all_rows:
        st.error(f"シート「{sheet_name}」にデータがありません。")
        st.stop()

    fare_table: dict[str, dict[float, float]] = {}
    distance_fare_table: dict[float, dict[float, float]] = {}
    distance_map: dict[str, str] = {}
    seen_cities: list[str] = []
    seen_set: set[str] = set()

    for row in all_rows:
        if len(row) < 3:
            continue
        city_raw = row[0].strip()
        weight_raw = row[1].strip()
        fare_raw = row[2].strip()
        distance_raw = row[3].strip() if len(row) >= 4 else ""

        if not city_raw:
            continue

        weight = _parse_number(weight_raw)
        fare = _parse_number(fare_raw)
        if weight is None or fare is None:
            continue

        city = _normalize_city(city_raw)
        if city not in seen_set:
            seen_cities.append(city)
            seen_set.add(city)
            fare_table[city] = {}
        fare_table[city][weight] = fare

        if city not in distance_map and distance_raw:
            distance_map[city] = distance_raw
        d_val = _parse_number(distance_raw)
        if d_val is not None:
            if d_val not in distance_fare_table:
                distance_fare_table[d_val] = {}
            distance_fare_table[d_val][weight] = fare

    if not fare_table and not distance_fare_table:
        st.error(f"シート「{sheet_name}」から有効なデータを読み込めませんでした。")
        st.stop()

    all_weights = sorted({w for city_data in fare_table.values() for w in city_data})
    return seen_cities, all_weights, fare_table, distance_map, distance_fare_table

# ============================================================
# [追加] 検索ログ読み込み（都市名→距離キャッシュ）
# ============================================================
@st.cache_data(ttl=300, show_spinner=False)
def load_search_log_cache(spreadsheet_id: str) -> dict[str, float]:
    """
    「検索結果」シートから「距離タリフ(Google Maps)」行を読み込み、
    都市名（正規化済み） → 実走行距離(km) の辞書を返す。
    同じ都市名が複数ある場合は最新行（末尾）を優先。
    シートが存在しない場合は空辞書を返す。
    """
    try:
        gc = get_gspread_client()
        ss = gc.open_by_key(spreadsheet_id)
        try:
            log_ws = ss.worksheet(LOG_SHEET_NAME)
        except gspread.exceptions.WorksheetNotFound:
            return {}

        all_rows = log_ws.get_all_values()
        if len(all_rows) <= 1:
            return {}

        cache: dict[str, float] = {}
        for row in all_rows[1:]:  # ヘッダー行をスキップ
            if len(row) < 7:
                continue
            match_type = row[3].strip()       # D列: マッチ種別
            city_raw   = row[2].strip()       # C列: 行先
            actual_km_raw = row[6].strip()    # G列: 実走行距離(km)

            if match_type != "距離タリフ(Google Maps)":
                continue
            if not city_raw or not actual_km_raw:
                continue

            km = _parse_number(actual_km_raw)
            if km is not None:
                cache[_normalize_city(city_raw)] = km  # 後勝ち（最新優先）

        return cache

    except Exception:
        return {}

# ============================================================
# [追加] 検索ログ書き込み
# ============================================================
def write_search_log(
    spreadsheet_id: str,
    year_name: str,
    city_input: str,
    match_type: str,
    weight_input: float,
    matched_weight: float,
    actual_km: Optional[float],
    applied_dist: Optional[float],
    fare: float,
):
    """「検索結果」シートに1行追記する。シートがなければ自動作成。"""
    try:
        gc = get_gspread_client()
        ss = gc.open_by_key(spreadsheet_id)

        try:
            log_ws = ss.worksheet(LOG_SHEET_NAME)
        except gspread.exceptions.WorksheetNotFound:
            log_ws = ss.add_worksheet(title=LOG_SHEET_NAME, rows=1000, cols=10)
            log_ws.append_row(LOG_HEADERS)

        now = datetime.datetime.now().strftime("%Y/%m/%d %H:%M")
        log_ws.append_row([
            now,
            year_name,
            city_input,
            match_type,
            weight_input,
            matched_weight,
            actual_km if actual_km is not None else "",
            applied_dist if applied_dist is not None else "",
            int(fare),
        ])

        # ログ書き込み後はキャッシュをクリアして次回検索で最新を反映
        load_search_log_cache.clear()

    except Exception as e:
        st.error(f"【デバッグ】検索ログ書き込みエラー: {type(e).__name__}: {e}")
        import traceback
        st.code(traceback.format_exc())

# ============================================================
# Google Maps Distance Matrix API
# ============================================================
@st.cache_data(ttl=86400, show_spinner=False)
def get_road_distance_km(destination: str) -> tuple[Optional[float], str]:
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return None, "環境変数 GOOGLE_MAPS_API_KEY が設定されていません。"

    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": ORIGIN_ADDRESS,
        "destinations": destination,
        "key": api_key,
        "language": "ja",
        "units": "metric",
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "OK":
            return None, f"API ステータスエラー: {data.get('status', '不明')}"

        element = data["rows"][0]["elements"][0]
        elem_status = element.get("status", "不明")
        if elem_status != "OK":
            if elem_status == "NOT_FOUND":
                return None, f"「{destination}」の住所が Google Maps で見つかりませんでした。"
            if elem_status == "ZERO_RESULTS":
                return None, f"「{destination}」までの経路が見つかりませんでした。"
            return None, f"距離取得エラー: {elem_status}"

        distance_m = element["distance"]["value"]
        return distance_m / 1000.0, ""

    except requests.exceptions.Timeout:
        return None, "Google Maps API がタイムアウトしました（10秒）。"
    except Exception as e:
        return None, f"Google Maps API エラー: {e}"

# ============================================================
# 検索ロジック
# ============================================================
def find_weight_ceiling(input_weight: float, weights: list[float]) -> Optional[float]:
    candidates = [w for w in weights if w >= input_weight]
    return min(candidates) if candidates else None

def match_city(normalized_input: str, city_list: list[str]) -> Optional[str]:
    if normalized_input in city_list:
        return normalized_input
    for city in city_list:
        if city.startswith(normalized_input):
            return city
    return None

def find_distance_ceiling(actual_km: float, distance_tiers: list[float]) -> Optional[float]:
    candidates = [d for d in distance_tiers if d >= actual_km]
    return min(candidates) if candidates else None

# ============================================================
# サイドバー
# ============================================================
config = load_config()
spreadsheets_cfg = config.get("spreadsheets", [])

with st.sidebar:
    st.title("⚙️ 設定")
    st.markdown("---")

    if not spreadsheets_cfg:
        st.error("config.yaml にスプレッドシートが設定されていません。")
        st.stop()

    year_names = [s["name"] for s in spreadsheets_cfg]
    selected_year_name = st.selectbox("📅 参照する年度", year_names)
    selected_cfg = next(s for s in spreadsheets_cfg if s["name"] == selected_year_name)
    spreadsheet_id = selected_cfg["id"]
    sheet_name_cfg = selected_cfg.get("sheet_name", "OKTable")

    st.markdown("---")
    st.markdown("**現在の参照年度**")
    st.markdown(f'<div class="year-badge">📋 {selected_year_name}</div>', unsafe_allow_html=True)
    st.caption("データは取得後 1 時間キャッシュされます。")

    if st.button("🔄 キャッシュを更新", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ============================================================
# データ取得
# ============================================================
city_list, weights, fare_table, distance_map, distance_fare_table = load_fare_data(
    spreadsheet_id=spreadsheet_id,
    sheet_name=sheet_name_cfg,
)

# [追加] 検索ログキャッシュを読み込む
log_distance_cache = load_search_log_cache(spreadsheet_id)

# ============================================================
# メイン UI
# ============================================================
st.title("💧 富士ミネラル向けタリフ")
st.markdown(
    f'<span class="year-badge">参照タリフ: {selected_year_name}</span>',
    unsafe_allow_html=True,
)
st.caption(f"📍 起点住所: {ORIGIN_ADDRESS}")
st.markdown("---")

col_city, col_weight, col_btn = st.columns([3, 2, 1])
with col_city:
    city_input = st.text_input(
        "🌏 行先（都市名）",
        placeholder="例: 上海、バンコク、ロサンゼルス",
        help="タリフに登録済みの都市名はそのまま検索します。未登録の場合は検索ログ→Google Maps の順で距離を取得して距離タリフを適用します。",
    )
with col_weight:
    weight_input = st.number_input(
        "⚖️ 重量 (kg)",
        min_value=0.0,
        max_value=99999.0,
        value=0.0,
        step=0.5,
        format="%.1f",
        help="入力値以上の最小重量区分を自動的に参照します。",
    )
with col_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    search_clicked = st.button("🔍 検索", type="primary", use_container_width=True)

# ============================================================
# 検索実行
# ============================================================
if search_clicked:
    if not city_input or weight_input <= 0:
        st.warning("行先と重量（0より大きい値）を入力してください。")
    else:
        normalized_input = _normalize_city(city_input)
        matched_city = match_city(normalized_input, city_list)
        matched_weight = find_weight_ceiling(weight_input, weights)

        if matched_weight is None:
            st.error(
                f"重量 **{weight_input} kg** 以上の運賃データがありません。\n\n"
                f"このタリフの最大重量: **{max(weights):g} kg**"
            )

        elif matched_city is not None:
            # ── ① タリフに都市名が存在するケース ──────────────────────────
            if matched_city != normalized_input:
                st.caption(f"「{city_input}」を「{matched_city}」として検索しました。")

            fare = fare_table[matched_city].get(matched_weight)
            if fare is None:
                st.error(f"「{matched_city}」× **{matched_weight:g} kg** の運賃データが見つかりません。")
            else:
                st.markdown("---")
                st.subheader("📊 検索結果")

                ref_col1, ref_col2, ref_col3 = st.columns(3)
                with ref_col1:
                    st.markdown(
                        f'<div class="ref-box"><b>参照した都市名</b>'
                        f'<span class="ref-value">{matched_city}</span></div>',
                        unsafe_allow_html=True,
                    )
                with ref_col2:
                    weight_note = f"（入力: {weight_input:g} kg → 切り上げ）" \
                        if weight_input != matched_weight else ""
                    st.markdown(
                        f'<div class="ref-box"><b>参照した重量 {weight_note}</b>'
                        f'<span class="ref-value">{matched_weight:g} kg</span></div>',
                        unsafe_allow_html=True,
                    )
                with ref_col3:
                    distance_val = distance_map.get(matched_city, "—")
                    st.markdown(
                        f'<div class="ref-box"><b>参照した距離</b>'
                        f'<span class="ref-value">{distance_val}</span></div>',
                        unsafe_allow_html=True,
                    )

                st.markdown(f'<div class="fare-result-box">¥ {int(fare):,}</div>', unsafe_allow_html=True)
                st.metric(
                    label=f"{matched_city} | {matched_weight:g} kg | {selected_year_name}",
                    value=f"¥{int(fare):,}",
                )

                # [追加] 検索ログ書き込み
                write_search_log(
                    spreadsheet_id=spreadsheet_id,
                    year_name=selected_year_name,
                    city_input=city_input,
                    match_type="都市名",
                    weight_input=weight_input,
                    matched_weight=matched_weight,
                    actual_km=None,
                    applied_dist=None,
                    fare=fare,
                )

        else:
            # ── タリフに都市名なし → ②ログキャッシュ → ③Google Maps ──────
            if not distance_fare_table:
                st.error(
                    f"「{city_input}」はタリフに存在せず、距離タリフ設定も OKTable にありません。"
                )
            else:
                distance_tiers = sorted(distance_fare_table.keys())

                # ── ② 検索ログキャッシュにヒット？ [追加] ─────────────────
                cached_km = log_distance_cache.get(normalized_input)

                if cached_km is not None:
                    # ログキャッシュから距離を使用
                    actual_km = cached_km
                    source_label = "ログキャッシュ"
                    applied_dist = find_distance_ceiling(actual_km, distance_tiers)

                    if applied_dist is None:
                        st.error(
                            f"ログキャッシュの距離 **{actual_km:.1f} km** に対応するタリフ距離設定がありません。"
                        )
                    else:
                        fare = distance_fare_table[applied_dist].get(matched_weight)
                        if fare is None:
                            st.error(f"距離 **{applied_dist:g} km** × **{matched_weight:g} kg** の運賃データが見つかりません。")
                        else:
                            st.markdown("---")
                            st.subheader("📊 検索結果")
                            st.info(
                                f"「{city_input}」はタリフ未登録のため、過去の検索ログの距離を使用しました。",
                                icon="📋",
                            )

                            ref_col1, ref_col2, ref_col3, ref_col4 = st.columns(4)
                            with ref_col1:
                                st.markdown(
                                    f'<div class="ref-box"><b>入力した行先</b>'
                                    f'<span class="ref-value">{city_input}</span></div>',
                                    unsafe_allow_html=True,
                                )
                            with ref_col2:
                                weight_note = f"（入力: {weight_input:g} kg → 切り上げ）" \
                                    if weight_input != matched_weight else ""
                                st.markdown(
                                    f'<div class="ref-box"><b>参照した重量 {weight_note}</b>'
                                    f'<span class="ref-value">{matched_weight:g} kg</span></div>',
                                    unsafe_allow_html=True,
                                )
                            with ref_col3:
                                st.markdown(
                                    f'<div class="ref-box">'
                                    f'<b>使用距離 <span class="log-badge">ログキャッシュ</span></b>'
                                    f'<span class="ref-value">{actual_km:.1f} km</span></div>',
                                    unsafe_allow_html=True,
                                )
                            with ref_col4:
                                st.markdown(
                                    f'<div class="ref-box"><b>適用タリフ距離（切り上げ）</b>'
                                    f'<span class="ref-value">{applied_dist:g} km</span></div>',
                                    unsafe_allow_html=True,
                                )

                            st.markdown(f'<div class="fare-result-box">¥ {int(fare):,}</div>', unsafe_allow_html=True)
                            st.metric(
                                label=f"{city_input} ({actual_km:.1f}km → {applied_dist:g}km適用) | {matched_weight:g} kg | {selected_year_name}",
                                value=f"¥{int(fare):,}",
                            )

                            # [追加] 検索ログ書き込み（ログキャッシュ使用）
                            write_search_log(
                                spreadsheet_id=spreadsheet_id,
                                year_name=selected_year_name,
                                city_input=city_input,
                                match_type="ログキャッシュ",
                                weight_input=weight_input,
                                matched_weight=matched_weight,
                                actual_km=actual_km,
                                applied_dist=applied_dist,
                                fare=fare,
                            )

                else:
                    # ── ③ Google Maps APIで距離計算 ────────────────────────
                    with st.spinner(f"Google Maps で「{city_input}」までの道路距離を計算中..."):
                        actual_km, err_msg = get_road_distance_km(city_input)

                    if actual_km is None:
                        st.error(
                            f"「{city_input}」はタリフに存在せず、距離も取得できませんでした。\n\nエラー: {err_msg}"
                        )
                    else:
                        applied_dist = find_distance_ceiling(actual_km, distance_tiers)

                        if applied_dist is None:
                            st.error(
                                f"実走行距離 **{actual_km:.1f} km** に対応するタリフ距離設定がありません。\n\n"
                                f"最大タリフ距離: **{max(distance_tiers):g} km**"
                            )
                        else:
                            fare = distance_fare_table[applied_dist].get(matched_weight)
                            if fare is None:
                                st.error(f"距離 **{applied_dist:g} km** × **{matched_weight:g} kg** の運賃データが見つかりません。")
                            else:
                                st.markdown("---")
                                st.subheader("📊 検索結果")
                                st.info(
                                    f"「{city_input}」はタリフ未登録のため、Google Maps の実走行距離で距離タリフを適用しました。",
                                    icon="📍",
                                )

                                ref_col1, ref_col2, ref_col3, ref_col4 = st.columns(4)
                                with ref_col1:
                                    st.markdown(
                                        f'<div class="ref-box"><b>入力した行先</b>'
                                        f'<span class="ref-value">{city_input}</span></div>',
                                        unsafe_allow_html=True,
                                    )
                                with ref_col2:
                                    weight_note = f"（入力: {weight_input:g} kg → 切り上げ）" \
                                        if weight_input != matched_weight else ""
                                    st.markdown(
                                        f'<div class="ref-box"><b>参照した重量 {weight_note}</b>'
                                        f'<span class="ref-value">{matched_weight:g} kg</span></div>',
                                        unsafe_allow_html=True,
                                    )
                                with ref_col3:
                                    st.markdown(
                                        f'<div class="ref-box">'
                                        f'<b>実走行距離 <span class="maps-badge">Google Maps</span></b>'
                                        f'<span class="ref-value">{actual_km:.1f} km</span></div>',
                                        unsafe_allow_html=True,
                                    )
                                with ref_col4:
                                    st.markdown(
                                        f'<div class="ref-box"><b>適用タリフ距離（切り上げ）</b>'
                                        f'<span class="ref-value">{applied_dist:g} km</span></div>',
                                        unsafe_allow_html=True,
                                    )

                                st.markdown(f'<div class="fare-result-box">¥ {int(fare):,}</div>', unsafe_allow_html=True)
                                st.metric(
                                    label=f"{city_input} ({actual_km:.1f}km → {applied_dist:g}km適用) | {matched_weight:g} kg | {selected_year_name}",
                                    value=f"¥{int(fare):,}",
                                )

                                # [追加] 検索ログ書き込み（Google Maps使用）
                                write_search_log(
                                    spreadsheet_id=spreadsheet_id,
                                    year_name=selected_year_name,
                                    city_input=city_input,
                                    match_type="距離タリフ(Google Maps)",
                                    weight_input=weight_input,
                                    matched_weight=matched_weight,
                                    actual_km=actual_km,
                                    applied_dist=applied_dist,
                                    fare=fare,
                                )

st.caption(f"© 富士ミネラル向けタリフ | 参照タリフ: {selected_year_name}")
