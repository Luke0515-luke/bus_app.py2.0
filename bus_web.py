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

@st.cache_data(ttl=86400)
def fetch_all_routes(headers_dict):
    url = "https://tdx.transportdata.tw/api/basic/v2/Bus/Route/City/Tainan?%24format=JSON"
    try:
        res = requests.get(url, headers=headers_dict)
        if res.status_code == 200:
            data = res.json()
            routes = sorted(list(set([r['RouteName']['Zh_tw'] for r in data])))
            return routes
    except:
        return ["2", "5", "綠12", "黃22", "橘20", "藍20"]
    return []
# --- 新增：抓取台南即時氣象的函數 ---
@st.cache_data(ttl=600) # 天氣每 10 分鐘抓一次即可
def fetch_weather_data(headers_dict):
    # 使用 TDX 的觀測站即時氣象 API (以台南測站為例)
    weather_url = "https://tdx.transportdata.tw/api/basic/v1/Weather/Observation/Station/City/Tainan?%24format=JSON"
    try:
        res = requests.get(weather_url, headers=headers_dict)
        if res.status_code == 200:
            data = res.json()
            if data:
                # 抓取第一筆觀測資料的天氣現象與氣溫
                obs = data[0]
                temp = obs.get('AirTemperature', '未知')
                weather_desc = obs.get('Weather', '未知')
                return f"氣溫 {temp}°C，天氣狀況：{weather_desc}"
    except:
        return "暫時無法取得氣象資訊"
    return "尚無氣象資料"
# --- 程式執行主體 ---
# --- 程式執行主體 ---
# --- 執行主體修改 ---
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
        with st.sidebar:
            st.title("查詢設定")
            
            # 若路線改變，重置查詢按鈕的記憶
            def reset_search():
                st.session_state.search_clicked = False
                
            all_available_routes = fetch_all_routes(h)
            route_choice = st.selectbox(
                "請選擇路線", 
                all_available_routes,
                index=None, # 一開始不預選任何路線
                placeholder="請點選或輸入路線名稱...",
                key="bus_route_select",
                on_change=reset_search # 換路線時觸發重置
            )
            
            # 只有選了路線後，才顯示站點選單
            if route_choice:
                all_stops = fetch_route_stops(route_choice, h)
                if all_stops:
                    start_st = st.selectbox("請選擇起始站", all_stops, key="start_select")
                    end_st = st.selectbox("請選擇目的地 (僅作路徑參考)", all_stops, index=len(all_stops)-1, key="end_select")
                    
                    # --- 關鍵：使用 session_state 記住按鈕有被按過 ---
                    if st.button("🔍 開始查詢即時動態", type="primary"):
                        st.session_state.search_clicked = True
                else:
                    st.warning("無法載入站點資訊")
            else:
                st.info("請先在上方選擇一條公車路線。")

        # --- 2. 公車資料顯示區 (確認有選路線，且按鈕曾經被按過) ---
        if route_choice and st.session_state.get("search_clicked", False):
            weather_info = fetch_weather_data(h)
            current_weather = weather_info # 把天氣存下來給 AI
            
            url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/City/Tainan/{route_choice}?%24format=JSON"
            bus_list = fetch_bus_data(url, h)
            
            if bus_list:
                # 排序與過濾邏輯...
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
                    
                    # 把抓到的公車動態存下來給 AI
                    bus_status = f"目前在 {start_st} 準備前往 {end_st}。即時動態：{json.dumps(filtered_list, ensure_ascii=False)}"
                else:
                    st.info(f"目前 {start_st} 暫無即時到站資訊。")
                    bus_status = f"目前 {start_st} 暫無即時到站資訊。"
            else:
                st.error("無法取得公車資料，請確認 API 狀態。")
                
        elif not route_choice:
            st.image("https://img.icons8.com/clouds/200/bus.png")
            st.write("👋 你好！請在左側選單選擇公車路線，或直接在下方詢問 AI 助理。")

       
        # --- 3. AI 對話區 ---
        # --- 3. AI 對話區 ---
        st.divider()
        st.subheader("🤖 問問 AI 助理")
        user_question = st.chat_input("有什麼我可以幫忙的嗎？(可查公車建議、台南景點等)")
        
        if user_question:
            with st.spinner("AI 正在思考中..."):
                try:
                    # 準備給 AI 的提示詞
                    prompt_content = f"【目前天氣】：{current_weather}\n【公車狀態】：{bus_status}"
                    
                    # 呼叫 Groq API
                    chat_completion = client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": "你是一位專業、友善的台南公車導遊。"},
                            {"role": "user", "content": f"{prompt_content}\n使用者問題：{user_question}"}
                        ],
                        model="llama3-8b-8192",
                    )
                    
                    # 顯示 AI 回覆
                    ai_text = chat_completion.choices[0].message.content
                    st.info(f"AI 助理：{ai_text}")
                    
                except Exception as ai_e:
                    # 錯誤處理
                    st.error(f"AI 目前忙碌中，請稍後再試（錯誤代碼：{ai_e}）")
