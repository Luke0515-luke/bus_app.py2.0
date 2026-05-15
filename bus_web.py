import json
import streamlit as st
import requests
import pandas as pd
import google.generativeai as genai

# 1. 從 Streamlit Secrets 讀取金鑰
app_id = st.secrets["CLIENT_ID"]
app_key = st.secrets["CLIENT_SECRET"]
GEMINI_API_KEY = st.secrets["CLIENT_ID"]

# 2. 正確的 TDX 驗證網址與公車資料網址
auth_url = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token" 
url = "https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/City/Tainan/2?%24format=JSON"

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

class data():
    def __init__(self, app_id, app_key, auth_response):
        self.app_id = app_id
        self.app_key = app_key
        self.auth_response = auth_response

    def get_data_header(self):
        # 直接使用 requests 內建的 .json() 方法更安全
        auth_JSON = self.auth_response.json()
        access_token = auth_JSON.get('access_token')
        return {
            'authorization': 'Bearer ' + access_token,
            'Accept-Encoding': 'gzip'
        }

# --- 程式執行主體 ---
# --- 程式執行主體 ---

# --- 程式執行主體 ---
if "GEMINI_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    st.error("找不到 GEMINI_KEY，請檢查 Secrets！")

if __name__ == '__main__':
    st.set_page_config(page_title="台南公車 AI 助理", page_icon="🚌")
    st.header("🚌 台南公車即時動態 (AI 版)")

    # 1. 側邊欄選單
    with st.sidebar:
        st.title("查詢設定")
        route_choice = st.selectbox(
            "請選擇路線", 
            ["2", "5", "綠12", "黃22", "橘20", "藍20"]
        )
        st.write(f"目前查詢：{route_choice} 路公車")

    url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/City/Tainan/{route_choice}?%24format=JSON"

    try:
        a = Auth(app_id, app_key)
        auth_response = requests.post(auth_url, data=a.get_auth_header())
        d = data(app_id, app_key, auth_response)
        
        data_response = requests.get(url, headers=d.get_data_header())
        
        if data_response.status_code == 200:
            bus_list = data_response.json()
            final_list = []
            
            for stop in bus_list:
                # 這裡增加抓取站名 Zh_tw
                stop_name = stop.get('StopName', {}).get('Zh_tw', '未知站點')
                route_name = stop.get('RouteName', {}).get('Zh_tw', '未知')
                sub_route = stop.get('SubRouteName', {}).get('Zh_tw', '未知')
                seconds = stop.get('EstimateTime')
                
                status = f"{seconds // 60} 分鐘" if seconds is not None else "尚未發車"
                
                final_list.append({
                    "路線名稱": route_name,
                    "站點": stop_name,
                    "方向": sub_route,
                    "到站狀態": status
                })
            
            # 顯示表格
            if final_list:
                st.dataframe(final_list, use_container_width=True)
                
                # --- ✨ 新增：Gemini AI 對話功能 ---
                st.divider() # 畫一條分隔線
                st.subheader("🤖 問問 AI 助理")
                
                user_question = st.chat_input("例如：哪一站要等最久？")
                
                if user_question:
                    with st.spinner("AI 正在分析即時資料..."):
                        # 將目前的 final_list 轉成文字餵給 Gemini
                        context = json.dumps(final_list, ensure_ascii=False)
                        prompt = f"""
                        你是台南公車小助手。以下是目前的即時公車資料：
                        {context}
                        請根據資料回答使用者問題：{user_question}
                        請用簡短、活潑的中文回答。
                        """
                        response = model.generate_content(prompt)
                        st.info(f"AI 建議：{response.text}")
            else:
                st.info("目前查無此路線的即時資訊。")
                
    except Exception as e:
        st.error(f"發生錯誤：{e}")




        
