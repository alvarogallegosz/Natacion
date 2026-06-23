import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import fsolve
import pandas as pd
import datetime
import io
import hashlib
from supabase import create_client, Client

# --- IMPORTS PARA EL ENVÍO DE CORREOS ---
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# -------------------------------------------------------------
# 1. FUNCIONES UTILITARIAS Y DE ENCRIPTACIÓN (Sin llamadas a Streamlit)
# -------------------------------------------------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def calcular_edad_tecnica_al_31_dic(fecha_nacimiento, temporada_activa):
    if isinstance(fecha_nacimiento, str):
        fecha_nacimiento = datetime.datetime.strptime(fecha_nacimiento, '%Y-%m-%d').date()
    edad_tecnica = temporada_activa - fecha_nacimiento.year
    return edad_tecnica

def evaluar_elegibilidad_internacional(edad_tecnica, ente_rector):
    entes_internacionales = ["PANAM", "SURAM", "WA"]
    if ente_rector in entes_internacionales:
        if edad_tecnica < 14:
            return False, f"Ineligible: Edad técnica ({edad_tecnica} años) menor a 14 años exigidos para {ente_rector}."
    return True, "Elegible"

def calcular_fecha_alerta(fecha_inicio_competencia, dias_anticipacion=15):
    if isinstance(fecha_inicio_competencia, str):
        fecha_inicio_competencia = datetime.datetime.strptime(fecha_inicio_competencia, '%Y-%m-%d').date()
    fecha_alerta = fecha_inicio_competencia - datetime.timedelta(days=dias_anticipacion)
    return fecha_alerta

def enviar_email(asunto, cuerpo, destinatario):
    try:
        msg = MIMEMultipart()
        msg['From'] = st.secrets["EMAIL_REMITE"]
        msg['To'] = destinatario
        msg['Subject'] = asunto
        msg.attach(MIMEText(cuerpo, 'plain'))

        with smtplib.SMTP_SSL(st.secrets["EMAIL_SMTP_SERVER"], int(st.secrets["EMAIL_SMTP_PORT"])) as server:
            server.login(st.secrets["EMAIL_REMITE"], st.secrets["EMAIL_PASSWORD"])
            server.sendmail(st.secrets["EMAIL_REMITE"], destinatario, msg.as_string())
        return True
    except Exception as e:
        print(f"Error al enviar email: {e}")
        return False

# -------------------------------------------------------------
# 2. CONFIGURACIÓN INICIAL DE LA PÁGINA (Debe ser lo primero de st)
# -------------------------------------------------------------
st.set_page_config(page_title="Simulador de proyección de rendimiento para natación", layout="wide")

# -------------------------------------------------------------
# 3. INYECCIÓN DE ESTILOS CSS
# -------------------------------------------------------------
st.markdown(
    """
    <style>
    div[data-testid="stMetricValue"] { font-size: 22px !important; }
    div[data-testid="stMetricLabel"] { font-size: 13px !important; }
    section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] .css-10trblm, section[data-testid="stSidebar"] h4 {
        font-size: 12px !important;
    }
    @media print {
        .no-print { display: none !important; }
        .print-only { display: block !important; }
    }
    </style>
    """,
    unsafe_html=True
)

def spc():
    st.markdown("<div style='height: 4px;'></div>", unsafe_html=True)

# -------------------------------------------------------------
# 4. CONEXIÓN SEGURA CON SUPABASE
# -------------------------------------------------------------
try:
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Faltan las credenciales de Supabase en los Secrets de la aplicación.")
    st.stop()

# -------------------------------------------------------------
# 5. MOTORES CACHEDOS DE CONSULTAS (Caché local Lite)
# -------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=600)
def obtener_datos_hitos_atleta(nadador_id):
    try:
        res_atleta = supabase.table("usuarios").select("fecha_nacimiento").eq("id", nadador_id).execute()
        res_hitos = supabase.table("historial_hitos").select("elegible, catalogo_competencias(fecha_inicio, fecha, nombre_evento)").eq("usuario_id", nadador_id).execute()
        if res_atleta.data and res_atleta.data[0].get("fecha_nacimiento"):
            return {
                "fecha_nacimiento": res_atleta.data[0]["fecha_nacimiento"],
                "hitos": res_hitos.data if res_hitos.data else []
            }
    except Exception as e:
        print(f"Error interno en consulta cacheada de Supabase: {e}")
    return None

@st.cache_data(show_spinner=False, ttl=3600)
def cargar_marcas_referencia_optimizadas(prueba, genero, categoria):
    try:
        ref_resp = supabase.table("marcas_referencia").select("m_ano, m_panam_b, m_panam_a, m_wa_b, m_wa_a, m_wr")\
            .eq("prueba", prueba)\
            .eq("genero", genero)\
            .eq("categoria", categoria).execute()
        if ref_resp.data:
            return ref_resp.data[0]
    except Exception as e:
        print(f"Error extrayendo marcas optimizadas: {e}")
    return None

# -------------------------------------------------------------
# 6. LÓGICA DE CATEGORÍAS Y SESIONES
# -------------------------------------------------------------
def calcular_categoria_competencia(fecha_nac_str):
    if not fecha_nac_str:
        return "Desconocida", 0
    try:
        fecha_nac = datetime.date.fromisoformat(str(fecha_nac_str))
    except Exception:
        return "Error Formato", 0
        
    ano_actual = datetime.date.today().year 
    edad_competencia = ano_actual - fecha_nac.year
    
    if 5 <= edad_competencia <= 6: cat = "Preinfantil A"
    elif 7 <= edad_competencia <= 8: cat = "Preinfantil B"
    elif edad_competencia == 9: cat = "Preinfantil C"
    elif 10 <= edad_competencia <= 11: cat = "Infantil A"
    elif 12 <= edad_competencia <= 13: cat = "Infantil B"
    elif 14 <= edad_competencia <= 15: cat = "Juvenil A"
    elif 16 <= edad_competencia <= 18: cat = "Juvenil B"
    elif edad_competencia > 18: cat = "Máxima"
    else: cat = "Semillero / Menor"
    return cat, edad_competencia

# (Continúa el resto de tu lógica de login, sidebar y app principal a continuación...)
