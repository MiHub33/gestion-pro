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
    
    df_ses = mapear_sesiones(datos[act_ses]["M15"])
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
        
        df_w1 = dm["W1"].copy()
        df_w1['Rango'] = df_w1['High'] - df_w1['Low']
        awr_4w = df_w1['Rango'].tail(4).mean()
        awr_12w = df_w1['Rango'].tail(12).mean()

        pct = (rango_hoy/adr_20d*100) if adr_20d>0 else 0
        fmt = ".2f" if act_met in ["NASDAQ", "BTC"] else ".4f"
        
        if pct >= 90:
            bg, br, msg, acc = "rgba(239, 83, 80, 0.15)", "#ef5350", "🔴 MOVIMIENTO AGOTADO (REVERSIÓN)", "El mercado consumió su rango diario. NO buscar continuaciones. Riesgo extremo."
        elif pct >= 70:
            bg, br, msg, acc = "rgba(255, 167, 38, 0.15)", "#ffa726", "⚠️ AL LÍMITE DE EXPANSIÓN", f"Reducir lotaje. Quedan max {max(0, adr_20d-rango_hoy):.2f} puntos seguros."
        else:
            bg, br, msg, acc = "rgba(38, 166, 154, 0.15)", "#26a69a", "🟢 RECORRIDO DISPONIBLE (VÍA LIBRE)", f"Vía libre para buscar {max(0, adr_20d-rango_hoy):.2f} puntos de profit."
            
        html_hud = f"""<div style="background:{bg}; border:1px solid {br}; padding:20px; border-radius:10px; text-align:center; margin-bottom:20px;"><h2>{msg}</h2><p>Rango Hoy: <b>{rango_hoy:{fmt}}</b> / ADR Histórico: <b>{adr_20d:{fmt}}</b> ({pct:.1f}%)</p><p style="color:{br}; font-size:18px; margin:0;">🎯 <b>ACCIONABLE:</b> {acc}</p></div>"""
        st.markdown(html_hud.replace('\n', ''), unsafe_allow_html=True)

        html_tabla = f"""<table class="stat-table"><tr><th>Período de Análisis</th><th>Métrica de Control</th><th>Valor (Puntos)</th><th>Diagnóstico</th></tr><tr><td><b>DIARIO (Corto Plazo)</b></td><td>ADR Promedio (Últimos 5 Días)</td><td>{adr_5d:{fmt}}</td><td>Mide la volatilidad reciente para TP intradía.</td></tr><tr><td><b>DIARIO (Medio Plazo)</b></td><td>ADR Histórico (Últimos 20 Días)</td><td>{adr_20d:{fmt}}</td><td>Rango de expansión promedio mensual (Techo).</td></tr><tr><td><b>SEMANAL (Estructura)</b></td><td>AWR Promedio (Último Mes)</td><td>{awr_4w:{fmt}}</td><td>Rango promedio de lunes a viernes.</td></tr><tr><td><b>MENSUAL (Macro)</b></td><td>AWR Trimestral (Últimas 12 Sem.)</td><td>{awr_12w:{fmt}}</td><td>Sesgo de distribución institucional mayor.</td></tr></table>"""
        st.markdown(html_tabla.replace('\n', ''), unsafe_allow_html=True)

