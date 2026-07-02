import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import fsolve
import pandas as pd
import datetime
import io
import hashlib
from supabase import create_client, Client
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as tf
import random
import zipfile
# -------------------------------------------------------------
# FUNCIÓN DE ENCRIPTACIÓN DE CONTRASEÑAS
# -------------------------------------------------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# -------------------------------------------------------------
# CACHÉ INTELIGENTE PARA CONSULTAS A SUPABASE (OPTIMIZACIÓN DE RENDIMIENTO)
# -------------------------------------------------------------

@st.cache_data(ttl=86400, show_spinner=False)
def obtener_marcas_referencia_cache(prueba, genero, categoria):
    """Marca de referencia: Cambia ~1 vez al año. Caché por 24h."""
    try:
        supabase = st.session_state.get("supabase_client")
        if not supabase:
            return []
        ref_resp = supabase.table("marcas_referencia").select("*") \
            .eq("prueba", prueba) \
            .eq("genero", genero) \
            .eq("categoria", categoria).execute()
        return ref_resp.data if ref_resp.data else []
    except Exception:
        return []

@st.cache_data(ttl=3600, show_spinner=False)
def obtener_usuario_por_id_cache(usuario_id):
    """Datos de usuario (fecha_nacimiento, nombre, etc.): No cambian. Caché 1h."""
    try:
        supabase = st.session_state.get("supabase_client")
        if not supabase:
            return None
        response = supabase.table("usuarios") \
            .select("id, nombre, genero, rol, estatus, fecha_nacimiento") \
            .eq("id", usuario_id) \
            .execute()
        return response.data[0] if response.data else None
    except Exception:
        return None

@st.cache_data(ttl=3600, show_spinner=False)
def obtener_catalogo_competencias_cache():
    """Catálogo de competencias: Rara vez cambia. Caché 1h."""
    try:
        supabase = st.session_state.get("supabase_client")
        if not supabase:
            return []
        response = supabase.table("catalogo_competencias").select("*").execute()
        return response.data if response.data else []
    except Exception:
        return []

@st.cache_data(ttl=300, show_spinner=False)
def obtener_historial_hitos_cache(nadador_id):
    """Historial de hitos: Vinculado a competiciones. Caché 5 min para fluidez."""
    try:
        supabase = st.session_state.get("supabase_client")
        if not supabase:
            return []
        res_hitos = supabase.table("historial_hitos") \
            .select("*, catalogo_competencias(*)") \
            .eq("usuario_id", nadador_id) \
            .execute()
        return res_hitos.data if res_hitos.data else []
    except Exception:
        return []

@st.cache_data(ttl=300, show_spinner=False)
def obtener_marcas_historicas_cache(prueba, usuario_id):
    """Marcas históricas: Se actualizan cada 2-3 meses tras cada hito. Caché 5 min."""
    try:
        supabase = st.session_state.get("supabase_client")
        if not supabase:
            return []
        response = supabase.table("marcas_historicas") \
            .select("id, edad, tiempo, nota") \
            .eq("prueba", prueba) \
            .eq("usuario_id", usuario_id) \
            .order("edad", desc=False).execute()
        return response.data if response.data else []
    except Exception:
        return []

# -------------------------------------------------------------
# MOTOR DE EVALUACIÓN DE HITOS Y COMPETENCIAS
# -------------------------------------------------------------

def calcular_edad_tecnica_al_31_dic(fecha_nacimiento, temporada_activa):
    """
    Calcula la edad del nadador al 31 de diciembre del año en curso, 
    según la normativa técnica para categorización.
    """
    if isinstance(fecha_nacimiento, str):
        fecha_nacimiento = datetime.datetime.strptime(fecha_nacimiento, '%Y-%m-%d').date()
        
    edad_tecnica = temporada_activa - fecha_nacimiento.year
    return edad_tecnica

def evaluar_elegibilidad_internacional(edad_tecnica, ente_rector):
    """
    Verifica si el nadador cumple con la edad mínima para eventos internacionales.
    Retorna: (Booleano de elegibilidad, Motivo de rechazo o None)
    """
    entes_internacionales = ["PANAM AQUATICS", "WORLD AQUATICS"]
    if ente_rector in entes_internacionales:
        if edad_tecnica < 14:
            return False, f"Edad técnica insuficiente ({edad_tecnica} años). Mínimo requerido: 14 años."
    return True, None

def calcular_fecha_alerta(fecha_inicio_competencia, dias_anticipacion=15):
    """
    Calcula la fecha exacta en la que el cron/sistema debe notificar al atleta.
    """
    if isinstance(fecha_inicio_competencia, str):
        fecha_inicio_competencia = datetime.datetime.strptime(fecha_inicio_competencia, '%Y-%m-%d').date()
        
    fecha_alerta = fecha_inicio_competencia - datetime.timedelta(days=dias_anticipacion)
    return fecha_alerta
# -------------------------------------------------------------
# TRANSFORMACIÓN DE TIEMPOS DE SEGUNDOS (ss,00) A MINUTOS (mm:ss,00)
# -------------------------------------------------------------
def formatear_a_minutos(segundos_flotante: float) -> str:
    """Convierte segundos (ej: 84.15) a formato de natación M:SS.hh (ej: 1:24.15)"""
    try:
        if segundos_flotante <= 0 or pd.isna(segundos_flotante):
            return "-"
        minutos = int(segundos_flotante // 60)
        segundos = segundos_flotante % 60
        
        if minutos > 0:
            return f"{minutos}:{segundos:05.2f}"  # M:SS.hh (fuerza 2 dígitos en segundos)
        else:
            return f"{segundos:.2f} s"            # Si es menor a un minuto, lo deja en segundos
    except (ValueError, TypeError):
        return "-"
def convertir_string_a_segundos(tiempo_str: str) -> float:
    """
    Convierte un string formateado (M:SS.hh o SS.hh) a segundos flotantes.
    Ejemplos: '1:13.34' -> 73.34 | '46.28' -> 46.28
    """
    try:
        tiempo_str = tiempo_str.strip()
        if ":" in tiempo_str:
            partes_minutos = tiempo_str.split(":")
            minutos = int(partes_minutos[0])
            segundos = float(partes_minutos[1])
            return float(round((minutos * 60) + segundos, 2))
        else:
            return float(round(float(tiempo_str), 2))
    except Exception:
        raise ValueError("Formato de tiempo inválido. Use 'M:SS.hh' o 'SS.hh'")    
# -------------------------------------------------------------
# FUNCIÓN DE CALCULO DE EDAD_HITO (MÓDULO INDEPENDIENTE)
# -------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=600)  # Almacena en caché por 10 minutos
def obtener_datos_hitos_atleta(nadador_id):
    """
    Consulta de forma segura y aislada la información del atleta.
    Al estar decorada con @st.cache_data, Streamlit garantiza que NO 
    se generen loops infinitos ni sobrecargas a Supabase.
    """
    try:
        res_atleta = supabase.table("usuarios") \
            .select("fecha_nacimiento") \
            .eq("id", nadador_id) \
            .execute()
            
        res_hitos = supabase.table("historial_hitos") \
            .select("*, catalogo_competencias(*)") \
            .eq("usuario_id", nadador_id) \
            .execute()
            
        if res_atleta.data and res_atleta.data[0].get("fecha_nacimiento"):
            return {
                "fecha_nacimiento": res_atleta.data[0]["fecha_nacimiento"],
                "hitos": res_hitos.data if res_hitos.data else []
            }
    except Exception as e:
        print(f"Error interno en consulta cacheada de Supabase: {e}")
    return None

def sincronizar_hitos_competencias_atleta(nadador_id, fecha_nacimiento, genero_atleta):
    """
    Revisa el catálogo de competencias y asegura que el atleta tenga creados sus hitos
    para las competencias Nacionales e Internacionales de la temporada actual.
    """
    try:
        supabase_client = st.session_state.get("supabase_client")
        if not supabase_client:
            return

        # 1. Obtener el catálogo global de competencias
        competencias = obtener_catalogo_competencias_cache()
        if not competencias:
            return

        # 2. Obtener los hitos que ya tiene registrados el nadador actualmente
        hitos_actuales = supabase_client.table("historial_hitos") \
            .select("competencia_id") \
            .eq("usuario_id", nadador_id) \
            .execute()
        
        ids_competencias_registradas = [h["competencia_id"] for h in hitos_actuales.data] if hitos_actuales.data else []

        # 3. Evaluar qué competencias le corresponden y faltan por registrar
        for comp in competencias:
            comp_id = comp.get("id")
            # Evitamos duplicados si ya existe el hito para esta competencia
            if comp_id in ids_competencias_registradas:
                continue

            tipo_evento = str(comp.get("categoria_evento", "")).upper()
            
            # Filtramos estrictamente por Nacional o Internacional (con restricción)
            if "NACIONAL" in tipo_evento or "INTERNACIONAL" in tipo_evento:
                fecha_inicio_str = comp.get("fecha_inicio")
                
                if fecha_inicio_str:
                    fecha_comp = pd.to_datetime(fecha_inicio_str).date()
                    
                    # Calcular la edad exacta que tendrá el atleta en esa competencia
                    edad_en_evento = calcular_edad_decimal(fecha_nacimiento, fecha_comp)
                    
                    # Estructurar el nuevo registro de hito alineado con tu backend
                    nuevo_hito = {
                        "usuario_id": nadador_id,
                        "competencia_id": comp_id,
                        "nombre_hito": comp.get("nombre_evento", "Campeonato Obligatorio"),
                        "fecha_evento": fecha_inicio_str,
                        "edad_hito": float(round(edad_en_evento, 2)),
                        "descripcion": f"Sincronizado automáticamente para la temporada {comp.get('temporada', '')}"
                    }
                    
                    # Insertar en la tabla historial_hitos de Supabase
                    supabase_client.table("historial_hitos").insert(nuevo_hito).execute()
                    
        # Forzar la limpieza del caché local de hitos para que cargue los nuevos de inmediato
        st.cache_data.clear()

    except Exception as e:
        print(f"Error silencioso en la sincronización automática de hitos: {e}")

# -------------------------------------------------------------
# FUNCIÓN DE ENVÍO DE CORREOS (MÓDULO INDEPENDIENTE)
# -------------------------------------------------------------
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

# 1. CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(page_title="Swimming Club Training Control and Performance Forecasting System", layout="wide")

st.markdown(
    """
    <style>
    div[data-testid="stMetricValue"] { font-size: 22px !important; }
    div[data-testid="stMetricLabel"] { font-size: 13px !important; }
    section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] .css-10trblm, section[data-testid="stSidebar"] h4 {
        font-size: 12px !important;
    }
    
    /* === NUEVO ESQUEMA DE ESTILIZACIÓN GLOBAL PARA TODAS LAS TABLAS === */
    .stDataFrame div[data-testid="stTable"] table, table.dataframe, .tabla-estilizada {
        border-collapse: collapse !important;
        width: 100% !important;
        border: none !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important;
    }
    .stDataFrame div[data-testid="stTable"] th, table.dataframe th, .tabla-estilizada th {
        background-color: #F2F4F4 !important;  /* Gris suave limpio */
        color: #2C3E50 !important;             /* Texto oscuro elegante */
        font-weight: 600 !important;           /* Letras semibold */
        padding: 10px 14px !important;
        border-top: 1px solid #111111 !important;    /* Línea negra ultra fina superior */
        border-bottom: 1px solid #111111 !important; /* Línea negra ultra fina inferior */
        border-left: none !important;
        border-right: none !important;
        font-size: 13px !important;
        text-align: center !important;
    }
    .stDataFrame div[data-testid="stTable"] td, table.dataframe td, .tabla-estilizada td {
        padding: 8px 12px !important;         /* Padding para que los datos respiren */
        border-bottom: 1px solid #E5E7E9 !important; /* Separadores internos muy tenues */
        border-top: none !important;
        border-left: none !important;
        border-right: none !important;
        font-size: 12px !important;
        color: #34495E !important;
        text-align: center !important;
    }
    /* Resaltado especial elegante para la última fila de Totales o Resúmenes */
    table.dataframe tr:last-child td, .tabla-estilizada tr:last-child td {
        font-weight: bold !important;
        border-bottom: 2px solid #111111 !important;
        background-color: #FAFAFA !important;
    }
    
    @media print {
        .no-print { display: none !important; }
        .print-only { display: block !important; }
    }
    </style>
    """,
    unsafe_allow_html=True
)

def spc():
    st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)

# -------------------------------------------------------------
# CONEXIÓN SEGURA CON SUPABASE
# -------------------------------------------------------------
try:
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Faltan las credenciales de Supabase en los Secrets de la aplicación.")
    st.stop()


# -------------------------------------------------------------
# LÓGICA DE CATEGORÍAS ETARIAS (Edad cumplida al 31 de Diciembre)
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
    
    if 5 <= edad_competencia <= 6:
        cat = "Preinfantil A"
    elif 7 <= edad_competencia <= 8:
        cat = "Preinfantil B"
    elif edad_competencia == 9:
        cat = "Preinfantil C"
    elif 10 <= edad_competencia < 12:
        cat = "Infantil A"
    elif 12 <= edad_competencia < 14:
        cat = "Infantil B"
    elif 14 <= edad_competencia < 16:
        cat = "Juvenil A"
    elif 16 <= edad_competencia < 18:
        cat = "Juvenil B"
    elif 18 <= edad_competencia < 25:
        cat = "Máxima"
    elif edad_competencia >= 25:
        cat = "Máster"
    else:
        cat = "Semillero / Menor"
        
    return cat, edad_competencia

def calcular_edad_decimal(fecha_nacimiento_str, fecha_marca):
    if not fecha_nacimiento_str or not fecha_marca:
        return None
    try:
        if isinstance(fecha_nacimiento_str, str):
            fecha_nac_obj = datetime.date.fromisoformat(fecha_nacimiento_str)
        else:
            fecha_nac_obj = fecha_nacimiento_str
            
        diferencia_dias = (fecha_marca - fecha_nac_obj).days
        edad_decimal = diferencia_dias / 365.25
        return round(edad_decimal, 2)
    except Exception:
        return None

# -------------------------------------------------------------
# FUNCIÓN AUXILIAR: CONSULTA Y FILTRADO DE ATLETAS (ETAPA 2)
# -------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def obtener_atletas_filtrados_supabase():
    """Consulta la base de datos y devuelve una lista de diccionarios con la data de los atletas."""
    try:
        supabase = st.session_state.get("supabase_client")
        if not supabase:
            return []
        
        # Ajusta "usuarios" por el nombre exacto de tu tabla si difiere
        response = supabase.table("usuarios").select("id, nombre, email, genero, fecha_nacimiento").execute()
        if not response.data:
            return []
            
        lista_atletas = []
        for usuario in response.data:
            # Extraemos los campos asegurando que existan
            nombre = usuario.get("nombre", "Sin Nombre")
            email = usuario.get("email", "")
            genero = usuario.get("genero", "M") # 'M' o 'F'
            fecha_nac = usuario.get("fecha_nacimiento")
            
            # Usamos tu función para calcular la categoría y la edad
            categoria, edad = calcular_categoria_competencia(fecha_nac)
            
            # Solo agregamos si tiene un correo válido registrado
            if email and email.strip() != "":
                lista_atletas.append({
                    "id": usuario.get("id"),
                    "nombre": nombre,
                    "email": email,
                    "genero": "Masculino" if genero == "M" else "Femenino",
                    "genero_codigo": genero,
                    "categoria": categoria,
                    "edad": edad
                })
        return lista_atletas
    except Exception as e:
        st.error(f"Error al consultar base de datos de atletas: {e}")
        return []
# -------------------------------------------------------------
# FUNCIÓN CALCULAR PUNTOS WA
# -------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def calcular_puntos_wa(tiempo_atleta: float, record_mundial: float) -> int:
    """
    Calcula los puntos WA basándose en el WR específico de la prueba y género activos.
    """
    try:
        t = float(tiempo_atleta)
        wr = float(record_mundial)
        if t <= 0 or wr <= 0:
            return 0
        return max(0, int(1000 * ((wr / t) ** 3)))
    except (ValueError, TypeError):
        return 0
# -------------------------------------------------------------
# CONTROL DE ACCESO, REGISTRO Y RECUPERACIÓN DE SESIÓN UNIFICADO
# -------------------------------------------------------------
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.usuario_id = None
    st.session_state.nombre_nadador = ""
    st.session_state.genero = "F"
    st.session_state.rol = "Nadador"
    st.session_state.fecha_nacimiento = None
    st.session_state.categoria_atleta = ""
    st.session_state.edad_comp_atleta = 0
    st.session_state.nadador_seleccionado_id = None
    st.session_state.nadador_seleccionado_nombre = ""
    st.session_state.nadador_seleccionado_genero = "F"
    st.session_state.nadador_seleccionado_categoria = ""

# Inicialización de variables para verificación por código temporal
if "reg_codigo_verificacion" not in st.session_state:
    st.session_state.reg_codigo_verificacion = None
    st.session_state.reg_datos_temporales = None
if "rec_codigo_verificacion" not in st.session_state:
    st.session_state.rec_codigo_verificacion = None
    st.session_state.rec_datos_temporales = None

def login_usuario(user, password):
    try:
        user_lower = user.strip().lower()
        hashed_pw = hash_password(password)
        response = supabase.table("usuarios").select("id, nombre, genero, rol, estatus, fecha_nacimiento").eq("usuario", user).eq("contrasena", hashed_pw).execute()
        if response.data:
            user_data = response.data[0]
            
            if user_data.get("estatus") == "Pendiente":
                st.error("⚠️ Tu cuenta está en proceso de revisión por la administración. Aún no puedes ingresar.")
                return False
                
            if user_data.get("estatus", "Activo") in ["Suspendido", "Bloqueado"]:
                st.error(f"❌ Cuenta {user_data['estatus']}. Contacte a la dirección técnica.")
                return False
                
            st.session_state.autenticado = True
            st.session_state.usuario_id = user_data["id"]
            st.session_state.nombre_nadador = user_data["nombre"]
            st.session_state.genero = user_data.get("genero", "F")
            st.session_state.rol = user_data.get("rol", "Nadador")
            st.session_state.fecha_nacimiento = user_data.get("fecha_nacimiento")
            
            cat, ed_c = calcular_categoria_competencia(st.session_state.fecha_nacimiento)
            st.session_state.categoria_atleta = cat
            st.session_state.edad_comp_atleta = ed_c
            
            st.session_state.nadador_seleccionado_id = user_data["id"]
            st.session_state.nadador_seleccionado_nombre = user_data["nombre"]
            st.session_state.nadador_seleccionado_genero = user_data.get("genero", "F")
            st.session_state.nadador_seleccionado_categoria = cat
            return True
        return False
    except Exception as e:
        st.error(f"Error en Login: {e}")
        return False

if not st.session_state.autenticado:
    st.markdown("<h2 style='text-align: center;'>🏊‍♂️ Swimming Club Training Control and Performance Forecasting System - Sistema de Control de Entrenamientos y Proyección de Rendimientos</h2>", unsafe_allow_html=True)
    c_login, _ = st.columns([1.5, 1.5])
    with c_login:
        tab_login, tab_registro, tab_recuperar = st.tabs(["🔑 Iniciar Sesión", "📝 Registro de Usuarios", "🔄 Recuperar Contraseña"])
        
        with tab_login:
            st.caption("Nota: Los nombres de usuario se procesan en minúsculas.")
            with st.form("form_login"):
                usuario_input = st.text_input("Usuario o Correo:")
                contrasena_input = st.text_input("Contraseña:", type="password")
                if st.form_submit_button("Ingresar"):
                    if login_usuario(usuario_input, contrasena_input):
                        st.success("Acceso autorizado.")
                        st.rerun()
                    else:
                        st.error("Credenciales incorrectas o cuenta en revisión. Verifique sus datos.")
                        
        with tab_registro:
            st.markdown("### 📝 Registro de Nuevas Cuentas")
