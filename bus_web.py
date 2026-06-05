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
ALL_ROUTES = [
    "2", "5", "6", "14", "18", "19", "70", 
    "紅幹線", "紅1", "紅2", "紅3", "紅10",
    "綠幹線", "綠1", "綠2", "綠11", "綠12", "綠17",
    "藍幹線", "藍1", "藍2", "藍20", "藍23",
    "橘幹線", "橘3", "橘11", "橘12", "橘20",
    "黃幹線", "黃1", "黃2", "黃3", "黃4", "黃20", "黃22"
]

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
        with st.sidebar:
            st.title("查詢設定")
            
            def reset_search():
                st.session_state.search_clicked = False
                
            # 改動點：直接吃上面寫好的 ALL_ROUTES 清單，不聯網，反應速度極快！
            route_choice = st.selectbox(
                "請選擇路線", 
                ALL_ROUTES,
                index=None, 
                placeholder="請點選或輸入路線名稱...",
                key="bus_route_select",
                on_change=reset_search 
            )
            
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
                st.info("請先在上方選擇一條公車路線。")

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
        st.divider()
        st.subheader("🤖 問問 AI 助理")
        user_question = st.chat_input("有什麼我可以幫忙的嗎？(可查公車建議、台南景點等)")
        
        if user_question:
            with st.spinner("AI 正在思考中..."):
                try:  
                    prompt_content = f"【目前天氣】: {current_weather}\n【公車狀態】: {bus_status}"
                
                    chat_completion = client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": "你是一位專業、友善的台南公車導遊。"},
                            {"role": "user", "content": f"{prompt_content}\n使用者問題 : {user_question}"}
                        ],
                        model="llama3-8b-8192"
                    )
                
                    ai_text = chat_completion.choices[0].message.content
                    st.info(f"AI 助理 : {ai_text}")
                except Exception as ai_e:                  
                    st.error(f"抱歉，AI 助理暫時發生錯誤：{ai_e}")
                    
    except Exception as e:  
        st.error(f"發生系統錯誤 : {e}")
