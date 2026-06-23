import streamlit as st
import pandas as pd

from datetime import datetime, timedelta
import os
import yfinance as yf

# --- PERSISTENCIA Y DATOS ---
DB_PATH = "registro_gestion_trades.csv"

def cargar_panorama():
    if os.path.exists(DB_PATH):
        try:
            df_loaded = pd.read_csv(DB_PATH)
            if 'Activo' not in df_loaded.columns:
                df_loaded.insert(1, 'Activo', 'NASDAQ')
            columnas_deseadas = ['Fecha', 'Activo', 'Rango', 'Tipo', 'Resultado']
            for col in columnas_deseadas:
                if col not in df_loaded.columns:
                    df_loaded[col] = "NASDAQ" if col == "Activo" else ""
            return df_loaded[columnas_deseadas]
        except:
            pass
    return pd.DataFrame(columns=['Fecha', 'Activo', 'Rango', 'Tipo', 'Resultado'])

def guardar_panorama(df_data):
    df_data.to_csv(DB_PATH, index=False)

# --- ANÁLISIS DE TENDENCIA (EMA 200 y EMA 89) ---
@st.cache_data(ttl=900)
def obtener_tendencia_semanal(symbol, interval):
    try:
        ticker = yf.Ticker(symbol)
        periodo = "5d" if interval == "5m" else "1mo"
        data = ticker.history(period=periodo, interval=interval)
        
        if data.empty or len(data) < 200: return None
        
        data['EMA200'] = data['Close'].ewm(span=200, adjust=False).mean()
        data['EMA89'] = data['Close'].ewm(span=89, adjust=False).mean()
        
        hoy = datetime.now()
        lunes_actual = hoy - timedelta(days=hoy.weekday())
        lunes_actual = lunes_actual.replace(hour=0, minute=0, second=0, microsecond=0)
        
        data.index = data.index.tz_localize(None)
        data_semanal = data[data.index >= lunes_actual]
        
        if data_semanal.empty: return None
        
        total = len(data_semanal)
        alc_200 = (data_semanal['Close'] > data_semanal['EMA200']).sum() / total * 100
        alc_89 = (data_semanal['Close'] > data_semanal['EMA89']).sum() / total * 100
        
        return {
            "200": {"alc": alc_200, "baj": 100 - alc_200},
            "89": {"alc": alc_89, "baj": 100 - alc_89}
        }
    except:
        return None

