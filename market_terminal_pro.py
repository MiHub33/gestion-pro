import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import yfinance as yf
import base64

# Intentar importar fpdf de forma segura para evitar crasheos si la nube se actualiza
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

# --- FUNCIONES ---
@st.cache_data(ttl=300)
def descargar_datos(symbol):
    try:
        t = yf.Ticker(symbol)
        data = {
            "M5": t.history(period="5d", interval="5m"),
            "M15": t.history(period="1mo", interval="15m"),
            "M30": t.history(period="1mo", interval="30m"),
            "H1": t.history(period="1mo", interval="1h"),
            "H4": t.history(period="1mo", interval="1h").resample('4H').last().dropna(),
            "D1": t.history(period="2y", interval="1d"),
            "W1": t.history(period="5y", interval="1wk")
        }
        for k in data:
            if not data[k].empty: data[k].index = data[k].index.tz_localize(None)
        return data
    except Exception: return None

def calcular_tendencia(df, span):
    if df is None or df.empty or len(df) < span: return 0, 100
    df = df.copy()
    df['EMA'] = df['Close'].ewm(span=span, adjust=False).mean()
    hoy = datetime.now()
    lunes = hoy - timedelta(days=hoy.weekday())
    lunes = lunes.replace(hour=0, minute=0, second=0, microsecond=0)
    df_sem = df[df.index >= lunes]
    if df_sem.empty: return 0, 100
    alc = (df_sem['Close'] > df_sem['EMA']).sum() / len(df_sem) * 100
    return alc, 100 - alc

def mapear_sesiones(df_m15):
    if df_m15 is None or df_m15.empty: return pd.DataFrame()
    df = df_m15.copy()
    df.index = df.index.tz_localize('UTC').tz_convert('America/New_York')
    df['Hora'] = df.index.hour
    df['Minuto'] = df.index.minute
    
    fechas = []
    for dt in df.index:
        if dt.hour >= 19:
            fechas.append((dt + timedelta(days=1)).date())
        else:
            fechas.append(dt.date())
    df['Trading_Day'] = fechas
    
    df['Sesion'] = 'FILTRADO'
    df.loc[(df['Hora'] >= 19) & (df['Hora'] < 24), 'Sesion'] = 'ASIA'
    df.loc[(df['Hora'] >= 2) & (df['Hora'] < 5), 'Sesion'] = 'LONDRES'
    df.loc[((df['Hora'] == 8) & (df['Minuto'] >= 30)) | ((df['Hora'] > 8) & (df['Hora'] < 12)), 'Sesion'] = 'NY_AM'
    df.loc[((df['Hora'] == 13) & (df['Minuto'] >= 30)) | ((df['Hora'] > 13) & (df['Hora'] < 16)), 'Sesion'] = 'NY_PM'
    
    ag = df[df['Sesion'] != 'FILTRADO'].groupby(['Trading_Day', 'Sesion']).agg(
        Open=('Open', 'first'), Close=('Close', 'last'), High=('High', 'max'), Low=('Low', 'min')
    ).unstack(level='Sesion')
    
    res = pd.DataFrame(index=ag.index)
    for s in ['ASIA', 'LONDRES', 'NY_AM', 'NY_PM']:
        if s in ag['Open'].columns:
            res[f'{s}_Bias'] = ["<span class='bull'>📈 ALC</span>" if c > o else "<span class='bear'>📉 BAJ</span>" for c, o in zip(ag['Close'][s], ag['Open'][s])]
            
    def verificar_quiebre(h_curr, l_curr, h_prev, l_prev):
        if pd.isna(h_curr) or pd.isna(h_prev): return "❌ Sin Quiebre"
        if h_curr > h_prev and l_curr < l_prev: return "🔥 Ambos (Total)"
        if h_curr > h_prev: return "🍏 Sweep Máximo"
        if l_curr < l_prev: return "🍎 Sweep Mínimo"
        return "❌ Sin Quiebre"
        
    for idx in res.index:
        res.loc[idx, 'LON_vs_ASI'] = verificar_quiebre(ag['High'].get('LONDRES', {}).get(idx), ag['Low'].get('LONDRES', {}).get(idx), ag['High'].get('ASIA', {}).get(idx), ag['Low'].get('ASIA', {}).get(idx))
        res.loc[idx, 'NYAM_vs_LON'] = verificar_quiebre(ag['High'].get('NY_AM', {}).get(idx), ag['Low'].get('NY_AM', {}).get(idx), ag['High'].get('LONDRES', {}).get(idx), ag['Low'].get('LONDRES', {}).get(idx))
        res.loc[idx, 'NYPM_vs_NYAM'] = verificar_quiebre(ag['High'].get('NY_PM', {}).get(idx), ag['Low'].get('NY_PM', {}).get(idx), ag['High'].get('NY_AM', {}).get(idx), ag['Low'].get('NY_AM', {}).get(idx))
    
    return res.sort_index(ascending=False)

