import json
import math
import streamlit as st
import requests
from groq import Groq

app_id = st.secrets["CLIENT_ID"]
app_key = st.secrets["CLIENT_SECRET"]

if "GROQ_API_KEY" in st.secrets:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
else:
    st.error("找不到 GROQ_API_KEY，請檢查 Secrets！")

ROUTE_CATEGORIES = {
    "黃線 (新營/後壁/白河/麻豆)": [
        "黃幹線", "黃1", "黃2", "黃3", "黃4", "黃5", "黃6", "黃6-1", "黃7", "黃9",
        "黃10", "黃11", "黃11-1", "黃12", "黃13", "黃14", "黃14-1", "黃15", "黃16",
        "黃20", "黃22", "黃23", "黃24", "黃25"
    ],
    "棕線 (新營/鹽水/學甲/佳里)": [
        "棕幹線", "棕1", "棕2", "棕3", "棕3-1", "棕4", "棕5", "棕6", "棕20", "棕10", "棕11"
    ],
    "綠線 (玉井/新化/左鎮/楠西)": [
        "綠幹線", "綠1", "綠2", "綠2-1", "綠3", "綠4", "綠5", "綠6", "綠7", "綠10", "綠11",
        "綠12", "綠12-1", "綠12-2", "綠13", "綠14", "綠15", "綠16", "綠17", "綠20", "綠20-1",
        "綠21", "綠22", "綠23", "綠24", "綠25", "綠26", "綠27", "綠28", "綠29", "綠30",
        "綠30-1", "綠31", "綠32"
    ],
    "橘線 (佳里/麻豆/玉井/大內)": [
        "橘幹線", "橘1", "橘2", "橘3", "橘4", "橘4-1", "橘5", "橘6", "橘9", "橘9-1",
        "橘10", "橘10-1", "橘11", "橘11-1", "橘12", "橘13", "橘14", "橘20"
    ],
    "藍線 (安平/佳里/將軍/北門)": [
        "藍幹線", "藍1", "藍2", "藍3", "藍4", "藍10", "藍11", "藍13", "藍14", "藍15",
        "藍20", "藍21", "藍22", "藍23", "藍24", "藍25", "藍26", "藍27", "藍28", "藍29", "藍30"
    ],
    "紅線 (台南/關廟/龍崎/高鐵)": [
        "紅幹線", "紅1", "紅2", "紅3", "紅4", "紅10", "紅11", "紅12", "紅13", "紅14"
    ],
    "市區數字公車 (台南市區)": [
        "0左", "0右", "6", "7", "9", "10", "11", "14", "15", "18",
        "19", "20", "21", "31", "32", "33", "62", "70左", "70右", "77", "98",
        "101", "102", "103", "107", "111", "168", "901", "902", "904", "905"
    ],
    "高鐵快捷": ["H31"],
    "觀光": ["東山咖啡線", "梅嶺線", "菱波官田線", "雙層巴士"]
}

auth_url = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"

class Auth():
    def __init__(self, app_id, app_key):
        self.app_id = app_id
        self.app_key = app_key
    def get_auth_header(self):
        return {
            'content-type': 'application/x-www-form-urlencoded',
            'grant_type': 'client_credentials',
            'client_id': self.app_id,
            'client_secret': self.app_key
        }

class DataProcessor():
    def __init__(self, auth_response):
        self.auth_response = auth_response
    def get_data_header(self):
        auth_JSON = self.auth_response.json()
        access_token = auth_JSON.get('access_token')
        return {
            'authorization': f'Bearer {access_token}',
            'Accept-Encoding': 'gzip'
        }

# ── 公里距離計算（Haversine）──────────────────────────────
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

# ── 快取函數 ──────────────────────────────────────────────

