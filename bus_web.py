import json
import streamlit as st
import requests
import pandas as pd
from google import genai 

# 從 Secrets 讀取金鑰 [cite: 1]
app_id = st.secrets["CLIENT_ID"] [cite: 1]
app_key = st.secrets["CLIENT_SECRET"] [cite: 1]

if "GEMINI_KEY" in st.secrets: [cite: 1]
    client = genai.Client(api_key=st.secrets["GEMINI_KEY"]) [cite: 1]
else:
    st.error("找不到 GEMINI_KEY，請檢查 Secrets！") [cite: 1]

auth_url = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token" [cite: 1]

class Auth(): [cite: 1]
    def __init__(self, app_id, app_key): [cite: 1]
        self.app_id = app_id [cite: 1]
        self.app_key = app_key [cite: 1]
    def get_auth_header(self): [cite: 1]
        return {
            'content-type': 'application/x-www-form-urlencoded', [cite: 2]
            'grant_type': 'client_credentials', [cite: 2]
            'client_id': self.app_id, [cite: 2]
            'client_secret': self.app_key [cite: 2]
        }

class DataProcessor(): [cite: 2]
    def __init__(self, auth_response): [cite: 2]
        self.auth_response = auth_response [cite: 2]
    def get_data_header(self): [cite: 2]
        auth_JSON = self.auth_response.json() [cite: 2]
        access_token = auth_JSON.get('access_token') [cite: 2]
        return {
            'authorization': f'Bearer {access_token}', [cite: 3]
            'Accept-Encoding': 'gzip' [cite: 3]
        }

# --- 新增：抓取路線所有站點名稱的函數 ---
@st.cache_data(ttl=3600)
def fetch_route_stops(route_name, headers_dict):
    stops_url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/StopOfRoute/City/Tainan/{route_name}?%24format=JSON"
    try:
        res = requests.get(stops_url, headers=headers_dict)
        if res.status_code == 200:
            data = res.json()
            if data:
                # 預設取該路線「去程」的所有站名
                return [s['StopName']['Zh_tw'] for s in data[0]['Stops']]
    except:
        return []
    return []

@st.cache_data(ttl=30) [cite: 3]
def fetch_bus_data(url, headers_dict): [cite: 3]
    try: [cite: 3]
        res = requests.get(url, headers=headers_dict) [cite: 3]
        if res.status_code == 200: [cite: 3]
            return res.json() [cite: 3]
    except: [cite: 3]
        return None [cite: 3]
    return None [cite: 3]

if __name__ == '__main__': [cite: 4]
    st.set_page_config(page_title="台南公車 AI 助理", page_icon="🚌") [cite: 4]
    st.header("🚌 台南公車即時時刻查詢") [cite: 4]

    try: [cite: 5]
        a = Auth(app_id, app_key) [cite: 5]
        auth_res = requests.post(auth_url, data=a.get_auth_header()) [cite: 5]
        d = DataProcessor(auth_res) [cite: 5]

        with st.sidebar: [cite: 4]
            st.title("查詢設定") [cite: 4]
            route_choice = st.selectbox( [cite: 4]
                "請選擇路線", 
                ["2", "5", "綠12", "黃22", "橘20", "藍20"],
                key="bus_route_select"
            )
            
            # 抓取並顯示站點選單
            all_stops = fetch_route_stops(route_choice, d.get_data_header())
            if all_stops:
                start_station = st.selectbox("請選擇起始站", all_stops)
                end_station = st.selectbox("請選擇目的地", all_stops, index=len(all_stops)-1)
            else:
                st.warning("無法載入站點列表")

        # 抓取即時到站資料 [cite: 4]
        url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/City/Tainan/{route_choice}?%24format=JSON" [cite: 4]
        bus_list = fetch_bus_data(url, d.get_data_header()) [cite: 5]
        
        if bus_list: [cite: 5]
            filtered_list = [] [cite: 5]
            for stop in bus_list: [cite: 6]
                stop_name = stop.get('StopName', {}).get('Zh_tw', '未知') [cite: 6]
                
                # 只篩選出使用者選定的起點與終點
                if stop_name in [start_station, end_station]:
                    estimate = stop.get('EstimateTime') [cite: 6]
                    status = f"{estimate // 60} 分鐘" if estimate is not None else "尚未發車" [cite: 7]
                    
                    filtered_list.append({
                        "類型": "起始站" if stop_name == start_station else "目的地",
                        "站點": stop_name,
                        "到站狀態": status
                    })
            
            if filtered_list: [cite: 7]
                st.subheader(f"📍 從 {start_station} 到 {end_station}")
                st.table(filtered_list) # 使用 table 顯示起訖點更直觀
                
                st.divider() [cite: 8]
                st.subheader("🤖 問問 AI 助理") [cite: 8]
                user_question = st.chat_input("想知道這兩站之間的乘車建議嗎？") [cite: 8]
                
                if user_question: [cite: 8]
                    with st.spinner("AI 正在分析資料..."): [cite: 10]
                        try: [cite: 10]
                            prompt_context = f"起始站：{start_station}，目的地：{end_station}。即時資料：{json.dumps(filtered_list, ensure_ascii=False)}"
                            response = client.models.generate_content( [cite: 11]
                                model="gemini-2.0-flash", [cite: 11]
                                contents=f"{prompt_context}\n問題：{user_question}" [cite: 11]
                            ) [cite: 12]
                            st.info(f"AI 回覆：{response.text}") [cite: 12]
                        except Exception as e: [cite: 13]
                            if "429" in str(e): [cite: 14]
                                st.error("⚠️ AI 助理忙碌中，請等一分鐘再試。") [cite: 14]
                            else:
                                st.error(f"發生其他錯誤：{e}") [cite: 15]
            else:
                st.info("目前該路段暫無即時時刻資訊。") [cite: 15]
                
    except Exception as e: [cite: 16]
        st.error(f"錯誤：{e}") [cite: 16]
