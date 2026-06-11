import json
import streamlit as st
import requests
import pandas as pd
from groq import Groq

# 1. 讀取 Secrets
app_id = st.secrets["CLIENT_ID"] 
app_key = st.secrets["CLIENT_SECRET"] 

if "GROQ_API_KEY" in st.secrets: 
    client = Groq(api_key=st.secrets["GROQ_API_KEY"]) 
else:
    st.error("找不到 GROQ_API_KEY，請檢查 Secrets！")

# --- 2. 預先輸入台南常用公車路線（完全不聯網，速度最快） ---
# --- 2. 預先輸入台南常用公車路線（分類字典格式） ---
# --- 2. 預先輸入大台南公車完整路線分類字典（不需聯網，速度最快） ---
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
        "綠幹線", "綠1", "綠2","綠2-1", "綠3", "綠4", "綠5", "綠6", "綠7", "綠10", "綠11", 
        "綠12","綠12-1","綠12-2", "綠13", "綠14", "綠15", "綠16", "綠17", "綠20","綠20-1", "綠21", "綠22", 
        "綠23", "綠24", "綠25", "綠26", "綠27", "綠28", "綠29", "綠30","綠30-1", "綠31", "綠32"
    ],
    "橘線 (佳里/麻豆/玉井/大內)": [
        "橘幹線", "橘1", "橘2", "橘3", "橘4", "橘4-1", "橘5", "橘6", "橘9", "橘9-1", 
        "橘10", "橘10-1", "橘11", "橘11-1", "橘12", "橘13", "橘14", "橘20"
    ],
    "藍線 (安平/佳里/將軍/北門)": [
        "藍幹線", "藍1", "藍2", "藍3", "藍4", "藍10", "藍11", "藍13","藍14", "藍15", 
        "藍20", "藍21", "藍22", "藍23", "藍24", "藍25", "藍26", "藍27", "藍28", "藍29", "藍30"
    ],
    "紅線 (台南/關廟/龍崎/高鐵)": [
        "紅幹線", "紅1", "紅2", "紅3", "紅4", "紅10", "紅11", "紅12", 
        "紅13", "紅14"
    ],
   
    "市區數字公車 (台南市區)": [
        "0左", "0右", "6", "7", "9", "10", "11", "14", "15", "18", 
        "19", "20", "21", "31", "32", "33", "62","70左", "70右", "77", "98", "101", "102", "103", "107", "111", "168", 
        "901", "902", "904", "905"
    ],
   "高鐵快捷": [
        "H31"
    ],
    "觀光": [
        "東山咖啡線", "梅嶺線", "菱波官田線", "雙層巴士"
    ]
}

# --- TDX 驗證與資料處理類別 ---
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

# 當使用者選了路線，才去 TDX 抓該路線的「所有站點」清單（有快取 1 小時）
@st.cache_data(ttl=3600)
# --- 🛠️ 離線站點快取讀取機制（極省 API 用量關鍵） ---
def fetch_route_stops(route_name, headers_dict):
    # 1. 嘗試讀取本機的靜態站點快取 JSON
    try:
        with open("tainan_stops_cache.json", "r", encoding="utf-8") as f:
            local_cache = json.load(f)
            if route_name in local_cache and local_cache[route_name]:
                return local_cache[route_name]
    except FileNotFoundError:
        # 如果還沒產生 json 檔，就放行讓它去抓 API，確保程式不當機
        pass

    # 2. 如果本機快取找不到，才勉為其難去抓 TDX API
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


# 關鍵：當按下按鈕，才會動態抓取公車「即時預估到站時刻」（有快取 30 秒控制頻率）
@st.cache_data(ttl=30)
# --- 🛠️ 終極精簡聯網：一次把時間、車牌、無障礙全部抓完 ---
def fetch_bus_data(route_name, headers_dict):
    # 這個網址其實就包含了：到站時間、當前停靠車牌、以及車輛類型(無障礙)
    url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/City/Tainan/{route_name}?%24format=JSON"
    try:
        res = requests.get(url, headers=headers_dict)
        if res.status_code == 200: 
            return res.json() 
    except Exception as e:
        st.error(f"即時資料抓取失敗: {e}")
        return None
    return None