@st.cache_data(ttl=3600)
def fetch_route_stops(route_name, headers_dict):
    try:
        with open("tainan_stops_cache.json", "r", encoding="utf-8") as f:
            local_cache = json.load(f)
            if route_name in local_cache and local_cache[route_name]:
                return local_cache[route_name]
    except FileNotFoundError:
        pass
    stops_url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/StopOfRoute/City/Tainan/{route_name}?%24format=JSON"
    try:
        res = requests.get(stops_url, headers=headers_dict)
        if res.status_code == 200:
            data = res.json()
            if data:
                return [s['StopName']['Zh_tw'] for s in data[0]['Stops']]
    except:
        return []
    return []

@st.cache_data(ttl=30)
def fetch_bus_data(route_name, headers_dict):
    url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/City/Tainan/{route_name}?%24format=JSON"
    try:
        res = requests.get(url, headers=headers_dict)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        st.error(f"即時資料抓取失敗: {e}")
        return None
    return None

# ── 天氣：改用 Open-Meteo（免費、不需 API key、可指定座標） ──
@st.cache_data(ttl=600)
def fetch_weather_by_coord(lat, lon, label=""):
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,weathercode,windspeed_10m"
            f"&timezone=Asia%2FTaipei"
        )
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            cur = data.get("current", {})
            temp = cur.get("temperature_2m", "?")
            wcode = cur.get("weathercode", -1)
            wind = cur.get("windspeed_10m", "?")
            # WMO 天氣碼簡易對照
            wcode_map = {
                0: "晴天☀️", 1: "大致晴朗🌤️", 2: "部分多雲⛅", 3: "陰天☁️",
                45: "有霧🌫️", 48: "凍霧🌫️",
                51: "毛毛雨🌦️", 53: "毛毛雨🌦️", 55: "濃毛毛雨🌧️",
                61: "小雨🌧️", 63: "中雨🌧️", 65: "大雨🌧️",
                71: "小雪❄️", 73: "中雪❄️", 75: "大雪❄️",
                80: "陣雨🌦️", 81: "中陣雨🌧️", 82: "強陣雨⛈️",
                95: "雷雨⛈️", 96: "雷雨夾雹⛈️", 99: "強雷雨夾雹⛈️"
            }
            desc = wcode_map.get(wcode, f"天氣碼{wcode}")
            prefix = f"【{label}】" if label else ""
            return f"{prefix}{desc}，氣溫 {temp}°C，風速 {wind} km/h"
    except:
        pass
    return "無法取得天氣資訊"

# ── UBike：查詢指定座標附近站點（台南） ──
@st.cache_data(ttl=60)
def fetch_ubike_near(lat, lon, headers_dict, radius_km=0.3):
    url = "https://tdx.transportdata.tw/api/basic/v2/Bike/Station/City/Tainan?%24format=JSON"
    avail_url = "https://tdx.transportdata.tw/api/basic/v2/Bike/Availability/City/Tainan?%24format=JSON"
    try:
        res = requests.get(url, headers=headers_dict, timeout=5)
        avail_res = requests.get(avail_url, headers=headers_dict, timeout=5)
        if res.status_code == 200 and avail_res.status_code == 200:
            stations = res.json()
            avail_list = avail_res.json()
            avail_map = {a["StationUID"]: a for a in avail_list}
            nearby = []
            for st_info in stations:
                pos = st_info.get("StationPosition", {})
                s_lat = pos.get("PositionLat")
                s_lon = pos.get("PositionLon")
                if s_lat and s_lon:
                    dist = haversine(lat, lon, s_lat, s_lon)
                    if dist <= radius_km:
                        uid = st_info.get("StationUID", "")
                        av = avail_map.get(uid, {})
                        nearby.append({
                            "name": st_info.get("StationName", {}).get("Zh_tw", "未知"),
                            "dist": dist,
                            "available": av.get("AvailableRentBikes", "?"),
                            "empty": av.get("AvailableReturnBikes", "?")
                        })
            nearby.sort(key=lambda x: x["dist"])
            return nearby
    except:
        pass
    return []

