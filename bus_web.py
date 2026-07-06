import json
import math
import streamlit as st
import requests
from groq import Groq
from datetime import datetime

app_id = st.secrets["CLIENT_ID"]
app_key = st.secrets["CLIENT_SECRET"]

if "GROQ_API_KEY" in st.secrets:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
else:
    st.error("找不到 GROQ_API_KEY，請檢查 Secrets！")

ROUTE_CATEGORIES = {
    "黃線": ["黃幹線","黃1","黃2","黃3","黃4","黃5","黃6","黃6-1","黃7","黃9","黃10","黃11","黃11-1","黃12","黃13","黃14","黃14-1","黃15","黃16","黃20","黃22","黃23","黃24","黃25"],
    "棕線": ["棕幹線","棕1","棕2","棕3","棕3-1","棕4","棕5","棕6","棕20","棕10","棕11"],
    "綠線": ["綠幹線","綠1","綠2","綠2-1","綠3","綠4","綠5","綠6","綠7","綠10","綠11","綠12","綠12-1","綠12-2","綠13","綠14","綠15","綠16","綠17","綠20","綠20-1","綠21","綠22","綠23","綠24","綠25","綠26","綠27","綠28","綠29","綠30","綠30-1","綠31","綠32"],
    "橘線": ["橘幹線","橘1","橘2","橘3","橘4","橘4-1","橘5","橘6","橘9","橘9-1","橘10","橘10-1","橘11","橘11-1","橘12","橘13","橘14","橘20"],
    "藍線": ["藍幹線","藍1","藍2","藍3","藍4","藍10","藍11","藍13","藍14","藍15","藍20","藍21","藍22","藍23","藍24","藍25","藍26","藍27","藍28","藍29","藍30"],
    "紅線": ["紅幹線","紅1","紅2","紅3","紅4","紅10","紅11","紅12","紅13","紅14"],
    "市區": ["0左","0右","6","7","9","10","11","14","15","18","19","20","21","31","32","33","62","70左","70右","77","98","101","102","103","107","111","168","901","902","904","905"],
    "高鐵快捷": ["H31"],
    "觀光": ["東山咖啡線","梅嶺線","菱波官田線","雙層巴士"]
}

auth_url = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
TAINAN_LAT, TAINAN_LON = 22.9997, 120.2270

class Auth():
    def __init__(self, app_id, app_key):
        self.app_id = app_id
        self.app_key = app_key
    def get_auth_header(self):
        return {'content-type':'application/x-www-form-urlencoded','grant_type':'client_credentials','client_id':self.app_id,'client_secret':self.app_key}