# Requerimiento 5: Si ya se envió el código de registro, mostrar interfaz de verificación
            if st.session_state.reg_codigo_verificacion:
                st.info(f"Se ha enviado un código de verificación al correo: **{st.session_state.reg_datos_temporales['email']}**")
                with st.form("form_verificacion_registro"):
                    codigo_ingresado = st.text_input("Ingrese el código temporal de 6 dígitos:")
                    
                    if st.form_submit_button("Confirmar y Registrar Cuenta"):
                        if codigo_ingresado.strip() == str(st.session_state.reg_codigo_verificacion):
                            try:
                                supabase.table("usuarios").insert(st.session_state.reg_datos_temporales).execute()
                                status_inicial = st.session_state.reg_datos_temporales["estatus"]
                                nuevo_nombre = st.session_state.reg_datos_temporales["nombre"]
                                nuevo_rol = st.session_state.reg_datos_temporales["rol"]
                                nuevo_email = st.session_state.reg_datos_temporales["email"]
                                
                                if status_inicial == "Pendiente":
                                    enviar_email("Cuenta en Revisión", f"Hola {nuevo_nombre}, tu cuenta de {nuevo_rol} ha sido registrada. Está pendiente de revisión por el administrador.", nuevo_email)
                                    enviar_email("Nuevo Registro Pendiente", f"El usuario {nuevo_nombre} ({nuevo_rol}) se ha registrado. Email: {nuevo_email}. Favor revisar en consola admin.", st.secrets["EMAIL_ADMIN"])
                                    st.success(f"¡Registro exitoso como **{nuevo_rol}**! Tu cuenta debe ser aprobada por el administrador.")
                                else:
                                    st.success(f"¡Registro exitoso como **{nuevo_rol}**! Ya puede iniciar sesión.")
                                
                                # Limpiar estados temporales
                                st.session_state.reg_codigo_verificacion = None
                                st.session_state.reg_datos_temporales = None
                            except Exception as reg_err:
                                st.error(f"Error en registro: {reg_err}")
                        else:
                            st.error("❌ El código ingresado es incorrecto. Inténtelo de nuevo.")
                    
                if st.button("❌ Cancelar Registro"):
                    st.session_state.reg_codigo_verificacion = None
                    st.session_state.reg_datos_temporales = None
                    st.rerun()
            
            else:
                # Flujo normal de llenado de datos de registro
                nuevo_rol = st.selectbox("Seleccione el Rol para la nueva cuenta:", options=["Nadador", "Head Coach", "Entrenador", "Administrador"], key="reg_rol_selector")
                es_nadador_reg = (nuevo_rol == "Nadador")
                
                with st.form("form_registro_dinamico"):
                    nuevo_nombre = st.text_input("Nombre completo:")
                    
                    # Requerimiento 3: Ejemplo sombreado del formato de usuario (placeholder)
                    nuevo_usuario = st.text_input("Nombre de Usuario (Alias):", placeholder="ejemplo: alberto_jordan o maria_jimenez")
                    nuevo_email = st.text_input("Correo Electrónico:", placeholder="ejemplo: altair19@gmail.com")
                    
                    # Requerimiento 2: Doble entrada de confirmación de contraseña en registro
                    nueva_contrasena = st.text_input("Establecer Contraseña:", type="password")
                    confirmar_contrasena = st.text_input("Confirmar Contraseña:", type="password")
                    
                    nuevo_genero = None
                    nueva_fecha_nac = None
                    
                    if es_nadador_reg:
                        st.markdown("---")
                        st.markdown("##### 🧬 Datos Biométricos Requeridos (Categorías Feveda)")
                        nuevo_genero = st.selectbox("Género:", options=["F", "M"], format_func=lambda x: "Femenino" if x == "F" else "Masculino")
                        nueva_fecha_nac = st.date_input("Fecha de Nacimiento:", min_value=datetime.date(1950, 1, 1), max_value=datetime.date.today())
                    
                    if st.form_submit_button("🚀 Enviar Código de Verificación"):
                        if nuevo_nombre and nuevo_usuario and nueva_contrasena and confirmar_contrasena and nuevo_email:
                            if nueva_contrasena != confirmar_contrasena:
                                st.error("❌ Las contraseñas no coinciden.")
                            else:
                                # Requerimiento 1 aplicado a registro para asegurar consistencia
                                nuevo_usuario_clean = nuevo_usuario.strip().lower()
                                try:
                                    chequeo = supabase.table("usuarios").select("id").eq("usuario", nuevo_usuario_clean).execute()
                                    if chequeo.data:
                                        st.error("El nombre de usuario ya está tomado.")
                                    else:
                                        # Generación del código temporal (Requerimiento 5)
                                        codigo_temp = random.randint(100000, 999999)
                                        status_inicial = "Pendiente" if nuevo_rol in ["Head Coach", "Entrenador", "Administrador"] else "Activo"
                                        
                                        # Guardar datos estructurados en la sesión temporalmente
                                        st.session_state.reg_datos_temporales = {
                                            "nombre": nuevo_nombre, 
                                            "usuario": nuevo_usuario_clean, 
                                            "email": nuevo_email.strip(),
                                            "contrasena": hash_password(nueva_contrasena),
                                            "rol": nuevo_rol, 
                                            "estatus": status_inicial,
                                            "genero": nuevo_genero if es_nadador_reg else None,
                                            "fecha_nacimiento": nueva_fecha_nac.isoformat() if (es_nadador_reg and nueva_fecha_nac) else None
                                        }
                                        
                                        # Enviar correo con código temporal
                                        cuerpo_mail = f"Hola {nuevo_nombre},\n\nTu código temporal de verificación para registrarte en el sistema es: {codigo_temp}\n\nSi no solicitaste este registro, ignora este correo."
                                        if enviar_email("Código de Verificación de Registro", cuerpo_mail, nuevo_email.strip()):
                                            st.session_state.reg_codigo_verificacion = codigo_temp
                                            st.success("📩 Código enviado con éxito. Revise su bandeja de entrada.")
                                            st.rerun()
                                        else:
                                            st.error("No se pudo enviar el correo de verificación. Revise la configuración SMTP o la dirección provista.")
                                except Exception as reg_err:
                                    st.error(f"Error en validación: {reg_err}")
                        else:
                            st.error("Por favor complete todos los datos obligatorios del formulario.")

        with tab_recuperar:
            st.markdown("### Restablecer Contraseña")
            # Requerimiento 6: Rutina de seguridad e interfaz para confirmación de código en Recuperación
            if st.session_state.rec_codigo_verificacion:
                st.info(f"Se ha enviado un código de seguridad a la dirección vinculada.")
                with st.form("form_verificacion_recuperacion"):
                    codigo_rec_ingresado = st.text_input("Ingrese el código temporal de recuperación:")
                    
                    if st.form_submit_button("Validar Código y Cambiar Contraseña"):
                        if codigo_rec_ingresado.strip() == str(st.session_state.rec_codigo_verificacion):
                            try:
                                datos = st.session_state.rec_datos_temporales
                                supabase.table("usuarios").update({"contrasena": datos["nueva_contrasena"]}).eq("id", datos["user_id"]).execute()
                                st.success("✅ Contraseña actualizada correctamente. Ya puede iniciar sesión.")
                                
                                # Limpiar estados temporales
                                st.session_state.rec_codigo_verificacion = None
                                st.session_state.rec_datos_temporales = None
                            except Exception as rec_err:
                                st.error(f"Error al actualizar la contraseña: {rec_err}")
                        else:
                            st.error("❌ El código ingresado es incorrecto.")
                            
                if st.button("❌ Cancelar Recuperación"):
                    st.session_state.rec_codigo_verificacion = None
                    st.session_state.rec_datos_temporales = None
                    st.rerun()
            
            else:
                with st.form("form_recuperacion"):
                    # Requerimiento 1 aplicado aquí para evitar fallas por mayúsculas/minúsculas
                    rec_usuario = st.text_input("Nombre de Usuario (Alias):")
                    rec_email = st.text_input("Correo Electrónico Asociado:")
                    nueva_clave = st.text_input("Nueva Contraseña Deseada:", type="password")
                    confirmar_clave = st.text_input("Confirmar Nueva Contraseña:", type="password")
                    
                    if st.form_submit_button("🔄 Solicitar Código de Recuperación"):
                        if not (rec_usuario and rec_email and nueva_clave and confirmar_clave):
                            st.error("Todos los campos del formulario de recuperación son obligatorios.")
                        elif nueva_clave != confirmar_clave:
                            st.error("La confirmación no coincide con la nueva contraseña introducida.")
                        else:
                            rec_usuario_clean = rec_usuario.strip().lower()
                            try:
                                verificacion = supabase.table("usuarios").select("id, estatus, nombre").eq("usuario", rec_usuario_clean).eq("email", rec_email.strip()).execute()
                                if verificacion.data:
                                    user_info = verificacion.data[0]
                                    if user_info.get("estatus") in ["Suspendido", "Bloqueado"]:
                                        st.error("Esta cuenta se encuentra suspendida o bloqueada por la administración.")
                                    else:
                                        # Generación del código temporal (Requerimiento 6)
                                        codigo_rec_temp = random.randint(100000, 999999)
                                        st.session_state.rec_datos_temporales = {
                                            "user_id": user_info["id"],
                                            "nueva_contrasena": hash_password(nueva_clave)
                                        }
                                        
                                        cuerpo_rec_mail = f"Hola {user_info['nombre']},\n\nHas solicitado un restablecimiento de contraseña. Tu código de seguridad temporal es: {codigo_rec_temp}\n\nSi no realizaste esta acción, contacta de inmediato al administrador."
                                        if enviar_email("Código de Seguridad - Recuperación de Contraseña", cuerpo_rec_mail, rec_email.strip()):
                                            st.session_state.rec_codigo_verificacion = codigo_rec_temp
                                            st.success("📩 Código de seguridad enviado al correo electrónico.")
                                            st.rerun()
                                        else:
                                            st.error("Error al enviar el correo de recuperación.")
                                else:
                                    st.error("❌ Los datos proporcionados no coinciden con ningún registro activo.")
                            except Exception as rec_err:
                                st.error(f"Error durante el proceso de restablecimiento: {rec_err}")
                            
    st.stop()

# -------------------------------------------------------------
# CONSTRUCCIÓN ORDENADA DE LA BARRA LATERAL (SIDEBAR)
# -------------------------------------------------------------
st.sidebar.markdown(f"**Usuario:** {st.session_state.nombre_nadador}  \n**Nivel:** `{st.session_state.rol}`")
if st.sidebar.button("🚪 Salir del Sistema"):
    st.session_state.autenticado = False
    st.rerun()
# Agrega esto en tu sidebar o cerca de los controles de selección
with st.sidebar:
    st.markdown("<hr style='width: 30%; margin: 8px auto; border-top: 1px solid #ccc;'/>", unsafe_allow_html=True)
    if st.sidebar.button("🔄 Refrescar Datos (Limpiar Caché)"):
        # Limpia toda la caché de datos
        st.cache_data.clear()
        # Fuerza una recarga inmediata de la página para aplicar los cambios
        st.rerun()
if st.session_state.rol in ["Head Coach", "Entrenador", "Administrador"]:
    spc()
    st.sidebar.subheader("🎯 Panel de Navegación de Atletas")
    try:
        # Filtrado basado en tu tabla intermedia "asignaciones"
        if st.session_state.rol == "Entrenador":
            resp_asig = supabase.table("asignaciones").select("atleta_id").eq("entrenador_id", st.session_state.usuario_id).execute()
            ids_asignados = [reg["atleta_id"] for reg in resp_asig.data] if resp_asig.data else []
            
            if ids_asignados:
                resp_atletas = supabase.table("usuarios").select("id, nombre, genero, fecha_nacimiento").eq("rol", "Nadador").eq("estatus", "Activo").in_("id", ids_asignados).execute()
            else:
                resp_atletas = None  # No tiene nadadores asignados
        else:
            # Head Coach y Administrador tienen acceso global
            resp_atletas = supabase.table("usuarios").select("id, nombre, genero, fecha_nacimiento").eq("rol", "Nadador").eq("estatus", "Activo").execute()
        
        if resp_atletas and resp_atletas.data:
            df_atl = pd.DataFrame(resp_atletas.data)
            dict_atletas = dict(zip(df_atl["id"], df_atl["nombre"]))
            
            sel_id = st.sidebar.selectbox("Monitorear Nadador:", options=list(dict_atletas.keys()), format_func=lambda x: dict_atletas[x])
            atleta_row = df_atl[df_atl["id"] == sel_id].iloc[0]
            
            st.session_state.nadador_seleccionado_id = int(atleta_row["id"])
            st.session_state.nadador_seleccionado_nombre = atleta_row["nombre"]
            st.session_state.nadador_seleccionado_genero = atleta_row["genero"]
            
            cat_calc, _ = calcular_categoria_competencia(atleta_row["fecha_nacimiento"])
            st.session_state.nadador_seleccionado_categoria = cat_calc
        else:
            st.sidebar.warning("⚠️ No tienes nadadores asignados en este momento. (Por defecto asignados al Head Coach)")
            st.session_state.nadador_seleccionado_id = None
    except Exception as e:
        st.error(f"Error cargando nómina de atletas filtrada: {e}")
else:
    st.session_state.nadador_seleccionado_id = st.session_state.usuario_id
    st.session_state.nadador_seleccionado_nombre = st.session_state.nombre_nadador
    st.session_state.nadador_seleccionado_genero = st.session_state.genero
    st.session_state.nadador_seleccionado_categoria = st.session_state.categoria_atleta
modo_equipo = False
tipo_filtro = "Todos los Atletas"
filtro_genero = "Todos"
cat_sel = None
ids_sel = []

if st.session_state.rol in ["Head Coach", "Entrenador", "Administrador"]:
    spc()
    st.sidebar.subheader("👥 Análisis Colectivo")
    modo_equipo = st.sidebar.checkbox("Activar Comparativa de Equipo", value=False)
    
    if modo_equipo:
        spc()
        st.sidebar.subheader("🔍 Filtros de Segmentación de Equipo")
        filtro_genero = st.sidebar.radio("Segmentar por Género:", options=["Todos", "Femenino (F)", "Masculino (M)"])
        tipo_filtro = st.sidebar.radio("Segmentar adicionalmente por:", options=["Todos los Atletas", "Categoría Etaria", "Atletas Específicos"])
        
        try:
            resp_preload = supabase.table("usuarios").select("id, nombre, fecha_nacimiento, genero").eq("rol", "Nadador").eq("estatus", "Activo").execute()
            atletas_preload = resp_preload.data if resp_preload.data else []
            
            if filtro_genero == "Femenino (F)":
                atletas_preload = [a for a in atletas_preload if a["genero"] == "F"]
            elif filtro_genero == "Masculino (M)":
                atletas_preload = [a for a in atletas_preload if a["genero"] == "M"]

            if tipo_filtro == "Categoría Etaria" and atletas_preload:
                categorias_disponibles = sorted(list(set([calcular_categoria_competencia(a["fecha_nacimiento"])[0] for a in atletas_preload])))
                if categorias_disponibles:
                    cat_sel = st.sidebar.selectbox("Seleccione la categoría:", options=categorias_disponibles)
                    
            elif tipo_filtro == "Atletas Específicos" and atletas_preload:
                dict_nom = {a["id"]: a["nombre"] for a in atletas_preload}
                if dict_nom:
                    ids_sel = st.sidebar.multiselect("Seleccione nadadores:", options=list(dict_nom.keys()), format_func=lambda x: dict_nom[x])
        except Exception as e:
            st.sidebar.error("Error cargando los filtros secundarios.")

# -------------------------------------------------------------
# AJUSTE DINÁMICO POR CATEGORÍA Y ORDENAMIENTO DE PRUEBAS
# -------------------------------------------------------------
spc()
st.sidebar.subheader("📊 Ajustes por prueba")

cat_atleta = st.session_state.nadador_seleccionado_categoria
es_preinfantil = cat_atleta.startswith("Preinfantil")

if es_preinfantil:
    lista_pruebas = [
        '--- 🏊‍♂️ LIBRE ---', '25 Libre', '50 Libre',
        '--- 🏊‍♂️ ESPALDA ---', '25 Espalda',
        '--- 🏊‍♂️ MARIPOSA ---', '25 Mariposa',
        '--- 🏊‍♂️ PECHO ---', '25 Pecho',
        '--- 🏊‍♂️ COMBINADO ---', '100 Combinado'
    ]
elif cat_atleta == "Infantil A":
    lista_pruebas = [
        '--- 🏊‍♂️ LIBRE ---', '50 Libre', '100 Libre', '200 Libre', '400 Libre',
        '--- 🏊‍♂️ ESPALDA ---', '50 Espalda',
        '--- 🏊‍♂️ MARIPOSA ---', '50 Mariposa',
        '--- 🏊‍♂️ PECHO ---', '50 Pecho',
        '--- 🏊‍♂️ COMBINADO ---', '200 Combinado'
    ]
elif cat_atleta == "Infantil B":
    lista_pruebas = [
        '--- 🏊‍♂️ LIBRE ---', '50 Libre', '100 Libre', '200 Libre', '400 Libre', '800 Libre',
        '--- 🏊‍♂️ ESPALDA ---', '50 Espalda', '100 Espalda', '200 Espalda',
        '--- 🏊‍♂️ MARIPOSA ---', '50 Mariposa', '100 Mariposa', '200 Mariposa',
        '--- 🏊‍♂️ PECHO ---', '50 Pecho', '100 Pecho', '200 Pecho',
        '--- 🏊‍♂️ COMBINADO ---', '200 Combinado'
    ]
else:
    lista_pruebas = [
        '--- 🏊‍♂️ LIBRE ---', '50 Libre', '100 Libre', '200 Libre', '400 Libre', '800 Libre', '1500 Libre',
        '--- 🏊‍♂️ ESPALDA ---', '50 Espalda', '100 Espalda', '200 Espalda',
        '--- 🏊‍♂️ MARIPOSA ---', '50 Mariposa', '100 Mariposa', '200 Mariposa',
        '--- 🏊‍♂️ PECHO ---', '50 Pecho', '100 Pecho', '200 Pecho',
        '--- 🏊‍♂️ COMBINADO ---', '200 Combinado', '400 Combinado'
    ]

titulo_grafico = st.sidebar.selectbox("Estilo y Distancia:", options=lista_pruebas, index=1)

if titulo_grafico.startswith("---"):
    st.sidebar.info("👆 Selecciona una distancia específica en el menú superior para ver o editar los datos.")
    st.stop()

contenedor_sliders = st.sidebar.container()

m_ano, m_panam_b, m_panam_a, m_wa_b, m_wa_a, m_wr = 0.0, 0.0, 0.0, 0.0, 0.0, 25.0

if es_preinfantil:
    def get_m_ano_infantil_a(prueba_str):
        try:
            resp = supabase.table("marcas_referencia").select("m_ano")\
                .eq("prueba", prueba_str)\
                .eq("genero", st.session_state.nadador_seleccionado_genero)\
                .eq("categoria", "Infantil A").execute()
            if resp.data and resp.data[0].get("m_ano"):
                return float(resp.data[0]["m_ano"])
        except Exception:
            pass
        return 0.0

    if titulo_grafico.startswith("25 "):
        estilo = titulo_grafico.split(" ")[1]
        ref_50 = get_m_ano_infantil_a(f"50 {estilo}")
        m_ano = ref_50 / 2.0  
        m_wr = m_ano * 0.8 if m_ano > 0 else 15.0 
    elif titulo_grafico == "50 Libre":
        m_ano = get_m_ano_infantil_a("50 Libre")
        m_wr = m_ano * 0.8 if m_ano > 0 else 30.0
    elif titulo_grafico == "100 Combinado":
        m_l = get_m_ano_infantil_a("50 Libre")
        m_e = get_m_ano_infantil_a("50 Espalda")
        m_p = get_m_ano_infantil_a("50 Pecho")
        m_m = get_m_ano_infantil_a("50 Mariposa")
        
        if all(v > 0 for v in [m_l, m_e, m_p, m_m]):
            m_ano = ((m_l + m_e + m_p + m_m) / 2.0) * 1.15
        else:
            m_ano = 0.0
        m_wr = m_ano * 0.8 if m_ano > 0 else 70.0
