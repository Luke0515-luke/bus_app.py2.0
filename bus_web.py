import json
import streamlit as st
import requests
import pandas as pd

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
if __name__ == '__main__':
    st.header("🚌 台南公車即時動態看板")
    
    # 驗證與抓取資料邏輯
    try:
        # 先嘗試取得資料（如果 auth_response 已存在）
        a = Auth(app_id, app_key)
        auth_response = requests.post(auth_url, data=a.get_auth_header())
        d = data(app_id, app_key, auth_response)
        data_response = requests.get(url, headers=d.get_data_header())
        
        if data_response.status_code == 200:
            bus_list = data_response.json()
            
            # 建立一個清單來存網頁表格要用的資料
            final_list = []
            
            for stop in bus_list:
                # 抓取路線名稱
                route_name = stop.get('RouteName', {}).get('Zh_tw', '未知')
                # 抓取方向資訊
                sub_route = stop.get('SubRouteName', {}).get('Zh_tw', '未知')
                # 抓取預估時間
                seconds = stop.get('EstimateTime')
                
                # 判斷時間狀態
                if seconds is not None:
                    status = f"{seconds // 60} 分鐘"
                else:
                    status = "尚未發車"
                
                # 將資料整理進清單
                final_list.append({
                    "路線名稱": route_name,
                    "方向": sub_route,
                    "到站狀態": status
                })
            
            # 將整理好的清單轉成表格顯示在網頁上
            if final_list:
                st.table(final_list)
            else:
                st.info("目前無公車即時資訊。")
        else:
            st.error(f"資料抓取失敗，錯誤碼：{data_response.status_code}")

    except Exception as e:
        st.error(f"發生錯誤：{e}")