# PESTAÑA 4: COINCIDENCIAS Y REPORTES
with tabs[3]:
    c_analisis, c_reporte = st.columns([7, 3])
    with c_analisis:
        c1, c2, c3 = st.columns(3)
        with c1: act_sel = st.selectbox("Activo", ["NASDAQ", "LINK"], key="est_sel")
        with c2: macro_tf = st.selectbox("Temp. Mayor", ["W1", "D1", "H4", "H1", "M30", "M15"])
        with c3: micro_tf = st.selectbox("Temp. Menor", ["H1", "M30", "M15", "M5"])
        
        d_sel = datos[act_sel]
        interval_mapping = {"H1": "1h", "M30": "30min", "M15": "15min", "M5": "5min"}
        if d_sel is not None and macro_tf != micro_tf:
            df_macro, df_micro = d_sel[macro_tf].copy(), d_sel[micro_tf].copy()
            if not df_macro.empty and not df_micro.empty and len(df_macro)>=200 and len(df_micro)>=200:
                df_macro['EMA200'] = df_macro['Close'].ewm(span=200, adjust=False).mean()
                df_micro['EMA200'] = df_micro['Close'].ewm(span=200, adjust=False).mean()
                df_macro['Macro_Bull'] = df_macro['Close'] > df_macro['EMA200']
                df_micro['Micro_Bull'] = df_micro['Close'] > df_micro['EMA200']
                target_resample = interval_mapping.get(micro_tf, "15min")
                df_macro_res = df_macro[['Macro_Bull']].resample(target_resample).ffill()
                df_total = df_micro.join(df_macro_res, how='inner')
                df_total['Next_Return'] = df_total['Close'].shift(-1) - df_total['Close']
                c_alc = df_total[(df_total['Micro_Bull'] == True) & (df_total['Macro_Bull'] == True)]
                c_baj = df_total[(df_total['Micro_Bull'] == False) & (df_total['Macro_Bull'] == False)]
                len_alc, len_baj = len(c_alc), len(c_baj)
                efectividad_alc = (c_alc['Next_Return'] > 0).sum() / len_alc * 100 if len_alc > 0 else 0
                efectividad_baj = (c_baj['Next_Return'] < 0).sum() / len_baj * 100 if len_baj > 0 else 0
                html_table = f"""<table class="stat-table"><tr><th>Combinación Seleccionada</th><th>Estado de Confluencia</th><th>Muestras Acumuladas</th><th>Efectividad</th></tr><tr><td><b>{macro_tf} + {micro_tf}</b></td><td><span class="bull">Ambas Alcistas</span></td><td>{len_alc} velas</td><td>El precio continuó al <b>ALZA</b> el <span class="bull"><b>{efectividad_alc:.1f}%</b></span> de las veces.</td></tr><tr><td><b>{macro_tf} + {micro_tf}</b></td><td><span class="bear">Ambas Bajistas</span></td><td>{len_baj} velas</td><td>El precio continuó a la <span class="bear"><b>BAJA</b></span> el <span class="bear"><b>{efectividad_baj:.1f}%</b></span> de las veces.</td></tr></table>"""
                st.markdown(html_table.replace('\n', ''), unsafe_allow_html=True)

    with c_reporte:
        st.write("### 🖨️ Reportes")
        tipo_reporte = st.radio("Período:", ["Semanal", "Mensual"])
        try:
            if st.button("💾 Generar PDF"):
                pdf = ReportePDF()
                pdf.add_page()
                pdf.set_text_color(40, 40, 40)
                pdf.set_font('helvetica', 'B', 16)
                pdf.cell(0, 10, f"Reporte {tipo_reporte} - {act_sel}", 0, 1)
                pdf.set_font('helvetica', '', 12)
                pdf.cell(0, 8, f"Temporalidades: {macro_tf} vs {micro_tf}", 0, 1)
                pdf_bytes = bytes(pdf.output())
                b64 = base64.b64encode(pdf_bytes).decode()
                st.markdown(f'<a href="data:application/pdf;base64,{b64}" download="Reporte_{act_sel}.pdf" style="text-decoration:none; padding:10px; background-color:#2962ff; color:white; border-radius:5px;">📥 Descargar PDF</a>', unsafe_allow_html=True)
        except:
            st.error("Función PDF disponible tras configurar requirements.txt")