else:
    try:
        ref_resp = supabase.table("marcas_referencia").select("*")\
            .eq("prueba", titulo_grafico)\
            .eq("genero", st.session_state.nadador_seleccionado_genero)\
            .eq("categoria", st.session_state.nadador_seleccionado_categoria).execute()
        if ref_resp.data:
            ref_data = ref_resp.data[0]
            m_ano = float(ref_data["m_ano"]) if ref_data["m_ano"] else 0.0
            m_panam_b = float(ref_data["m_panam_b"]) if ref_data["m_panam_b"] else 0.0
            m_panam_a = float(ref_data["m_panam_a"]) if ref_data["m_panam_a"] else 0.0
            m_wa_b = float(ref_data["m_wa_b"]) if ref_data["m_wa_b"] else 0.0
            m_wa_a = float(ref_data["m_wa_a"]) if ref_data["m_wa_a"] else 0.0
            m_wr = float(ref_data["m_wr"]) if ref_data["m_wr"] else 25.0
    except Exception as e:
        st.error(f"Error extrayendo marcas de la categoría: {e}")

spc()
st.sidebar.subheader("🚨 Simulación de Escenarios")
simulacion_externa = st.sidebar.checkbox("Activar Modo Simulación Externa", value=False)

try:
    response = supabase.table("marcas_historicas") \
        .select("id, edad, tiempo, nota") \
        .eq("prueba", titulo_grafico) \
        .eq("usuario_id", st.session_state.nadador_seleccionado_id) \
        .order("edad", desc=False).execute() 
        
    if response.data:
        df_procesado = pd.DataFrame(response.data)
        df_procesado = df_procesado.rename(columns={"edad": "Edad", "tiempo": "Tiempo", "nota": "Evento / Fecha"})
        
        df_procesado["Edad"] = pd.to_numeric(df_procesado["Edad"])
        df_procesado["Tiempo"] = pd.to_numeric(df_procesado["Tiempo"])
        df_procesado = df_procesado.sort_values("Edad").reset_index(drop=True)
        
        db_t0 = float(df_procesado.iloc[0]["Edad"])
        db_T0 = float(df_procesado.iloc[0]["Tiempo"])
        n_registros = len(df_procesado)
        
        if n_registros == 1:
            db_t_pb, db_T_pb = db_t0, db_T0
        elif n_registros == 2:
            if float(df_procesado.iloc[-1]["Tiempo"]) <= float(df_procesado.iloc[-2]["Tiempo"]):
                db_t_pb, db_T_pb = float(df_procesado.iloc[-1]["Edad"]), float(df_procesado.iloc[-1]["Tiempo"])
            else:
                db_t_pb, db_T_pb = float(df_procesado.iloc[-2]["Edad"]), float(df_procesado.iloc[-2]["Tiempo"])
        else:
            indice_min_tiempo = df_procesado["Tiempo"].idxmin()
            posicion_desde_el_final = (n_registros - 1) - indice_min_tiempo
            
            if posicion_desde_el_final >= 2:
                db_t_pb, db_T_pb = float(df_procesado.iloc[-1]["Edad"]), float(df_procesado.iloc[-1]["Tiempo"])
            else:
                t_ultima, t_penultima = float(df_procesado.iloc[-1]["Tiempo"]), float(df_procesado.iloc[-2]["Tiempo"])
                if t_ultima <= t_penultima:
                    db_t_pb, db_T_pb = float(df_procesado.iloc[-1]["Edad"]), t_ultima
                else:
                    db_t_pb, db_T_pb = float(df_procesado.iloc[-2]["Edad"]), t_penultima
    else:
        df_procesado = pd.DataFrame(columns=["id", "Edad", "Tiempo", "Evento / Fecha"])
        db_t0, db_T0, db_t_pb, db_T_pb = None, None, None, None
except Exception:
    df_procesado = pd.DataFrame(columns=["id", "Edad", "Tiempo", "Evento / Fecha"])
    db_t0, db_T0, db_t_pb, db_T_pb = None, None, None, None

inputs_bloqueados = not simulacion_externa

val_t0 = db_t0 if (db_t0 is not None) else 10.0
val_T0 = db_T0 if (db_T0 is not None) else float(round(m_wr * 1.8, 2))
val_t_pb = db_t_pb if (db_t_pb is not None) else 12.0
val_T_pb = db_T_pb if (db_T_pb is not None) else float(round(m_wr * 1.3, 2))

if es_preinfantil:
    val_T_target = float(round(m_ano, 2)) if m_ano > 0 else 25.0
else:
    val_T_target = float(round(m_wa_a * 0.99, 2)) if m_wa_a > 0 else float(round(m_wr * 1.08, 2))

spc()
st.sidebar.subheader("📐 Parámetros de Límites y PB")
# =============================================================================
# 📐 PARÁMETROS DE LÍMITES Y PB (Mantén tus inputs tal como están)
# =============================================================================
t0 = st.sidebar.number_input("1. Edad Start (t0):", min_value=4.0, value=val_t0, step=0.01, disabled=inputs_bloqueados)
T0 = st.sidebar.number_input("2. Tiempo Inicial (T0):", min_value=1.0, value=val_T0, step=0.1, disabled=inputs_bloqueados)
t_peak = st.sidebar.number_input("3. Edad Peak Proyectado (t_peak):", min_value=5.0, max_value=30.0, value=23.0)
T_target = st.sidebar.number_input("4. Tiempo Objetivo Peak (T_target):", min_value=1.0, value=val_T_target)
t_pb = st.sidebar.number_input("5. Edad del PB de Control (t_pb):", min_value=4.0, value=val_t_pb, step=0.01, disabled=inputs_bloqueados)
T_pb = st.sidebar.number_input("6. Tiempo del PB de Control (T_pb):", min_value=1.0, value=val_T_pb, step=0.01, disabled=inputs_bloqueados)

tipo_vista = st.sidebar.selectbox("Enfoque del Gráfico", ["Macro (Historial Completo)", "Micro (Ventana Anual)"])

# =============================================================================
# 🔎 UBICACIÓN CORREGIDA: CONTROLES DE VISTA CON LÍMITES DINÁMICOS Y COMPLETO
# =============================================================================
if tipo_vista == "Micro (Ventana Anual)":
    limite_inf_abs = float(t0)
    limite_sup_abs = float(t_peak)
    rango_def_min = max(limite_inf_abs, min(float(t_pb), limite_sup_abs))
    rango_def_max = min(rango_def_min + 1.0, limite_sup_abs)
    edad_min_zoom, edad_max_zoom = st.sidebar.slider(
        "🔎 Rango de la Ventana (Edad)", min_value=limite_inf_abs, max_value=limite_sup_abs,
        value=(rango_def_min, rango_def_max), step=0.1, format="%.2f años"
    )
else:
    edad_min_zoom = 0.0
    edad_max_zoom = 100.0

with contenedor_sliders:
    spc()
    st.markdown("**⏱️ Rapidez de Deriva e Intervalo**")
    h = st.slider("Factor ajustable de rapidez de deriva (h):", min_value=0.1, max_value=1.0, value=0.35, step=0.05)
    t_intermedia = st.slider("Consultar Edad Intermedia:", min_value=float(t0), max_value=float(t_peak), value=float(round((t0+t_peak)/2, 1)), step=0.1)

if not modo_equipo and st.session_state.rol == "Nadador":
    st.sidebar.markdown("---")
    st.sidebar.caption("📅 *Requerido proyectar cada 3 meses hasta los 18 años para verificar marcas, asistir a campeonatos y optar por becas universitarias nacionales e internacionales.*")

if modo_equipo:
    st.markdown(f"### 🏊‍♂️ Planificación y control de resultados de competencia: Comparativo")
elif simulacion_externa:
    st.markdown(f"### 🧪 Simulación de Escenarios: {titulo_grafico}")
else:
    st.markdown(f"### 🏊‍♂️ Planificación y control de resultados de competencia: {st.session_state.nadador_seleccionado_nombre}")

st.markdown(f"**Género:** {'Masculino (M)' if st.session_state.nadador_seleccionado_genero == 'M' else 'Femenino (F)'} | **Categoría de Competencia Activa:** `{st.session_state.nadador_seleccionado_categoria}`")

#==========================================================================================================
# MOTOR MATEMÁTICO DOBLE CALCULO DE CURVA AJUSTADO
#==========================================================================================================
def resolver_k_individual(eq_t0, eq_T0, eq_t_pb, eq_T_pb, eq_t_peak, eq_T_target):
    if eq_t_peak > eq_t0 and eq_t_pb > eq_t0:
        tau_eq = (eq_t_pb - eq_t0) / (eq_t_peak - eq_t0)
        def ecuacion_k_eq(k_val):
            ter_exp = (np.exp(-k_val * tau_eq) - np.exp(-k_val)) / (1 - np.exp(-k_val))
            return (eq_T_target + (eq_T0 - eq_T_target) * ter_exp) - eq_T_pb
        k_opt_eq, _, _, _ = fsolve(ecuacion_k_eq, 1.0, full_output=True)
        return k_opt_eq[0]
    return 0.4

def calcular_curva_atleta(edades_arr, eq_t0, eq_T0, eq_t_pb, eq_T_pb, eq_t_peak, eq_T_target, k_eq, h_eq):
    tiempos = []
    D_eq = eq_T_pb - eq_T_target
    for t in edades_arr:
        if t < eq_t_pb:
            tau_t = (t - eq_t0) / (eq_t_peak - eq_t0)
            ter_exp = (np.exp(-k_eq * tau_t) - np.exp(-k_eq)) / (1 - np.exp(-k_eq))
            T_t = eq_T_target + (eq_T0 - eq_T_target) * ter_exp
        else:
            T_t = eq_T_pb - D_eq * (1 - np.exp(-h_eq * (t - eq_t_pb)))
        tiempos.append(T_t)
    return np.array(tiempos)

k = resolver_k_individual(t0, T0, t_pb, T_pb, t_peak, T_target)

c1, c2, c3 = st.columns(3)
with c1: st.metric(label="Factor de Ajuste Fisiológico (k)", value=f"{k:.4f}")
with c2: st.metric(label="Margen de Deriva de Seguridad (D)", value=f"{(T_pb - T_target):.2f} s")
with c3: 
    T_intermedia_val = float(calcular_curva_atleta([t_intermedia], t0, T0, t_pb, T_pb, t_peak, T_target, k, h)[0])
    st.metric(label=f"Proyección a los {t_intermedia:.1f} años", value=f"{T_intermedia_val:.2f} s")

# -------------------------------------------------------------
# RENDIMIENTO GRÁFICO: MODO EQUIPO (COMPARATIVO ENTRE NADADORES)
# -------------------------------------------------------------
if modo_equipo:
    try:
        resp_todos = supabase.table("usuarios").select("id, nombre, fecha_nacimiento, genero").eq("rol", "Nadador").eq("estatus", "Activo").execute()
        atletas_lista = resp_todos.data if resp_todos.data else []
        
        if filtro_genero == "Femenino (F)":
            atletas_lista = [a for a in atletas_lista if a["genero"] == "F"]
        elif filtro_genero == "Masculino (M)":
            atletas_lista = [a for a in atletas_lista if a["genero"] == "M"]

        atletas_filtrados = []
        if tipo_filtro == "Todos los Atletas":
            atletas_filtrados = atletas_lista
        elif tipo_filtro == "Categoría Etaria" and cat_sel:
            atletas_filtrados = [a for a in atletas_lista if calcular_categoria_competencia(a["fecha_nacimiento"])[0] == cat_sel]
        elif tipo_filtro == "Atletas Específicos" and ids_sel:
            atletas_filtrados = [a for a in atletas_lista if a["id"] in ids_sel]

        if not atletas_filtrados:
            st.warning("No se encontraron atletas activos con los criterios de segmentación elegidos.")
        else:
            # 1. Obtener la lista de IDs de los atletas filtrados
            lista_ids = [atl["id"] for atl in atletas_filtrados]
            
            # 2. Realizar UNA SOLA consulta masiva a Supabase para todo el colectivo
            res_marcas_colectivo = supabase.table("marcas_historicas")\
                .select("usuario_id, edad, tiempo, nota")\
                .eq("prueba", titulo_grafico)\
                .in_("usuario_id", lista_ids)\
                .order("edad", desc=False).execute()
                
            # Convertir la respuesta a un DataFrame global para filtrarlo en memoria
            df_global_marcas = pd.DataFrame(res_marcas_colectivo.data) if res_marcas_colectivo.data else pd.DataFrame()

            fig = plt.figure(figsize=(8.5, 11.0))
            ax = fig.add_axes([0.14, 0.58, 0.72, 0.33])
            from matplotlib.ticker import FuncFormatter

            # Creamos el formateador dinámico para el eje de Matplotlib
            formateador_eje_y = FuncFormatter(lambda x, pos: formatear_a_minutos(x))

            # Se lo aplicamos al eje de tiempos (asumiendo que es ax1 o ax el que tiene los segundos)
            ax.yaxis.set_major_formatter(formateador_eje_y)
            colores = plt.get_cmap("tab10", len(atletas_filtrados))
            hay_datos_visibles = False
            linea_fisiologica_anotada = False
            
            todas_las_edades_0 = []
            todos_los_tiempos_colectivo = []
            datos_atletas_cargados = []
            
            # 3. Bucle para procesar los datos localmente (sin llamadas de red adicionales)
            for idx, atl in enumerate(atletas_filtrados):
                a_id = atl["id"]
                a_nom = atl["nombre"]
                
                # Filtrar el DataFrame global en memoria en lugar de consultar a la BD
                if not df_global_marcas.empty and a_id in df_global_marcas["usuario_id"].values:
                    df_atl_m = df_global_marcas[df_global_marcas["usuario_id"] == a_id].copy()
                    df_atl_m = df_atl_m.rename(columns={"edad": "Edad", "tiempo": "Tiempo", "nota": "Evento / Fecha"})
                    hay_datos_visibles = True
                    
                    todas_las_edades_0.append(float(df_atl_m.iloc[0]["Edad"]))
                    todos_los_tiempos_colectivo.extend(df_atl_m["Tiempo"].tolist())
                    
                    datos_atletas_cargados.append({
                        "nom": a_nom,
                        "df": df_atl_m,
                        "color": colores(idx)
                    })

            if hay_datos_visibles:
                edad_0_min_colectivo = min(todas_las_edades_0)
                lim_x_min = max(4.0, edad_0_min_colectivo - 0.5)
                lim_x_max = t_peak + 1.0
                ax.set_xlim(lim_x_min, lim_x_max)
                
                peor_tiempo_colectivo = max(todos_los_tiempos_colectivo)
                lim_y_inferior = m_wr * 0.95
                lim_y_superior = peor_tiempo_colectivo + (peor_tiempo_colectivo * 0.05)
                ax.set_ylim(lim_y_inferior, lim_y_superior)
                
                for item in datos_atletas_cargados:
                    df_atl_m = item["df"]
                    color_curr = item["color"]
                    a_nom = item["nom"]
                    
                    t0_i = float(df_atl_m.iloc[0]["Edad"])
                    T0_i = float(df_atl_m.iloc[0]["Tiempo"])
                    idx_pb_i = df_atl_m["Tiempo"].idxmin()
                    t_pb_i = float(df_atl_m.loc[idx_pb_i, "Edad"])
                    T_pb_i = float(df_atl_m.loc[idx_pb_i, "Tiempo"])
                    
                    k_i = resolver_k_individual(t0_i, T0_i, t_pb_i, T_pb_i, t_peak, T_target)
                    edades_curva_i = np.linspace(t0_i, t_peak, 300)
                    tiempos_curva_i = calcular_curva_atleta(edades_curva_i, t0_i, T0_i, t_pb_i, T_pb_i, t_peak, T_target, k_i, h)
                    
                    if not linea_fisiologica_anotada:
                        ax.plot(edades_curva_i, tiempos_curva_i, color="#7F8C8D", linestyle=":", linewidth=1.2, label="Proyección fisiológica estimada")
                        linea_fisiologica_anotada = True
                    else:
                        ax.plot(edades_curva_i, tiempos_curva_i, color="#7F8C8D", linestyle=":", linewidth=1.2)
                    
                    ax.plot(df_atl_m["Edad"], df_atl_m["Tiempo"], color=color_curr, linestyle="-", linewidth=1.5, label=f"Evolución real - {a_nom}")
                    ax.scatter(df_atl_m["Edad"], df_atl_m["Tiempo"], color=color_curr, edgecolor="black", s=25, linewidths=0.5, zorder=3)
                    ax.scatter(t_pb_i, T_pb_i, color=color_curr, marker="*", edgecolor="black", s=80, linewidths=0.5, zorder=5)

                x_texto = lim_x_min + 0.1
                if not es_preinfantil:
                    referencias = [
                        {"val": m_ano, "lbl": "Mín. Año", "col": "#A06000", "va": "bottom"}, 
                        {"val": m_panam_b, "lbl": "PANAM Jr B", "col": "#006644", "va": "bottom"},      
                        {"val": m_panam_a, "lbl": "PANAM Jr A", "col": "#2A658A", "va": "top"},   
                        {"val": m_wa_b, "lbl": "WA B", "col": "#943100", "va": "bottom"},            
                        {"val": m_wa_a, "lbl": "WA A", "col": "#883963", "va": "top"},          
                        {"val": m_wr, "lbl": "World Record", "col": "#2C3E50", "va": "top"}   
                    ]
                    for r in referencias:
                        if r["val"] > 0 and lim_y_inferior <= r["val"] <= lim_y_superior:
                            ax.axhline(y=r["val"], color=r["col"], linestyle=":", linewidth=0.6, alpha=0.7)
                            desplazamiento_y = (lim_y_superior - lim_y_inferior) * 0.006 if r["va"] == "bottom" else -((lim_y_superior - lim_y_inferior) * 0.006)
                            ax.text(x_texto, r["val"] + desplazamiento_y, f"{r['lbl']}: {r['val']:.2f}s", color=r["col"], fontsize=7, va=r["va"], ha="left")
                else:
                    if m_ano > 0:
                        ax.axhline(y=m_ano, color="#A06000", linestyle="--", linewidth=0.6, alpha=0.7)
                        ax.text(x_texto, m_ano - ((lim_y_superior - lim_y_inferior) * 0.006), f"Target (Base Inf. A): {m_ano:.2f}s", color="#A06000", fontsize=7, va="top", ha="left")
                
                ax.set_title(f"Análisis Comparativo de Equipo - {titulo_grafico}", fontsize=12, pad=10)
                ax.set_xlabel("Edad del Atleta (Años)", fontsize=9.5)
                ax.set_ylabel("Tiempo de Carrera (Segundos)", fontsize=9.5)
                ax.grid(True, which="both", axis="both", linestyle=":", color="#CCD1D1", linewidth=0.5)
                ax.set_axisbelow(True)
                ax.legend(loc="upper right", fontsize=8, framealpha=0.8)
                
                st.pyplot(fig)
            else:
                st.info("No se hallaron marcas en la base de datos para los nadadores seleccionados en esta prueba.")
    except Exception as e:
        st.error(f"Error procesando los segmentos de equipo: {e}")
