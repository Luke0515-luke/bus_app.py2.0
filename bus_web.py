Import json
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
   "高鐵快捷與觀觀線路": [
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

# 當使用者選了路線，才去 TDX 抓該路線的「所有站點」清單（有快取 1 小時）
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

# 關鍵：當按下按鈕，才會動態抓取公車「即時預估到站時刻」（有快取 30 秒控制頻率）
@st.cache_data(ttl=30)
def fetch_bus_data(url, headers_dict):
    try:
        res = requests.get(url, headers=headers_dict)
        if res.status_code == 200: 
            return res.json() 
    except:
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

        # 側邊欄設定
        # 側邊欄設定
                # 側邊欄設定
        with st.sidebar:
            st.title("🚌 快速路線篩選")
            
            def reset_search():
                st.session_state.search_clicked = False

            # 【核心步驟 1】初始化按鈕的記憶狀態
            if "selected_filter" not in st.session_state:
                st.session_state.selected_filter = None  # 一開始沒有選任何按鈕

            # 【核心步驟 2】打造像手機 App 一樣的按鈕鍵盤排版 (4欄位)
            st.write("請點選顏色或數字進行篩選：")
            
            # 第一排按鈕：綠、橘、1、2
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

            # 第二排按鈕：棕、藍、4、5
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

            # 第三排按鈕：紅、黃、7、8
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

            # 第四排按鈕：市區、H(高鐵)、0、清除
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
                    st.session_state.selected_filter = None  # 清除篩選
                    reset_search()

            # 顯示目前篩選狀態
            current_filter = st.session_state.selected_filter
            if current_filter:
                st.success(f"目前已選擇篩選：【{current_filter}】")
            else:
                st.info("目前顯示：全部路線")

            # 【核心步驟 3】根據點擊的按鈕，動態過濾出「符合條件」的公車支線清單
            filtered_routes = []
            
            # 撈出我們在頂部 ROUTE_CATEGORIES 定義的所有公車代號
            all_possible_routes = []
            for routes_list in ROUTE_CATEGORIES.values():
                all_possible_routes.extend(routes_list)
            # 去除重複值並排序
            all_possible_routes = sorted(list(set(all_possible_routes)))

            # 開始進行過濾邏輯
            if current_filter is None:
                filtered_routes = all_possible_routes
            elif current_filter == "市區":
                # 撈出純數字或是包含左右環狀線的市區公車
                filtered_routes = ROUTE_CATEGORIES["市區數字公車 (台南市區)"]
            else:
                # 如果選了「黃」，就撈出名稱有「黃」的公車；選了「2」，就撈出名稱有「2」的公車
                filtered_routes = [r for r in all_possible_routes if current_filter in r]

            # 【核心步驟 4】第二層選單：只顯示被篩選過後的公車路線
            route_choice = st.selectbox(
                "請選擇公車路線", 
                filtered_routes,
                index=None,
                placeholder="請選擇或輸入路線...",
                key="bus_route_select",
                on_change=reset_search
            )
            
            # 【核心步驟 5】第三層選單：選起訖站點（保持原本的邏輯）
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

            # --- 3. 第三層選單：選擇起訖站點（保持原本的邏輯） ---
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
                if category_choice:
                    st.info("請接著選擇具體的公車支線。")
                else:
                    st.info("請先在上方選擇公車分類。")

        # --- 3. 公車時刻顯示區：這裡完全不用改！ ---
        # 只要上面的 route_choice 是對的文字（例如 "黃22"），後面的 URL 拼接就會完全正常
        if route_choice and st.session_state.get("search_clicked", False):
            weather_info = fetch_weather_data(h)
            current_weather = weather_info 
            
            url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/City/Tainan/{route_choice}?%24format=JSON"
            bus_list = fetch_bus_data(url, h)
            
            if bus_list:
                bus_list = sorted(bus_list, key=lambda x: x.get('EstimateTime') if x.get('EstimateTime') is not None else 99999)
                filtered_list = [
                    {
                        "公車路線": route_choice,
                        "起始站點": stop.get('StopName', {}).get('Zh_tw'),
                        "預估到站時間": f"{stop.get('EstimateTime') // 60} 分鐘" if stop.get('EstimateTime') is not None else "尚未發車"
                    }
                    for stop in bus_list if stop.get('StopName', {}).get('Zh_tw') == start_st
                ]
                
                if filtered_list:
                    st.subheader(f"📍 正在 {start_st} 等候的公車 (往 {end_st})")
                    st.caption(f"🌡️ 當前天氣：{weather_info}")
                    st.table(filtered_list)
                    
                    bus_status = f"目前在 {start_st} 準備前往 {end_st}。即時動態：{json.dumps(filtered_list, ensure_ascii=False)}"
                else:
                    st.info(f"目前 {start_st} 暫無即時到站資訊。")
                    bus_status = f"目前 {start_st} 暫無即時到站資訊。"
            else:
                st.error("無法取得公車資料，請確認 API 狀態。")
                
        elif not route_choice:
            st.image("https://img.icons8.com/clouds/200/bus.png")
            st.write("👋 你好！請在左側選單選擇公車路線，或直接在下方詢問 AI 助理。")

       
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