# PESTAÑA 5: GATILLOS PRAGMÁTICOS CON CEREBRO DINÁMICO
with tabs[4]:
    act_gat = st.selectbox("Activo a Operar", ["NASDAQ", "LINK", "BTC"], key="s3")
    
    # Motor de lectura de Sweep en vivo
    df_ses_gat = mapear_sesiones(datos[act_gat]["M15"])
    dir_nyam = "al cambio de estructura (CHoCH)"
    
    if not df_ses_gat.empty:
        sw_hoy = str(df_ses_gat['LON_vs_ASI'].iloc[0])
        if "Máximo" in sw_hoy: 
            dir_nyam = "en 🔴 <b>SHORT (Vender)</b>"
        elif "Mínimo" in sw_hoy: 
            dir_nyam = "en 🟢 <b>LONG (Comprar)</b>"
        elif "Ambos" in sw_hoy: 
            dir_nyam = "esperando confirmación (Alta volatilidad)"
        else: 
            dir_nyam = "a favor del Bias de H1 (Sin Sweep previo)"

    # Instrucciones
    if act_gat == "NASDAQ":
        asia = "💤 <b>NO OPERAR M5.</b> Solo marcar Máximo y Mínimo del rango en H1."
        londres = "👁️ <b>VIGILAR.</b> Esperar que el precio rompa el Máximo o Mínimo de Asia (Sweep)."
        nyam = f"🔫 <b>GATILLO PRINCIPAL:</b> Si Semáforo Verde -> Entrar en M5 {dir_nyam}. <b>Target: 30 a 50 puntos.</b>"
        nypm = "🛑 <b>CONTROL:</b> Si Semáforo Rojo -> Buscar Reversión en M5. Si Verde -> Mantener operación a favor de la mañana."
    elif act_gat == "LINK":
        asia = "🔫 <b>GATILLO RANGO:</b> Operar los extremos. Comprar en piso o vender en techo si hay rechazo en M15. <b>Target: 50 a 100 puntos.</b>"
        londres = "👁️ <b>VIGILAR.</b> Esperar cacería de stops del rango asiático."
        nyam = f"🔫 <b>GATILLO TENDENCIA:</b> Evaluar Sweep. Entrar {dir_nyam} apoyado en FVG de M5."
        nypm = "📈 <b>CONTINUACIÓN:</b> Seguir la tendencia de la mañana si el ADR lo permite."
    else: # BTC
        asia = "👁️ <b>VIGILAR H1.</b> Acompañar la dirección de la EMA 200 en temporalidad mayor."
        londres = "🛑 <b>CONTROL.</b> Alta manipulación. No anticipar el movimiento."
        nyam = f"🔫 <b>GATILLO SINCRONIZADO:</b> Buscar gatillo {dir_nyam} <b>solo si</b> el NASDAQ también acompaña."
        nypm = "💰 <b>TOMA DE GANANCIAS.</b> Cerrar posiciones abiertas. No iniciar operaciones nuevas."

    st.markdown(f"""
    <div style="background-color: rgba(28, 32, 48, 0.9); border-left: 5px solid #2962ff; padding: 25px; border-radius: 8px;">
        <h2 style="color: #ffffff; margin-top: 0; margin-bottom: 20px;">Instrucciones Directas: {act_gat}</h2>
        <div style="margin-bottom: 15px; font-size: 16px;">
            <div style="color: #b2b5be; margin-bottom: 5px;">🌙 <b>ASIA (19:00 - 02:00 EST):</b></div>
            <div style="color: #ffffff; padding-left: 20px;">{asia}</div>
        </div>
        <div style="margin-bottom: 15px; font-size: 16px;">
            <div style="color: #b2b5be; margin-bottom: 5px;">🌅 <b>LONDRES (02:00 - 08:30 EST):</b></div>
            <div style="color: #ffffff; padding-left: 20px;">{londres}</div>
        </div>
        <div style="margin-bottom: 15px; font-size: 16px;">
            <div style="color: #26a69a; margin-bottom: 5px;">☀️ <b>NUEVA YORK AM (08:30 - 12:00 EST):</b></div>
            <div style="color: #ffffff; padding-left: 20px;">{nyam}</div>
        </div>
        <div style="font-size: 16px;">
            <div style="color: #ffa726; margin-bottom: 5px;">🌇 <b>NUEVA YORK PM (13:30 - 16:00 EST):</b></div>
            <div style="color: #ffffff; padding-left: 20px;">{nypm}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# BOTÓN GLOBAL
st.write("")
if st.button("🔄 Refrescar Terminal"):
    st.cache_data.clear()
    st.rerun()