# -------------------------------------------------------------
# RENDIMIENTO GRÁFICO: MODO INDIVIDUAL O SIMULACIÓN
# -------------------------------------------------------------
else:
    fig = plt.figure(figsize=(8.5, 11.0))
    ax = fig.add_axes([0.14, 0.58, 0.72, 0.33])
    from matplotlib.ticker import FuncFormatter

    # Creamos el formateador dinámico para el eje de Matplotlib
    formateador_eje_y = FuncFormatter(lambda x, pos: formatear_a_minutos(x))

    # Se lo aplicamos al eje de tiempos (asumiendo que es ax1 o ax el que tiene los segundos)
    ax.yaxis.set_major_formatter(formateador_eje_y)    
    edades_curva = np.linspace(t0, t_peak, 300)
    tiempos_curva = calcular_curva_atleta(edades_curva, t0, T0, t_pb, T_pb, t_peak, T_target, k, h)
    
    todos_los_tiempos_ind = [T0, T_pb, T_target]
    if not simulacion_externa and len(df_procesado) > 0:
        todos_los_tiempos_ind.extend(df_procesado["Tiempo"].tolist())

    if tipo_vista == "Micro (Ventana Anual)":
        edades_ventana = np.linspace(edad_min_zoom, edad_max_zoom, 300)
        tiempos_curva_ventana = calcular_curva_atleta(edades_ventana, t0, T0, t_pb, T_pb, t_peak, T_target, k, h).tolist()
        
        tiempos_reales_ventana = []
        if not simulacion_externa and len(df_procesado) > 0:
            for _, row in df_procesado.iterrows():
                if edad_min_zoom <= row["Edad"] <= edad_max_zoom:
                    tiempos_reales_ventana.append(row["Tiempo"])
                    
        todos_tiempos_v = tiempos_curva_ventana + tiempos_reales_ventana
        
        if todos_tiempos_v:
            t_min_v = min(todos_tiempos_v)
            t_max_v = max(todos_tiempos_v)
        else:
            t_min_v = min(tiempos_curva)
            t_max_v = max(tiempos_curva)

        margen_y = max(0.5, (t_max_v - t_min_v) * 0.15)
        lim_y_inferior = t_min_v - margen_y
        lim_y_superior = t_max_v + margen_y
        
        lim_x_min = edad_min_zoom
        lim_x_max = edad_max_zoom
    else:
        peor_tiempo_ind = max(todos_los_tiempos_ind)
        lim_y_inferior = m_wr * 0.92 if m_wr > 0 else min(todos_los_tiempos_ind) * 0.90
        lim_y_superior = peor_tiempo_ind + (peor_tiempo_ind * 0.08)
        
        if len(df_procesado) > 0:
            min_edad_real = float(df_procesado["Edad"].min())
            lim_x_min = min(float(t0), min_edad_real) - 0.5
        else:
            lim_x_min = max(4.0, float(t0) - 0.5)
            
        lim_x_max = t_peak + 1.0

    ax.set_xlim(lim_x_min, lim_x_max)
    ax.set_ylim(lim_y_inferior, lim_y_superior)
    ax.set_autoscale_on(False)

    datos_tabla_micro = []
    nadador_id = st.session_state.get("nadador_seleccionado_id")
    
    if nadador_id and tipo_vista == "Micro (Ventana Anual)":
        datos_atleta = obtener_datos_hitos_atleta(nadador_id)
        if datos_atleta and datos_atleta.get("fecha_nacimiento"):
            try:
                fecha_nacimiento_real = datetime.date.fromisoformat(str(datos_atleta["fecha_nacimiento"])[:10])
            except Exception:
                fecha_nacimiento_real = None
            
            if fecha_nacimiento_real:
                for hito in datos_atleta.get("hitos", []):
                    try:
                        comp_info = hito.get("catalogo_competencias")
                        if not comp_info:
                            continue
                        
                        fecha_comp_str = comp_info.get("fecha_inicio") or comp_info.get("fecha")
                        if not fecha_comp_str:
                            continue
                        
                        if isinstance(fecha_comp_str, str):
                            fecha_evento_real = datetime.date.fromisoformat(fecha_comp_str[:10])
                        elif isinstance(fecha_comp_str, (datetime.date, datetime.datetime)):
                            fecha_evento_real = fecha_comp_str if isinstance(fecha_comp_str, datetime.date) else fecha_comp_str.date()
                        else:
                            continue
                        
                        dias_de_vida = (fecha_evento_real - fecha_nacimiento_real).days
                        edad_hito_calculada = dias_de_vida / 365.25

                        if lim_x_min <= edad_hito_calculada <= lim_x_max:
                            es_elegible = hito.get("elegible", True)
                            color_linea = "#2ECC71" if es_elegible else "#E74C3C" 
                            estilo_linea = "--" if es_elegible else ":"
                            
                            ax.axvline(
                                x=edad_hito_calculada, 
                                color=color_linea, 
                                linestyle=estilo_linea, 
                                linewidth=0.7, 
                                alpha=0.6, 
                                zorder=5
                            )
                            
                            # Anclamos el texto en la base del gráfico para no chocar con la leyenda
                            y_pos = lim_y_inferior + ((lim_y_superior - lim_y_inferior) * 0.03)
                            nombre_evento = comp_info.get("nombre_evento") or "Competencia"
                            nombre_corto = nombre_evento[:18] + "..." if len(nombre_evento) > 18 else nombre_evento
                            
                            ax.text(
                                x=edad_hito_calculada + 0.015, 
                                y=y_pos, 
                                s=f"{nombre_corto} {fecha_evento_real.strftime('%d/%m/%Y')}", 
                                color=color_linea, 
                                fontsize=7.5, 
                                weight="light",
                                rotation=90, 
                                va="bottom", 
                                ha="left", 
                                alpha=0.85, 
                                zorder=6
                            )

                            tiempo_proyectado_val = calcular_curva_atleta(
                                [edad_hito_calculada], t0, T0, t_pb, T_pb, t_peak, T_target, k, h
                            )[0]
                            
                            datos_tabla_micro.append({
                                "Competencia / Evento": nombre_evento,
                                "Fecha": fecha_evento_real.strftime('%d/%m/%Y'),
                                "Edad": f"{edad_hito_calculada:.2f} a",
                                "Marca Proyectada": f"{tiempo_proyectado_val:.2f} s"
                            })
                    except Exception as e_hito:
                        print(f"Advertencia procesando hito individual: {e_hito}")

    if datos_tabla_micro:
        datos_tabla_micro.sort(key=lambda x: float(x["Edad"].replace(" a", "").strip()))

    ax.plot(edades_curva, tiempos_curva, color="#007A87", linewidth=1.8, label="Proyección Fisiológica")

    if not simulacion_externa and len(df_procesado) > 0:
        ax.plot(df_procesado["Edad"], df_procesado["Tiempo"], color="#D55E00", linestyle="--", linewidth=1.0, alpha=0.6, label="Evolución Real (PBs)")
        ax.scatter(df_procesado["Edad"], df_procesado["Tiempo"], color="#D55E00", edgecolor="black", s=25, linewidths=0.6, zorder=3)

    offset_y = (lim_y_superior - lim_y_inferior) * 0.025
    estilo_bbox = dict(boxstyle="round,pad=0.25", fc="#F8F9F9", ec="#BDC3C7", alpha=0.9, linewidth=0.5)

    if lim_x_min <= t0 <= lim_x_max and lim_y_inferior <= T0 <= lim_y_superior:
        ax.scatter(t0, T0, color="#7F8C8D", edgecolor="black", s=35, linewidths=0.6, zorder=4)
        ax.text(t0 + 0.1, T0, f"P. Start\n{t0:.2f}a\n{formatear_a_minutos(val_T0)}", fontsize=8, va="bottom", ha="left", bbox=estilo_bbox)
        ax.axvline(x=t0, color="#7F8C8D", linestyle=":", linewidth=0.7, alpha=0.5)

    if lim_x_min <= t_pb <= lim_x_max and lim_y_inferior <= T_pb <= lim_y_superior:
        ax.scatter(t_pb, T_pb, color="#F1C40F", marker="*", edgecolor="black", s=100, linewidths=0.6, zorder=5, label="PB Actual de Control")
        ax.text(t_pb + 0.15, T_pb, f"PB Actual\n{t_pb:.2f}a\n{formatear_a_minutos(val_T_pb)}", fontsize=8, va="center", ha="left", bbox=estilo_bbox)
        ax.axvline(x=t_pb, color="red", linestyle="--", linewidth=0.7, alpha=0.4)

    if lim_x_min <= t_intermedia <= lim_x_max and lim_y_inferior <= T_intermedia_val <= lim_y_superior:
        ax.scatter(t_intermedia, T_intermedia_val, color="red", marker="o", s=30, zorder=5, label="Punto Consultado")
        ax.text(t_intermedia, T_intermedia_val + offset_y, f"Consulta: {t_intermedia:.1f}a\n{formatear_a_minutos(T_intermedia_val)}", fontsize=8, va="bottom", ha="center", bbox=estilo_bbox)
        ax.axvline(x=t_intermedia, color="red", linestyle=":", linewidth=0.7, alpha=0.4)

    if lim_x_min <= t_peak <= lim_x_max and lim_y_inferior <= T_target <= lim_y_superior:
        ax.scatter(t_peak, T_target, color="#2ECC71", marker="s", edgecolor="black", s=35, linewidths=0.6, zorder=4, label="Meta Peak")
        ax.text(t_peak - 0.1, T_target, f"Meta Peak\n{t_peak:.2f}a\n{formatear_a_minutos(T_target)}", fontsize=8, va="bottom", ha="right", bbox=estilo_bbox)
        ax.axvline(x=t_peak, color="#2ECC71", linestyle=":", linewidth=0.7, alpha=0.5)

    x_texto = lim_x_min + (lim_x_max - lim_x_min) * 0.05
    if not es_preinfantil:
        referencias = [
            {"val": m_ano, "lbl": "Mín. Año", "col": "#A06000", "va": "bottom"}, 
            {"val": m_panam_b, "lbl": "PANAM Jr B", "col": "#006644", "va": "bottom"},      
            {"val": m_panam_a, "lbl": "PANAM Jr A", "col": "#2A658A", "va": "top"},   
            {"val": m_wa_b, "lbl": "WA B", "col": "#943100", "va": "bottom"},               
            {"val": m_wa_a, "lbl": "WA A", "col": "#883963", "va": "top"},            
            {"val": m_wr, "lbl": "World Record", "col": "#2C3E50", "va": "top"}   
        ]
        for r in referencias:
            if r["val"] > 0 and lim_y_inferior <= r["val"] <= lim_y_superior:
                ax.axhline(y=r["val"], color=r["col"], linestyle=":", linewidth=0.6, alpha=0.7)
                desplazamiento_y = (lim_y_superior - lim_y_inferior) * 0.006 if r["va"] == "bottom" else -((lim_y_superior - lim_y_inferior) * 0.006)
                ax.text(x_texto, r["val"] + desplazamiento_y, f"{r['lbl']}: {r['val']:.2f}s", color=r["col"], fontsize=7, va=r["va"], ha="left")
    else:
        if m_ano > 0:
            ax.axhline(y=m_ano, color="#A06000", linestyle="--", linewidth=0.6, alpha=0.7)
            ax.text(x_texto, m_ano - ((lim_y_superior - lim_y_inferior) * 0.006), f"Target (Base Inf. A): {m_ano:.2f}s", color="#A06000", fontsize=7, va="top", ha="left")

    if simulacion_externa:
        ax.set_title(f"Simulación de Escenarios - {titulo_grafico}", fontsize=12, pad=10)
    else:
        ax.set_title(f"Curva de Rendimiento Asintótica - {titulo_grafico}\nAtleta: {st.session_state.nadador_seleccionado_nombre} | Categoría: {st.session_state.nadador_seleccionado_categoria}", fontsize=12, pad=10)

    ax.set_xlabel("Edad del Atleta (Años)", fontsize=9.5)
    ax.set_ylabel("Tiempo de Carrera (Segundos)", fontsize=9.5)
    ax.grid(True, which="both", axis="both", linestyle=":", color="#CCD1D1", linewidth=0.5)
    ax.set_axisbelow(True) 
    
    # Leyenda dinámica más pequeña si estamos en modo Micro
    tamano_leyenda = 6.5 if tipo_vista == "Micro (Ventana Anual)" else 8
    ax.legend(loc="upper right", fontsize=tamano_leyenda, framealpha=0.8)

    df_table_render = None
    es_modo_micro_tabla = (tipo_vista == "Micro (Ventana Anual)")

    if es_modo_micro_tabla:
        if datos_tabla_micro:
            df_table_render = pd.DataFrame(datos_tabla_micro)
            anchos_columnas = [0.46, 0.18, 0.16, 0.20]
        else:
            df_table_render = pd.DataFrame([{
                "Competencia / Evento": "No hay hitos o competencias en este rango de edad",
                "Fecha": "-",
                "Edad": "-",
                "Tiempo Prog.": "-"
            }])
            anchos_columnas = [0.52, 0.16, 0.16, 0.16]
    else:
        if not simulacion_externa and len(df_procesado) > 0:
            df_table_render = df_procesado[["Edad", "Tiempo", "Evento / Fecha"]].copy()
            
            # =============================================================================
            # EXTRACCIÓN DINÁMICA DEL WR CORRESPONDIENTE A LA PRUEBA Y GÉNERO ACTIVOS
            # =============================================================================
            # Aquí interceptamos el WR exacto que está usando tu gráfico actual.
            # Puedes usar la variable con la que pintas la línea horizontal del WR en el lienzo.
            wr_referencia_real = m_wr  # <-- SUSTITUYE CON TU VARIABLE DE WR (Ej: wr_actual, wr_prueba, etc.)
            
            # Se calcula la columna usando el WR específico de esta prueba
            df_table_render["WA"] = df_table_render["Tiempo"].apply(
                lambda x: calcular_puntos_wa(x, wr_referencia_real)
            )
            
            # Reordenamiento estético para el lienzo
            df_table_render = df_table_render[["Edad", "Tiempo", "WA", "Evento / Fecha"]]
            
            # Formateo de strings para presentación visual
            df_table_render["Edad"] = df_table_render["Edad"].map(lambda x: f"{x:.2f} a")
            df_table_render["Tiempo"] = df_table_render["Tiempo"].apply(formatear_a_minutos)
            df_table_render["WA"] = df_table_render["WA"].map(lambda x: f"{x} pts" if x > 0 else "-")
            
            anchos_columnas = [0.13, 0.13, 0.14, 0.60]
        else:
            df_table_render = pd.DataFrame([{
                "Edad": "-", 
                "Tiempo": "-", 
                "WA": "-",
                "Evento / Fecha": "Sin marcas históricas registradas"
            }])
            anchos_columnas = [0.13, 0.13, 0.14, 0.60]

    if df_table_render is not None and not df_table_render.empty:
        total_filas = len(df_table_render)
        limite_filas_por_bloque = 18
        
        def estilizar_tabla_nativo(instancia_tabla):
            instancia_tabla.auto_set_font_size(False)
            instancia_tabla.set_fontsize(8.5)
            instancia_tabla.scale(1.0, 1.3)
            for (row, col), cell in instancia_tabla.get_celld().items():
                cell.set_linewidth(0.5)            # Línea sutil muy delgada
                cell.set_edgecolor('#E5E7EB')       # Gris claro moderno
                if row == 0:
                    cell.set_text_props(color='black', weight='light')
                    cell.set_facecolor('#C0C0C0')
                else:
                    cell.set_facecolor('#F8F9F9' if row % 2 == 0 else 'white')

        if total_filas <= limite_filas_por_bloque:
            ax_table = fig.add_axes([0.14, 0.054, 0.72, 0.48])
            ax_table.axis('off')
            mpl_table = ax_table.table(
                cellText=df_table_render.values, 
                colLabels=df_table_render.columns, 
                cellLoc='center', 
                loc='upper center', 
                colWidths=anchos_columnas
            )
            estilizar_tabla_nativo(mpl_table)
        else:
            if total_filas > 36: 
                df_table_render = df_table_render.iloc[:32]
            df_bloque_izq = df_table_render.iloc[:limite_filas_por_bloque]
            df_bloque_der = df_table_render.iloc[limite_filas_por_bloque:]
            
            # Distribución proporcional adaptada para el bloque doble en paralelo
            anchos_doble = anchos_columnas if es_modo_micro_tabla else [0.15, 0.15, 0.16, 0.54]
            
            ax_table1 = fig.add_axes([0.14, 0.054, 0.34, 0.48])
            ax_table1.axis('off')
            mpl_table1 = ax_table1.table(cellText=df_bloque_izq.values, colLabels=df_bloque_izq.columns, cellLoc='center', loc='upper center', colWidths=anchos_doble)
            estilizar_tabla_nativo(mpl_table1)
            
            ax_table2 = fig.add_axes([0.52, 0.054, 0.34, 0.54])
            ax_table2.axis('off')
            mpl_table2 = ax_table2.table(cellText=df_bloque_der.values, colLabels=df_bloque_der.columns, cellLoc='center', loc='upper center', colWidths=anchos_doble)
            estilizar_tabla_nativo(mpl_table2)

    st.pyplot(fig, use_container_width=True)

# -------------------------------------------------------------------------
# ST.MARKDOWN - CENTRO DE EXPORTACIÓN
# -------------------------------------------------------------------------
st.markdown("---")
st.markdown("### 🖨️ Centro de Exportación de Reportes y Gráficos")

if len(df_procesado) > 0 or modo_equipo:
    export_df = df_procesado.drop(columns=["id", "usuario_id"], errors="ignore")
    csv_data = export_df.to_csv(index=False).encode('utf-8')
    txt_string = export_df.to_string(index=False)
    
    # 1. Creamos el "escudo" inicializando la variable en None
    img_buffer = None
    
    if modo_equipo and not atletas_filtrados:
        st.warning("No se encontraron atletas activos con los criterios de segmentación elegidos.")
    else:
        # Solo intentamos guardar si la figura realmente existe en esta ejecución
        if 'fig' in locals() and fig is not None:
            img_buffer = io.BytesIO()
            fig.savefig(img_buffer, format="png", bbox_inches=None, dpi=300)
            img_buffer.seek(0)
    
    c_exp1, c_exp2, c_exp3 = st.columns(3)
    with c_exp1:
        st.download_button(label="📥 Descargar Historial (CSV)", data=csv_data, file_name=f"marcas_{titulo_grafico}_{st.session_state.get('nadador_seleccionado_nombre', 'equipo')}.csv", mime="text/csv")
    with c_exp2:
        st.download_button(label="📄 Descargar Datos (TXT)", data=txt_string, file_name=f"reporte_{titulo_grafico}_{st.session_state.get('nadador_seleccionado_nombre', 'equipo')}.txt", mime="text/plain")
    with c_exp3:
        # 2. Protegemos el botón: si no hay buffer de imagen, no se rompe la app
        if img_buffer is not None:
            st.download_button(label="🖼️ Guardar Gráfico Completo (Imagen PNG - Tamaño Carta)", data=img_buffer, file_name=f"grafico_{titulo_grafico}_{st.session_state.get('nadador_seleccionado_nombre', 'equipo')}.png", mime="image/png")
        else:
            st.info("📉 Gráfico no disponible (Sin atletas o datos).")


# -------------------------------------------------------------
# MÓDULOS DE GESTIÓN SEGÚN ROL
# -------------------------------------------------------------
st.markdown("---")

if simulacion_externa:
    st.info("⚠️ **Modo Simulación Externa Activo.** El módulo de gestión y control de marcas se encuentra oculto para evitar alteraciones accidentales en la base de datos real.")
