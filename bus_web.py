import json
import streamlit as st
import requests
import pandas as pd
# 1. 升級為新的 Gemini 套件
from google import genai 

# 從 Secrets 讀取金鑰
app_id = st.secrets["CLIENT_ID"]
app_key = st.secrets["CLIENT_SECRET"]

# 2. 初始化最新的 Gemini 客戶端
if "GEMINI_KEY" in st.secrets:
    client = genai.Client(api_key=st.secrets["GEMINI_KEY"])
else:
    st.error("找不到 GEMINI_KEY，請檢查 Secrets！")

# --- TDX 驗證與資料類別 (保持不變) ---
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

class DataProcessor(): # 重新命名以避免與關鍵字衝突
    def __init__(self, auth_response):
        self.auth_response = auth_response
    def get_data_header(self):
        auth_JSON = self.auth_response.json()
        access_token = auth_JSON.get('access_token')
        return {
            'authorization': f'Bearer {access_token}',
            'Accept-Encoding': 'gzip'
        }

# --- 程式執行主體 ---
if __name__ == '__main__':
    st.set_page_config(page_title="台南公車 AI 助理", page_icon="🚌")
    st.header("🚌 台南公車即時動態 (2026 升級版)")

    with st.sidebar:
        st.title("查詢設定")
        route_choice = st.selectbox(
            "請選擇路線", 
            ["2", "5", "綠12", "黃22", "橘20", "藍20"],
            key="bus_route_select"
        )

    url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/City/Tainan/{route_choice}?%24format=JSON"

    try:
        a = Auth(app_id, app_key)
        auth_res = requests.post(auth_url, data=a.get_auth_header())
        d = DataProcessor(auth_res)
        
        data_res = requests.get(url, headers=d.get_data_header())
        
        if data_res.status_code == 200:
            bus_list = data_res.json()
            final_list = []
            for stop in bus_list:
                final_list.append({
                    "站點": stop.get('StopName', {}).get('Zh_tw', '未知'),
                    "方向": stop.get('SubRouteName', {}).get('Zh_tw', '未知'),
                    "到站狀態": f"{stop.get('EstimateTime', 0) // 60} 分鐘" if stop.get('EstimateTime') is not None else "尚未發車"
                })
            
            if final_list:
                # 3. 修正：使用 width='stretch' 取代舊語法
                st.dataframe(final_list, width='stretch')
                
                st.divider()
                st.subheader("🤖 問問 AI 助理")
                user_question = st.chat_input("想知道什麼？")
                
                if user_question:
                    with st.spinner("AI 正在分析資料..."):
                        # 4. 使用最新 SDK 的呼叫方式
                        response = client.models.generate_content(
                            model="gemini-2.0-flash", # 自動升級到最強的 2.0
                            contents=f"資料：{json.dumps(final_list, ensure_ascii=False)}\n問題：{user_question}"
                        )
                        st.info(f"AI 回覆：{response.text}")
            else:
                st.info("目前查無即時資訊。")
    except Exception as e:
        st.error(f"錯誤：{e}")
