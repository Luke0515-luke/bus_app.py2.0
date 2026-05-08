import json
import streamlit as st
import requests
import pandas as pd


app_id = st.secrets["CLIENT_ID"]
app_key = st.secrets["CLIENT_SECRET"]

auth_url="https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
url = "https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/City/Tainan/2?%24format=JSON"

class Auth():

    def __init__(self, app_id, app_key):
        self.app_id = app_id
        self.app_key = app_key

    def get_auth_header(self):
        content_type = 'application/x-www-form-urlencoded'
        grant_type = 'client_credentials'

        return{
            'content-type' : content_type,
            'grant_type' : grant_type,
            'client_id' : self.app_id,
            'client_secret' : self.app_key
        }

class data():

    def __init__(self, app_id, app_key, auth_response):
        self.app_id = app_id
        self.app_key = app_key
        self.auth_response = auth_response

    def get_data_header(self):
        auth_JSON = json.loads(self.auth_response.text)
        access_token = auth_JSON.get('access_token')

        return{
            'authorization': 'Bearer ' + access_token,
            'Accept-Encoding': 'gzip'
        }

if __name__ == '__main__':
    try:
        d = data(app_id, app_key, auth_response)
        data_response = requests.get(url, headers=d.get_data_header())
    except:
        a = Auth(app_id, app_key)
        auth_response = requests.post(auth_url, a.get_auth_header())
        d = data(app_id, app_key, auth_response)
        data_response = requests.get(url, headers=d.get_data_header())
    print(auth_response)
    if data_response.status_code == 200:
    bus_list = data_response.json()
    
    print(f"{'路線名稱':<8} | {'方向':<25} | {'到站狀態'}")
    print("-" * 50)
    
    for stop in bus_list:
        # 1. 抓取路線名稱
        route_name = stop.get('RouteName', {}).get('Zh_tw', '未知')
        
        # 2. 抓取起訖站資訊
        sub_route = stop.get('SubRouteName', {}).get('Zh_tw', '未知')
        
        # 3. 抓取預估時間 (秒)
        seconds = stop.get('EstimateTime')
        
        # 4. 判斷狀態
        if seconds is not None:
            status = f"{seconds // 60} 分鐘"
        else:
            status = "尚未發車"
            
        if data_response.status_code == 200:
        bus_list = data_response.json()
        
        # 在網頁上顯示大標題
        st.header("🚌 公車即時動態")
        
        # 建立一個清單來存資料
        final_list = []
        for stop in bus_list:
            route_name = stop.get('RouteName', {}).get('Zh_tw', '未知')
            sub_route = stop.get('SubRouteName', {}).get('Zh_tw', '未知')
            seconds = stop.get('EstimateTime')
            status = f"{seconds // 60} 分鐘" if seconds is not None else "尚未發車"
            
            # 把資料存進清單
            final_list.append({
                "路線名稱": route_name,
                "方向": sub_route,
                "到站狀態": status
            })
        
        # 關鍵：用 st.table 把它畫到網頁畫面上！
        st.table(final_list)