# 抓取台南即時氣象的函數
@st.cache_data(ttl=600) 
def fetch_weather_data(headers_dict):
    weather_url = "https://tdx.transportdata.tw/api/basic/v1/Weather/Observation/Station/City/Tainan?%24format=JSON"
    try:
        res = requests.get(weather_url, headers=headers_dict)
        if res.status_code == 200:
            data = res.json()
            if data:
                obs = data[0]
                temp = obs.get('AirTemperature', '未知')
                weather_desc = obs.get('Weather', '未知')
                return f"氣溫 {temp}°C，天氣狀況：{weather_desc}"
    except:
        return "暫時無法取得氣象資訊"
    return "尚無氣象資料"

# --- 程式執行主體 ---
# --- 程式執行主體 ---
if __name__ == '__main__':
    st.set_page_config(page_title="台南公車 AI 助理", page_icon="🚌")
    st.header("🚌 台南公車即時時刻查詢")

    try:
        # 1. 執行身份驗證
        a = Auth(app_id, app_key)
        auth_res = requests.post(auth_url, data=a.get_auth_header())
        d = DataProcessor(auth_res)
        h = d.get_data_header()

        # --- 初始化預設變數給 AI 使用 ---
        current_weather = "使用者尚未查詢"
        bus_status = "使用者尚未查詢路線"

        # --- 側邊欄設定：快速路線篩選鍵盤與選單 ---
        with st.sidebar:
            st.title("🚌 快速路線篩選")
            
            def reset_search():
                st.session_state.search_clicked = False

            if "selected_filter" not in st.session_state:
                st.session_state.selected_filter = None

            st.write("請點選顏色或數字進行篩選：")
            
            # 第一排按鈕
            row1_col1, row1_col2, row1_col3, row1_col4 = st.columns(4)
            with row1_col1:
                if st.button("綠", use_container_width=True):
                    st.session_state.selected_filter = "綠"; reset_search()
            with row1_col2:
                if st.button("橘", use_container_width=True):
                    st.session_state.selected_filter = "橘"; reset_search()
            with row1_col3:
                if st.button("1", use_container_width=True):
                    st.session_state.selected_filter = "1"; reset_search()
            with row1_col4:
                if st.button("2", use_container_width=True):
                    st.session_state.selected_filter = "2"; reset_search()

            # 第二排按鈕
            row2_col1, row2_col2, row2_col3, row2_col4 = st.columns(4)
            with row2_col1:
                if st.button("棕", use_container_width=True):
                    st.session_state.selected_filter = "棕"; reset_search()
            with row2_col2:
                if st.button("藍", use_container_width=True):
                    st.session_state.selected_filter = "藍"; reset_search()
            with row2_col3:
                if st.button("4", use_container_width=True):
                    st.session_state.selected_filter = "4"; reset_search()
            with row2_col4:
                if st.button("5", use_container_width=True):
                    st.session_state.selected_filter = "5"; reset_search()

            # 第三排按鈕
            row3_col1, row3_col2, row3_col3, row3_col4 = st.columns(4)
            with row3_col1:
                if st.button("紅", use_container_width=True):
                    st.session_state.selected_filter = "紅"; reset_search()
            with row3_col2:
                if st.button("黃", use_container_width=True):
                    st.session_state.selected_filter = "黃"; reset_search()
            with row3_col3:
                if st.button("7", use_container_width=True):
                    st.session_state.selected_filter = "7"; reset_search()
            with row3_col4:
                if st.button("8", use_container_width=True):
                    st.session_state.selected_filter = "8"; reset_search()

            # 第四排按鈕
            row4_col1, row4_col2, row4_col3, row4_col4 = st.columns(4)
            with row4_col1:
                if st.button("市區", use_container_width=True):
                    st.session_state.selected_filter = "市區"; reset_search()
            with row4_col2:
                if st.button("高鐵", use_container_width=True):
                    st.session_state.selected_filter = "高鐵"; reset_search()
            with row4_col3:
                if st.button("觀光", use_container_width=True):
                    st.session_state.selected_filter = "觀光"; reset_search()
            with row4_col4:
                if st.button("0", use_container_width=True):
                    st.session_state.selected_filter = "0"; reset_search()

            st.write("") 
            if st.button("❌ 清除篩選條件", use_container_width=True):
                st.session_state.selected_filter = None; reset_search()

            current_filter = st.session_state.selected_filter
            if current_filter == "高鐵":
                st.success("目前已選擇篩選：【高鐵快捷公車】")
            elif current_filter == "觀光":
                st.success("目前已選擇篩選：【大台南觀光巴士】")
            elif current_filter:
                st.success(f"目前已選擇篩選：【{current_filter}】")
            else:
                st.info("目前顯示：全部路線")

            # --- 🛠️ 篩選與排序優化核心邏輯 ---
            all_possible_routes = []
            for routes_list in ROUTE_CATEGORIES.values():
                all_possible_routes.extend(routes_list)
            
            seen = set()
            all_possible_routes = [x for x in all_possible_routes if not (x in seen or seen.add(x))]

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
                            if route_str.startswith(current_filter): return (0, val, route_str)
                            return (1, val, route_str)
                        return (2, 999, route_str)
                    filtered_routes = sorted(raw_filtered, key=custom_numeric_sort)
                else:
                    filtered_routes = raw_filtered

            # 【核心步驟 4】第二層選單
            route_choice = st.selectbox(
                "請選擇公車路線", 
                filtered_routes,
                index=None,
                placeholder="請選擇或輸入路線...",
                key="bus_route_select",
                on_change=reset_search
            )
            
            # 【核心步驟 5】第三層選單：改為一選路線就自動開啟右側看板權限
            if route_choice:
                st.session_state.search_clicked = True
                all_stops = fetch_route_stops(route_choice, h)
                if all_stops:
                    start_st = st.selectbox("請選擇起始站 (可選)", all_stops, index=0, key="start_select")
                    end_st = st.selectbox("請選擇目的地 (僅作路徑參考)", all_stops, index=len(all_stops)-1, key="end_select")
                else:
                    st.warning(f"⚠️ 無法載入【{route_choice}】的站點資訊。")
                    start_st = None
            else:
                st.info("請先點選上方按鈕或在選單中選擇路線。")
                start_st = None

            # --- 🛠️ 專屬後台：手動更新快取工具 ---
            st.write("---")
            with st.expander("⚙️ 系統維護工具"):
                st.caption("每個月或台南公車大改點時，點擊下方按鈕一次即可。")
                if st.button("🔄 預載並更新全台南站點資料 (一個月點一次)", use_container_width=True):
                    with st.spinner("正在將全台南公車站點離線化，請稍候..."):
                        all_cache = {}
                        progress_bar = st.progress(0)
                        all_routes_to_fetch = []
                        for r_list in ROUTE_CATEGORIES.values():
                            all_routes_to_fetch.extend(r_list)
                        all_routes_to_fetch = list(set(all_routes_to_fetch))
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
                        st.success("🎉 全台南站點快取建立成功！已完美離線化。")

        # --- 3. 公車時刻顯示區：全功能垂直即時動態時間軸（往返同步、紅色警示燈優化版） ---
        if route_choice and st.session_state.get("search_clicked", False):
            weather_info = fetch_weather_data(h)
            current_weather = weather_info 
            
            # 呼叫一次 API，同時取得去回程所有動態資料
            bus_list = fetch_bus_data(route_choice, h)
            
            if bus_list is not None:
                direction_0 = [item for item in bus_list if item.get("Direction") == 0]
                direction_1 = [item for item in bus_list if item.get("Direction") == 1]
                
                direction_0 = sorted(direction_0, key=lambda x: x.get('StopSequence', 0))
                direction_1 = sorted(direction_1, key=lambda x: x.get('StopSequence', 0))
                
                dest_0 = direction_0[-1].get("StopName", {}).get("Zh_tw", "去程") if direction_0 else "去程"
                dest_1 = direction_1[-1].get("StopName", {}).get("Zh_tw", "回程") if direction_1 else "回程"

                st.subheader(f"🚌 {route_choice} 全線即時動態看板")
                st.caption(f"🌡️ 當前天氣：{weather_info}")

                if "dir_toggle" not in st.session_state:
                    st.session_state.dir_toggle = "去程"
                
                # 頂部控制按鈕列 (去程、回程、重新整理)
                col_btn1, col_btn2, col_btn3 = st.columns([1.5, 1.5, 1])
                with col_btn1:
                    if st.button(f"➡️ 往 {dest_0}", use_container_width=True, type="primary" if st.session_state.dir_toggle == "去程" else "secondary"):
                        st.session_state.dir_toggle = "去程"
                with col_btn2:
                    if st.button(f"⬅️ 往 {dest_1}", use_container_width=True, type="primary" if st.session_state.dir_toggle == "回程" else "secondary"):
                        st.session_state.dir_toggle = "回程"
                with col_btn3:
                    if st.button("🔄 重新整理", use_container_width=True):
                        st.toast("⏳ 正在更新即時站態...", icon="🚌")
                        st.rerun()

                active_list = direction_0 if st.session_state.dir_toggle == "去程" else direction_1

                if active_list:
                    # 🎨 注入 CSS 樣式
                    st.markdown("""
                        <style>
                        .timeline-container { position: relative; padding-left: 35px; margin-left: 15px; border-left: 4px solid #4A90E2; padding-top: 10px; padding-bottom: 10px; }
                        .timeline-item { position: relative; margin-bottom: 18px; }
                        .timeline-circle { position: absolute; left: -44px; top: 12px; width: 14px; height: 14px; background-color: white; border: 4px solid #4A90E2; border-radius: 50%; z-index: 2; }
                        .station-box { display: flex; justify-content: space-between; align-items: center; background-color: #FAFAFA; padding: 10px 15px; border-radius: 8px; border: 1px solid #EAEAEA; min-height: 55px; }
                        .station-info { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
                        .station-name { font-size: 15px; font-weight: bold; color: #333333; }
                        .bus-tag { background-color: #FF5A5F; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; display: inline-flex; align-items: center; }
                        .wheelchair-tag { background-color: #2ECC71; color: white; padding: 3px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; display: inline-flex; align-items: center; }
                        .time-badge { padding: 6px 12px; border-radius: 20px; color: white; font-weight: bold; font-size: 12px; min-width: 90px; text-align: center; display: inline-block; }
                        .ts-gray { background-color: #BDBDBD; }
                        .ts-red { background-color: #D32F2F; animation: pulse 0.8s infinite; }
                        .ts-orange { background-color: #FFA726; }
                        .ts-green { background-color: #66BB6A; }
                        @keyframes pulse { 0% { opacity: 0.8; } 50% { opacity: 1; } 100% { opacity: 0.8; } }
                        </style>
                    """, unsafe_allow_html=True)

                    # 💡 用大字串緩衝區拼接完整的 HTML，解決 </div> 亂碼問題
                    html_buffer = '<div class="timeline-container">'
                    ai_log_list = []
                    
                    for item in active_list:
                        s_name = item.get("StopName", {}).get("Zh_tw", "未知站點")
                        eta_seconds = item.get("EstimateTime")
                        stop_status = item.get("StopStatus", 0)
                        plate_number = item.get("PlateNumb", "")
                        
                        v_type = item.get("VehicleType")
                        is_low_floor = (v_type in [3, 4]) or (item.get("IsLowFloor") == True)
                        car_size = "中巴" if v_type == 2 else "大巴"

                        # 燈號判斷邏輯 (<=2分鐘紅燈閃爍, <=3分鐘橘燈)
                        if eta_seconds is None:
                            if stop_status == 1: time_text = "尚未發車"; badge_cls = "ts-gray"
                            elif stop_status == 2: time_text = "交管不停"; badge_cls = "ts-gray"
                            elif stop_status == 3: time_text = "末班車已過"; badge_cls = "ts-gray"
                            else: time_text = "未發車"; badge_cls = "ts-gray"
                        elif eta_seconds <= 120:
                            time_text = "即將進站"
                            badge_cls = "ts-red"
                        elif eta_seconds <= 180:
                            time_text = f"{eta_seconds // 60} 分鐘"
                            badge_cls = "ts-orange"
                        else:
                            time_text = f"{eta_seconds // 60} 分鐘"
                            badge_cls = "ts-green"

                        bus_html = ""
                        if plate_number and plate_number != "🧱" and plate_number != "無車牌":
                            wheelchair_text = "♿ 低底盤" if is_low_floor else "一般車"
                            bus_html = f"""
                            <span class="bus-tag">🚌 {plate_number} ({car_size})</span>
                            <span class="wheelchair-tag">{wheelchair_text}</span>
                            """

                        # 將各車站節點加進大字串包中
                        html_buffer += f"""
                        <div class="timeline-item">
                            <div class="timeline-circle"></div>
                            <div class="station-box">
                                <div class="station-info">
                                    <span class="station-name">{s_name}</span>
                                    {bus_html}
                                </div>
                                <span class="time-badge {badge_cls}">{time_text}</span>
                            </div>
                        </div>
                        """

                        if start_st and s_name == start_st:
                            ai_log_list.append({
                                "當前等候站": s_name, 
                                "動態": time_text, 
                                "車牌": plate_number,
                                "是否無障礙": "是" if is_low_floor else "否"
                            })

                    # 閉合隱形容器
                    html_buffer += "</div>"
                    
                    # 🎯 單次輸出，完美閉合結構
                    st.markdown(html_buffer, unsafe_allow_html=True)
                    
                    target_st_name = start_st if start_st else "未設定"
                    bus_status = f"使用者目前關注路線：{route_choice}（往{st.session_state.dir_toggle}方向）。關注站點【{target_st_name}】的當前動態紀錄：{json.dumps(ai_log_list, ensure_ascii=False)}"
                else:
                    st.info("暫時無此方向的站點班次資訊。")
            else:
                st.error("無法取得即時動態，請檢查網路或 TDX 帳號狀態。")
                
        else:
            # 💡 這裡對齊一開始的 if route_choice 判斷
            st.info("請在左側選單選擇公車路線以查看即時動態看板。")

    except Exception as main_err:
        st.error(f"系統執行主體發生錯誤: {main_err}")

        # --- 4. AI 對話區（已修正縮排與顯示 Bug） ---
                # --- 3. AI 對話區 ---
                # --- 3. AI 對話區 ---
        st.divider()
        st.subheader("🤖 問問 AI 助理")

        # 【步驟 1】初始化對話紀錄
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        # 【步驟 2】在網頁畫面上重繪過去的對話（前端顯示）
        for message in st.session_state.chat_history:
            if message["role"] == "user":
                with st.chat_message("user"):
                    st.write(message["content"])
            else:
                with st.chat_message("assistant"):
                    st.write(message["content"])

        # 【步驟 3】接收使用者新輸入
        user_question = st.chat_input("有什麼我可以幫忙的嗎？(可查公車建議、台南景點等)")
        
        if user_question:
            # 立即在畫面上秀出使用者的最新問題
            with st.chat_message("user"):
                st.write(user_question)

            with st.spinner("AI 正在思考中..."):
                try:  
                    # 這是當前最新的環境變數與問題
                    prompt_content = f"【目前天氣】: {current_weather}\n【公車狀態】: {bus_status}"
                    current_user_payload = f"{prompt_content}\n使用者問題 : {user_question}"
                    
                    # 🧠 【靈魂步驟：建構給 Groq 的記憶包】
                    # 首先放最基本的人設
                    groq_messages = [
                        {"role": "system", "content": "你是一位專業、友善的台南公車導遊。請根據當前的天氣、公車狀態以及使用者之前的對話脈絡，給予貼心流暢的中文回答。"}
                    ]
                    
                    # 接著，把過去聊過的所有歷史紀錄「依序」塞進去給 Groq 看
                    for hist in st.session_state.chat_history:
                        groq_messages.append({"role": hist["role"], "content": hist["content"]})
                    
                    # 最後，把「當前的天氣動態 + 使用者最新問的問題」當作最後一發子彈塞進去
                    groq_messages.append({"role": "user", "content": current_user_payload})
                
                    # 傳送包含「完整記憶歷史」的封包給 Groq
                    chat_completion = client.chat.completions.create(
                        messages=groq_messages, # <-- 換成我們精心打包好的記憶矩陣！
                        model="llama-3.3-70b-versatile"
                    )
                
                    ai_text = chat_completion.choices[0].message.content
                    
                    # 在畫面上秀出 AI 的回答
                    with st.chat_message("assistant"):
                        st.write(ai_text)
                    
                    # 💾 【最後關鍵：把這次的對話存入 session_state 記憶庫】
                    # 注意：我們存進記憶庫時，使用者這邊「存單純的問題」就好，不要把落落長的天氣公車背景資料存進歷史，這樣下次對話歷史才乾淨。
                    st.session_state.chat_history.append({"role": "user", "content": user_question})
                    st.session_state.chat_history.append({"role": "assistant", "content": ai_text})

                except Exception as ai_e:                  
                    st.error(f"抱歉，AI 助理暫時發生錯誤：{ai_e}")
                    
    except Exception as e:  
        st.error(f"發生系統錯誤 : {e}")