# ── 附近公車站：先把全台南站牌快取起來，再用座標篩選 ──
@st.cache_data(ttl=300)
def fetch_all_bus_stops(access_token):
    """把全台南站牌一次抓回來並快取，key 用 token 字串避免 dict 無法 hash"""
    url = "https://tdx.transportdata.tw/api/basic/v2/Bus/Stop/City/Tainan?%24format=JSON"
    headers = {
        'authorization': f'Bearer {access_token}',
        'Accept-Encoding': 'gzip'
    }
    try:
        res = requests.get(url, headers=headers, timeout=20)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        st.warning(f"附近站牌 API 錯誤：{e}")
    return []

def find_nearby_stops(all_stops, lat, lon, radius_km=0.5):
    """從已快取的站牌資料中篩選附近站點"""
    nearby = []
    seen = set()
    for stop in all_stops:
        pos = stop.get("StopPosition", {})
        s_lat = pos.get("PositionLat")
        s_lon = pos.get("PositionLon")
        name = stop.get("StopName", {}).get("Zh_tw", "")
        if s_lat and s_lon and name and name not in seen:
            dist = haversine(lat, lon, s_lat, s_lon)
            if dist <= radius_km:
                seen.add(name)
                nearby.append({"name": name, "dist": dist})
    nearby.sort(key=lambda x: x["dist"])
    return nearby[:15]

# ── CSS ──────────────────────────────────────────────────
TIMELINE_CSS = """
<style>
* { box-sizing: border-box; font-family: 'Noto Sans TC', sans-serif; }
body { margin: 0; padding: 8px; background: transparent; }
.timeline-container {
    position: relative; padding-left: 35px;
    margin-left: 15px; border-left: 4px solid #4A90E2;
    padding-top: 10px; padding-bottom: 10px;
}
.timeline-item { position: relative; margin-bottom: 18px; }
.timeline-circle {
    position: absolute; left: -44px; top: 12px;
    width: 14px; height: 14px; background-color: white;
    border: 4px solid #4A90E2; border-radius: 50%; z-index: 2;
}
.station-box {
    display: flex; justify-content: space-between; align-items: center;
    background-color: #FAFAFA; padding: 10px 15px;
    border-radius: 8px; border: 1px solid #EAEAEA; min-height: 55px;
}
.station-info { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.station-name { font-size: 15px; font-weight: bold; color: #333333; }
.bus-tag {
    background-color: #FF5A5F; color: white; padding: 3px 8px;
    border-radius: 4px; font-size: 11px; font-weight: bold;
    display: inline-flex; align-items: center;
}
.wheelchair-tag {
    background-color: #2ECC71; color: white; padding: 3px 6px;
    border-radius: 4px; font-size: 11px; font-weight: bold;
    display: inline-flex; align-items: center;
}
.ubike-tag {
    background-color: #007bff; color: white; padding: 3px 8px;
    border-radius: 4px; font-size: 11px; font-weight: bold;
    display: inline-flex; align-items: center; gap: 4px;
}
.time-badge {
    padding: 6px 12px; border-radius: 20px; color: white;
    font-weight: bold; font-size: 12px; min-width: 90px;
    text-align: center; display: inline-block;
}
.ts-gray   { background-color: #BDBDBD; }
.ts-orange { background-color: #FFA726; animation: pulse 1s infinite; }
.ts-green  { background-color: #66BB6A; }
@keyframes pulse {
    0%   { opacity: 0.8; } 50%  { opacity: 1.0; } 100% { opacity: 0.8; }
}
</style>
"""

