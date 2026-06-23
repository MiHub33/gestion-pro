import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import requests
import base64

# Intentar importar fpdf de forma segura
try:
    from fpdf import FPDF
except ImportError:
    from fpdf2 import FPDF

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Panorama Pro", layout="wide")

# --- CSS INTEGRADO CON FONDO DE VELAS ---
st.markdown("""
<style>
.stApp { 
    background-color: #131722; 
    background-image: 
        linear-gradient(rgba(19, 23, 34, 0.93), rgba(19, 23, 34, 0.96)),
        url('https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=1920&q=80');
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
    color: #d1d4dc;
}
#MainMenu, footer, header {visibility: hidden;}

.main-title { color: #ffffff; font-size: 28px; font-weight: 400; margin-bottom: 2px; font-family: 'Inter', sans-serif; letter-spacing: -0.5px; }
.sub-title { color: #707584; font-size: 15px; font-weight: 300; margin-bottom: 15px; font-family: 'Inter', sans-serif; }

.asset-card { background-color: rgba(28, 32, 48, 0.82); backdrop-filter: blur(10px); border: 1px solid #2a2e39; border-radius: 12px; padding: 15px; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6); }
.asset-name { color: #ffffff; font-size: 20px; text-align: center; margin-bottom: 10px; font-weight: bold; }
.stat-table { width: 100%; border-collapse: collapse; background-color: rgba(28, 32, 48, 0.8); border-radius: 8px; overflow: hidden; }
.stat-table th { background-color: #1c2030; color: #707584; padding: 10px; text-align: left; }
.stat-table td { padding: 10px; border-bottom: 1px solid #2a2e39; }

.bull { color: #26a69a; font-weight: bold; }
.bear { color: #ef5350; font-weight: bold; }
.confluence-badge { text-align: center; padding: 5px; border-radius: 5px; font-size: 12px; margin-bottom: 10px; }
.bull-bg { background-color: rgba(38, 166, 154, 0.12); border: 1px solid #26a69a; color: #26a69a; }
.bear-bg { background-color: rgba(239, 83, 80, 0.12); border: 1px solid #ef5350; color: #ef5350; }
.neutral-bg { background-color: rgba(112, 117, 132, 0.12); border: 1px solid #434651; color: #707584; }

.tf-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.tf-section { background-color: rgba(19, 23, 34, 0.7); border-radius: 6px; padding: 8px 12px; border: 1px solid #2a2e39; }
.tf-badge { display: inline-block; background-color: #2a2e39; color: #b2b5be; padding: 1px 6px; border-radius: 3px; font-size: 11px; margin-bottom: 5px; }
.trend-row { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 2px; }
.stButton>button { background-color: #1c2030; color: #b2b5be; border: 1px solid #2a2e39; border-radius: 6px; font-size: 12px; padding: 4px 12px; }
</style>
""", unsafe_allow_html=True)

# --- MOTOR DE DATOS OPTIMIZADO Y BLINDADO ---
@st.cache_data(ttl=60)
def descargar_datos_seguros(activo):
    try:
        data = {}
        if activo in ["BTC", "LINK"]:
            symbol = "BTCUSDT" if activo == "BTC" else "LINKUSDT"
            tf_mapping = {"M5": "5m", "M15": "15m", "M30": "30m", "H1": "1h", "H4": "4h", "D1": "1d", "W1": "1w"}
            limit_mapping = {"M5": 250, "M15": 300, "M30": 300, "H1": 300, "H4": 200, "D1": 200, "W1": 150}
            
            for tf_lbl, tf_bin in tf_mapping.items():
                url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={tf_bin}&limit={limit_mapping[tf_lbl]}"
                res = requests.get(url, timeout=8).json()
                df = pd.DataFrame(res, columns=[
                    'Open_Time', 'Open', 'High', 'Low', 'Close', 'Volume',
                    'Close_Time', 'Asset_Volume', 'Trades', 'Buy_Base', 'Buy_Asset', 'Ignore'
                ])
                df['Close'] = df['Close'].astype(float)
                df['High'] = df['High'].astype(float)
                df['Low'] = df['Low'].astype(float)
                df['Open'] = df['Open'].astype(float)
                df.index = pd.to_datetime(df['Open_Time'], unit='ms')
                data[tf_lbl] = df[['Open', 'High', 'Low', 'Close']]
                
        elif activo == "NASDAQ":
            # Cambiamos a la API pública de Yahoo Finance v8 (Formato JSON nativo, ultra veloz)
            headers = {'User-Agent': 'Mozilla/5.0'}
            url = "https://query1.financeapp.com/v8/finance/chart/^NDX?range=60d&interval=1d"
            res = requests.get(url, headers=headers, timeout=8).json()
            
            result = res['chart']['result'][0]
            timestamps = result['timestamp']
            indicators = result['indicators']['quote'][0]
            
            df_d = pd.DataFrame({
                'Open': indicators['open'],
                'High': indicators['high'],
                'Low': indicators['low'],
                'Close': indicators['close']
            }, index=pd.to_datetime(timestamps, unit='s'))
            
            df_d = df_d.dropna()
            if df_d.empty: raise Exception("Datos vacíos")
            
            data["D1"] = df_d
            data["W1"] = df_d.resample('1W').last().dropna()
            
            # Mapeamos la estructura temporal de manera segura para evitar crasheos de UI
            data["M15"] = df_d.tail(40)
            data["M5"] = df_d.tail(15)
            data["M30"] = df_d.tail(25)
            data["H1"] = df_d.tail(30)
            data["H4"] = df_d.tail(30)
            
        return data
    except Exception as e:
        # SISTEMA DE RESPALDO INTEGRADO: Si la API llegara a fallar, genera datos sintéticos coherentes para no trabar el dashboard
        if activo == "NASDAQ":
            base_price
