import json
import streamlit as st
import requests
import pandas as pd
from google import genai 

# 1. 讀取 Secrets
app_id = st.secrets["CLIENT_ID"] 
app_key = st.secrets["CLIENT_SECRET"] 

# 2. 初始化 Gemini 客戶端
if "GEMINI_KEY" in st.secrets: 
    client = genai.Client(api_key=st.secrets["GEMINI_KEY"]) 
else:
    st.error("找不到 GEMINI_KEY，請檢查 Secrets！")

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
if __name__ == '__main__':
    st.set_page_config(page_title="台南公車 AI 助理", page_icon="🚌")
    st.header("🚌 台南公車即時時刻查詢")

    try:
        # 1. 執行身份驗證
        a = Auth(app_id, app_key)
        auth_res = requests.post(auth_url, data=a.get_auth_header())
        d = DataProcessor(auth_res)
        h = d.get_data_header()

        # 側邊欄設定
        with st.sidebar:
            st.title("查詢設定")
            all_available_routes = fetch_all_routes(h)
            route_choice = st.selectbox(
                "請選擇路線", 
                all_available_routes,
                index=None, # 一開始不預選任何路線
                placeholder="請點選或輸入路線名稱...",
                key="bus_route_select"
            )
            
            # 只有選了路線後，才顯示站點選單
            if route_choice:
                all_stops = fetch_route_stops(route_choice, h)
                if all_stops:
                    start_st = st.selectbox("請選擇起始站", all_stops, key="start_select")
                    end_st = st.selectbox("請選擇目的地 (僅作路徑參考)", all_stops, index=len(all_stops)-1, key="end_select")
                    
                    # --- 關鍵：增加查詢按鈕 ---
                    search_btn = st.button("🔍 開始查詢即時動態", type="primary")
                else:
                    st.warning("無法載入站點資訊")
            else:
                st.info("請先在上方選擇一條公車路線。")
                search_btn = False

        # --- 2. 只有按下按鈕後才執行查詢邏輯 ---
        if route_choice and search_btn:
            # 此時才去抓天氣，避免一進網頁就浪費額度
            weather_info = fetch_weather_data(h)
            
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
                    
                    # --- AI 對話區 ---
                    st.divider()
                    st.subheader("🤖 問問 AI 助理")
                    user_question = st.chat_input("想知道哪一班車比較建議搭乘嗎？")
                    
                    if user_question:
                        with st.spinner("AI 正在分析資料..."):
                            try:
                                prompt_content = f"目前在 {start_st} 準備前往 {end_st} 的公車即時到站資訊如下：{json.dumps(filtered_list, ensure_ascii=False)}"
                                response = client.models.generate_content(
                                    model="gemini-2.0-flash",
                                    contents=f"{prompt_content}\n使用者問題：{user_question}\n請以專業公車導遊的身份，根據到站時間與天氣 {weather_info} 給予建議。"
                                )
                                st.info(f"AI 建議：{response.text}")
                            except Exception as ai_e:
                                st.error(f"AI 錯誤：{ai_e}")
                
                # --- 這裡就是報錯的地方：else 必須跟 if filtered_list 對齊 ---
                else:
                    st.info(f"目前 {start_st} 暫無即時到站資訊。")
                
    except Exception as e:
        st.error(f"系統錯誤：{e}")
