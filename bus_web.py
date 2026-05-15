import json
import streamlit as st
import requests
import pandas as pd
import google.generativeai as genai

# 1. 從 Streamlit Secrets 讀取金鑰
app_id = st.secrets["CLIENT_ID"]
app_key = st.secrets["CLIENT_SECRET"]
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

        