else:
    tab_pizarra, tab_reportes, tab_marcas, tab_entrenador, tab_asignaciones, tab_calendario, tab_admin = st.tabs([
        "📝 Pizarra Diaria", 
        "📊 Reportes de Entrenamiento", 
        "📋 Resultados de competencias", 
        "⏱️ Configurar Marcas Mínimas",
        "🎯 Asignaciones de Nadadores",
        "📅 Calendario Anual de Competencias", 
        "🛡️ Consola Global (Admin)"
    ])
    with tab_marcas:
        col_ins, col_vistas = st.columns([1, 2])
        with col_ins:
            st.markdown("**Ingresar Nueva Marca**")
            with st.form("form_insertar_marca", clear_on_submit=True):
                ins_fecha_evento = st.date_input("Fecha de la Competencia:", min_value=datetime.date(2020, 1, 1), max_value=datetime.date.today(), value=datetime.date.today())
                
                # CAMBIO 1: Cambiamos a text_input para admitir formatos con dos puntos (:)
                ins_tiempo_str = st.text_input("Tiempo Oficial (Formatos: '1:13.34' o '46.28'):", placeholder="1:13.34")
                
                ins_nota = st.text_input("Evento / Fecha:")
                
                if st.form_submit_button("💾 Guardar Registro"):
                    if st.session_state.rol in ["Head Coach", "Entrenador", "Administrador"] or st.session_state.usuario_id == st.session_state.nadador_seleccionado_id:
                        try:
                            # CAMBIO 2: Validar y convertir el string a segundos flotantes inmediatamente
                            ins_tiempo = convertir_string_a_segundos(ins_tiempo_str)
                            
                            id_atleta = st.session_state.nadador_seleccionado_id
                            fecha_nacimiento_atleta = st.session_state.fecha_nacimiento
                            
                            if st.session_state.rol in ["Head Coach", "Entrenador", "Administrador"]:
                                atleta_query = supabase.table("usuarios").select("fecha_nacimiento").eq("id", id_atleta).execute()
                                if atleta_query.data:
                                    fecha_nacimiento_atleta = atleta_query.data[0]["fecha_nacimiento"]
                            
                            if not fecha_nacimiento_atleta:
                                st.error("❌ El atleta no posee fecha de nacimiento en su perfil.")
                            else:
                                edad_calculada = calcular_edad_decimal(fecha_nacimiento_atleta, ins_fecha_evento)
                                if edad_calculada is None:
                                    st.error("❌ Error al procesar la fecha de nacimiento.")
                                else:
                                    nueva_m = {
                                        "prueba": titulo_grafico, 
                                        "edad": float(edad_calculada), 
                                        "tiempo": float(ins_tiempo), # <--- Se guarda el float limpio en Supabase
                                        "nota": ins_nota, 
                                        "usuario_id": id_atleta
                                    }
                                    supabase.table("marcas_historicas").insert(nueva_m).execute()
                                    st.success(f"¡Marca guardada! Convertido a {ins_tiempo}s. Edad: {edad_calculada} años.")
                                    st.rerun()
                                    
                        except ValueError as e:
                            # Captura si el usuario metió mal el formato del tiempo (letras, etc.)
                            st.error(f"❌ {e}")
                        except Exception as e:
                            st.error(f"Error al guardar el registro: {e}")
                        
        with col_vistas:
            st.markdown("**Historial Cronológico de Tiempos**")
            if len(df_procesado) > 0:
                if st.session_state.rol in ["Head Coach", "Entrenador", "Administrador"]:
                    opciones_eliminacion = {
                        f"Edad: {row['Edad']} | Tiempo: {row['Tiempo']} | {row['Evento / Fecha']}": row['id']
                        for _, row in df_procesado.iterrows()
                    }
                    
                    seleccion_etiqueta = st.selectbox(
                        "Seleccione el registro que desea eliminar:", 
                        options=list(opciones_eliminacion.keys())
                    )
                    
                    id_del = opciones_eliminacion[seleccion_etiqueta]
                    
                    if st.button("🗑️ Eliminar Fila"):
                        supabase.table("marcas_historicas").delete().eq("id", int(id_del)).execute()
                        st.warning("Registro removido con éxito.")
                        st.rerun()
                        
                st.dataframe(df_procesado.drop(columns=["id"], errors="ignore"), use_container_width=True)

    with tab_entrenador:
        if st.session_state.rol in ["Head Coach", "Administrador"]:
            st.markdown(f"### ⚙️ Umbrales de Competencia para la Categoría")
            
            if titulo_grafico in ['25 Libre', '25 Espalda', '25 Pecho', '25 Mariposa', '100 Combinado'] or es_preinfantil:
                st.info(f"💡 **Aviso:** Las marcas de referencia para pruebas Preinfantiles ({titulo_grafico}) se calculan automáticamente basándose en las marcas mínimas de 50m de la categoría Infantil A. No se configuran manualmente en este panel para proteger la integridad de los cálculos.")
            else:
                u_cat = st.selectbox("Categoría a Modificar u Organizar:", options=["Infantil A", "Infantil B", "Juvenil A", "Juvenil B", "Máxima"])
                
                db_m_ano, db_m_panam_b, db_m_panam_a, db_m_wa_b, db_m_wa_a, db_m_wr = None, None, None, None, None, None
                try:
                    ref_dinamica = supabase.table("marcas_referencia").select("*")\
                        .eq("prueba", titulo_grafico)\
                        .eq("genero", st.session_state.nadador_seleccionado_genero)\
                        .eq("categoria", u_cat).execute()
                    if ref_dinamica.data:
                        r_det = ref_dinamica.data[0]
                        db_m_ano = float(r_det["m_ano"]) if r_det["m_ano"] is not None else None
                        db_m_panam_b = float(r_det["m_panam_b"]) if r_det["m_panam_b"] is not None else None
                        db_m_panam_a = float(r_det["m_panam_a"]) if r_det["m_panam_a"] is not None else None
                        db_m_wa_b = float(r_det["m_wa_b"]) if r_det["m_wa_b"] is not None else None
                        db_m_wa_a = float(r_det["m_wa_a"]) if r_det["m_wa_a"] is not None else None
                        db_m_wr = float(r_det["m_wr"]) if r_det["m_wr"] is not None else None
                except Exception:
                    pass

                with st.form("form_update_referencias"):
                    u_ano = st.number_input("Marca Mínima Año (seg):", value=db_m_ano if db_m_ano is not None else 0.0, disabled=(db_m_ano is None))
                    u_panamb = st.number_input("PANAM Jr - Marca B (seg):", value=db_m_panam_b if db_m_panam_b is not None else 0.0, disabled=(db_m_panam_b is None))
                    u_panama = st.number_input("PANAM Jr - Marca A (seg):", value=db_m_panam_a if db_m_panam_a is not None else 0.0, disabled=(db_m_panam_a is None))
                    u_wab = st.number_input("World Aquatics - Marca B (seg):", value=db_m_wa_b if db_m_wa_b is not None else 0.0, disabled=(db_m_wa_b is None))
                    u_waa = st.number_input("World Aquatics - Marca A (seg):", value=db_m_wa_a if db_m_wa_a is not None else 0.0, disabled=(db_m_wa_a is None))
                    u_wr = st.number_input("Récord Mundial de Estilo Absoluto:", value=db_m_wr if db_m_wr is not None else 25.0, disabled=(db_m_wr is None))
                    
                    if st.form_submit_button("⚡ Guardar Configuración de Tiempos"):
                        up_data = {}
                        if db_m_ano is not None: up_data["m_ano"] = u_ano
                        if db_m_panam_b is not None: up_data["m_panam_b"] = u_panamb
                        if db_m_panam_a is not None: up_data["m_panam_a"] = u_panama
                        if db_m_wa_b is not None: up_data["m_wa_b"] = u_wab
                        if db_m_wa_a is not None: up_data["m_wa_a"] = u_waa
                        if db_m_wr is not None: up_data["m_wr"] = u_wr
                        
                        if up_data:
                            supabase.table("marcas_referencia").upsert({
                                "prueba": titulo_grafico, "genero": st.session_state.nadador_seleccionado_genero,
                                "categoria": u_cat, **up_data
                            }, on_conflict="prueba,genero,categoria").execute()
                            st.success(f"Tiempos de referencia actualizados para {u_cat}.")
                            st.rerun()
        else:
            st.warning("🔒 Requiere credenciales de Head Coach.")
    
    with tab_asignaciones:
        if st.session_state.rol in ["Head Coach", "Administrador"]:
            st.markdown("---")
            st.subheader("📋 Panel de Gestión de Asignaciones (Exclusivo Head Coach)")
            
            try:
                # Obtener entrenadores asistentes activos
                resp_ent = supabase.table("usuarios").select("id, nombre").eq("rol", "Entrenador").eq("estatus", "Activo").execute()
                lista_entrenadores = resp_ent.data if resp_ent.data else []
                
                # Obtener todos los nadadores activos
                resp_nad = supabase.table("usuarios").select("id, nombre, fecha_nacimiento").eq("rol", "Nadador").eq("estatus", "Activo").execute()
                lista_todos_nadadores = resp_nad.data if resp_nad.data else []
                
                if lista_entrenadores and lista_todos_nadadores:
                    dict_entrenadores = {e["id"]: e["nombre"] for e in lista_entrenadores}
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("##### 👤 Asignación Individual")
                        entrenador_sel = st.selectbox("Asistente Destino:", options=list(dict_entrenadores.keys()), format_func=lambda x: dict_entrenadores[x], key="asig_ind_ent")
                        nadador_sel = st.selectbox("Nadador a asignar:", options=[n["id"] for n in lista_todos_nadadores], format_func=lambda x: next(b["nombre"] for b in lista_todos_nadadores if b["id"] == x), key="asig_ind_nad")
                        
                        if st.button("Confirmar Asignación Individual", type="primary"):
                            # 1. Eliminar cualquier vinculación previa de ese nadador
                            supabase.table("asignaciones").delete().eq("atleta_id", nadador_sel).execute()
                            # 2. Registrar nueva vinculación en la tabla asignaciones
                            supabase.table("asignaciones").insert({"entrenador_id": entrenador_sel, "atleta_id": nadador_sel}).execute()
                            
                            st.success(f"✅ Nadador asignado con éxito a {dict_entrenadores[entrenador_sel]}.")
                            st.cache_data.clear()
                            st.rerun()
                            
                    with col2:
                        st.markdown("##### 👥 Asignación por Categoría Completa")
                        entrenador_cat_sel = st.selectbox("Asistente Destino:", options=list(dict_entrenadores.keys()), format_func=lambda x: dict_entrenadores[x], key="asig_cat_ent")
                        
                        # Agrupar categorías existentes de forma dinámica basándonos en la fecha de nacimiento
                        cats_existentes = sorted(list(set([calcular_categoria_competencia(n["fecha_nacimiento"])[0] for n in lista_todos_nadadores])))
                        categoria_sel = st.selectbox("Seleccionar Categoría:", options=cats_existentes)
                        
                        if st.button("Asignar Categoría Completa"):
                            ids_categoria = []
                            for nad in lista_todos_nadadores:
                                cat_nad, _ = calcular_categoria_competencia(nad["fecha_nacimiento"])
                                if cat_nad == categoria_sel:
                                    ids_categoria.append(nad["id"])
                            
                            if ids_categoria:
                                # 1. Limpiar asignaciones previas de estos atletas específicos
                                supabase.table("asignaciones").delete().in_("atleta_id", ids_categoria).execute()
                                
                                # 2. Inserción por lotes adaptada a tus columnas id_entrenador e id_nadador
                                nuevas_asig = [{"entrenador_id": entrenador_cat_sel, "atleta_id": nid} for nid in ids_categoria]
                                supabase.table("asignaciones").insert(nuevas_asig).execute()
                                
                                st.success(f"🎉 Se asignaron {len(ids_categoria)} nadadores de la categoría **{categoria_sel}** a {dict_entrenadores[entrenador_cat_sel]}.")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.warning("No se encontraron nadadores en esta categoría.")
                else:
                    st.info("Debe contar con Entrenadores y Nadadores activos para habilitar las opciones de asignación.")
            except Exception as e:
                st.error(f"Error operando la tabla de asignaciones: {e}")
        else:
            st.warning("🔒 Requiere credenciales de Head Coach.")        
    # -------------------------------------------------------------
    # PESTAÑA: CALENDARIO ANUAL DE COMPETENCIAS
    # -------------------------------------------------------------
    with tab_calendario:
        st.markdown("### 📅 Gestión del Calendario de Competencias")
        
        temporada_actual = datetime.date.today().year
        st.markdown(f"**Competencias Programadas - Temporada {temporada_actual}**")
        
        # 1. Vista de solo lectura (Disponible para todos, incluyendo Nadadores)
        try:
            resp_comp = supabase.table("catalogo_competencias").select("*").eq("temporada", temporada_actual).order("fecha_inicio", desc=False).execute()
            if resp_comp.data:
                df_comp = pd.DataFrame(resp_comp.data)
                # Formateo de fechas para mejor lectura
                df_comp["fecha_inicio"] = pd.to_datetime(df_comp["fecha_inicio"]).dt.strftime('%d-%m-%Y')
                df_comp["fecha_fin"] = pd.to_datetime(df_comp["fecha_fin"]).dt.strftime('%d-%m-%Y')
                
                st.dataframe(
                    df_comp[["nombre_evento", "ente_rector", "categoria_evento", "fecha_inicio", "fecha_fin"]], 
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info(f"No hay competencias registradas en el catálogo para la temporada {temporada_actual}.")
        except Exception as e:
            st.error(f"Error cargando calendario: {e}")

        # 2. Controles de Edición (Restringido a Head Coach y Adminstrador)
        if st.session_state.rol in ["Head Coach", "Administrador"]:
            st.markdown("---")
            col_add, col_edit = st.columns(2)
            
            with col_add:
                st.markdown("**➕ Programar Nueva Competencia**")
                with st.form("form_add_comp", clear_on_submit=True):
                    add_temp = st.number_input("Temporada (Año):", min_value=2024, max_value=2050, value=temporada_actual, step=1)
                    add_nombre = st.text_input("Nombre del Evento:")
                    add_ente = st.selectbox("Ente Rector:", ["FEVEDA", "PANAM", "SURAM", "WA"])
                    add_cat = st.selectbox("Nivel / Categoría:", ["Nacional", "Internacional"])
                    
                    c_ini, c_fin = st.columns(2)
                    with c_ini: add_f_ini = st.date_input("Fecha Inicio:", min_value=datetime.date(2024, 1, 1))
                    with c_fin: add_f_fin = st.date_input("Fecha Fin:", min_value=datetime.date(2024, 1, 1))
                    
                    if st.form_submit_button("💾 Guardar en Catálogo"):
                        if add_nombre:
                            nueva_comp = {
                                "temporada": add_temp,
                                "nombre_evento": add_nombre,
                                "ente_rector": add_ente,
                                "categoria_evento": add_cat,
                                "fecha_inicio": add_f_ini.isoformat(),
                                "fecha_fin": add_f_fin.isoformat(),
                                "creador_id": st.session_state.usuario_id
                            }
                            supabase.table("catalogo_competencias").insert(nueva_comp).execute()
                            st.success("Competencia agregada exitosamente.")
                            st.rerun()
                        else:
                            st.error("El nombre del evento es obligatorio.")
                            
            with col_edit:
                st.markdown("**✏️ Auditar / Posponer / Suspender**")
                if resp_comp.data:
                    # Crear diccionario para el selectbox
                    dict_comps = {f"{c['nombre_evento']} ({c['fecha_inicio']})": c for c in resp_comp.data}
                    comp_seleccionada = st.selectbox("Seleccione Competencia a Modificar:", options=list(dict_comps.keys()))
                    
                    if comp_seleccionada:
                        datos_c = dict_comps[comp_seleccionada]
                        with st.form("form_edit_comp"):
                            st.caption("Modifique las fechas en caso de postergación, o agregue '(SUSPENDIDO)' al nombre si el evento se cancela.")
                            
                            edit_nombre = st.text_input("Nombre del Evento:", value=datos_c["nombre_evento"])
                            c_edit_ini, c_edit_fin = st.columns(2)
                            
                            # Manejo seguro de fechas desde la base de datos
                            val_f_ini = datetime.date.fromisoformat(datos_c["fecha_inicio"])
                            val_f_fin = datetime.date.fromisoformat(datos_c["fecha_fin"])
                            
                            with c_edit_ini: edit_f_ini = st.date_input("Nueva Fecha Inicio:", value=val_f_ini)
                            with c_edit_fin: edit_f_fin = st.date_input("Nueva Fecha Fin:", value=val_f_fin)
                            
                            if st.form_submit_button("🔄 Aplicar Correcciones"):
                                supabase.table("catalogo_competencias").update({
                                    "fecha_inicio": edit_f_ini.isoformat(),
                                    "fecha_fin": edit_f_fin.isoformat(),
                                    "nombre_evento": edit_nombre
                                }).eq("id", datos_c["id"]).execute()
                                
                                st.warning("Competencia actualizada. Los hitos de los atletas se ajustarán a estas nuevas fechas.")
                                st.rerun()
                else:
                    st.info("No hay competencias para auditar.")

    # -------------------------------------------------------------
        # 3. GENERADOR AUTOMÁTICO DE HITOS (ASIGNACIÓN DE ATLETAS)
        # -------------------------------------------------------------
        if st.session_state.rol in ["Head Coach", "Administrador"]:
            st.markdown("---")
            st.markdown("### 🎯 Generación de Hitos y Auditoría de Elegibilidad")
            st.caption("Seleccione una competencia programada para evaluar a la nómina de nadadores activos y generar sus hitos de seguimiento.")
            
            if resp_comp.data:
                comp_inscripcion = st.selectbox("Competencia a procesar:", options=list(dict_comps.keys()), key="sel_ins")
                datos_comp_ins = dict_comps[comp_inscripcion]
                
                if st.button("🚀 Procesar Nómina y Generar Hitos"):
                    with st.spinner("Evaluando normativas y generando expedientes..."):
                        try:
                            # 1. Obtener la nómina de atletas activos
                            resp_atletas = supabase.table("usuarios").select("id, nombre, fecha_nacimiento").eq("rol", "Nadador").eq("estatus", "Activo").execute()
                            atletas = resp_atletas.data
                            
                            if not atletas:
                                st.warning("No hay atletas activos en el sistema para procesar.")
                            else:
                                temporada_evento = datos_comp_ins["temporada"]
                                ente = datos_comp_ins["ente_rector"]
                                comp_id = datos_comp_ins["id"]
                                
                                contadores = {"elegibles": 0, "ineligibles": 0, "omitidos": 0}
                                
                                for atleta in atletas:
                                    atleta_id = atleta["id"]
                                    fnac = atleta["fecha_nacimiento"]
                                    
                                    # Verificar si el hito ya existe para no duplicar
                                    check_exist = supabase.table("historial_hitos").select("id").eq("usuario_id", atleta_id).eq("competencia_id", comp_id).execute()
                                    if check_exist.data:
                                        contadores["omitidos"] += 1
                                        continue
                                        
                                    if not fnac:
                                        estado_elegible = False
                                        motivo = "Perfil incompleto: Falta fecha de nacimiento."
                                    else:
                                        # Llamada a la función que agregamos al inicio del script
                                        edad_tecnica = calcular_edad_tecnica_al_31_dic(fnac, temporada_evento)
                                        estado_elegible, motivo = evaluar_elegibilidad_internacional(edad_tecnica, ente)
                                    
                                    # Calcular fecha para la alerta (15 días antes)
                                    f_alerta = calcular_fecha_alerta(datos_comp_ins["fecha_inicio"], 15)
                                    
                                    # Crear el registro pivote en historial_hitos
                                    nuevo_hito = {
                                        "usuario_id": atleta_id,
                                        "competencia_id": comp_id,
                                        "temporada_auditada": temporada_evento,
                                        "elegible": estado_elegible,
                                        "motivo_ineligibilidad": motivo if not estado_elegible else None,
                                        "estado_cumplimiento": "Pendiente",
                                        "fecha_alerta": f_alerta.isoformat()
                                    }
                                    
                                    supabase.table("historial_hitos").insert(nuevo_hito).execute()
                                    
                                    if estado_elegible:
                                        contadores["elegibles"] += 1
                                    else:
                                        contadores["ineligibles"] += 1
                                        
                                st.success(f"✅ Proceso completado con éxito.")
                                st.info(f"📊 **Resumen:** {contadores['elegibles']} atletas asignados (Pendientes) | {contadores['ineligibles']} descartados por normativa | {contadores['omitidos']} ya estaban registrados.")
                                
                        except Exception as e:
                            st.error(f"Error durante la generación de hitos: {e}")
        else:
            st.warning("🔒 Requiere credenciales de Head Coach.")
    with tab_admin:
        if st.session_state.rol == "Administrador":
            st.markdown("### 🛡️ Consola de Control de Usuarios e Integridad de Datos")
            try:
                resp_usuarios = supabase.table("usuarios").select("id, nombre, usuario, email, rol, genero, estatus, fecha_nacimiento").execute()
                if resp_usuarios.data:
                    df_usr = pd.DataFrame(resp_usuarios.data)
                    st.dataframe(df_usr, use_container_width=True)
                    
                    st.markdown("**Editar Perfil de Usuario**")
                    c_sel, c_rol, c_est, c_gen = st.columns(4)
                    with c_sel:
                        id_mod = st.selectbox("ID Usuario:", options=df_usr["id"].tolist())
                        user_actual = df_usr[df_usr["id"] == id_mod].iloc[0]
                    with c_rol:
                        nuevo_rol_user = st.selectbox("Rol:", options=["Nadador", "Head Coach", "Entrenador", "Administrador"], index=["Nadador", "Head Coach", "Entrenador", "Administrador"].index(user_actual["rol"]))
                    with c_est:
                        nuevo_est_user = st.selectbox("Estatus:", options=["Activo", "Pendiente", "Suspendido", "Bloqueado"], index=["Activo", "Pendiente", "Suspendido", "Bloqueado"].index(user_actual["estatus"]))
                    
                    campos_deshabilitados = nuevo_rol_user in ["Head Coach", "Entrenador", "Administrador"]
                    
                    with c_gen:
                        gen_inicial = user_actual["genero"] if user_actual["genero"] in ["F", "M"] else "F"
                        nuevo_gen_user = st.selectbox("Género:", options=["F", "M"], index=["F", "M"].index(gen_inicial), disabled=campos_deshabilitados)
                    
                    f_nac_inicial = datetime.date.fromisoformat(str(user_actual["fecha_nacimiento"])) if user_actual["fecha_nacimiento"] else datetime.date.today()
                    nueva_f_nac_admin = st.date_input("Corregir Fecha Nacimiento:", value=f_nac_inicial, disabled=campos_deshabilitados)
                    
                    if st.button("⚠️ Forzar Cambios de Perfil"):
                        if user_actual.get("estatus") == "Pendiente" and nuevo_est_user == "Activo":
                            enviar_email(
                                "¡Tu cuenta ha sido activada!", 
                                f"Hola {user_actual['nombre']}, tu cuenta ya está activa y puedes acceder al sistema.", 
                                user_actual["email"]
                            )

                        datos_update = {"rol": nuevo_rol_user, "estatus": nuevo_est_user}
                        if campos_deshabilitados:
                            datos_update["genero"] = None
                            datos_update["fecha_nacimiento"] = None
                        else:
                            datos_update["genero"] = nuevo_gen_user
                            datos_update["fecha_nacimiento"] = nueva_f_nac_admin.isoformat()
                            
                        supabase.table("usuarios").update(datos_update).eq("id", int(id_mod)).execute()
                        st.success("Cambios aplicados con éxito.")
                        st.rerun()
            except Exception as e:
                st.error(f"Error en panel de control: {e}")
            st.markdown("### 💾 Centro de Respaldos y Salvaguarda Local")
            st.info("Descarga copias de seguridad directas desde Supabase en formato CSV para resguardo local o auditorías.")
            
            # Lista oficial de las tablas del Core
            tablas_sistema = ["usuarios", "marcas_historicas", "marcas_referencia", "asignaciones", "catalogo_competencias", "bitacora_entrenamientos", "historial_hitos"]
            
            opcion_backup = st.selectbox("Seleccione el alcance del respaldo:", ["Tabla Individual", "Base de Datos Completa (ZIP)"])
            
            if opcion_backup == "Tabla Individual":
                tabla_sel = st.selectbox("Seleccione la tabla a respaldar:", tablas_sistema)
                
                try:
                    res_backup = supabase.table(tabla_sel).select("*").execute()
                    if res_backup.data:
                        df_backup = pd.DataFrame(res_backup.data)
                        csv_bytes = df_backup.to_csv(index=False).encode('utf-8-sig')
                        
                        st.download_button(
                            label=f"📥 Descargar Tabla '{tabla_sel}' (CSV)",
                            data=csv_bytes,
                            file_name=f"backup_{tabla_sel}_{datetime.date.today().isoformat()}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.warning("La tabla seleccionada se encuentra vacía.")
                except Exception as e:
                    st.error(f"Error al conectar con el servidor de réplica: {e}")
            
            else:
                # =============================================================================
                # LÓGICA MASTER COMPLETADA: COMPRESIÓN EN MEMORIA (ZIP)
                # =============================================================================
                
                with st.spinner("Generando compresión de todas las estructuras del club..."):
                    try:
                        # 1. Crear un búfer de bytes en memoria para el archivo ZIP
                        buffer_zip = io.BytesIO()
                        
                        # 2. Abrir el contenedor ZIP en modo escritura
                        with zipfile.ZipFile(buffer_zip, "w", zipfile.ZIP_DEFLATED) as zip_file:
                            tablas_vacias = []
                            
                            # Recorrer cada tabla del sistema para extraerla individualmente
                            for tabla in tablas_sistema:
                                res_table = supabase.table(tabla).select("*").execute()
                                
                                if res_table.data:
                                    df_table = pd.DataFrame(res_table.data)
                                    # Convertir la tabla a CSV crudo en formato string
                                    csv_string = df_table.to_csv(index=False, encoding='utf-8-sig')
                                    # Escribir el string directamente como un archivo independiente dentro del ZIP
                                    zip_file.writestr(f"backup_{tabla}.csv", csv_string)
                                else:
                                    tablas_vacias.append(tabla)
                        
                        # 3. Mover el puntero del búfer al principio para que Streamlit pueda leerlo completo
                        buffer_zip.seek(0)
                        
                        # Mostrar advertencias si hubo tablas que no aportaron datos
                        if tablas_vacias:
                            st.caption(f"⚠️ Nota: Las tablas {tablas_vacias} no se incluyeron por estar vacías en Supabase.")
                        
                        # 4. Renderizar el botón de descarga del ZIP maestro listo e instantáneo
                        st.success("✅ Respaldo total empaquetado de forma exitosa.")
                        st.download_button(
                            label="📥 Descargar Base de Datos Completa (ZIP)",
                            data=buffer_zip.getvalue(),
                            file_name=f"MASTER_BACKUP_CLUB_{datetime.date.today().isoformat()}.zip",
                            mime="application/zip",
                            use_container_width=True
                        )
                        
                    except Exception as e:
                        st.error(f"Error crítico durante el empaquetado del Master Backup: {e}")
        else:
            st.warning("🔒 Acceso restringido al Administrador.")
        
# -------------------------------------------------------------
    # PESTAÑA: PIZARRA DE ENTRENAMIENTO DIARIO (WIDGETS GARANTIZADOS)
    # -------------------------------------------------------------
    with tab_pizarra:
        if st.session_state.rol in ["Head Coach", "Entrenador", "Administrador"]:
            st.markdown("### 📋 Estructura del Entrenamiento de Hoy")
            st.caption("Diseña la sesión agregando bloques. Al finalizar, controla la asistencia para imputar la carga individual.")
            
            # 1. Inicializar la pizarra en la memoria de sesión si no existe
            if "pizarra_entrenamiento" not in st.session_state:
                st.session_state.pizarra_entrenamiento = []

            # 2. Formulario de ingreso rápido de series
            with st.expander("➕ Añadir nueva serie al entrenamiento", expanded=True):
                c_rep, c_dist, c_est = st.columns(3)
                with c_rep:
                    repeticiones = st.number_input("Repeticiones", min_value=1, value=1, step=1, key="piz_rep")
                with c_dist:
                    distancia = st.number_input("Distancia (m)", min_value=15, value=100, step=25, key="piz_dist")
                with c_est:
                    estilo = st.selectbox("Estilo / Foco", ["Libre", "Espalda", "Pecho", "Mariposa", "Combinado", "Piernas", "Brazos", "Técnica / Drills", "Afloje"], key="piz_est")
                    
                c_int, c_imp, c_not = st.columns(3)
                with c_int:
                    intensidad = st.selectbox("Ritmo / Intensidad RPE", ["Suave (Aeróbico Ligero 3-4)", "Medio (Aeróbico Medio 5-6)", "Sostenido (Umbral 7-8)", "Ritmo de Competencia (Anaeróbico 9-10)", "Sprint (Máximo 10-11)"], key="piz_int")
                with c_imp:
                    implementos = st.multiselect("Implementos", ["Aletas", "Paletas", "Tabla", "Pullbuoy", "Snorkel", "Paracaídas", "Ligas"], key="piz_imp")
                with c_not:
                    notas = st.text_input("Instrucciones breves (Opcional)", placeholder="Ej: c/1:30 nado y descanso, Respiración c/3, Descanso 20s", key="piz_not")

                if st.button("Añadir a la sesión", use_container_width=True, key="btn_add_piz"):
                    bloque = {
                        "reps": repeticiones,
                        "dist": distancia,
                        "estilo": estilo,
                        "intensidad": intensidad,
                        "implementos": implementos,
                        "notas": notas
                    }
                    st.session_state.pizarra_entrenamiento.append(bloque)
                    st.rerun()

            # Visualización del entrenamiento acumulado
            if st.session_state.pizarra_entrenamiento:
                st.markdown("---")
                volumen_total = 0
                texto_exportacion = f"🏊‍♂️ *Entrenamiento del Día*\n📅 Fecha: {datetime.date.today().strftime('%d/%m/%Y')}\n\n"
                
                for i, blk in enumerate(st.session_state.pizarra_entrenamiento):
                    subtotal = blk['reps'] * blk['dist']
                    volumen_total += subtotal
                    txt_impl = f" [{', '.join(blk['implementos'])}]" if blk['implementos'] else ""
                    txt_not = f" - _{blk['notas']}_" if blk['notas'] else ""
                    texto_exportacion += f"• {blk['reps']} x {blk['dist']}m {blk['estilo']} | {blk['intensidad']}{txt_impl}{txt_not}\n"

                st.info(texto_exportacion)
                st.metric("Volumen Total de la Sesión", f"{volumen_total} metros")
                
                c_undo, c_clear = st.columns(2)
                with c_undo:
                    if st.button("⏪ Deshacer último bloque", use_container_width=True, key="piz_btn_undo"):
                        st.session_state.pizarra_entrenamiento.pop()
                        st.rerun()
                with c_clear:
                    if st.button("🗑️ Limpiar pizarra completa", use_container_width=True, key="piz_btn_clear"):
                        st.session_state.pizarra_entrenamiento = []
                        st.rerun()

                # =============================================================================
                # 3. SECCIÓN DE SEGMENTACIÓN (WIDGETS FORZADOS A APARECER EN PANTALLA)
                # =============================================================================
                st.markdown("---")
                st.markdown("### 🔍 Segmentación de Destinatarios (Asistencia/Carga)")
                
                # Fila de botones de opción horizontales (Disposición de tu foto)
                col_foto1, col_foto2 = st.columns(2)
                with col_foto1:
                    filtro_genero = st.radio(
                        "Segmentar por Género:", 
                        options=["Todos", "Femenino (F)", "Masculino (M)"],
                        horizontal=True,
                        key="piz_radio_genero_idx"
                    )
                with col_foto2:
                    tipo_filtro = st.radio(
                        "Segmentar adicionalmente por:", 
                        options=["Todos los Atletas", "Categoría Etaria", "Atletas Específicos"],
                        horizontal=True,
                        key="piz_radio_tipo_idx"
                    )

# RESOLUCIÓN DEL CLIENTE DE SUPABASE (Busca la variable global directa de tu app)
                ctx_supabase = None
                try:
                    ctx_supabase = supabase
                except NameError:
                    ctx_supabase = st.session_state.get("supabase_client")

                atletas_pool = []
                if ctx_supabase:
                    try:
                        # =============================================================================
                        # FILTRADO DE SEGURIDAD CONTRA LEAKS DE ACCESO
                        # =============================================================================
                        es_entrenador = st.session_state.get("rol") == "Entrenador"
                        entrenador_id = st.session_state.get("usuario_id") # ID único del entrenador logueado
                        
                        permitir_consulta = True
                        ids_autorizados = []

                        # Si es Entrenador, restringimos el pool basándonos en la tabla de asignaciones
                        if es_entrenador:
                            if entrenador_id:
                                resp_asig = ctx_supabase.table("asignaciones").select("atleta_id").eq("entrenador_id", entrenador_id).execute()
                                if resp_asig.data:
                                    ids_autorizados = [reg["atleta_id"] for reg in resp_asig.data]
                                
                                # Si el entrenador no tiene atletas asignados, vaciamos el pool preventivamente
                                if not ids_autorizados:
                                    permitir_consulta = False
                            else:
                                st.error("❌ Error de sesión: No se encontró el ID del entrenador.")
                                permitir_consulta = False

                        if permitir_consulta:
                            # Construimos la query base para Nadadores Activos
                            query_atletas = ctx_supabase.table("usuarios").select("id, nombre, email, genero, fecha_nacimiento").eq("rol", "Nadador").eq("estatus", "Activo")
                            
                            # Si es Entrenador, aplicamos el filtro estricto de inclusión
                            if es_entrenador:
                                query_atletas = query_atletas.in_("id", ids_autorizados)
                                
                            resp_sb = query_atletas.execute()
                            
                            if resp_sb.data:
                                atletas_pool = resp_sb.data
                        else:
                            st.warning("⚠️ No tienes atletas asignados en tu perfil de Entrenador.")

                    except Exception as e:
                        st.error(f"Error al cargar nómina desde Supabase: {e}")

                # Filtrar la lista local por el género seleccionado
                if filtro_genero == "Femenino (F)":
                    atletas_pool = [a for a in atletas_pool if a.get("genero") == "F"]
                elif filtro_genero == "Masculino (M)":
                    atletas_pool = [a for a in atletas_pool if a.get("genero") == "M"]

                # Mapear colecciones de datos seguras para los selectores
                categorias_disponibles = sorted(list(set([
                    calcular_categoria_competencia(a["fecha_nacimiento"])[0] 
                    for a in atletas_pool if a.get("fecha_nacimiento")
                ]))) if atletas_pool else []

                dict_nom = {a["id"]: a["nombre"] for a in atletas_pool} if atletas_pool else {}
                atletas_finales = []

                # --- DESPLEGABLES CON RENDERIZADO INCONDICIONAL ---
                if tipo_filtro == "Categoría Etaria":
                    cat_sel = st.selectbox(
                        "Seleccione la Categoría Etaria:", 
                        options=categorias_disponibles if categorias_disponibles else ["Cargando categorías activos..."], 
                        key="piz_selectbox_cat"
                    )
                    if categorias_disponibles:
                        atletas_finales = [
                            a for a in atletas_pool 
                            if calcular_categoria_competencia(a["fecha_nacimiento"])[0] == cat_sel
                        ]
                        
                elif tipo_filtro == "Atletas Específicos":
                    ids_sel = st.multiselect(
                        "Seleccione Nadador(es) Individual(es):", 
                        options=list(dict_nom.keys()), 
                        format_func=lambda x: dict_nom.get(x, "Cargando atleta..."),
                        key="piz_multiselect_atletas"
                    )
                    if ids_sel:
                        atletas_finales = [a for a in atletas_pool if a["id"] in ids_sel]
                else:
                    # Todos los Atletas del género seleccionado
                    atletas_finales = pool_actual = atletas_pool

                # Alertas visuales dinámicas de control
                if tipo_filtro == "Atletas Específicos" and not atletas_finales:
                    st.info("💡 Despliega el selector de arriba y marca al menos un nadador para habilitar el botón de consolidación.")
                else:
                    st.success(f"🎯 Grupo confirmado para imputación: {len(atletas_finales)} atleta(s).")

# =# =============================================================================
                # 5. CENTRO DE DIFUSIÓN Y EXPORTACIÓN DE LA JORNADA (PIZARRA)
                # =============================================================================
                st.markdown("---")
                st.markdown("### 📢 Centro de Difusión y Publicación de la Pizarra")
                st.caption("Genera el formato de comunicación para enviar a los atletas por canales digitales o preparar la hoja impresa para la piscina.")

                # 🛠️ EXTRACCIÓN BLINDADA DESDE EL STATE PARA EVITAR NAMEERROR
                import datetime
                fecha_difusion = st.session_state.get("piz_date_input_save", datetime.date.today())
                carril_difusion = st.session_state.get("piz_carril_input_save", "")
                
                # Calcular el volumen de forma independiente en tiempo real
                volumen_total_difusion = 0
                if "pizarra_entrenamiento" in st.session_state and st.session_state.pizarra_entrenamiento:
                    volumen_total_difusion = sum(blk['reps'] * blk['dist'] for blk in st.session_state.pizarra_entrenamiento)

                # 1. Construir el string de texto limpio del entrenamiento
                texto_entrenamiento = f"🏊‍♂️ *PLAN DE ENTRENAMIENTO DEL DÍA* - Fecha: {fecha_difusion}\n"
                if carril_difusion:
                    texto_entrenamiento += f"📍 *Grupo/Carril:* {carril_difusion}\n"
                texto_entrenamiento += f"📊 *Volumen Total:* {volumen_total_difusion:,} metros\n\n"
                texto_entrenamiento += "📝 *Desglose del Menú:*\n"
                
                if "pizarra_entrenamiento" in st.session_state and st.session_state.pizarra_entrenamiento:
                    for idx, blk in enumerate(st.session_state.pizarra_entrenamiento, 1):
                        impls = f" c/ {', '.join(blk['implementos'])}" if blk['implementos'] else ""
                        texto_entrenamiento += f"• {blk['reps']}x{blk['dist']}m {blk['estilo']} | {blk['intensidad']}{impls}\n"
                else:
                    texto_entrenamiento += f"• No hay bloques cargados en la pizarra actualmente.\n"

                # 2. Codificar para URLs de comunicación
                import urllib.parse
                texto_url = urllib.parse.quote(texto_entrenamiento)
                
                link_whatsapp = f"https://api.whatsapp.com/send?text={texto_url}"
                link_correo = f"mailto:?subject=Plan%20de%20Entrenamiento%20{fecha_difusion}&body={texto_url}"

                # 3. Renderizar botones de acción en filas limpias
                c_com1, c_com2, c_com3 = st.columns(3)
                with c_com1:
                    st.link_button("🟢 Enviar por WhatsApp", link_whatsapp, use_container_width=True)
                with c_com2:
                    st.link_button("📩 Enviar por Correo", link_correo, use_container_width=True)
                with c_com3:
                    # Genera la descarga física remota limpiando el markdown
                    st.download_button(
                        label="🖨️ Descargar Hoja de Carril (TXT)",
                        data=texto_entrenamiento.replace("*", ""), 
                        file_name=f"pizarra_{fecha_difusion}_{str(carril_difusion).replace(' ', '_') if carril_difusion else 'general'}.txt",
                        mime="text/plain",
                        use_container_width=True
                    )

                # Vista previa colapsable
                with st.expander("👀 Ver vista previa del mensaje a enviar"):
                    st.code(texto_entrenamiento, language="markdown")
                
# =============================================================================
                # 4. BLOQUE DE CONSOLIDACIÓN FINAL (REGISTRO HISTÓRICO)
                # =============================================================================
                st.markdown("#### 💾 Consolidar y Registrar Jornada")
                c_fecha, c_carril = st.columns(2)
                with c_fecha:
                    fecha_jornada = st.date_input("Fecha de la sesión:", datetime.date.today(), key="piz_date_input_save")
                with c_carril:
                    identificador_carril = st.text_input("Identificador / Carril (Opcional):", placeholder="Ej: Carril 3, Grupo Avanzado", key="piz_carril_input_save")

                if st.button("💾 Consolidar Metros e Intensidades por Atleta", type="primary", use_container_width=True, key="btn_consolidar_piz"):
                        # Procesamiento de desgloses
                        desglose_estilos = {}
                        for blk in st.session_state.pizarra_entrenamiento:
                            est = blk['estilo']
                            mts = blk['reps'] * blk['dist']
                            desglose_estilos[est] = desglose_estilos.get(est, 0) + mts
                            
                        desglose_intensidad = {}
                        for blk in st.session_state.pizarra_entrenamiento:
                            inte = blk['intensidad']
                            mts = blk['reps'] * blk['dist']
                            desglose_intensidad[inte] = desglose_intensidad.get(inte, 0) + mts

                        # Lista de diccionarios para inserción masiva
                        registros_supabase = []
                        for at_obj in atletas_finales:
                            fila = {
                                "fecha": str(fecha_jornada),
                                "atleta_id": at_obj.get("id"),
                                "identificador_carril": identificador_carril if identificador_carril else "Carril Único",
                                "metros_totales": int(volumen_total),
                                "desglose_estilos": desglose_estilos,
                                "desglose_intensidad": desglose_intensidad,
                                "implementos_usados": list(set([imp for blk in st.session_state.pizarra_entrenamiento for imp in blk['implementos']]))
                            }
                            registros_supabase.append(fila)

                        # Inserción utilizando el cliente unificado de la Sección 3
                        if registros_supabase:
                            try:
                                # CAMBIO AQUÍ: Usamos directo 'ctx_supabase' que ya sabemos que funciona
                                if ctx_supabase:
                                    ctx_supabase.table("bitacora_entrenamientos").insert(registros_supabase).execute()
                                    
                                    st.success(f"💥 ¡Base de datos actualizada! Se grabaron con éxito las cargas individuales para los {len(registros_supabase)} atleta(s) en Supabase.")
                                    st.balloons()
                                else:
                                    st.error("Error: El cliente de Supabase no pudo ser detectado en el entorno.")
                            except Exception as e:
                                st.error(f"Error crítico al escribir en Supabase: {e}")
                        else:
                            st.warning("⚠️ No hay atletas seleccionados en el grupo para consolidar.")
              
        else:
            st.warning("🔒 Sección restringida al equipo técnico.")

# -------------------------------------------------------------
# PESTAÑA: REPORTES Y RENDIMIENTO HISTÓRICO (RECONFIGURADA)
# -------------------------------------------------------------
with tab_reportes:
    if st.session_state.rol in ["Head Coach", "Entrenador", "Administrador"]:        
        st.markdown("### 📊 Panel de Control y Análisis de Carga")
        st.caption("Filtra la nómina de la misma forma que en la pizarra y define la ventana temporal para evaluar el volumen acumulado y el modelo matemático de Bannister.")

        # =============================================================================
        # 1. TEMPORALIDAD DE LOS REPORTES (MANEJO DE VENTANAS CRÍTICAS EXTENDIDAS)
        # =============================================================================
        opciones_tiempo = {
            "7 días (Última semana)": 7,
            "28 días (Ciclo Corto)": 28,
            "30 días (Mensual)": 30,
            "42 días (Carga Crónica - CTL)": 42,
            "90 días (Macrociclo Trimestral)": 90,
            "180 días (Semestral)": 180,
            "365 días (Anual)": 365,
            "Total Histórico": None
        }
        
        ventana_sel = st.selectbox(
            "⏳ Ventana Temporal de Análisis:",
            options=list(opciones_tiempo.keys()),
            index=3,  # Defecto en 42 días por su relevancia científica
            key="rep_selectbox_temporalidad"
        )
        
        dias_atras = opciones_tiempo[ventana_sel]
        fecha_fin_rep = datetime.date.today()
    
        if dias_atras:
            fecha_limite = fecha_fin_rep - datetime.timedelta(days=dias_atras)
            rango_fechas_completo = pd.date_range(start=fecha_limite + datetime.timedelta(days=1), end=fecha_fin_rep).date
        else:
            fecha_limite = None
            rango_fechas_completo = None

        st.markdown("---")

        # =============================================================================
        # 2. SECCIÓN DE SEGMENTACIÓN CON FILTRADO DE SEGURIDAD ANTILEAK
        # =============================================================================
        st.markdown("### 🔍 Segmentación de Destinatarios (Filtros Activos)")
        
        col_rep1, col_rep2 = st.columns(2)
        with col_rep1:
            filtro_genero_rep = st.radio(
                "Segmentar por Género:", 
                options=["Todos", "Femenino (F)", "Masculino (M)"],
                horizontal=True,
                key="rep_radio_genero_idx"
            )
        with col_rep2:
            tipo_filtro_rep = st.radio(
                "Segmentar adicionalmente por:", 
                options=["Todos los Atletas", "Categoría Etaria", "Atletas Específicos"],
                horizontal=True,
                key="rep_radio_tipo_idx"
            )

        # Resolución del Cliente de Supabase
        ctx_supabase_rep = None
        try:
            ctx_supabase_rep = supabase
        except NameError:
            ctx_supabase_rep = st.session_state.get("supabase_client")

        atletas_pool_rep = []
        if ctx_supabase_rep:
            try:
                # ---------------------------------------------------------------------
                # CONTROL DE ACCESO PARA PARAMETRIZACIÓN DE ENTRENADORES
                # ---------------------------------------------------------------------
                es_entrenador_rep = st.session_state.get("rol") == "Entrenador"
                entrenador_id_rep = st.session_state.get("usuario_id")
                
                permitir_consulta_rep = True
                ids_autorizados_rep = []

                if es_entrenador_rep:
                    if entrenador_id_rep:
                        # Extraemos los atletas asignados al entrenador logueado
                        resp_asig_rep = ctx_supabase_rep.table("asignaciones").select("atleta_id").eq("entrenador_id", entrenador_id_rep).execute()
                        if resp_asig_rep.data:
                            ids_autorizados_rep = [reg["atleta_id"] for reg in resp_asig_rep.data]
                        
                        # Cortocircuito seguro si el pool del entrenador está vacío
                        if not ids_autorizados_rep:
                            permitir_consulta_rep = False
                    else:
                        st.error("❌ Error de sesión: No se detectó ID único de Entrenador.")
                        permitir_consulta_rep = False

                if permitir_consulta_rep:
                    # Query base para Nadadores Activos
                    query_atletas_rep = ctx_supabase_rep.table("usuarios").select("id, nombre, email, genero, fecha_nacimiento").eq("rol", "Nadador").eq("estatus", "Activo")
                    
                    # Si es Entrenador, inyectamos la restricción restrictiva IN
                    if es_entrenador_rep:
                        query_atletas_rep = query_atletas_rep.in_("id", ids_autorizados_rep)
                        
                    resp_sb = query_atletas_rep.execute()
                    if resp_sb.data:
                        atletas_pool_rep = resp_sb.data
                else:
                    st.warning("⚠️ No posees atletas asignados en este momento bajo tu perfil de Entrenador.")

            except Exception as e:
                st.error(f"Error al cargar nómina para reportes: {e}")

        # Aplicar filtros estables de género
        if filtro_genero_rep == "Femenino (F)":
            atletas_pool_rep = [a for a in atletas_pool_rep if a.get("genero") == "F"]
        elif filtro_genero_rep == "Masculino (M)":
            atletas_pool_rep = [a for a in atletas_pool_rep if a.get("genero") == "M"]

        # De aquí hacia abajo se mantiene tu lógica exacta...
        categorias_disponibles_rep = sorted(list(set([
            calcular_categoria_competencia(a["fecha_nacimiento"])[0] 
            for a in atletas_pool_rep if a.get("fecha_nacimiento")
        ]))) if atletas_pool_rep else []

        dict_nom_rep = {a["id"]: a["nombre"] for a in atletas_pool_rep} if atletas_pool_rep else {}
        atletas_finales_rep = []

        if tipo_filtro_rep == "Categoría Etaria":
            cat_sel_rep = st.selectbox(
                "Seleccione la Categoría Etaria:", 
                options=categorias_disponibles_rep if sorted(categorias_disponibles_rep) else ["Cargando categorías..."], 
                key="rep_selectbox_cat"
            )
            if sorted(categorias_disponibles_rep):
                atletas_finales_rep = [
                    a for a in atletas_pool_rep 
                    if calcular_categoria_competencia(a["fecha_nacimiento"])[0] == cat_sel_rep
                ]
        elif tipo_filtro_rep == "Atletas Específicos":
            ids_sel_rep = st.multiselect(
                "Seleccione Nadador(es) Individual(es):", 
                options=list(dict_nom_rep.keys()), 
                format_func=lambda x: dict_nom_rep.get(x, "Cargando atleta..."),
                key="rep_multiselect_atletas"
            )
            if ids_sel_rep:
                atletas_finales_rep = [a for a in atletas_pool_rep if a["id"] in ids_sel_rep]
        else:
            atletas_finales_rep = atletas_pool_rep

        if not atletas_finales_rep:
            st.info("💡 Selecciona atletas o categorías válidas para procesar el reporte.")
        else:
            st.success(f"🎯 Analizando métricas de {len(atletas_finales_rep)} atleta(s) en la ventana seleccionada.")
            st.markdown("---")

            # =============================================================================
            # 3. CONSOLIDACIÓN COLECTIVA (ESTILOS E INTENSIDADES DESDE JSONB)
            # =============================================================================
            ids_interes = [at["id"] for at in atletas_finales_rep]
   
            with st.spinner("Compilando históricos e intensidades..."):
                try:
                    query_rep = ctx_supabase_rep.table("bitacora_entrenamientos").select("*").in_("atleta_id", ids_interes)
                    if fecha_limite:
                        query_rep = query_rep.gte("fecha", str(fecha_limite))
                    
                    data_historica = query_rep.execute()
                    records = data_historica.data if data_historica else []
                    
                    if not records:
                        st.warning(f"📭 No se encontraron registros de entrenamiento grabados para este grupo.")
                    else:
                        # Filtrar estrictamente hasta el día de hoy para los análisis continuos
                        records_hasta_hoy = []
                        for r in records:
                            if r.get("fecha"):
                                f_rec = datetime.datetime.strptime(r["fecha"], "%Y-%m-%d").date() if isinstance(r["fecha"], str) else r["fecha"]
                                if f_rec <= fecha_fin_rep:
                                    records_hasta_hoy.append(r)

                        # El volumen acumulado macro refleja exactamente lo que se está graficando
                        volumen_acumulado_grupo = sum([r.get("metros_totales", 0) for r in records_hasta_hoy])
                        st.metric(label="🏊‍♂️ Volumen Total Imputado (Grupo Filtrado)", value=f"{volumen_acumulado_grupo:,} metros")
                        
                        global_estilos = {}
                        global_intensidades = {}
                        
                        for r in records_hasta_hoy:
                            estilos_dict = r.get("desglose_estilos") or {}
                            for est, mts in estilos_dict.items():
                                global_estilos[est] = global_estilos.get(est, 0) + mts
                            
                            int_dict = r.get("desglose_intensidad") or {}
                            for inten, mts in int_dict.items():
                                global_intensidades[inten] = global_intensidades.get(inten, 0) + mts
                        
                        # =============================================================================
                        # MOTOR GRÁFICO COMBINADO (ÁREAS ACUMULADAS) Y MATRIZ DE AUDITORÍA
                        # =============================================================================
                        st.markdown("---")
                        st.markdown("#### 🏊‍♂️ Evolución y Desglose de Volúmenes Diarios del Grupo")
                        st.caption("Serie de tiempo continua del colectivo hasta el día de hoy. Áreas: volumen total acumulado y distribución por Estilos (Eje Izquierdo). Líneas: tendencias por Intensidad con marcadores y estilos diferenciados (Eje Derecho).")

                        estilos_lista = ["Libre", "Espalda", "Pecho", "Mariposa", "Combinado", "Otros"]
                        intensidades_lista = ["Aeróbico Ligero", "Aeróbico Medio", "Umbral", "Anaeróbico"]
                        
                        columnas_vol = ["Fecha"] + estilos_lista + intensidades_lista + ["Total Día"]
                        matriz_volumen = []
                        
                        if rango_fechas_completo is None:
                            fechas_instancias = []
                            for r in records_hasta_hoy:
                                if r.get("fecha"):
                                    fechas_instancias.append(datetime.datetime.strptime(r["fecha"], "%Y-%m-%d").date())
                            if fechas_instancias:
                                rango_analisis = pd.date_range(start=min(fechas_instancias), end=max(fechas_instancias)).date
                            else:
                                rango_analisis = [datetime.date.today()]
                        else:
                            rango_analisis = rango_fechas_completo

                        # Construcción de la matriz estructurada día por día
                        for f in rango_analisis:
                            dia_recs = [r for r in records_hasta_hoy if (datetime.datetime.strptime(r["fecha"], "%Y-%m-%d").date() if isinstance(r["fecha"], str) else r["fecha"]) == f]
                            row_vol = {col: 0 for col in columnas_vol}
                            row_vol["Fecha"] = f
                            
                            for r in dia_recs:
                                dict_est = r.get("desglose_estilos") or {}
                                for k_est, v_m in dict_est.items():
                                    target_est = k_est if k_est in estilos_lista else "Otros"
                                    row_vol[target_est] += v_m
                                    row_vol["Total Día"] += v_m
                    
                                dict_int = r.get("desglose_intensity") or r.get("desglose_intensidad") or {}
                                for k_int, v_m in dict_int.items():
                                    target_int = "Aeróbico Ligero"
                                    if "Medio" in k_int: target_int = "Aeróbico Medio"
                                    elif "Umbral" in k_int or "Sostenido" in k_int: target_int = "Umbral"
                                    elif "Sprint" in k_int or "Anaeróbico" in k_int: target_int = "Anaeróbico"
                                    row_vol[target_int] += v_m
                            
                            matriz_volumen.append(row_vol)
                            
                        df_vol_diario = pd.DataFrame(matriz_volumen)
                        df_vol_diario = df_vol_diario.sort_values("Fecha").reset_index(drop=True)

                        # RENDIMIENTO DEL LIENZO CON GRÁFICO DE ÁREAS ACUMULADAS
                        fig_vol, ax1 = plt.subplots(figsize=(8.5, 3.8))
                        fechas_str = [f.strftime("%d/%m") for f in df_vol_diario["Fecha"]]
                        
                        # Preparar los datos vectoriales para las áreas acumulativas por estilo
                        y_estilos = [df_vol_diario[est].values for est in estilos_lista]
                        colores_estilos = ["#2ecc71", "#3498db", "#9b59b6", "#e67e22", "#f1c40f", "#95a5a6"]
                        
                        # Eje 1: Renderizado de Áreas Acumuladas
                        ax1.stackplot(
                            fechas_str, 
                            *y_estilos, 
                            labels=[f"Estilo: {est}" for est in estilos_lista], 
                            colors=colores_estilos, 
                            alpha=0.65
                        )
                            
                        ax1.set_xlabel("Días del Calendario (Serie de Tiempo Continua)", fontsize=7)
                        ax1.set_ylabel("Volumen Acumulado por Estilos (Metros)", fontsize=9)
                        ax1.tick_params(axis='y', labelsize=8)
                        ax1.grid(True, linestyle=":", alpha=0.3)
                        
                        # Eje 2: Líneas de Tendencia de Intensidad (Preservadas intactas)
                        ax2 = ax1.twinx()
                        config_lineas_int = [
                            {"color": "#27ae60", "linestyle": "-",  "marker": "x"}, # Aeróbico Ligero
                            {"color": "#f39c12", "linestyle": "--", "marker": "*"}, # Aeróbico Medio
                            {"color": "#d35400", "linestyle": "-.", "marker": ">"}, # Umbral
                            {"color": "#c0392b", "linestyle": ":",  "marker": "d"}  # Anaeróbico
                        ]
                        
                        for idx, inten in enumerate(intensidades_lista):
                            cfg = config_lineas_int[idx]
                            ax2.plot(
                                fechas_str, 
                                df_vol_diario[inten], 
                                label=f"Zona: {inten}", 
                                color=cfg["color"], 
                                linewidth=2.0, 
                                linestyle=cfg["linestyle"], 
                                marker=cfg["marker"], 
                                markersize=6
                            )
                            
                        ax2.set_ylabel("Carga por Intensidades (Metros)", fontsize=9)
                        ax2.tick_params(axis='y', labelsize=8)
                        
                        # Unificación limpia de leyendas
                        lines1, labels1 = ax1.get_legend_handles_labels()
                        lines2, labels2 = ax2.get_legend_handles_labels()
                        
                        # =============================================================================
                        # CALIBRACIÓN DINÁMICA DE LÍMITES DE EJES Y (COLCHÓN DE SEGURIDAD)
                        # =============================================================================
                        # 1. Eje Izquierdo (stackplot): Sumamos los estilos por fila para hallar el pico real acumulado
                        suma_acumulada_por_dia = df_vol_diario[estilos_lista].sum(axis=1)
                        max_ax1 = suma_acumulada_por_dia.max() if not suma_acumulada_por_dia.empty else 100
                        
                        # Al tener la leyenda arriba a la izquierda, un 30% da el margen perfecto para que no se solapen
                        ax1.set_ylim(0, max_ax1 * 1.30) 
                        
                        # 2. Eje Derecho (twinx): Evaluamos el valor individual más alto de las líneas de intensidad
                        max_ax2 = df_vol_diario[intensidades_lista].max().max() if not df_vol_diario[intensidades_lista].empty else 100
                        ax2.set_ylim(0, max_ax2 * 1.20) # 20% de holgura para el eje secundario
                        # =============================================================================
                        
                        # Posicionamos la leyenda fija en el extremo superior izquierdo, bien holgada
                        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=8, ncol=3)
                        
                        plt.xticks(rotation=45, fontsize=7)
                        plt.tight_layout()
                        st.pyplot(fig_vol)
         
                        # Botón para descargar el gráfico de volúmenes en PNG
                        buf_png_vol = io.BytesIO()
                        fig_vol.savefig(buf_png_vol, format="png", dpi=300)
                        st.download_button(
                            "🖼️ Guardar Gráfico de Volúmenes (PNG)", 
                            data=buf_png_vol.getvalue(), 
                            file_name=f"grafico_volumen_colectivo_{ventana_sel.split()[0]}.png", 
                            mime="image/png"
                        )
                        
                        # TABLA DIARIA DE SOPORTE CON FILA DE TOTALES ESTILIZADA
                        st.markdown("##### 📋 Matriz de Auditoría Diaria Colectiva")
                        df_tabla_vol = df_vol_diario.copy()
                        
                        fila_totales_vol = {"Fecha": "TOTAL ACUMULADO"}
                        for col in columnas_vol[1:]:
                            fila_totales_vol[col] = df_tabla_vol[col].sum()
                            
                        df_tabla_vol["Fecha"] = df_tabla_vol["Fecha"].map(lambda x: x.strftime("%Y-%m-%d"))
                        df_tabla_vol = pd.concat([df_tabla_vol, pd.DataFrame([fila_totales_vol])], ignore_index=True)
                        
                        st.write(df_tabla_vol.to_html(index=False, classes="tabla-estilizada"), unsafe_allow_html=True)

                        # =============================================================================
                        # 4. EXPORTACIONES LIMPIAS EN 2 BOTONES (CSV Y TXT CON REPORTE INTEGRADO)
                        # =============================================================================
                        st.markdown("---")
                        st.markdown("#### 📥 Exportación de Reportes Consolidados")
                        
                        # Generación del Bloque de Texto de Resumen Analítico
                        resumen_lineas = [
                            "=========================================",
                            "   RESUMEN ANALÍTICO DE CARGA Y VOLUMEN  ",
                            "=========================================",
                            f"Fecha de Reporte: {datetime.date.today()}",
                            f"Ventana Seleccionada: {ventana_sel}",
                            f"Atletas Analizados: {len(atletas_finales_rep)}",
                            f"Volumen Total del Grupo: {volumen_acumulado_grupo:,} metros\n",
                            "--- DESGLOSE POR ESTILOS ---"
                        ]
                        for est in estilos_lista:
                            mts = global_estilos.get(est, 0)
                            pct = (mts / volumen_acumulado_grupo) * 100 if volumen_acumulado_grupo else 0
                            resumen_lineas.append(f"- {est}: {mts:,} m ({pct:.1f}%)")
                                   
                        resumen_lineas.append("\n--- DESGLOSE POR INTENSIDADES ---")
                        for inten in intensidades_lista:
                            mts = global_intensidades.get(inten, 0)
                            pct = (mts / volumen_acumulado_grupo) * 100 if volumen_acumulado_grupo else 0
                            resumen_lineas.append(f"- {inten}: {mts:,} m ({pct:.1f}%)")
                        
                        resumen_txt_bloque = "\n".join(resumen_lineas)

                        # 1. Preparar CSV Unificado (Matriz diaria + Filas de Resumen Porcentual al final)
                        df_csv_base = df_tabla_vol.copy()
                        # Filas en blanco decorativas para separar la matriz del resumen dentro del CSV
                        fila_vacia = {col: "" for col in columnas_vol}
                        fila_titulo_est = {col: "" for col in columnas_vol}; fila_titulo_est["Fecha"] = "--- RESUMEN PORCENTUAL ESTILOS ---"
                        
                        df_csv_base = pd.concat([df_csv_base, pd.DataFrame([fila_vacia, fila_titulo_est])], ignore_index=True)
                        for est in estilos_lista:
                            mts = global_estilos.get(est, 0)
                            pct = (mts / volumen_acumulado_grupo) * 100 if volumen_acumulado_grupo else 0
                            row_pct = {col: "" for col in columnas_vol}
                            row_pct["Fecha"] = est
                            row_pct["Total Día"] = f"{pct:.1f}%"
                            df_csv_base = pd.concat([df_csv_base, pd.DataFrame([row_pct])], ignore_index=True)
                            
                        fila_titulo_int = {col: "" for col in columnas_vol}; fila_titulo_int["Fecha"] = "--- RESUMEN PORCENTUAL INTENSIDADES ---"
                        df_csv_base = pd.concat([df_csv_base, pd.DataFrame([fila_vacia, fila_titulo_int])], ignore_index=True)
                        for inten in intensidades_lista:
                            mts = global_intensidades.get(inten, 0)
                            pct = (mts / volumen_acumulado_grupo) * 100 if volumen_acumulado_grupo else 0
                            row_pct = {col: "" for col in columnas_vol}
                            row_pct["Fecha"] = inten
                            row_pct["Total Día"] = f"{pct:.1f}%"
                            df_csv_base = pd.concat([df_csv_base, pd.DataFrame([row_pct])], ignore_index=True)
                        
                        csv_unificado_data = df_csv_base.to_csv(index=False).encode('utf-8')

                        # 2. Preparar TXT Unificado (Matriz estructurada + Bloque analítico)
                        matriz_txt_string = df_tabla_vol.to_string(index=False)
                        txt_unificado_final = f"{matriz_txt_string}\n\n{resumen_txt_bloque}"

                        c_exp1, c_exp2 = st.columns(2)
                        with c_exp1:
                            st.download_button(
                                label="📥 Descargar Matriz de Volúmenes (CSV)", 
                                data=csv_unificado_data, 
                                file_name=f"matriz_completa_volumen_{ventana_sel.split()[0]}.csv", 
                                mime="text/csv", 
                                use_container_width=True
                            )
                        with c_exp2:
                            st.download_button(
                                label="📄 Descargar Reporte de Volúmenes (TXT)", 
                                data=txt_unificado_final.encode('utf-8'), 
                                file_name=f"reporte_completo_volumen_{ventana_sel.split()[0]}.txt", 
                                mime="text/plain", 
                                use_container_width=True
                            )

                        # =============================================================================
                        # 5. ANÁLISIS CIENTÍFICO AVANZADO INDIVIDUALIZADO (BANNISTER)
                        # =============================================================================
                        st.markdown("---")
                        st.markdown("### 📈 Análisis Científico de Carga (Modelo CTL / ATL / TSB)")
                        st.caption("Filtro dinámico por atleta individualizado para proyectar el Fitness (CTL), la Fatiga (ATL) y la Forma (TSB) usando la serie continua diaria.")

                        atletas_opciones_carga = {at["id"]: at["nombre"] for at in atletas_finales_rep}
                        atleta_sel_id = st.selectbox(
                            "🔍 Seleccione un nadador para visualizar su curva de carga acumulada:",
                            options=list(atletas_opciones_carga.keys()),
                            format_func=lambda x: atletas_opciones_carga[x],
                            key="rep_selectbox_atleta_carga_avanzada"
                        )
                        
                        # Filtrado estricto aplicando la regla del día de hoy
                        records_atleta = [r for r in records_hasta_hoy if r.get("atleta_id") == atleta_sel_id]
                        
                        if not records_atleta:
                            st.info("💡 Este atleta no cuenta con registros de volumen específicos válidos ejecutados hasta el día de hoy.")
                        else:
                            with st.expander("📘 Ver Fórmulas de Modelado y Rangos Metodológicos Objetivos", expanded=False):
                                st.markdown(r"""
                                **Ecuaciones del Modelo Híbrido (Metros + Porcentaje):**
                                * **Fitness (CTL):** $$\text{CTL}_t = \text{CTL}_{t-1} \cdot e^{-1/42} + w_t \cdot (1 - e^{-1/42})$$
                                * **Fatiga (ATL):** $$\text{ATL}_t = \text{ATL}_{t-1} \cdot e^{-1/7} + w_t \cdot (1 - e^{-1/7})$$
                                * **Balance de Forma Porcentual (Eje Derecho):** $$\text{TSB \%}_t = \left( \frac{\text{CTL}_t - \text{ATL}_t}{\text{CTL}_t} \right) \cdot 100$$
                                * Donde **$$(w_t)$$** representa la carga del día en Metros Equivalentes.
                                * **Coeficientes multiplicadores por intensidad:** Aeróbico Ligero: 1.0, Aeróbico Medio: 1.2, Umbral: 1.4, Anaeróbico: 1.7, Sprint: 1.7. Transforman los metros reales en *Metros Equivalentes**.
                                * **Rangos Objetivos:** Guía de valores objetivos para el macrociclo rumbo a la competencia (ej. zonas seguras de TSB para evitar sobreentrenamiento, rango óptimo de TSB positivo [+10 a +25] en la fase de tapering o puesta a punto justo antes del hito competitivo, y niveles de fatiga tolerables).
                                * 🔴 Zona de Fatiga Crítica: %TSB < -25    ⚠️ Fatiga Acumulada Alta: -25.0 < %TSB < -10.0    🟡 Zona de Estímulo Óptimo: -10.0 <= %TSB <= 5.0    🟢 Puesta a Punto / Tapering Óptimo: 10.0 <= %TSB <= 25.0
                                * Lógica Matemática del Tiempo Continuo **(Días de Descanso = Esfuerzo 0)**
                                """)

                            if rango_fechas_completo is not None:
                                vol_diario_map = {f: 0.0 for f in rango_fechas_completo}
                                mapeo_factores = {"Aeróbico Ligero": 1.0, "Aeróbico Medio": 1.2, "Umbral": 1.4, "Anaeróbico": 1.7, "Sprint": 1.7}
                                
                                for r in records_atleta:
                                    f_rec = datetime.datetime.strptime(r["fecha"], "%Y-%m-%d").date() if isinstance(r["fecha"], str) else r["fecha"]
                                    if f_rec in vol_diario_map:
                                        int_dict = r.get("desglose_intensity") or r.get("desglose_intensidad") or {}
                                        subtotal_ponderado = 0.0
                                        for k_int, m_int in int_dict.items():
                                            factor = 1.0
                                            for key_map, f_val in mapeo_factores.items():
                                                if key_map in k_int:
                                                    factor = f_val
                                                    break
                                            subtotal_ponderado += (m_int * factor)
                                        
                                        if not int_dict:  # Fallback
                                            subtotal_ponderado = r.get("metros_totales", 0) * r.get("factor_exigencia", 1.0)
                                        
                                        vol_diario_map[f_rec] += subtotal_ponderado
                                
                                # =============================================================================
                                # CÓMPUTO DE MATRICES (METROS + COMPONENTE PORCENTUAL)
                                # =============================================================================
                                df_cargas = pd.DataFrame([{"Fecha": f, "Volumen": vol_diario_map[f]} for f in rango_fechas_completo])
                                df_cargas["Fecha"] = pd.to_datetime(df_cargas["Fecha"])
                                df_cargas = df_cargas.sort_values("Fecha").reset_index(drop=True)
                                
                                df_cargas["CTL"] = df_cargas["Volumen"].ewm(span=42, adjust=False).mean()
                                df_cargas["ATL"] = df_cargas["Volumen"].ewm(span=7, adjust=False).mean()
                                df_cargas["TSB"] = df_cargas["CTL"] - df_cargas["ATL"]
                                
                                # Serie temporal del TSB porcentual relativo
                                df_cargas["TSB_Pct"] = ((df_cargas["CTL"] - df_cargas["ATL"]) / df_cargas["CTL"]) * 100
                                df_cargas["TSB_Pct"] = df_cargas["TSB_Pct"].fillna(0.0)
                                
                                ultima_fila = df_cargas.iloc[-1]
                                val_ctl = int(ultima_fila["CTL"])
                                val_atl = int(ultima_fila["ATL"])
                                val_tsb = int(ultima_fila["TSB"])
                                pct_tsb = round(float(ultima_fila["TSB_Pct"]), 1)
                                
                                # Evaluación semántica estricta del estado actual
                                if pct_tsb <= -25.0:
                                    estado_forma = f"🔴 Zona de Fatiga Crítica ({pct_tsb}% del CTL)"
                                elif -25.0 < pct_tsb < -10.0:
                                    estado_forma = f"⚠️ Fatiga Acumulada Alta ({pct_tsb}% del CTL)"
                                elif -10.0 <= pct_tsb <= 5.0:
                                    estado_forma = f"🟡 Zona de Estímulo Óptimo ({pct_tsb}% del CTL)"
                                elif 10.0 <= pct_tsb <= 25.0:
                                    estado_forma = f"🟢 Puesta a Punto / Tapering Óptimo (+{pct_tsb}% del CTL)"
                                else:
                                    estado_forma = f"❌ Exceso de Puesta a Punto / Desentrenamiento (+{pct_tsb}% del CTL)"
                                
                                # Despliegue de tarjetas de control
                                c_m1, c_m2, c_m3 = st.columns(3)
                                with c_m1: st.metric("💪 Fitness (CTL - Crónica)", value=f"{val_ctl:,} m")
                                with c_m2: st.metric("🔥 Fatiga (ATL - Aguda)", value=f"{val_atl:,} m")
                                with c_m3: st.metric("🎯 Balance de Forma (TSB)", value=f"{val_tsb:,} m", delta=estado_forma)
                                
# =============================================================================
                                # RENDERIZADO DEL MOTOR GRÁFICO HÍBRIDO PRO (ESCALA CORREGIDA)
                                # =============================================================================
                                fig_ban, ax1 = plt.subplots(figsize=(8.5, 3.8))
                                
                                # --- EJE 1 (Izquierdo): Métricas Clásicas en Metros ---
                                l_ctl = ax1.plot(df_cargas["Fecha"], df_cargas["CTL"], label="Capacidad Crónica (CTL)", color="#1f77b4", linewidth=2.2)
                                l_atl = ax1.plot(df_cargas["Fecha"], df_cargas["ATL"], label="Respuesta Aguda / Fatiga (ATL)", color="#d62728", linewidth=1.5, linestyle="--")
                                b_tsb = ax1.bar(df_cargas["Fecha"], df_cargas["TSB"], label="Balance de Forma (TSB m)", color="#2ca02c", alpha=0.25, width=1.0)
                                
                                ax1.set_ylabel("Volumen de Carga Ponderado (Metros)", color="#1f77b4", fontsize=9)
                                ax1.tick_params(axis='y', labelcolor="#1f77b4", labelsize=8)
                                ax1.grid(True, linestyle=":", alpha=0.2)
                                
                                # --- CORRECCIÓN DE ESCALA ASIMÉTRICA ---
                                # Buscamos los valores máximos y mínimos alcanzados en metros para ajustar ax1
                                max_metros = max(df_cargas["CTL"].max(), df_cargas["ATL"].max(), df_cargas["Volumen"].max(), 500.0)
                                min_metros = min(df_cargas["TSB"].min(), 0.0)
                                
                                # Le damos una holgura del 25% para que las líneas respiren y no se aplasten arriba
                                ax1.set_ylim(min_metros * 1.25, max_metros * 1.25)
                                
                                # --- EJE 2 (Derecho): Curva Porcentual Relativa y Líneas de Control ---
                                ax2 = ax1.twinx()
                                l_pct = ax2.plot(df_cargas["Fecha"], df_cargas["TSB_Pct"], label="Índice TSB (%)", color="#2c3e50", linewidth=2.5, marker="o", markersize=3)
                                
                                # Líneas horizontales límites solicitadas
                                ax2.axhline(25.0, color="#b03a2e", linestyle="-", linewidth=1.2, alpha=0.7)  # Máximo Positivo
                                ax2.axhline(10.0, color="#1e8449", linestyle=":", linewidth=1.2, alpha=0.7)  # Límite superior Tapering
                                ax2.axhline(-10.0, color="#1e8449", linestyle=":", linewidth=1.2, alpha=0.7) # Límite inferior Tapering
                                ax2.axhline(-25.0, color="#b03a2e", linestyle="-", linewidth=1.2, alpha=0.7) # Máximo Negativo
                                ax2.axhline(0.0, color="#7f8c8d", linestyle="-", linewidth=0.8, alpha=0.4)
                                
                                # Sombreando las Áreas Fisiológicas solicitadas
                                # Ajustamos los límites de los spans para que no distorsionen los límites del eje
                                ax2.axhspan(25.0, 500.0, color="#fbc4b7", alpha=0.35, label="Rosado: Exceso de Descanso (>+25%)")
                                ax2.axhspan(-500.0, -25.0, color="#fbc4b7", alpha=0.35, label="Rosado: Fatiga Crónica Máxima (<-25%)")
                                
                                # Áreas Amarillas (Zonas de transición/aproximación)
                                ax2.axhspan(5.0, 25.0, color="#f9e79f", alpha=0.3, label="Amarillo: Transición a Puesta a Punto")
                                ax2.axhspan(-25.0, -10.0, color="#f9e79f", alpha=0.3, label="Amarillo: Carga Exigente")
                                
                                # Área Verde Central (Puesta a punto óptima)
                                ax2.axhspan(10.0, 25.0, color="#abebc6", alpha=0.4, label="🟢 Tapering Óptimo (+10% a +25%)")
                                
                                ax2.set_ylabel("Balance Fisiológico Porcentual (% del CTL)", color="#2c3e50", fontsize=9)
                                ax2.tick_params(axis='y', labelcolor="#2c3e50", labelsize=8)
                                
                                # Ajuste de límites del eje porcentual basado en el extremo alcanzado
                                max_abs_pct = max(df_cargas["TSB_Pct"].abs().max(), 35.0)
                                ax2.set_ylim(-max_abs_pct - 15, max_abs_pct + 15)
                                
                                # Consolidación unificada de leyendas de ambos ejes
                                lineas_totales = l_ctl + l_atl + [b_tsb] + l_pct
                                etiquetas_totales = [l.get_label() for l in lineas_totales]
                                ax1.legend(lineas_totales, etiquetas_totales, loc="upper left", fontsize=7, ncol=2)
                                
                                ax1.set_title(f"Perfil Fisiológico Híbrido: {atletas_opciones_carga[atleta_sel_id]}", fontsize=11, fontweight="light")
                                plt.xticks(rotation=25, fontsize=5)
                                plt.tight_layout()
                                st.pyplot(fig_ban)
                                
                                # Botón para descargar gráfico híbrido
                                buf_png_ban = io.BytesIO()
                                fig_ban.savefig(buf_png_ban, format="png", dpi=300)
                                st.download_button(
                                    "🖼️ Guardar Gráfico Fisiológico (PNG)", 
                                    data=buf_png_ban.getvalue(), 
                                    file_name=f"perfil_hibrido_{atletas_opciones_carga[atleta_sel_id].lower().replace(' ', '_')}.png", 
                                    mime="image/png"
                                )

                                # =============================================================================
                                # VISTA DE LA TABLA DIARIA COMPLEMENTARIA
                                # =============================================================================
                                st.markdown("##### 📋 Tabla de Valores Diarios y Métricas de Estado")
                                df_tabla_ban = df_cargas.copy()
                                df_tabla_ban["Fecha"] = df_tabla_ban["Fecha"].dt.strftime("%Y-%m-%d")
                                
                                df_tabla_ban["Volumen"] = df_tabla_ban["Volumen"].round(1)
                                df_tabla_ban["CTL"] = df_tabla_ban["CTL"].round(1)
                                df_tabla_ban["ATL"] = df_tabla_ban["ATL"].round(1)
                                df_tabla_ban["TSB"] = df_tabla_ban["TSB"].round(1)
                                df_tabla_ban["TSB_Pct"] = df_tabla_ban["TSB_Pct"].round(1).astype(str) + " %"
                                
                                df_tabla_ban.columns = ["Fecha", "Metros Ponderados (Día)", "CTL (Fitness m)", "ATL (Fatiga m)", "TSB (Forma m)", "TSB Relativo (% del CTL)"]
                                st.write(df_tabla_ban.to_html(index=False, classes="tabla-estilizada"), unsafe_allow_html=True)
                                
                                # Botonera de descargas asociadas
                                csv_ban_data = df_tabla_ban.to_csv(index=False).encode('utf-8')
                                txt_ban_data = df_tabla_ban.to_string(index=False).encode('utf-8')
                                
                                c_ban_exp1, c_ban_exp2 = st.columns(2)
                                with c_ban_exp1:
                                    st.download_button(label="📥 Descargar Métricas de Estado (CSV)", data=csv_ban_data, file_name="metricas_fisiologicas.csv", mime="text/csv", use_container_width=True)
                                with c_ban_exp2:
                                    st.download_button(label="📄 Descargar Reporte de Carga (TXT)", data=txt_ban_data, file_name="reporte_carga.txt", mime="text/plain", use_container_width=True)
         
                except Exception as e:
                    st.error(f"Error al computar el reporte analítico avanzado: {e}")             
    else:
        st.warning("🔒 Esta función está reservada para el equipo técnico (Entrenadores y Administradores).")