# Intentar heredar de FPDF de forma segura
try:
    class ReportePDF(FPDF):
        def header(self):
            self.set_fill_color(20, 20, 20)
            self.rect(0, 0, 210, 45, 'F')
            self.set_y(15)
            self.set_font('helvetica', 'B', 22)
            self.set_text_color(255, 255, 255)
            self.cell(0, 10, 'AUDITORIA DE MERCADO - SMC', 0, 1, 'C')
            self.set_font('helvetica', '', 11)
            self.cell(0, 10, f"Fecha de emision: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 0, 1, 'C')
            self.ln(25)
except:
    pass

# --- UI ---
st.markdown('<div class="main-title">Panorama de Gestión Pro</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Escáner de Confluencia y Coincidencia Estadística</div>', unsafe_allow_html=True)

tabs = st.tabs(["🎛️ Monitor En Vivo", "⏱️ Sesiones SMC", "📊 Métricas y Riesgo", "📊 Coincidencias", "🎯 Asistente Pragmático"])
activos = {"BTC": "BTC-USD", "LINK": "LINK-USD", "NASDAQ": "NQ=F"}
datos = {n: descargar_datos(t) for n, t in activos.items()}

# PESTAÑA 1: MONITOR
with tabs[0]:
    c_btc, c_link, c_nas = st.columns(3)
    with c_btc:
        d = datos["BTC"]
        if d:
            h4_89_a, h4_89_b = calcular_tendencia(d["H4"], 89)
            h4_200_a, h4_200_b = calcular_tendencia(d["H4"], 200)
            h1_89_a, h1_89_b = calcular_tendencia(d["H1"], 89)
            h1_200_a, h1_200_b = calcular_tendencia(d["H1"], 200)
            p_alc = sum([h4_89_a>50, h4_200_a>50, h1_89_a>50, h1_200_a>50])
            badge = f'<div class="confluence-badge bull-bg">✓ {p_alc} de 4 Alcistas</div>' if p_alc>=3 else (f'<div class="confluence-badge bear-bg">⚠ {4-p_alc} de 4 Bajistas</div>' if (4-p_alc)>=3 else '<div class="confluence-badge neutral-bg">⇄ Mixto</div>')
            html = f"""<div class="asset-card"><div class="asset-name">BTC</div>{badge}<div class="tf-grid"><div class="tf-section"><span class="tf-badge">H4</span><div class="trend-row"><span>E89</span><span>📈 <span class="bull">{h4_89_a:.0f}%</span> | 📉 <span class="bear">{h4_89_b:.0f}%</span></span></div><div class="trend-row"><span>E200</span><span>📈 <span class="bull">{h4_200_a:.0f}%</span> | 📉 <span class="bear">{h4_200_b:.0f}%</span></span></div></div><div class="tf-section"><span class="tf-badge">H1</span><div class="trend-row"><span>E89</span><span>📈 <span class="bull">{h1_89_a:.0f}%</span> | 📉 <span class="bear">{h1_89_b:.0f}%</span></span></div><div class="trend-row"><span>E200</span><span>📈 <span class="bull">{h1_200_a:.0f}%</span> | 📉 <span class="bear">{h1_200_b:.0f}%</span></span></div></div></div></div>"""
            st.markdown(html.replace('\n', ''), unsafe_allow_html=True)
            
    for col, name in zip([c_link, c_nas], ["LINK", "NASDAQ"]):
        with col:
            d = datos[name]
            if d:
                arr = {}
                for tf in ["H1", "M30", "M15", "M5"]:
                    arr[f"{tf}_89_a"], arr[f"{tf}_89_b"] = calcular_tendencia(d[tf], 89)
                    arr[f"{tf}_200_a"], arr[f"{tf}_200_b"] = calcular_tendencia(d[tf], 200)
                p_alc = sum([v > 50 for k, v in arr.items() if '_a' in k])
                badge = f'<div class="confluence-badge bull-bg">✓ {p_alc} de 8 Alcistas</div>' if p_alc>=5 else (f'<div class="confluence-badge bear-bg">⚠ {8-p_alc} de 8 Bajistas</div>' if (8-p_alc)>=5 else '<div class="confluence-badge neutral-bg">⇄ Mixto</div>')
                html = f'<div class="asset-card"><div class="asset-name">{name}</div>{badge}<div class="tf-grid">'
                for tf in ["H1", "M30", "M15", "M5"]:
                    html += f'<div class="tf-section"><span class="tf-badge">{tf}</span><div class="trend-row"><span>E89</span><span>📈 <span class="bull">{arr[f"{tf}_89_a"]:.0f}%</span> | 📉 <span class="bear">{arr[f"{tf}_89_b"]:.0f}%</span></span></div><div class="trend-row"><span>E200</span><span>📈 <span class="bull">{arr[f"{tf}_200_a"]:.0f}%</span> | 📉 <span class="bear">{arr[f"{tf}_200_b"]:.0f}%</span></span></div></div>'
                html += '</div></div>'
                st.markdown(html, unsafe_allow_html=True)

# PESTAÑA 2: SESIONES
with tabs[1]:
    c_ctrl1, c_ctrl2 = st.columns([4, 4])
    with c_ctrl1: act_ses = st.selectbox("Activo para Mapa de Sesiones", list(activos.keys()), key="s1")
    with c_ctrl2: filtro_temporal = st.radio("Historial:", ["Diario (5 Días)", "Semanal (14 Días)"], horizontal=True, key="ses_radio")
    
    # FIX: Se comprueba que los datos existan antes de llamar a ["M15"]
    df_ses = mapear_sesiones(datos[act_ses]["M15"] if datos[act_ses] else None)
    
    if not df_ses.empty:
        df_ses = df_ses.head(5) if "Diario" in filtro_temporal else df_ses.head(14)
        rows = ""
        for idx, r in df_ses.iterrows():
            rows += f"<tr><td><b>{idx}</b></td><td>{r.get('ASIA_Bias','-')}</td><td>{r.get('LONDRES_Bias','-')}</td><td>{r.get('NY_AM_Bias','-')}</td><td>{r.get('NY_PM_Bias','-')}</td><td>{r.get('LON_vs_ASI','-')}</td><td>{r.get('NYAM_vs_LON','-')}</td><td>{r.get('NYPM_vs_NYAM','-')}</td></tr>"
        st.markdown(f'<table class="stat-table"><tr><th>Día Operativo</th><th>ASIA</th><th>LONDRES</th><th>NY-AM</th><th>NY-PM</th><th>Sweep LON vs ASI</th><th>Sweep NYAM vs LON</th><th>Sweep NYPM vs NYAM</th></tr>{rows}</table>', unsafe_allow_html=True)

# PESTAÑA 3: MÉTRICAS COMPLETAS
with tabs[2]:
    act_met = st.selectbox("Seleccionar Activo para Métricas", list(activos.keys()), key="s2")
    dm = datos[act_met]
    if dm:
        df_d1 = dm["D1"].copy()
        df_d1['Rango'] = df_d1['High'] - df_d1['Low']
        adr_5d = df_d1['Rango'].shift(1).tail(5).mean()
        adr_20d = df_d1['Rango'].shift(1).tail(20).mean()
        rango_hoy = df_d1['Rango'].iloc[-1]
        
        df