# ── 主程式 ────────────────────────────────────────────────
if __name__ == '__main__':
    st.set_page_config(page_title="台南公車 AI 助理", page_icon="🚌", layout="wide")
    st.header("🚌 台南公車即時時刻查詢")

    try:
        a = Auth(app_id, app_key)
        auth_res = requests.post(auth_url, data=a.get_auth_header())
        d = DataProcessor(auth_res)
        h = d.get_data_header()

        current_weather = "使用者尚未查詢"
        bus_status = "使用者尚未查詢路線"

        # 台南市政府座標（預設天氣位置）
        TAINAN_LAT, TAINAN_LON = 22.9997, 120.2270

        left_col, right_col = st.columns([1, 3])

        # ════════════════════════════════════════
        # 左欄：篩選 + GPS 功能
        # ════════════════════════════════════════
        with left_col:
            st.subheader("🔍 路線篩選")

            def reset_search():
                st.session_state.search_clicked = False

            if "selected_filter" not in st.session_state:
                st.session_state.selected_filter = None

            st.caption("點選顏色或數字篩選：")

            cols1 = st.columns(4)
            if cols1[0].button("綠", use_container_width=True): st.session_state.selected_filter = "綠"; reset_search()
            if cols1[1].button("橘", use_container_width=True): st.session_state.selected_filter = "橘"; reset_search()
            if cols1[2].button("1",  use_container_width=True): st.session_state.selected_filter = "1";  reset_search()
            if cols1[3].button("2",  use_container_width=True): st.session_state.selected_filter = "2";  reset_search()

            cols2 = st.columns(4)
            if cols2[0].button("棕", use_container_width=True): st.session_state.selected_filter = "棕"; reset_search()
            if cols2[1].button("藍", use_container_width=True): st.session_state.selected_filter = "藍"; reset_search()
            if cols2[2].button("3",  use_container_width=True): st.session_state.selected_filter = "3";  reset_search()
            if cols2[3].button("4",  use_container_width=True): st.session_state.selected_filter = "4";  reset_search()

            cols3 = st.columns(4)
            if cols3[0].button("紅", use_container_width=True): st.session_state.selected_filter = "紅"; reset_search()
            if cols3[1].button("黃", use_container_width=True): st.session_state.selected_filter = "黃"; reset_search()
            if cols3[2].button("5",  use_container_width=True): st.session_state.selected_filter = "5";  reset_search()
            if cols3[3].button("6",  use_container_width=True): st.session_state.selected_filter = "6";  reset_search()

            cols4 = st.columns(4)
            if cols4[0].button("市區", use_container_width=True): st.session_state.selected_filter = "市區"; reset_search()
            if cols4[1].button("高鐵", use_container_width=True): st.session_state.selected_filter = "高鐵"; reset_search()
            if cols4[2].button("7",    use_container_width=True): st.session_state.selected_filter = "7";    reset_search()
            if cols4[3].button("8",    use_container_width=True): st.session_state.selected_filter = "8";    reset_search()

            cols5 = st.columns(4)
            if cols5[0].button("觀光", use_container_width=True): st.session_state.selected_filter = "觀光"; reset_search()
            if cols5[1].button("9",    use_container_width=True): st.session_state.selected_filter = "9";    reset_search()
            if cols5[2].button("0",    use_container_width=True): st.session_state.selected_filter = "0";    reset_search()

            st.write("")
            if st.button("❌ 清除篩選", use_container_width=True):
                st.session_state.selected_filter = None
                reset_search()

            current_filter = st.session_state.selected_filter
            if current_filter == "高鐵":
                st.success("篩選：【高鐵快捷】")
            elif current_filter == "觀光":
                st.success("篩選：【觀光巴士】")
            elif current_filter:
                st.success(f"篩選：【{current_filter}】")
            else:
                st.info("顯示：全部路線")

            # 路線清單
            all_possible_routes = []
            for routes_list in ROUTE_CATEGORIES.values():
                all_possible_routes.extend(routes_list)
            seen_set = set()
            all_possible_routes = [x for x in all_possible_routes if not (x in seen_set or seen_set.add(x))]

            if current_filter is None:
                filtered_routes = all_possible_routes
            elif current_filter == "市區":
                filtered_routes = ROUTE_CATEGORIES["市區數字公車 (台南市區)"]
            elif current_filter == "高鐵":
                filtered_routes = ROUTE_CATEGORIES["高鐵快捷"]
            elif current_filter == "觀光":
                filtered_routes = ROUTE_CATEGORIES["觀光"]
            else:
                raw_filtered = [r for r in all_possible_routes if current_filter in r]
                if current_filter.isdigit():
                    def custom_numeric_sort(route_str):
                        just_nums = ''.join([c for c in route_str if c.isdigit()])
                        if just_nums:
                            val = int(just_nums)
                            return (0 if route_str.startswith(current_filter) else 1, val, route_str)
                        return (2, 999, route_str)
                    filtered_routes = sorted(raw_filtered, key=custom_numeric_sort)
                else:
                    filtered_routes = raw_filtered

            route_choice = st.selectbox(
                "選擇路線", filtered_routes, index=None,
                placeholder="請選擇或輸入路線...",
                key="bus_route_select", on_change=reset_search
            )

            start_st = None
            if route_choice:
                st.session_state.search_clicked = True
                all_stops = fetch_route_stops(route_choice, h)
                if all_stops:
                    start_st = st.selectbox("等候站", all_stops, index=0, key="start_select")
                    end_st   = st.selectbox("目的地", all_stops, index=len(all_stops)-1, key="end_select")
                else:
                    st.warning(f"⚠️ 無法載入【{route_choice}】站點。")
            else:
                st.info("請選擇路線")

            st.write("---")

            # ── GPS 附近站牌功能 ──────────────────────────
            st.subheader("📍 附近公車站")
            st.caption("點按鈕自動定位，找出附近站牌")

            # 初始化座標 session_state
            if "user_lat" not in st.session_state:
                st.session_state.user_lat = None
            if "user_lon" not in st.session_state:
                st.session_state.user_lon = None

            # 從 query_params 讀取 JS 寫入的座標
            qp = st.query_params
            if "lat" in qp and "lon" in qp:
                try:
                    st.session_state.user_lat = float(qp["lat"])
                    st.session_state.user_lon = float(qp["lon"])
                except:
                    pass

            # JS：取得 GPS 後直接把座標寫進 URL query string，觸發 Streamlit rerun
            gps_html = """
<button onclick="
  navigator.geolocation.getCurrentPosition(function(pos){
    var lat = pos.coords.latitude.toFixed(6);
    var lon = pos.coords.longitude.toFixed(6);
    var url = window.parent.location.href.split('?')[0] + '?lat=' + lat + '&lon=' + lon;
    window.parent.location.href = url;
  }, function(err){
    alert('無法取得位置，請確認瀏覽器已授權定位權限');
  });
" style="width:100%;padding:8px;border-radius:6px;background:#4A90E2;color:white;border:none;cursor:pointer;font-size:13px;font-weight:bold;">
📡 取得我的位置並搜尋
</button>
"""
            st.components.v1.html(gps_html, height=60)

            # 顯示目前座標
            if st.session_state.user_lat and st.session_state.user_lon:
                st.success(f"📍 {st.session_state.user_lat:.5f}, {st.session_state.user_lon:.5f}")
                with st.spinner("載入站牌資料中..."):
                    # 用 access_token 字串當 cache key（可 hash）
                    access_token = auth_res.json().get("access_token", "")
                    all_stops_data = fetch_all_bus_stops(access_token)
                if all_stops_data:
                    nearby_stops = find_nearby_stops(
                        all_stops_data,
                        st.session_state.user_lat,
                        st.session_state.user_lon,
                        radius_km=0.5
                    )
                    if nearby_stops:
                        st.write(f"**找到 {len(nearby_stops)} 個站牌（500m內）：**")
                        for ns in nearby_stops:
                            st.write(f"🚏 **{ns['name']}**（{ns['dist']*1000:.0f}m）")
                    else:
                        st.warning("附近 500m 內無公車站牌")
                else:
                    st.error("無法載入站牌資料，請稍後再試")
                if st.button("🗑️ 清除定位", use_container_width=True):
                    st.session_state.user_lat = None
                    st.session_state.user_lon = None
                    st.query_params.clear()
                    st.rerun()
            else:
                st.info("尚未定位")

            st.write("---")

            # 系統維護
            with st.expander("⚙️ 系統維護"):
                st.caption("每月或大改點時更新一次。")
                if st.button("🔄 更新全台南站點快取", use_container_width=True):
                    with st.spinner("離線化中..."):
                        all_cache = {}
                        progress_bar = st.progress(0)
                        all_routes_to_fetch = list(set(
                            r for r_list in ROUTE_CATEGORIES.values() for r in r_list
                        ))
                        total_routes = len(all_routes_to_fetch)
                        for idx, r_name in enumerate(all_routes_to_fetch):
                            s_url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/StopOfRoute/City/Tainan/{r_name}?%24format=JSON"
                            try:
                                response = requests.get(s_url, headers=h)
                                if response.status_code == 200:
                                    d_json = response.json()
                                    if d_json:
                                        all_cache[r_name] = [s['StopName']['Zh_tw'] for s in d_json[0]['Stops']]
                            except:
                                all_cache[r_name] = []
                            progress_bar.progress((idx + 1) / total_routes)
                        with open("tainan_stops_cache.json", "w", encoding="utf-8") as f:
                            json.dump(all_cache, f, ensure_ascii=False, indent=4)
                        st.success("🎉 快取建立成功！")

        # ════════════════════════════════════════
        # 右欄：天氣 + 公車時刻 + UBike
        # ════════════════════════════════════════
        with right_col:
            if route_choice and st.session_state.get("search_clicked", False):
                bus_list = fetch_bus_data(route_choice, h)

                # ── 天氣顯示（用 Open-Meteo，台南座標） ──
                weather_now = fetch_weather_by_coord(TAINAN_LAT, TAINAN_LON, "台南目前")
                current_weather = weather_now
                st.info(f"🌡️ {weather_now}")

                if bus_list is not None:
                    direction_0 = sorted([item for item in bus_list if item.get("Direction") == 0], key=lambda x: x.get('StopSequence', 0))
                    direction_1 = sorted([item for item in bus_list if item.get("Direction") == 1], key=lambda x: x.get('StopSequence', 0))
                    dest_0 = direction_0[-1].get("StopName", {}).get("Zh_tw", "去程") if direction_0 else "去程"
                    dest_1 = direction_1[-1].get("StopName", {}).get("Zh_tw", "回程") if direction_1 else "回程"

                    st.subheader(f"🚌 {route_choice} 全線即時動態")

                    if "dir_toggle" not in st.session_state:
                        st.session_state.dir_toggle = "去程"

                    col_btn1, col_btn2, col_btn3 = st.columns([1.5, 1.5, 1])
                    with col_btn1:
                        if st.button(f"➡️ 往 {dest_0}", use_container_width=True, type="primary" if st.session_state.dir_toggle == "去程" else "secondary"):
                            st.session_state.dir_toggle = "去程"
                    with col_btn2:
                        if st.button(f"⬅️ 往 {dest_1}", use_container_width=True, type="primary" if st.session_state.dir_toggle == "回程" else "secondary"):
                            st.session_state.dir_toggle = "回程"
                    with col_btn3:
                        if st.button("🔄 重新整理", use_container_width=True):
                            st.toast("⏳ 正在更新...", icon="🚌")
                            st.rerun()

                    active_list = direction_0 if st.session_state.dir_toggle == "去程" else direction_1

                    # ── 取得路線所有站點的座標（用於 UBike 查詢）──
                    stops_with_coord_url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/StopOfRoute/City/Tainan/{route_choice}?%24format=JSON"
                    stop_coord_map = {}  # 站名 → (lat, lon)
                    try:
                        coord_res = requests.get(stops_with_coord_url, headers=h, timeout=5)
                        if coord_res.status_code == 200:
                            coord_data = coord_res.json()
                            target_dir = 0 if st.session_state.dir_toggle == "去程" else 1
                            for route_dir in coord_data:
                                if route_dir.get("Direction") == target_dir:
                                    for s in route_dir.get("Stops", []):
                                        name = s.get("StopName", {}).get("Zh_tw", "")
                                        pos = s.get("StopPosition", {})
                                        lat = pos.get("PositionLat")
                                        lon = pos.get("PositionLon")
                                        if name and lat and lon:
                                            stop_coord_map[name] = (lat, lon)
                    except:
                        pass

                    # ── 預先撈 UBike 全部站點（一次查，避免重複打 API）──
                    ubike_all = []
                    ubike_avail_map = {}
                    try:
                        ub_res = requests.get(
                            "https://tdx.transportdata.tw/api/basic/v2/Bike/Station/City/Tainan?%24format=JSON",
                            headers=h, timeout=5
                        )
                        ub_avail_res = requests.get(
                            "https://tdx.transportdata.tw/api/basic/v2/Bike/Availability/City/Tainan?%24format=JSON",
                            headers=h, timeout=5
                        )
                        if ub_res.status_code == 200:
                            ubike_all = ub_res.json()
                        if ub_avail_res.status_code == 200:
                            for av in ub_avail_res.json():
                                ubike_avail_map[av["StationUID"]] = av
                    except:
                        pass

                    def get_ubike_near_stop(s_lat, s_lon, radius_km=0.3):
                        """從已載入的 UBike 資料找附近站"""
                        result = []
                        for ub in ubike_all:
                            pos = ub.get("StationPosition", {})
                            u_lat = pos.get("PositionLat")
                            u_lon = pos.get("PositionLon")
                            if u_lat and u_lon:
                                dist = haversine(s_lat, s_lon, u_lat, u_lon)
                                if dist <= radius_km:
                                    uid = ub.get("StationUID", "")
                                    av = ubike_avail_map.get(uid, {})
                                    result.append({
                                        "name": ub.get("StationName", {}).get("Zh_tw", ""),
                                        "available": av.get("AvailableRentBikes", "?"),
                                        "empty": av.get("AvailableReturnBikes", "?")
                                    })
                        return result

                    # ── 完整站點清單 ──
                    all_stops_raw = fetch_route_stops(route_choice, h)
                    realtime_map = {}
                    for item in active_list:
                        s = item.get("StopName", {}).get("Zh_tw", "")
                        if s:
                            realtime_map[s] = item

                    full_stop_list = all_stops_raw if all_stops_raw else [
                        item.get("StopName", {}).get("Zh_tw", "") for item in active_list
                    ]

                    if full_stop_list:
                        html_buffer = TIMELINE_CSS + '<div class="timeline-container">'
                        ai_log_list = []

                        for s_name in full_stop_list:
                            item = realtime_map.get(s_name, {})
                            eta_seconds = item.get("EstimateTime")
                            stop_status = item.get("StopStatus", 1)
                            plate_number = item.get("PlateNumb", "")
                            v_type = item.get("VehicleType")
                            is_low_floor = (v_type in [3, 4]) or (item.get("IsLowFloor") == True)
                            car_size = "中巴" if v_type == 2 else "大巴"

                            if eta_seconds is None:
                                if stop_status == 2:   time_text = "交管不停";  badge_cls = "ts-gray"
                                elif stop_status == 3: time_text = "末班車已過"; badge_cls = "ts-gray"
                                else:                  time_text = "尚未發車";  badge_cls = "ts-gray"
                            elif eta_seconds <= 120:
                                time_text = "即將進站"; badge_cls = "ts-orange"
                            else:
                                time_text = f"{eta_seconds // 60} 分鐘"; badge_cls = "ts-green"

                            bus_html = ""
                            if plate_number and plate_number not in ("🧱", "無車牌"):
                                wheelchair_text = "♿ 低底盤" if is_low_floor else "一般車"
                                bus_html = (
                                    f'<span class="bus-tag">🚌 {plate_number} ({car_size})</span>'
                                    f'<span class="wheelchair-tag">{wheelchair_text}</span>'
                                )

                            # ── UBike 標籤 ──
                            ubike_html = ""
                            if s_name in stop_coord_map:
                                s_lat, s_lon = stop_coord_map[s_name]
                                nearby_ub = get_ubike_near_stop(s_lat, s_lon)
                                for ub in nearby_ub:
                                    ubike_html += (
                                        f'<span class="ubike-tag">'
                                        f'🚲 可借:{ub["available"]} 可還:{ub["empty"]}'
                                        f'</span>'
                                    )

                            html_buffer += f"""
<div class="timeline-item">
  <div class="timeline-circle"></div>
  <div class="station-box">
    <div class="station-info">
      <span class="station-name">{s_name}</span>
      {bus_html}
      {ubike_html}
    </div>
    <span class="time-badge {badge_cls}">{time_text}</span>
  </div>
</div>
"""
                            if start_st and s_name == start_st:
                                ai_log_list.append({
                                    "當前等候站": s_name,
                                    "動態": time_text,
                                    "車牌": plate_number if plate_number else "無",
                                    "是否無障礙": "是" if is_low_floor else "否"
                                })

                        html_buffer += "</div>"
                        st.components.v1.html(html_buffer, height=600, scrolling=True)

                        target_st_name = start_st if start_st else "未設定"
                        bus_status = (
                            f"使用者目前關注路線：{route_choice}（往{st.session_state.dir_toggle}方向）。"
                            f"關注站點【{target_st_name}】的當前動態：{json.dumps(ai_log_list, ensure_ascii=False)}"
                        )
                    else:
                        st.info("暫時無此方向的站點資訊。")
                else:
                    st.error("無法取得即時動態，請檢查網路或 TDX 帳號狀態。")
            else:
                st.info("👈 請從左側選擇路線開始查詢")

        # ════════════════════════════════════════
        # AI 問答區
        # ════════════════════════════════════════
        st.divider()
        st.subheader("🤖 問問 AI 助理")

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.write(message["content"])

        user_question = st.chat_input("有什麼我可以幫忙的嗎？(可查公車建議、台南景點等)")

        if user_question:
            with st.chat_message("user"):
                st.write(user_question)
            with st.spinner("AI 正在思考中..."):
                try:
                    prompt_content = f"【目前天氣】: {current_weather}\n【公車狀態】: {bus_status}"
                    current_user_payload = f"{prompt_content}\n使用者問題 : {user_question}"
                    groq_messages = [
                        {"role": "system", "content": "你是一位專業、友善的台南公車導遊。請根據當前的天氣、公車狀態以及使用者之前的對話脈絡，給予貼心流暢的中文回答。"}
                    ]
                    for hist in st.session_state.chat_history:
                        groq_messages.append({"role": hist["role"], "content": hist["content"]})
                    groq_messages.append({"role": "user", "content": current_user_payload})
                    chat_completion = client.chat.completions.create(
                        messages=groq_messages, model="llama-3.3-70b-versatile"
                    )
                    ai_text = chat_completion.choices[0].message.content
                    with st.chat_message("assistant"):
                        st.write(ai_text)
                    st.session_state.chat_history.append({"role": "user", "content": user_question})
                    st.session_state.chat_history.append({"role": "assistant", "content": ai_text})
                except Exception as ai_e:
                    st.error(f"抱歉，AI 助理暫時發生錯誤：{ai_e}")

    except Exception as e:
        st.error(f"發生系統錯誤 : {e}")
