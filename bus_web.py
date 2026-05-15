import json
import streamlit as st
import requests
import pandas as pd
import google.generativeai as genai

# 1. 從 Streamlit Secrets 讀取金鑰
app_id = st.secrets["CLIENT_ID"]
app_key = st.secrets["CLIENT_SECRET"]

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


if __name__ == '__main__':
    st.set_page_config(page_title="台南公車 AI 版", page_icon="🚌")
    st.header("🚌 台南公車即時動態 (AI 助手版)")

    #
if __name__ == '__main__':
    # 設定網頁標題與圖示
    st.set_page_config(page_title="台南公車即時動態", page_icon="🚌")
    st.header("🚌 台南公車即時動態看板")

    # 1. 在側邊欄加入選單 (這就是你要的選單！)
    with st.sidebar:
        st.title("查詢設定")
        # 建立一個路線下拉選單，你可以自己增加常用路線
        route_choice = st.selectbox(
            "請選擇路線", 
            ["2", "5", "綠12", "黃22", "橘20", "藍20"]
        )
        st.write(f"目前查詢：{route_choice} 路公車")

    # 2. 修改 URL：把原本末端的 /2 改成 /{route_choice}
    # 這樣當選單切換時，API 抓取的路線就會跟著變
    url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/City/Tainan/{route_choice}?%24format=JSON"

    # 驗證與抓取資料邏輯
    try:
        a = Auth(app_id, app_key)
        auth_response = requests.post(auth_url, data=a.get_auth_header())
        d = data(app_id, app_key, auth_response)
        
        # 使用動態產生的 url 抓資料
        data_response = requests.get(url, headers=d.get_data_header())
        
        if data_response.status_code == 200:
            bus_list = data_response.json()
            final_list = []
            
            for stop in bus_list:
                route_name = stop.get('RouteName', {}).get('Zh_tw', '未知')
                sub_route = stop.get('SubRouteName', {}).get('Zh_tw', '未知')
                seconds = stop.get('EstimateTime')
                
                status = f"{seconds // 60} 分鐘" if seconds is not None else "尚未發車"
                
                final_list.append({
                    "路線名稱": route_name,
                    "方向": sub_route,
                    "到站狀態": status
                })
            
            if final_list:
                # 這裡改用 st.dataframe 會更像專業的 App 介面
                st.dataframe(final_list, use_container_width=True)
            else:
                st.info("目前查無此路線的即時資訊。")
      # ... 這是你原本 if 區塊的結尾
    except Exception as e:
        st.error(f"發生錯誤：{e}")