class DataProcessor():
    def __init__(self, auth_response):
        self.auth_response = auth_response
    def get_data_header(self):
        token = self.auth_response.json().get('access_token')
        return {'authorization': f'Bearer {token}', 'Accept-Encoding': 'gzip'}

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    d_lat = math.radians(lat2-lat1)
    d_lon = math.radians(lon2-lon1)
    a = math.sin(d_lat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(d_lon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

# ── Session state 初始化 ────────────────────────────────────
def init_session():
    defaults = {
        "selected_filter": None,
        "search_clicked": False,
        "dir_toggle": "去程",
        "user_lat": None,
        "user_lon": None,
        "recent_routes": [],        # 最近查詢路線 (最多5筆)
        "favorite_routes": [],      # 最愛路線
        "chat_sessions": {},        # {session_id: {"title": str, "history": list}}
        "current_session_id": None, # 目前對話 session
        "show_chat_history": False, # 是否顯示對話記錄頁面
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ── 快取函數 ────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_route_stops(route_name, token):
    try:
        with open("tainan_stops_cache.json","r",encoding="utf-8") as f:
            c = json.load(f)
            if route_name in c and c[route_name]:
                return c[route_name]
    except FileNotFoundError:
        pass
    url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/StopOfRoute/City/Tainan/{route_name}?%24format=JSON"
    headers = {'authorization': f'Bearer {token}', 'Accept-Encoding': 'gzip'}
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            data = res.json()
            if data:
                return [s['StopName']['Zh_tw'] for s in data[0]['Stops']]
    except:
        pass
    return []

@st.cache_data(ttl=30)
def fetch_bus_data(route_name, token):
    url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/City/Tainan/{route_name}?%24format=JSON"
    headers = {'authorization': f'Bearer {token}', 'Accept-Encoding': 'gzip'}
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return None

@st.cache_data(ttl=600)
def fetch_weather():
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={TAINAN_LAT}&longitude={TAINAN_LON}&current=temperature_2m,weathercode,windspeed_10m&timezone=Asia%2FTaipei"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            cur = res.json().get("current", {})
            temp = cur.get("temperature_2m","?")
            wind = cur.get("windspeed_10m","?")
            wmap = {0:"晴天☀️",1:"大致晴朗🌤️",2:"部分多雲⛅",3:"陰天☁️",45:"有霧🌫️",51:"毛毛雨🌦️",61:"小雨🌧️",63:"中雨🌧️",65:"大雨🌧️",80:"陣雨🌦️",95:"雷雨⛈️"}
            desc = wmap.get(cur.get("weathercode",-1), "未知")
            return f"{desc}，氣溫 {temp}°C，風速 {wind} km/h"
    except:
        pass
    return "無法取得天氣"

@st.cache_data(ttl=60)
def fetch_ubike_all(token):
    headers = {'authorization': f'Bearer {token}', 'Accept-Encoding': 'gzip'}
    stations, avail_map = [], {}
    try:
        r1 = requests.get("https://tdx.transportdata.tw/api/basic/v2/Bike/Station/City/Tainan?%24format=JSON", headers=headers, timeout=8)
        r2 = requests.get("https://tdx.transportdata.tw/api/basic/v2/Bike/Availability/City/Tainan?%24format=JSON", headers=headers, timeout=8)
        if r1.status_code == 200: stations = r1.json()
        if r2.status_code == 200:
            for av in r2.json(): avail_map[av["StationUID"]] = av
    except:
        pass
    return stations, avail_map

@st.cache_data(ttl=300)
def fetch_all_bus_stops(token):
    url = "https://tdx.transportdata.tw/api/basic/v2/Bus/Stop/City/Tainan?%24format=JSON"
    headers = {'authorization': f'Bearer {token}', 'Accept-Encoding': 'gzip'}
    try:
        res = requests.get(url, headers=headers, timeout=20)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        st.warning(f"附近站牌 API 錯誤：{e}")
    return []

def find_nearby_stops(all_stops, lat, lon, radius_km=0.5):
    nearby, seen = [], set()
    for stop in all_stops:
        pos = stop.get("StopPosition", {})
        s_lat, s_lon = pos.get("PositionLat"), pos.get("PositionLon")
        name = stop.get("StopName", {}).get("Zh_tw", "")
        if s_lat and s_lon and name and name not in seen:
            dist = haversine(lat, lon, s_lat, s_lon)
            if dist <= radius_km:
                seen.add(name)
                nearby.append({"name": name, "dist": dist})
    nearby.sort(key=lambda x: x["dist"])
    return nearby[:15]

def get_ubike_near(s_lat, s_lon, stations, avail_map, radius_km=0.3):
    result = []
    for ub in stations:
        pos = ub.get("StationPosition", {})
        u_lat, u_lon = pos.get("PositionLat"), pos.get("PositionLon")
        if u_lat and u_lon and haversine(s_lat, s_lon, u_lat, u_lon) <= radius_km:
            uid = ub.get("StationUID","")
            av = avail_map.get(uid, {})
            result.append({"name": ub.get("StationName",{}).get("Zh_tw",""), "available": av.get("AvailableRentBikes","?"), "empty": av.get("AvailableReturnBikes","?")})
    return result

def add_recent_route(route):
    lst = st.session_state.recent_routes
    if route in lst:
        lst.remove(route)
    lst.insert(0, route)
    st.session_state.recent_routes = lst[:5]

def new_chat_session():
    sid = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.session_state.chat_sessions[sid] = {"title": f"對話 {datetime.now().strftime('%m/%d %H:%M')}", "history": []}
    st.session_state.current_session_id = sid
    return sid

def get_current_history():
    sid = st.session_state.current_session_id
    if sid and sid in st.session_state.chat_sessions:
        return st.session_state.chat_sessions[sid]["history"]
    return []

# ── CSS ────────────────────────────────────────────────────
TIMELINE_CSS = """
<style>
* { box-sizing: border-box; font-family: 'Noto Sans TC', sans-serif; }
body { margin: 0; padding: 8px; background: transparent; }
.timeline-container { position: relative; padding-left: 35px; margin-left: 15px; border-left: 4px solid #4A90E2; padding-top: 10px; padding-bottom: 10px; }
.timeline-item { position: relative; margin-bottom: 18px; }
.timeline-circle { position: absolute; left: -44px; top: 12px; width: 14px; height: 14px; background-color: white; border: 4px solid #4A90E2; border-radius: 50%; z-index: 2; }
.station-box { display: flex; justify-content: space-between; align-items: center; background-color: #FAFAFA; padding: 10px 15px; border-radius: 8px; border: 1px solid #EAEAEA; min-height: 55px; }
.station-info { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.station-name { font-size: 15px; font-weight: bold; color: #333333; }
.bus-tag { background-color: #FF5A5F; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; display: inline-flex; align-items: center; }
.wheelchair-tag { background-color: #2ECC71; color: white; padding: 3px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; display: inline-flex; align-items: center; }
.no-wheelchair-tag { background-color: #95a5a6; color: white; padding: 3px 6px; border-radius: 4px; font-size: 11px; display: inline-flex; align-items: center; }
.ubike-tag { background-color: #007bff; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; display: inline-flex; align-items: center; gap: 4px; }
.time-badge { padding: 6px 12px; border-radius: 20px; color: white; font-weight: bold; font-size: 12px; min-width: 90px; text-align: center; display: inline-block; }
.ts-gray { background-color: #BDBDBD; }
.ts-orange { background-color: #FFA726; animation: pulse 1s infinite; }
.ts-green { background-color: #66BB6A; }
@keyframes pulse { 0%{opacity:.8} 50%{opacity:1} 100%{opacity:.8} }
</style>
"""

# ══════════════════════════════════════════════════════════
# 主程式
# ══════════════════════════════════════════════════════════
if __name__ == '__main__':
    st.set_page_config(page_title="台南公車 AI 助理", page_icon="🚌", layout="wide")
    init_session()

    try:
        a = Auth(app_id, app_key)
        auth_res = requests.post(auth_url, data=a.get_auth_header())
        token = auth_res.json().get("access_token", "")
        h = {'authorization': f'Bearer {token}', 'Accept-Encoding': 'gzip'}

        current_weather = "尚未查詢"
        bus_status = "尚未查詢路線"

        # ── 側邊欄 ────────────────────────────────────────
        with st.sidebar:
            st.title("🚌 台南公車助理")

            # ── AI 對話記錄按鈕 ──
            if st.button("💬 AI 對話記錄", use_container_width=True):
                st.session_state.show_chat_history = not st.session_state.show_chat_history

            if st.session_state.show_chat_history:
                st.subheader("📋 對話記錄")
                if st.button("➕ 新對話", use_container_width=True):
                    new_chat_session()
                    st.session_state.show_chat_history = False
                    st.rerun()
                if st.session_state.chat_sessions:
                    for sid, sess in sorted(st.session_state.chat_sessions.items(), reverse=True):
                        col_t, col_d = st.columns([4, 1])
                        with col_t:
                            label = ("▶ " if sid == st.session_state.current_session_id else "") + sess["title"]
                            if st.button(label, key=f"sess_{sid}", use_container_width=True):
                                st.session_state.current_session_id = sid
                                st.session_state.show_chat_history = False
                                st.rerun()
                        with col_d:
                            if st.button("🗑", key=f"del_{sid}"):
                                del st.session_state.chat_sessions[sid]
                                if st.session_state.current_session_id == sid:
                                    st.session_state.current_session_id = None
                                st.rerun()
                else:
                    st.info("尚無對話記錄")
                st.divider()

            # ── 最愛路線 ──
            if st.session_state.favorite_routes:
                st.subheader("⭐ 最愛路線")
                for fav in st.session_state.favorite_routes:
                    col_f, col_r = st.columns([3, 1])
                    with col_f:
                        if st.button(f"🚌 {fav}", key=f"fav_{fav}", use_container_width=True):
                            st.session_state.bus_route_select = fav
                            st.session_state.search_clicked = True
                            add_recent_route(fav)
                            st.rerun()
                    with col_r:
                        if st.button("✕", key=f"unfav_{fav}"):
                            st.session_state.favorite_routes.remove(fav)
                            st.rerun()
                st.divider()

            # ── 最近查詢 ──
            if st.session_state.recent_routes:
                st.subheader("🕐 最近查詢")
                for r in st.session_state.recent_routes:
                    if st.button(f"🔁 {r}", key=f"recent_{r}", use_container_width=True):
                        st.session_state.bus_route_select = r
                        st.session_state.search_clicked = True
                        add_recent_route(r)
                        st.rerun()
                st.divider()

            # ── 系統維護 ──
            with st.expander("⚙️ 系統維護"):
                st.caption("每月或大改點時更新一次。")
                if st.button("🔄 更新全台南站點快取", use_container_width=True):
                    with st.spinner("離線化中..."):
                        all_cache = {}
                        pb = st.progress(0)
                        all_r = list(set(r for rl in ROUTE_CATEGORIES.values() for r in rl))
                        for idx, r_name in enumerate(all_r):
                            s_url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/StopOfRoute/City/Tainan/{r_name}?%24format=JSON"
                            try:
                                rr = requests.get(s_url, headers=h)
                                if rr.status_code == 200:
                                    dj = rr.json()
                                    if dj: all_cache[r_name] = [s['StopName']['Zh_tw'] for s in dj[0]['Stops']]
                            except:
                                all_cache[r_name] = []
                            pb.progress((idx+1)/len(all_r))
                        with open("tainan_stops_cache.json","w",encoding="utf-8") as f:
                            json.dump(all_cache, f, ensure_ascii=False, indent=4)
                        st.success("🎉 快取建立成功！")

        st.header("🚌 台南公車即時時刻查詢")

        # ── 左右主欄 ──────────────────────────────────────
        left_col, right_col = st.columns([1, 3])

        # ════════════════════════════════
        # 左欄
        # ════════════════════════════════
        with left_col:
            st.subheader("🔍 路線篩選")

            def reset_search():
                st.session_state.search_clicked = False

            # 篩選按鈕
            st.caption("點選顏色或數字篩選：")
            cols1 = st.columns(4)
            if cols1[0].button("綠", use_container_width=True): st.session_state.selected_filter="綠"; reset_search()
            if cols1[1].button("橘", use_container_width=True): st.session_state.selected_filter="橘"; reset_search()
            if cols1[2].button("1",  use_container_width=True): st.session_state.selected_filter="1";  reset_search()
            if cols1[3].button("2",  use_container_width=True): st.session_state.selected_filter="2";  reset_search()

            cols2 = st.columns(4)
            if cols2[0].button("棕", use_container_width=True): st.session_state.selected_filter="棕"; reset_search()
            if cols2[1].button("藍", use_container_width=True): st.session_state.selected_filter="藍"; reset_search()
            if cols2[2].button("3",  use_container_width=True): st.session_state.selected_filter="3";  reset_search()
            if cols2[3].button("4",  use_container_width=True): st.session_state.selected_filter="4";  reset_search()

            cols3 = st.columns(4)
            if cols3[0].button("紅", use_container_width=True): st.session_state.selected_filter="紅"; reset_search()
            if cols3[1].button("黃", use_container_width=True): st.session_state.selected_filter="黃"; reset_search()
            if cols3[2].button("5",  use_container_width=True): st.session_state.selected_filter="5";  reset_search()
            if cols3[3].button("6",  use_container_width=True): st.session_state.selected_filter="6";  reset_search()

            cols4 = st.columns(4)
            if cols4[0].button("市區", use_container_width=True): st.session_state.selected_filter="市區"; reset_search()
            if cols4[1].button("高鐵", use_container_width=True): st.session_state.selected_filter="高鐵"; reset_search()
            if cols4[2].button("7",    use_container_width=True): st.session_state.selected_filter="7";    reset_search()
            if cols4[3].button("8",    use_container_width=True): st.session_state.selected_filter="8";    reset_search()

            cols5 = st.columns(4)
            if cols5[0].button("觀光", use_container_width=True): st.session_state.selected_filter="觀光"; reset_search()
            if cols5[1].button("9",    use_container_width=True): st.session_state.selected_filter="9";    reset_search()
            if cols5[2].button("0",    use_container_width=True): st.session_state.selected_filter="0";    reset_search()

            if st.button("❌ 清除篩選", use_container_width=True):
                st.session_state.selected_filter = None; reset_search()

            cf = st.session_state.selected_filter
            if cf: st.success(f"篩選：【{cf}】")
            else:  st.info("顯示：全部路線")

            # 路線清單
            all_routes = []
            for rl in ROUTE_CATEGORIES.values(): all_routes.extend(rl)
            seen_s = set()
            all_routes = [x for x in all_routes if not (x in seen_s or seen_s.add(x))]

            if cf is None: filtered_routes = all_routes
            elif cf == "市區": filtered_routes = ROUTE_CATEGORIES["市區"]
            elif cf == "高鐵": filtered_routes = ROUTE_CATEGORIES["高鐵快捷"]
            elif cf == "觀光": filtered_routes = ROUTE_CATEGORIES["觀光"]
            else:
                raw = [r for r in all_routes if cf in r]
                if cf.isdigit():
                    def nsort(rs):
                        nums = ''.join(c for c in rs if c.isdigit())
                        return (0 if rs.startswith(cf) else 1, int(nums) if nums else 999, rs)
                    filtered_routes = sorted(raw, key=nsort)
                else:
                    filtered_routes = raw

            route_choice = st.selectbox("選擇路線", filtered_routes, index=None,
                placeholder="請選擇或輸入路線...", key="bus_route_select", on_change=reset_search)

            # 最愛按鈕（路線旁邊）
            if route_choice:
                fav_list = st.session_state.favorite_routes
                is_fav = route_choice in fav_list
                fav_label = "⭐ 已加入最愛" if is_fav else "☆ 加入最愛"
                if st.button(fav_label, use_container_width=True, key="fav_toggle"):
                    if is_fav:
                        fav_list.remove(route_choice)
                    else:
                        fav_list.append(route_choice)
                    st.session_state.favorite_routes = fav_list
                    st.rerun()

            start_st = None
            if route_choice:
                st.session_state.search_clicked = True
                add_recent_route(route_choice)
                all_stops = fetch_route_stops(route_choice, token)
                if all_stops:
                    start_st = st.selectbox("等候站", all_stops, index=0, key="start_select")
                    st.selectbox("目的地", all_stops, index=len(all_stops)-1, key="end_select")
                else:
                    st.warning(f"⚠️ 無法載入【{route_choice}】站點。")
            else:
                st.info("請選擇路線")

            st.write("---")

            # ── GPS 附近站牌 ──────────────────────────────
            st.subheader("📍 附近公車站")

            # 手動輸入座標（簡單可靠）
            gps_html = """
<button onclick="
  navigator.geolocation.getCurrentPosition(function(pos){
    document.getElementById('lat_disp').value = pos.coords.latitude.toFixed(6);
    document.getElementById('lon_disp').value = pos.coords.longitude.toFixed(6);
  }, function(){ alert('請允許瀏覽器定位權限'); });
" style="width:100%;padding:8px;border-radius:6px;background:#4A90E2;color:white;border:none;cursor:pointer;font-size:13px;font-weight:bold;margin-bottom:8px;">
📡 自動取得座標（複製後貼到下方）
</button>
<div style="font-size:12px;margin-bottom:4px;">緯度：<input id="lat_disp" readonly style="width:120px;padding:3px;border:1px solid #ccc;border-radius:4px;" placeholder="點上方按鈕"/></div>
<div style="font-size:12px;">經度：<input id="lon_disp" readonly style="width:120px;padding:3px;border:1px solid #ccc;border-radius:4px;" placeholder="點上方按鈕"/></div>
"""
            st.components.v1.html(gps_html, height=110)

            gps_lat_input = st.text_input("緯度", placeholder="例：22.9997", key="gps_lat_in")
            gps_lon_input = st.text_input("經度", placeholder="例：120.2270", key="gps_lon_in")

            if st.button("🔍 搜尋附近站牌", use_container_width=True):
                try:
                    u_lat = float(gps_lat_input)
                    u_lon = float(gps_lon_input)
                    st.session_state.user_lat = u_lat
                    st.session_state.user_lon = u_lon
                except ValueError:
                    st.error("請輸入有效數字")

            if st.session_state.user_lat and st.session_state.user_lon:
                st.success(f"📍 {st.session_state.user_lat:.5f}, {st.session_state.user_lon:.5f}")
                with st.spinner("搜尋中..."):
                    all_stops_data = fetch_all_bus_stops(token)
                if all_stops_data:
                    nearby = find_nearby_stops(all_stops_data, st.session_state.user_lat, st.session_state.user_lon)
                    if nearby:
                        st.write(f"**找到 {len(nearby)} 個站牌（500m內）：**")
                        for ns in nearby:
                            st.write(f"🚏 **{ns['name']}**（{ns['dist']*1000:.0f}m）")
                    else:
                        st.warning("附近 500m 內無公車站牌")
                else:
                    st.error("無法載入站牌資料")
                if st.button("🗑️ 清除定位", use_container_width=True):
                    st.session_state.user_lat = None
                    st.session_state.user_lon = None
                    st.rerun()

        # ════════════════════════════════
        # 右欄
        # ════════════════════════════════
        with right_col:
            if route_choice and st.session_state.get("search_clicked", False):
                weather_info = fetch_weather()
                current_weather = weather_info
                st.info(f"🌡️ 台南目前天氣：{weather_info}")

                bus_list = fetch_bus_data(route_choice, token)
                if bus_list is not None:
                    dir0 = sorted([x for x in bus_list if x.get("Direction")==0], key=lambda x: x.get('StopSequence',0))
                    dir1 = sorted([x for x in bus_list if x.get("Direction")==1], key=lambda x: x.get('StopSequence',0))
                    dest_0 = dir0[-1].get("StopName",{}).get("Zh_tw","去程") if dir0 else "去程"
                    dest_1 = dir1[-1].get("StopName",{}).get("Zh_tw","回程") if dir1 else "回程"

                    st.subheader(f"🚌 {route_choice} 全線即時動態")

                    cb1, cb2, cb3 = st.columns([1.5,1.5,1])
                    with cb1:
                        if st.button(f"➡️ 往 {dest_0}", use_container_width=True, type="primary" if st.session_state.dir_toggle=="去程" else "secondary"):
                            st.session_state.dir_toggle = "去程"
                    with cb2:
                        if st.button(f"⬅️ 往 {dest_1}", use_container_width=True, type="primary" if st.session_state.dir_toggle=="回程" else "secondary"):
                            st.session_state.dir_toggle = "回程"
                    with cb3:
                        if st.button("🔄 重新整理", use_container_width=True):
                            st.rerun()

                    active_list = dir0 if st.session_state.dir_toggle=="去程" else dir1

                    # 站點座標
                    stop_coord_map = {}
                    try:
                        cr = requests.get(f"https://tdx.transportdata.tw/api/basic/v2/Bus/StopOfRoute/City/Tainan/{route_choice}?%24format=JSON", headers=h, timeout=5)
                        if cr.status_code == 200:
                            target_dir = 0 if st.session_state.dir_toggle=="去程" else 1
                            for rd in cr.json():
                                if rd.get("Direction") == target_dir:
                                    for s in rd.get("Stops",[]):
                                        name = s.get("StopName",{}).get("Zh_tw","")
                                        pos = s.get("StopPosition",{})
                                        if name and pos.get("PositionLat"):
                                            stop_coord_map[name] = (pos["PositionLat"], pos["PositionLon"])
                    except:
                        pass

                    ub_stations, ub_avail = fetch_ubike_all(token)

                    realtime_map = {item.get("StopName",{}).get("Zh_tw",""): item for item in active_list}
                    all_stops_raw = fetch_route_stops(route_choice, token)
                    full_stop_list = all_stops_raw or [item.get("StopName",{}).get("Zh_tw","") for item in active_list]

                    if full_stop_list:
                        html_buffer = TIMELINE_CSS + '<div class="timeline-container">'
                        ai_log_list = []

                        for s_name in full_stop_list:
                            item = realtime_map.get(s_name, {})
                            eta = item.get("EstimateTime")
                            status = item.get("StopStatus", 1)
                            plate = item.get("PlateNumb","")
                            v_type = item.get("VehicleType")
                            is_low = (v_type in [3,4]) or (item.get("IsLowFloor")==True)
                            car_size = "中巴" if v_type==2 else "大巴"

                            if eta is None:
                                if status==2:   time_text="交管不停";  bc="ts-gray"
                                elif status==3: time_text="末班車已過"; bc="ts-gray"
                                else:           time_text="尚未發車";  bc="ts-gray"
                            elif eta <= 120: time_text="即將進站"; bc="ts-orange"
                            else:            time_text=f"{eta//60} 分鐘"; bc="ts-green"

                            bus_html = ""
                            if plate and plate not in ("🧱","無車牌"):
                                # ✅ 無障礙圖示：有低底盤顯示綠色♿，否則顯示灰色一般車
                                if is_low:
                                    wc_html = '<span class="wheelchair-tag">♿ 低底盤</span>'
                                else:
                                    wc_html = '<span class="no-wheelchair-tag">🚌 一般車</span>'
                                bus_html = f'<span class="bus-tag">🚌 {plate} ({car_size})</span>{wc_html}'

                            ubike_html = ""
                            if s_name in stop_coord_map:
                                s_lat, s_lon = stop_coord_map[s_name]
                                for ub in get_ubike_near(s_lat, s_lon, ub_stations, ub_avail):
                                    ubike_html += f'<span class="ubike-tag">🚲 可借:{ub["available"]} 可還:{ub["empty"]}</span>'

                            html_buffer += f"""
<div class="timeline-item">
  <div class="timeline-circle"></div>
  <div class="station-box">
    <div class="station-info">
      <span class="station-name">{s_name}</span>
      {bus_html}{ubike_html}
    </div>
    <span class="time-badge {bc}">{time_text}</span>
  </div>
</div>
"""
                            if start_st and s_name == start_st:
                                ai_log_list.append({"站": s_name, "動態": time_text, "車牌": plate or "無", "無障礙": "是" if is_low else "否"})

                        html_buffer += "</div>"
                        st.components.v1.html(html_buffer, height=600, scrolling=True)
                        bus_status = f"路線：{route_choice}（往{st.session_state.dir_toggle}）。等候站動態：{json.dumps(ai_log_list, ensure_ascii=False)}"
                    else:
                        st.info("暫時無此方向站點資訊。")
                else:
                    st.error("無法取得即時動態。")
            else:
                st.info("👈 請從左側選擇路線開始查詢")

        # ════════════════════════════════
        # AI 問答區
        # ════════════════════════════════
        st.divider()
        st.subheader("🤖 AI 助理")

        # 確保有 session
        if st.session_state.current_session_id is None or \
           st.session_state.current_session_id not in st.session_state.chat_sessions:
            new_chat_session()

        sid = st.session_state.current_session_id
        sess = st.session_state.chat_sessions[sid]
        st.caption(f"目前對話：**{sess['title']}**")

        for msg in sess["history"]:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        user_q = st.chat_input("有什麼我可以幫忙的嗎？")
        if user_q:
            with st.chat_message("user"):
                st.write(user_q)
            with st.spinner("思考中..."):
                try:
                    payload = f"【天氣】{current_weather}\n【公車狀態】{bus_status}\n【問題】{user_q}"
                    msgs = [{"role":"system","content":"你是一位專業友善的台南公車導遊，請用流暢中文回答。"}]
                    for hst in sess["history"]:
                        msgs.append({"role": hst["role"], "content": hst["content"]})
                    msgs.append({"role":"user","content": payload})
                    resp = client.chat.completions.create(messages=msgs, model="llama-3.3-70b-versatile")
                    ai_text = resp.choices[0].message.content

                    # 自動更新對話標題（第一則訊息）
                    if len(sess["history"]) == 0:
                        sess["title"] = user_q[:20] + ("..." if len(user_q)>20 else "")

                    with st.chat_message("assistant"):
                        st.write(ai_text)
                    sess["history"].append({"role":"user","content": user_q})
                    sess["history"].append({"role":"assistant","content": ai_text})
                except Exception as e:
                    st.error(f"AI 錯誤：{e}")

    except Exception as e:
        st.error(f"發生系統錯誤：{e}")