# --- CONFIGURACIÓN DE INTERFAZ ---
st.set_page_config(page_title="Terminal de Gestión Pro", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #0a0a0a; }
    .floating-panel {
        background-color: #1e1e1e;
        padding: 30px;
        border-radius: 15px;
        border: 1px solid #333;
        box-shadow: 0px 10px 30px rgba(0, 0, 0, 0.7);
        margin-top: 20px;
    }
    .trend-text { font-size: 13px; margin-bottom: 1px; line-height: 1.2; }
    .ema-label { color: #888; font-weight: bold; font-size: 11px; }
    h1, h2, h3, p { color: #e0e0e0 !important; font-family: 'Inter', sans-serif; }
    [data-testid="stMetricValue"] { color: #ffffff !important; font-size: 20px; }
    .stButton>button { width: 100%; background-color: #333; color: white; border-radius: 8px; border: 1px solid #444; }
    #MainMenu, footer, header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

if 'df_gestion' not in st.session_state:
    st.session_state.df_gestion = cargar_panorama()

st.markdown('<div class="floating-panel">', unsafe_allow_html=True)
st.title("🎛️ Panorama de Gestión")

# --- SECCIÓN DE TENDENCIA SEMANAL ---
st.subheader("📊 Tendencia Semanal (EMA 89 / 200)")
col_btc, col_link, col_nas = st.columns(3)

activos_market = {"BTC": "BTC-USD", "LINK": "LINK-USD", "NASDAQ": "NQ=F"}

for col, (nombre, ticker) in zip([col_btc, col_link, col_nas], activos_market.items()):
    with col:
        st.markdown(f"**{nombre}**")
        res_h1 = obtener_tendencia_semanal(ticker, "1h")
        res_m5 = obtener_tendencia_semanal(ticker, "5m")
        
        if res_h1 and res_m5:
            st.markdown(f"<span class='ema-label'>H1</span>", unsafe_allow_html=True)
            st.markdown(f"<p class='trend-text'>E89: 📈{res_h1['89']['alc']:.0f}% | 📉{res_h1['89']['baj']:.0f}%</p>", unsafe_allow_html=True)
            st.markdown(f"<p class='trend-text'>E200: 📈{res_h1['200']['alc']:.0f}% | 📉{res_h1['200']['baj']:.0f}%</p>", unsafe_allow_html=True)
            
            st.markdown(f"<span class='ema-label'>M5</span>", unsafe_allow_html=True)
            st.markdown(f"<p class='trend-text'>E89: 📈{res_m5['89']['alc']:.0f}% | 📉{res_m5['89']['baj']:.0f}%</p>", unsafe_allow_html=True)
            st.markdown(f"<p class='trend-text'>E200: 📈{res_m5['200']['alc']:.0f}% | 📉{res_m5['200']['baj']:.0f}%</p>", unsafe_allow_html=True)
            
            avg_alc = (res_m5['89']['alc'] + res_m5['200']['alc']) / 2
            st.progress(avg_alc/100)

st.markdown("---")

# --- FORMULARIO DE REGISTRO CON SELECTOR DE ACTIVO ---
with st.container():
    col1, col2 = st.columns(2)
    with col1:
        fecha = st.date_input("Fecha", datetime.now())
        activo = st.selectbox("Activo Operado", ["NASDAQ", "LINK"])
        rango = st.selectbox("Rango Horario", ["9A12HS", "12A16HS", "17A23HS"])
    with col2:
        tipo = st.radio("Posición", ["Long", "Short"], horizontal=True)
        res = st.radio("Resultado", ["Positivo", "Negativo"], horizontal=True)
    
    if st.button("Sincronizar Trade"):
        nuevo = pd.DataFrame([[str(fecha), activo, rango, tipo, res]], columns=['Fecha', 'Activo', 'Rango', 'Tipo', 'Resultado'])
        st.session_state.df_gestion = pd.concat([st.session_state.df_gestion, nuevo], ignore_index=True)
        guardar_panorama(st.session_state.df_gestion)
        st.success("Operación registrada en el historial.")
        st.rerun()

# --- ESTADÍSTICAS Y GESTIÓN ---
df = st.session_state.df_gestion

if not df.empty:
    st.markdown("---")
    total_pos = len(df[df['Resultado'] == 'Positivo'])
    total_neg = len(df[df['Resultado'] == 'Negativo'])
    stats_rango = df[df['Resultado'] == 'Positivo'].groupby('Rango').size()
    mejor_rango = stats_rango.idxmax() if not stats_rango.empty else "N/A"

    c1, c2, c3 = st.columns(3)
    c1.metric("Puntos Positivos", total_pos)
    c2.metric("Puntos Negativos", total_neg)
    c3.metric("Rango Favorito", mejor_rango)

    st.subheader("📋 Historial de Sesiones")
    df_con_seleccion = df.copy()
    df_con_seleccion.insert(0, "Seleccionar", False)
    
    edited_df = st.data_editor(
        df_con_seleccion,
        hide_index=True,
        column_config={"Seleccionar": st.column_config.CheckboxColumn(required=True)},
        disabled=["Fecha", "Activo", "Rango", "Tipo", "Resultado"],
        use_container_width=True
    )

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🗑️ Eliminar Seleccionados"):
            indices_a_quitar = edited_df[edited_df["Seleccionar"] == True].index
            st.session_state.df_gestion = df.drop(indices_a_quitar).reset_index(drop=True)
            guardar_panorama(st.session_state.df_gestion)
            st.rerun()
    with col_btn2:
        if st.button("💥 Borrar TODO"):
            st.session_state.df_gestion = pd.DataFrame(columns=['Fecha', 'Activo', 'Rango', 'Tipo', 'Resultado'])
            guardar_panorama(st.session_state.df_gestion)
            st.rerun()

    # --- PDF ---
    class PDF(FPDF):
        def header(self):
            self.set_fill_color(20, 20, 20)
            self.rect(0, 0, 210, 45, 'F')
            self.set_y(15)
            self.set_font('helvetica', 'B', 24)
            self.set_text_color(255, 255, 255)
            self.cell(0, 10, 'INFORME DE GESTION', 0, 1, 'C')
            self.ln(25)

    if st.button("Descargar Informe PDF"):
        pdf = PDF()
        pdf.add_page()
        pdf.set_text_color(40, 40, 40)
        pdf.set_font('helvetica', 'B', 16)
        pdf.cell(0, 10, "Estadisticas de Operatoria", 0, 1)
        pdf.ln(5)
        pdf.set_font('helvetica', '', 12)
        pdf.cell(0, 8, f"Total Trades Positivos: {total_pos}", 0, 1)
        pdf.cell(0, 8, f"Total Trades Negativos: {total_neg}", 0, 1)
        pdf.set_font('helvetica', 'B', 12)
        pdf.cell(0, 8, f"Rango mas favorable: {mejor_rango}", 0, 1)
        pdf.ln(10)

        pdf.set_fill_color(220, 220, 220)
        pdf.set_font('helvetica', 'B', 10)
        headers = ['Fecha', 'Activo', 'Rango', 'Tipo', 'Resultado']
        for h in headers: pdf.cell(38, 10, h, 1, 0, 'C', 1)
        pdf.ln()

        pdf.set_font('helvetica', '', 10)
        for _, r in df.iterrows():
            pdf.cell(38, 8, str(r['Fecha']), 1, 0, 'C')
            pdf.cell(38, 8, str(r['Activo']), 1, 0, 'C')
            pdf.cell(38, 8, str(r['Rango']), 1, 0, 'C')
            pdf.cell(38, 8, str(r['Tipo']), 1, 0, 'C')
            pdf.cell(38, 8, str(r['Resultado']), 1, 1, 'C')

        pdf_bytes = bytes(pdf.output())
        st.download_button(label="💾 Guardar PDF", data=pdf_bytes, file_name="Informe_Gestion.pdf", mime="application/pdf")
else:
    st.markdown("---")
    st.info("💡 **Historial libre de registros**. Las estadísticas generales, tablas interactivas y descargas de PDF volverán a mostrarse en este espacio apenas sincronices tu primera operación del día.")

st.markdown('</div>', unsafe_allow_html=True)
