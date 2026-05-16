import json
import streamlit as st
import requests
import pandas as pd
from google import genai 

# 1. 讀取 Secrets (確保這段在最左邊，沒有縮排)
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
# --- 1. 新增：自動抓取台南所有路線清單的函數 ---
@st.cache_data(ttl=86400) # 路線清單一天抓一次即可
def fetch_all_routes(headers_dict):
    url = "https://tdx.transportdata.tw/api/basic/v2/Bus/Route/City/Tainan?%24format=JSON"
    try:
        res = requests.get(url, headers=headers_dict)
        if res.status_code == 200:
            data = res.json()
            # 提取所有路線的中文名稱，並進行排序
            routes = sorted(list(set([r['RouteName']['Zh_tw'] for r in data])))
            return routes
    except:
        return ["2", "5", "綠12", "黃22", "橘20", "藍20"] # 失敗時的備案
    return []

# --- 2. 修改主程式中的側邊欄部分 ---
if __name__ == '__main__':
    st.set_page_config(page_title="台南公車 AI 助理", page_icon="🚌")
    st.header("🚌 台南公車即時時刻查詢")

    try:
        a = Auth(app_id, app_key)
        auth_res = requests.post(auth_url, data=a.get_auth_header())
        d = DataProcessor(auth_res)
        h = d.get_data_header()

        with st.sidebar:
            st.title("查詢設定")
            
            # 自動抓取所有路線
            all_available_routes = fetch_all_routes(h)
            
            route_choice = st.selectbox(
                "請選擇路線", 
                all_available_routes, # 這裡現在會顯示台南所有的路線了！
                index=all_available_routes.index("2") if "2" in all_available_routes else 0,
                key="bus_route_select"
            )
            
            # 取得該路線的站點列表
            all_stops = fetch_route_stops(route_choice, h)
            if all_stops:
                start_st = st.selectbox("請選擇起始站", all_stops)
                end_st = st.selectbox("請選擇目的地", all_stops, index=len(all_stops)-1)
            else:
                st.warning("無法載入站點")

        # ... (後續抓取即時資料與 AI 的邏輯保持不變) ...

            all_stops = fetch_route_stops(route_choice, d.get_data_header())
            if all_stops:
                start_st = st.selectbox("請選擇起始站", all_stops)
                end_st = st.selectbox("請選擇目的地", all_stops, index=len(all_stops)-1)
            else:
                st.warning("無法載入站點")

        # 取得即時資料
        url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/City/Tainan/{route_choice}?%24format=JSON"
        bus_list = fetch_bus_data(url, d.get_data_header())
        
        if bus_list: 
            filtered_list = []
            for stop in bus_list: 
                name = stop.get('StopName', {}).get('Zh_tw', '未知') 
                if name in [start_st, end_st]:
                    estimate = stop.get('EstimateTime')
                    status = f"{estimate // 60} 分鐘" if estimate is not None else "尚未發車"
                    filtered_list.append({
                        "類型": "起始站" if name == start_st else "目的地",
                        "站點": name,
                        "到站狀態": status
                    })
            
            if filtered_list:
                st.subheader(f"📍 從 {start_st} 到 {end_st}")
                st.table(filtered_list)
                
                st.divider()
                st.subheader("🤖 問問 AI 助理")
                user_question = st.chat_input("想知道這兩站之間的乘車建議嗎？")
                
                if user_question:
                    if not filtered_list: 
                        st.warning("暫無資料可分析。") 
                    else:
                        with st.spinner("AI 正在分析資料..."):
                            try:
                                prompt_content = f"資料：{json.dumps(filtered_list, ensure_ascii=False)}"
                                response = client.models.generate_content( 
                                    model="gemini-2.0-flash", 
                                    contents=f"{prompt_content}\n問題：{user_question}" 
                                )
                                st.info(f"AI 回覆：{response.text}")
                            except Exception as e:
                                if "429" in str(e):
                                    st.error("⚠️ 配額用完，請稍後再試。") 
                                else:
                                    st.error(f"AI 錯誤：{e}")
            else:
                st.info("目前該路段暫無即時資訊。") 
                
    except Exception as e:
        st.error(f"系統錯誤：{e}")
