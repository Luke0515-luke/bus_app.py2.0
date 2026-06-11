import json
import streamlit as st
import requests
import pd as pd  # 如果需要更進階的 dataframe 操作，先保留
from groq import Groq

# 1. 讀取 Secrets
app_id = st.secrets["CLIENT_ID"] 
app_key = st.secrets["CLIENT_SECRET"] 

if "GROQ_API_KEY" in st.secrets: 
    client = Groq(api_key=st.secrets["GROQ_API_KEY"]) 
else:
    st.error("找不到 GROQ_API_KEY，請檢查 Secrets！")

# --- 2. 預先輸入大台南公車完整路線分類字典（依官方 PDA 建立） ---
ROUTE_CATEGORIES = {
    "黃線 (新營/後壁/白河/麻豆)": [
        "黃幹線", "黃1", "黃2", "黃2-1", "黃3", "黃4", "黃5", "黃6", "黃6-1", "黃7", "黃9", 
        "黃10", "黃10-1", "黃10-2", "黃11", "黃11-1", "黃11-2", "黃12", "黃12-1", "黃12-2", 
        "黃13", "黃14", "黃14-1", "黃15", "黃16", "黃16-1", "黃20", "黃21", "黃22"
    ],
    "棕線 (新營/鹽水/學甲/佳里)": [
        "棕幹線", "棕1", "棕2", "棕3", "棕3-1", "棕4", "棕5", "棕6", "棕10", "棕11"
    ],
    "綠線 (玉井/新化/左鎮/楠西)": [
        "綠幹線", "綠1", "綠2", "綠2-1", "綠3", "綠4", "綠5", "綠6", "綠7", "綠10", "綠11", 
        "綠12", "綠12-1", "綠12-2", "綠13", "綠14", "綠15", "綠16", "綠17", "綠20", "綠20-1", 
        "綠21", "綠22", "綠23", "綠24", "綠25", "綠26", "綠27", "綠28", "綠29", "綠30", "綠30-1", 
        "綠31", "綠32"
    ],
    "橘線 (佳里/麻豆/玉井/大內)": [
        "橘幹線", "橘1", "橘2", "橘3", "橘4", "橘4-1", "橘5", "橘6", "橘9", "橘9-1", 
        "橘10", "橘10-1", "橘11", "橘11-1", "橘12", "橘13", "橘14", "橘20", "橘21"
    ],
    "藍線 (安平/佳里/將軍/北門)": [
        "藍幹線", "藍1", "藍2", "藍3", "藍4", "藍10", "藍11", "藍13", "藍14", "藍15", 
        "藍20", "藍21", "藍22", "藍23", "藍24", "藍25", "藍26", "藍27", "藍28", "藍29", "藍30"
    ],
    "紅線 (台南/關廟/龍崎/高鐵)": [
        "紅幹線", "紅1", "紅2", "紅3", "紅4", "紅10", "紅11", "紅12", "紅13", "紅14"
    ],
    "市區數字公車 (台南市區)": [
        "0左", "0右", "6", "7", "9", "10", "11", "14", "15", "18", "19", "20", "21", 
        "31", "32", "33", "62", "70左", "70右", "77", "98", "101", "102", "103", "107", 
        "111", "168", "901", "902", "904", "905"
    ],
    "高鐵快捷與觀光線路": [
        "H31", "33", "東山咖啡線", "梅嶺線", "菱波官田線", "雙層巴士"
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

@st.cache_data(ttl=3600)
def fetch_route_stops(route_name, headers_dict):
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
def fetch_bus_data(url, headers_dict):
    try:
        res = requests.get(url, headers=headers_dict)
        if res.status_code == 200: 
            return res.json() 
    except:
        return None
    return None

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


if __name__ == '__main__':
    st.set_page_config(page_title="台南公車 AI 助理", page_icon="🚌")
    st.header("🚌 台南公車即時時刻查詢")

    try:
        a = Auth(app_id, app_key)
        auth_res = requests.post(auth_url, data=a.get_auth_header())
        d = DataProcessor(auth_res)
        h = d.get_data_header()

        current_weather = "使用者尚未查詢"
        bus_status = "使用者尚未查詢路線"

        # --- 側邊欄設定（已修正重複元件與 key 衝突問題） ---
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
                    st.session_state.selected_filter = "綠"
                    reset_search()
            with row1_col2:
                if st.button("橘", use_container_width=True):
                    st.session_state.selected_filter = "橘"
                    reset_search()
            with row1_col3:
                if st.button("1", use_container_width=True):
                    st.session_state.selected_filter = "1"
                    reset_search()
            with row1_col4:
                if st.button("2", use_container_width=True):
                    st.session_state.selected_filter = "2"
                    reset_search()

            # 第二排按鈕
            row2_col1, row2_col2, row2_col3, row2_col4 = st.columns(4)
            with row2_col1:
                if st.button("棕", use_container_width=True):
                    st.session_state.selected_filter = "棕"
                    reset_search()
            with row2_col2:
                if st.button("藍", use_container_width=True):
                    st.session_state.selected_filter = "藍"
                    reset_search()
            with row2_col3:
                if st.button("4", use_container_width=True):
                    st.session_state.selected_filter = "4"
                    reset_search()
            with row2_col4:
                if st.button("5", use_container_width=True):
                    st.session_state.selected_filter = "5"
                    reset_search()

            # 第三排按鈕
            row3_col1, row3_col2, row3_col3, row3_col4 = st.columns(4)
            with row3_col1:
                if st.button("紅", use_container_width=True):
                    st.session_state.selected_filter = "紅"
                    reset_search()
            with row3_col2:
                if st.button("黃", use_container_width=True):
                    st.session_state.selected_filter = "黃"
                    reset_search()
            with row3_col3:
                if st.button("7", use_container_width=True):
                    st.session_state.selected_filter = "7"
                    reset_search()
            with row3_col4:
                if st.button("8", use_container_width=True):
                    st.session_state.selected_filter = "8"
                    reset_search()

            # 第四排按鈕
            row4_col1, row4_col2, row4_col3, row4_col4 = st.columns(4)
            with row4_col1:
                if st.button("市區", use_container_width=True):
                    st.session_state.selected_filter = "市區"
                    reset_search()
            with row4_col2:
                if st.button("高鐵", use_container_width=True):
                    st.session_state.selected_filter = "H"
                    reset_search()
            with row4_col3:
                if st.button("0", use_container_width=True):
                    st.session_state.selected_filter = "0"
                    reset_search()
            with row4_col4:
                if st.button("❌", use_container_width=True):
                    st.session_state.selected_filter = None
                    reset_search()

            current_filter = st.session_state.selected_filter
            if current_filter:
                st.success(f"目前已選擇篩選：【{current_filter}】")
            else:
                st.info("目前顯示：全部路線")

            all_possible_routes = []
            for routes_list in ROUTE_CATEGORIES.values():
                all_possible_routes.extend(routes_list)
            all_possible_routes = sorted(list(set(all_possible_routes)))

            if current_filter is None:
                filtered_routes = all_possible_routes
            elif current_filter == "市區":
                filtered_routes = ROUTE_CATEGORIES["市區數字公車 (台南市區)"]
            else:
                filtered_routes = [r for r in all_possible_routes if current_filter in r]

            # 路線選單
            route_choice = st.selectbox(
                "請選擇公車路線", 
                filtered_routes,
                index=None,
                placeholder="請選擇或輸入路線...",
                key="bus_route_select",
                on_change=reset_search
            )
            
            # 【核心修正】起訖站選單「全程式只保留這一段」，絕不重複
            if route_choice:
                all_stops = fetch_route_stops(route_choice, h)
                if all_stops:
                    start_st = st.selectbox("請選擇起始站", all_stops, key="start_select")
                    end_st = st.selectbox("請選擇目的地 (僅作路徑參考)", all_stops, index=len(all_stops)-1, key="end_select")
                    
                    if st.button("🔍 開始查詢即時動態", type="primary"):
                        st.session_state.search_clicked = True
                else:
                    st.warning("無法載入站點資訊")
            else:
                st.info("請先點選上方按鈕或在選單中選擇路線。")

        # --- 3. 主畫面顯示區：結合垂直時間軸站牌、無障礙與低碳資訊 ---
        if route_choice and st.session_state.get("search_clicked", False):
            weather_info = fetch_weather_data(h)
            current_weather = weather_info 
            
            url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/City/Tainan/{route_choice}?%24format=JSON"
            bus_list = fetch_bus_data(url, h)
            
            if bus_list:
                # 依官方排序或站點序號排順序
                bus_list = sorted(bus_list, key=lambda x: x.get('StopSequence', 0))
                
                st.subheader(f"🚌 {route_choice} 即時動態站牌 (往 {end_st})")
                st.caption(f"🌡️ 當前天氣：{weather_info}")

                # 注入網頁 CSS 樣式，完美復刻垂直時間軸
                st.markdown("""
                    <style>
                    .timeline-container { position: relative; padding-left: 30px; margin-left: 15px; border-left: 4px solid #7A5443; }
                    .timeline-item { position: relative; margin-bottom: 20px; }
                    .timeline-circle { position: absolute; left: -39px; top: 4px; width: 18px; height: 18px; background-color: white; border: 4px solid #7A5443; border-radius: 50%; z-index: 1; }
                    .station-info { display: flex; justify-content: space-between; align-items: center; background-color: #F8F9FA; padding: 10px 15px; border-radius: 8px; }
                    .station-name { font-size: 16px; font-weight: bold; color: #333333; }
                    .badge { padding: 6px 14px; border-radius: 20px; color: white; font-weight: bold; font-size: 13px; min-width: 85px; text-align: center; }
                    .status-gray { background-color: #9E9E9E; }
                    .status-orange { background-color: #FFA726; }
                    .status-green { background-color: #66BB6A; }
                    </style>
                """, unsafe_allow_html=True)

                st.markdown('<div class="timeline-container">', unsafe_allow_html=True)
                
                ai_log_list = []
                for item in bus_list:
                    stop_name = item.get("StopName", {}).get("Zh_tw", "未知站點")
                    eta_seconds = item.get("EstimateTime")
                    plate_number = item.get("PlateNumb", "")
                    
                    # 讀取隱藏的車輛進階資訊
                    vehicle_info = item.get("VehicleInfo", {})
                    v_type = vehicle_info.get("VehicleType")
                    is_electric = vehicle_info.get("IsElectricVehicle")

                    # 組裝無障礙與環保圖示
                    icons = ""
                    if v_type == 1: icons += " ♿無障礙"
                    if is_electric == True: icons += " ⚡電動車"

                    # 判斷時間外觀
                    if eta_seconds is None:
                        time_text = "尚未發車"
                        badge_class = "status-gray"
                    elif eta_seconds <= 120:
                        time_text = "即將進站"
                        badge_class = "status-orange"
                    else:
                        time_text = f"{eta_seconds // 60} 分鐘"
                        badge_class = "status-green"

                    # 車牌與型態的小字提示
                    bus_info_str = f"<br><small style='color:#757575;'>車牌: {plate_number} {icons}</small>" if plate_number else ""

                    # 只在選定的起始站點高亮提示（可選擇性加入背景色區別，此處維持簡潔）
                    st.markdown(f"""
                        <div class="timeline-item">
                            <div class="timeline-circle"></div>
                            <div class="station-info">
                                <div class="station-name">{stop_name}{bus_info_str}</div>
                                <div class="badge {badge_class}">{time_text}</div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

                    # 紀錄使用者目前在等的站點資料給 AI 當背景知識
                    if stop_name == start_st:
                        ai_log_list.append({
                            "路線": route_choice,
                            "站點": stop_name,
                            "時間": time_text,
                            "車牌": plate_number if plate_number else "尚未發車",
                            "特性": icons.strip() if icons else "一般車型"
                        })

                st.markdown('</div>', unsafe_allow_html=True)
                bus_status = f"目前等候站點資訊：{json.dumps(ai_log_list, ensure_ascii=False)}"
            else:
                st.error("無法取得公車即時動態資料。")
                
        elif not route_choice:
            st.image("https://img.icons8.com/clouds/200/bus.png")
            st.write("👋 你好！請在左側選單點選顏色與數字鍵盤，或直接在下方詢問 AI 助理。")

        # --- 4. AI 對話區（記憶鏈完全體） ---
        st.divider()
        st.subheader("🤖 問問 AI 助理")

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        for message in st.session_state.chat_history:
            if message["role"] == "user":
                with st.chat_message("user"):
                    st.write(message["content"])
            else:
                with st.chat_message("assistant"):
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
                        {"role": "system", "content": "你是一位專業、友善的台南公車導遊。請根據當前的天氣、公車狀態（包含車牌、低地板無障礙、電動車等資訊）以及使用者之前的對話脈絡，給予貼心流暢的中文回答。"}
                    ]
                    
                    for hist in st.session_state.chat_history:
                        groq_messages.append({"role": hist["role"], "content": hist["content"]})
                    
                    groq_messages.append({"role": "user", "content": current_user_payload})
                
                    chat_completion = client.chat.completions.create(
                        messages=groq_messages,
                        model="llama-3.3-70b-versatile"
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
