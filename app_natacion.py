import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import fsolve
import pandas as pd
import datetime
import io
import hashlib
from supabase import create_client, Client

# --- NUEVOS IMPORTS PARA EL ENVÍO DE CORREOS ---
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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
        if edad_tecnica < 12:
            return False, f"Edad técnica insuficiente ({edad_tecnica} años). Mínimo requerido: 12 años."
    return True, None

# ... (El resto de tu script continúa exactamente igual a partir de aquí) ...
    
# -------------------------------------------------------------
# FUNCIÓN DE CALCULO DE EDAD_HITO (MÓDULO INDEPENDIENTE)
# -------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=600)
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
st.set_page_config(page_title="Simulador de proyección de rendimiento para natación", layout="wide")

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
    elif 10 <= edad_competencia <= 11:
        cat = "Infantil A"
    elif 12 <= edad_competencia <= 13:
        cat = "Infantil B"
    elif 14 <= edad_competencia <= 15:
        cat = "Juvenil A"
    elif 16 <= edad_competencia <= 18:
        cat = "Juvenil B"
    elif edad_competencia > 18:
        cat = "Máxima"
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

def login_usuario(user, password):
    try:
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
    st.markdown("<h2 style='text-align: center;'>🏊‍♂️ Sistema de Proyección de Rendimiento y Gestión de Resultados en Competencia - Club de Natación Centro Gallego</h2>", unsafe_allow_html=True)
    c_login, _ = st.columns([1.5, 1.5])
    with c_login:
        tab_login, tab_registro, tab_recuperar = st.tabs(["🔑 Iniciar Sesión", "📝 Registro de Usuarios", "🔄 Recuperar Contraseña"])
        
        with tab_login:
            st.caption("Nota: Los nombres de usuario y contraseñas distinguen mayúsculas/minúsculas.")
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
            st.caption("Nota: Los nombres de usuario y contraseñas distinguen mayúsculas/minúsculas.")
            nuevo_rol = st.selectbox("Seleccione el Rol para la nueva cuenta:", options=["Nadador", "Entrenador", "Administrador"], key="reg_rol_selector")
            es_nadador_reg = (nuevo_rol == "Nadador")
            
            with st.form("form_registro_dinamico"):
                nuevo_nombre = st.text_input("Nombre completo:")
                nuevo_usuario = st.text_input("Nombre de Usuario (Alias):")
                nuevo_email = st.text_input("Correo Electrónico:")
                nueva_contrasena = st.text_input("Establecer Contraseña:", type="password")
                
                nuevo_genero = None
                nueva_fecha_nac = None
                
                if es_nadador_reg:
                    st.markdown("---")
                    st.markdown("##### 🧬 Datos Biométricos Requeridos (Categorías Feveda)")
                    nuevo_genero = st.selectbox("Género:", options=["F", "M"], format_func=lambda x: "Femenino" if x == "F" else "Masculino")
                    nueva_fecha_nac = st.date_input("Fecha de Nacimiento:", min_value=datetime.date(1950, 1, 1), max_value=datetime.date.today())
                    
                if st.form_submit_button("🚀 Crear Cuenta en el Sistema"):
                    if nuevo_nombre and nuevo_usuario and nueva_contrasena and nuevo_email:
                        try:
                            chequeo = supabase.table("usuarios").select("id").eq("usuario", nuevo_usuario).execute()
                            if chequeo.data:
                                st.error("El nombre de usuario ya está tomado.")
                            else:
                                status_inicial = "Pendiente" if nuevo_rol in ["Entrenador", "Administrador"] else "Activo"
                                
                                nuevo_registro = {
                                    "nombre": nuevo_nombre, 
                                    "usuario": nuevo_usuario, 
                                    "email": nuevo_email,
                                    "contrasena": hash_password(nueva_contrasena),
                                    "rol": nuevo_rol, 
                                    "estatus": status_inicial,
                                    "genero": nuevo_genero if es_nadador_reg else None,
                                    "fecha_nacimiento": nueva_fecha_nac.isoformat() if (es_nadador_reg and nueva_fecha_nac) else None
                                }
                                supabase.table("usuarios").insert(nuevo_registro).execute()
                                
                                if status_inicial == "Pendiente":
                                    enviar_email("Cuenta en Revisión", f"Hola {nuevo_nombre}, tu cuenta de {nuevo_rol} ha sido registrada. Esta pendiente de revision por el administrador.", nuevo_email)
                                    enviar_email("Nuevo Registro Pendiente", f"El usuario {nuevo_nombre} ({nuevo_rol}) se ha registrado. Email: {nuevo_email}. Favor revisar en consola admin.", st.secrets["EMAIL_ADMIN"])
                                    st.success(f"¡Registro exitoso como **{nuevo_rol}**! Tu cuenta debe ser aprobarla el administrador.")
                                else:
                                    st.success(f"¡Registro exitoso como **{nuevo_rol}**! Ya puede iniciar sesión.")
                        except Exception as reg_err:
                            st.error(f"Error en registro: {reg_err}")
                    else:
                        st.error("Por favor complete todos los datos obligatorios del formulario.")

        with tab_recuperar:
            st.markdown("### Restablecer Contraseña")
            with st.form("form_recuperacion"):
                rec_usuario = st.text_input("Nombre de Usuario (Alias):")
                rec_email = st.text_input("Correo Electrónico Asociado:")
                nueva_clave = st.text_input("Nueva Contraseña Deseada:", type="password")
                confirmar_clave = st.text_input("Confirmar Nueva Contraseña:", type="password")
                
                if st.form_submit_button("🔄 Actualizar Contraseña"):
                    if not (rec_usuario and rec_email and nueva_clave and confirmar_clave):
                        st.error("Todos los campos del formulario de recuperación son obligatorios.")
                    elif nueva_clave != confirmar_clave:
                        st.error("La confirmación no coincide con la nueva contraseña introducida.")
                    else:
                        try:
                            verificacion = supabase.table("usuarios").select("id, estatus").eq("usuario", rec_usuario).eq("email", rec_email).execute()
                            if verificacion.data:
                                user_info = verificacion.data[0]
                                if user_info.get("estatus") in ["Suspendido", "Bloqueado"]:
                                    st.error("Esta cuenta se encuentra suspendida o bloqueada por la administración.")
                                else:
                                    supabase.table("usuarios").update({"contrasena": hash_password(nueva_clave)}).eq("id", user_info["id"]).execute()
                                    st.success("✅ Contraseña actualizada correctamente.")
                            else:
                                st.error("❌ Los datos proporcionados no coinciden.")
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
    st.markdown("---")
    if st.button("🔄 Refrescar Datos (Limpiar Caché)"):
        # Limpia toda la caché de datos
        st.cache_data.clear()
        # Fuerza una recarga inmediata de la página para aplicar los cambios
        st.rerun()
if st.session_state.rol in ["Entrenador", "Administrador"]:
    spc()
    st.sidebar.subheader("🎯 Panel de Navegación de Atletas")
    try:
        resp_atletas = supabase.table("usuarios").select("id, nombre, genero, fecha_nacimiento").eq("rol", "Nadador").eq("estatus", "Activo").execute()
        if resp_atletas.data:
            df_atl = pd.DataFrame(resp_atletas.data)
            dict_atletas = dict(zip(df_atl["id"], df_atl["nombre"]))
            
            sel_id = st.sidebar.selectbox("Monitorear Nadador:", options=list(dict_atletas.keys()), format_func=lambda x: dict_atletas[x])
            atleta_row = df_atl[df_atl["id"] == sel_id].iloc[0]
            
            st.session_state.nadador_seleccionado_id = int(atleta_row["id"])
            st.session_state.nadador_seleccionado_nombre = atleta_row["nombre"]
            st.session_state.nadador_seleccionado_genero = atleta_row["genero"]
            
            cat_calc, _ = calcular_categoria_competencia(atleta_row["fecha_nacimiento"])
            st.session_state.nadador_seleccionado_categoria = cat_calc
    except Exception as e:
        st.error(f"Error cargando nómina de atletas: {e}")
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

if st.session_state.rol in ["Entrenador", "Administrador"]:
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
    h = st.slider("Factor ajustable de rapidez de deriva (h):", min_value=0.1, max_value=1.0, value=0.4, step=0.05)
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
# RENDIMIENTO GRÁFICO: MODO EQUIPO
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
            fig = plt.figure(figsize=(8.5, 11.0))
            ax = fig.add_axes([0.14, 0.52, 0.72, 0.33])
            colores = plt.get_cmap("tab10", len(atletas_filtrados))
            hay_datos_visibles = False
            linea_fisiologica_anotada = False
            todas_las_edades_0 = []
            todos_los_tiempos_colectivo = []
            datos_atletas_cargados = []
            
            # Recolección de datos de los atletas seleccionados
            for idx, atl in enumerate(atletas_filtrados):
                a_id = atl["id"]
                a_nom = atl["nombre"]
                res_marcas = supabase.table("marcas_historicas")\
                    .select("edad, tiempo, nota")\
                    .eq("prueba", titulo_grafico)\
                    .eq("usuario_id", a_id)\
                    .order("edad", desc=False).execute()
                if res_marcas.data:
                    df_atl_m = pd.DataFrame(res_marcas.data)
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
                
                # --- NUEVA CONSULTA DE MARCAS DE REFERENCIA PARA EL EQUIPO ---
                ref_gen_target = "F" if filtro_genero == "Femenino (F)" else "M"
                ref_cat_target = cat_sel if (tipo_filtro == "Categoría Etaria" and cat_sel) else st.session_state.nadador_seleccionado_categoria
                
                m_ano_e, m_panam_b_e, m_panam_a_e, m_wa_b_e, m_wa_a_e, m_wr_e = 0.0, 0.0, 0.0, 0.0, 0.0, 25.0
                
                try:
                    ref_resp_e = supabase.table("marcas_referencia").select("*")\
                        .eq("prueba", titulo_grafico)\
                        .eq("genero", ref_gen_target)\
                        .eq("categoria", ref_cat_target).execute()
                        
                    if ref_resp_e.data:
                        rd = ref_resp_e.data[0]
                        m_ano_e = float(rd.get("m_ano") or 0.0)
                        m_panam_b_e = float(rd.get("m_panam_b") or 0.0)
                        m_panam_a_e = float(rd.get("m_panam_a") or 0.0)
                        m_wa_b_e = float(rd.get("m_wa_b") or 0.0)
                        m_wa_a_e = float(rd.get("m_wa_a") or 0.0)
                        m_wr_e = float(rd.get("m_wr") or 25.0)
                except Exception as e_ref:
                    print(f"Error cargando marcas de referencia para el equipo: {e_ref}")
                
                # Configuramos los límites Y en base a los datos correctos del equipo
                lim_y_inferior = m_wr_e * 0.95
                lim_y_superior = peor_tiempo_colectivo + (peor_tiempo_colectivo * 0.05)
                ax.set_ylim(lim_y_inferior, lim_y_superior)
                
                # Bucle de dibujo de curvas por cada atleta
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
                    
                # Dibujo de las líneas de referencia del equipo
                x_texto = lim_x_min + 0.1
                if not es_preinfantil:
                    referencias = [
                        {"val": m_ano_e, "lbl": "Mín. Año", "col": "#A06000", "va": "bottom"}, 
                        {"val": m_panam_b_e, "lbl": "PANAM Jr B", "col": "#006644", "va": "bottom"},      
                        {"val": m_panam_a_e, "lbl": "PANAM Jr A", "col": "#2A658A", "va": "top"},   
                        {"val": m_wa_b_e, "lbl": "WA B", "col": "#943100", "va": "bottom"},               
                        {"val": m_wa_a_e, "lbl": "WA A", "col": "#883963", "va": "top"},            
                        {"val": m_wr_e, "lbl": "World Record", "col": "#2C3E50", "va": "top"}   
                    ]
                    for r in referencias:
                        if r["val"] > 0 and lim_y_inferior <= r["val"] <= lim_y_superior:
                            ax.axhline(y=r["val"], color=r["col"], linestyle=":", linewidth=0.6, alpha=0.7)
                            desplazamiento_y = (lim_y_superior - lim_y_inferior) * 0.006 if r["va"] == "bottom" else -((lim_y_superior - lim_y_inferior) * 0.006)
                            ax.text(x_texto, r["val"] + desplazamiento_y, f"{r['lbl']}: {r['val']:.2f}s", color=r["col"], fontsize=7, va=r["va"], ha="left")
                            
                ax.set_title("Comparativa de Rendimiento de Equipo", fontsize=13, pad=10)
                ax.set_xlabel("Edad del Atleta (Años)", fontsize=9.5)
                ax.set_ylabel("Tiempo de Carrera (Segundos)", fontsize=9.5)
                ax.grid(True, which="both", axis="both", linestyle=":", color="#CCD1D1", linewidth=0.5)
                ax.legend(loc="upper right", fontsize=7, framealpha=0.8)
                st.pyplot(fig, use_container_width=True)
                
    except Exception as e:
        st.error(f"Error procesando el análisis por equipo: {e}")
# -------------------------------------------------------------
# RENDIMIENTO GRÁFICO: MODO INDIVIDUAL O SIMULACIÓN
# -------------------------------------------------------------
else:
    fig = plt.figure(figsize=(8.5, 11.0))
    ax = fig.add_axes([0.14, 0.52, 0.72, 0.33])
    
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
                                "Tiempo Prog.": f"{tiempo_proyectado_val:.2f} s"
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
        ax.text(t0 + 0.1, T0, f"P. Start\n{t0:.2f}a\n{T0:.2f}s", fontsize=8, va="bottom", ha="left", bbox=estilo_bbox)
        ax.axvline(x=t0, color="#7F8C8D", linestyle=":", linewidth=0.7, alpha=0.5)

    if lim_x_min <= t_pb <= lim_x_max and lim_y_inferior <= T_pb <= lim_y_superior:
        ax.scatter(t_pb, T_pb, color="#F1C40F", marker="*", edgecolor="black", s=100, linewidths=0.6, zorder=5, label="PB Actual de Control")
        ax.text(t_pb + 0.15, T_pb, f"PB Actual\n{t_pb:.2f}a\n{T_pb:.2f}s", fontsize=8, va="center", ha="left", bbox=estilo_bbox)
        ax.axvline(x=t_pb, color="red", linestyle="--", linewidth=0.7, alpha=0.4)

    if lim_x_min <= t_intermedia <= lim_x_max and lim_y_inferior <= T_intermedia_val <= lim_y_superior:
        ax.scatter(t_intermedia, T_intermedia_val, color="red", marker="o", s=30, zorder=5, label="Punto Consultado")
        ax.text(t_intermedia, T_intermedia_val + offset_y, f"Consulta: {t_intermedia:.1f}a\n{T_intermedia_val:.2f}s", fontsize=8, va="bottom", ha="center", bbox=estilo_bbox)
        ax.axvline(x=t_intermedia, color="red", linestyle=":", linewidth=0.7, alpha=0.4)

    if lim_x_min <= t_peak <= lim_x_max and lim_y_inferior <= T_target <= lim_y_superior:
        ax.scatter(t_peak, T_target, color="#2ECC71", marker="s", edgecolor="black", s=35, linewidths=0.6, zorder=4, label="Meta Peak")
        ax.text(t_peak - 0.1, T_target, f"Meta Peak\n{t_peak:.2f}a\n{T_target:.2f}s", fontsize=8, va="bottom", ha="right", bbox=estilo_bbox)
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
            df_table_render["Edad"] = df_table_render["Edad"].map(lambda x: f"{x:.2f} a")
            df_table_render["Tiempo"] = df_table_render["Tiempo"].map(lambda x: f"{x:.2f} s")
            anchos_columnas = [0.15, 0.15, 0.70]
        else:
            df_table_render = pd.DataFrame([{
                "Edad": "-", 
                "Tiempo": "-", 
                "Evento / Fecha": "Sin marcas históricas registradas"
            }])
            anchos_columnas = [0.15, 0.15, 0.70]

    if df_table_render is not None and not df_table_render.empty:
        total_filas = len(df_table_render)
        limite_filas_por_bloque = 16
        
        def estilizar_tabla_nativo(instancia_tabla):
            instancia_tabla.auto_set_font_size(False)
            instancia_tabla.set_fontsize(8.5)
            instancia_tabla.scale(1.0, 1.3)
            for (row, col), cell in instancia_tabla.get_celld().items():
                if row == 0:
                    cell.set_text_props(color='white', weight='bold')
                    cell.set_facecolor('#007A87')
                else:
                    cell.set_facecolor('#F8F9F9' if row % 2 == 0 else 'white')

        if total_filas <= limite_filas_por_bloque:
            ax_table = fig.add_axes([0.14, 0.054, 0.72, 0.40])
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
            if total_filas > 32: 
                df_table_render = df_table_render.iloc[:32]
            df_bloque_izq = df_table_render.iloc[:limite_filas_por_bloque]
            df_bloque_der = df_table_render.iloc[limite_filas_por_bloque:]
            
            anchos_doble = anchos_columnas if es_modo_micro_tabla else [0.18, 0.18, 0.64]
            
            ax_table1 = fig.add_axes([0.14, 0.054, 0.34, 0.40])
            ax_table1.axis('off')
            mpl_table1 = ax_table1.table(cellText=df_bloque_izq.values, colLabels=df_bloque_izq.columns, cellLoc='center', loc='upper center', colWidths=anchos_doble)
            estilizar_tabla_nativo(mpl_table1)
            
            ax_table2 = fig.add_axes([0.52, 0.054, 0.34, 0.40])
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
    
    img_buffer = io.BytesIO()
    fig.savefig(img_buffer, format="png", bbox_inches=None, dpi=300)
    img_buffer.seek(0)
    
    c_exp1, c_exp2, c_exp3 = st.columns(3)
    with c_exp1:
        st.download_button(label="📥 Descargar Historial (CSV)", data=csv_data, file_name=f"marcas_{titulo_grafico}_{st.session_state.nadador_seleccionado_nombre}.csv", mime="text/csv")
    with c_exp2:
        st.download_button(label="📄 Descargar Datos (TXT)", data=txt_string, file_name=f"reporte_{titulo_grafico}_{st.session_state.nadador_seleccionado_nombre}.txt", mime="text/plain")
    with c_exp3:
        st.download_button(label="🖼️ Guardar Gráfico Completo (Imagen PNG - Tamaño Carta)", data=img_buffer, file_name=f"grafico_{titulo_grafico}_{st.session_state.nadador_seleccionado_nombre}.png", mime="image/png")


# -------------------------------------------------------------
# MÓDULOS DE GESTIÓN SEGÚN ROL
# -------------------------------------------------------------
st.markdown("---")

if simulacion_externa:
    st.info("⚠️ **Modo Simulación Externa Activo.** El módulo de gestión y control de marcas se encuentra oculto para evitar alteraciones accidentales en la base de datos real.")
else:
    tab_pizarra, tab_reportes, tab_marcas, tab_entrenador, tab_calendario, tab_admin = st.tabs([
        "📝 Pizarra Diaria", 
        "📊 Reportes y Envío", 
        "📋 Control de Marcas", 
        "⏱️ Configurar Tiempos", 
        "📅 Calendario Anual", 
        "🛡️ Consola Global (Admin)"
    ])
    with tab_marcas:
        col_ins, col_vistas = st.columns([1, 2])
        with col_ins:
            st.markdown("**Ingresar Nueva Marca**")
            with st.form("form_insertar_marca", clear_on_submit=True):
                ins_fecha_evento = st.date_input("Fecha de la Competencia:", min_value=datetime.date(2020, 1, 1), max_value=datetime.date.today(), value=datetime.date.today())
                ins_tiempo = st.number_input("Tiempo Oficial (seg):", min_value=20.0,  max_value=1800.0, step=0.01)
                ins_nota = st.text_input("Evento / Fecha:")
                
                if st.form_submit_button("💾 Guardar Registro"):
                    if st.session_state.rol in ["Entrenador", "Administrador"] or st.session_state.usuario_id == st.session_state.nadador_seleccionado_id:
                        try:
                            id_atleta = st.session_state.nadador_seleccionado_id
                            fecha_nacimiento_atleta = st.session_state.fecha_nacimiento
                            
                            if st.session_state.rol in ["Entrenador", "Administrador"]:
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
                                        "tiempo": float(ins_tiempo),
                                        "nota": ins_nota, 
                                        "usuario_id": id_atleta
                                    }
                                    supabase.table("marcas_historicas").insert(nueva_m).execute()
                                    st.success(f"Marca guardada. Edad calculada automáticamente: {edad_calculada} años.")
                                    st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar el registro: {e}")
                        
        with col_vistas:
            st.markdown("**Historial Cronológico de Tiempos**")
            if len(df_procesado) > 0:
                if st.session_state.rol in ["Entrenador", "Administrador"]:
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
        if st.session_state.rol in ["Entrenador", "Administrador"]:
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
            st.warning("🔒 Requiere credenciales de Dirección Técnico o Entrenador.")

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

        # 2. Controles de Edición (Restringido a Entrenadores y Admins)
        if st.session_state.rol in ["Entrenador", "Administrador"]:
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
        if st.session_state.rol in ["Entrenador", "Administrador"]:
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
                        nuevo_rol_user = st.selectbox("Rol:", options=["Nadador", "Entrenador", "Administrador"], index=["Nadador", "Entrenador", "Administrador"].index(user_actual["rol"]))
                    with c_est:
                        nuevo_est_user = st.selectbox("Estatus:", options=["Activo", "Pendiente", "Suspendido", "Bloqueado"], index=["Activo", "Pendiente", "Suspendido", "Bloqueado"].index(user_actual["estatus"]))
                    
                    campos_deshabilitados = nuevo_rol_user in ["Entrenador", "Administrador"]
                    
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
        else:
            st.warning("🔒 Acceso restringido al Administrador.")
# -------------------------------------------------------------
    # PESTAÑA: PIZARRA DE ENTRENAMIENTO DIARIO (ETAPA 1)
    # -------------------------------------------------------------
    with tab_pizarra:
        if st.session_state.rol in ["Entrenador", "Administrador"]:
            st.markdown("### 📋 Estructura del Entrenamiento de Hoy")
            st.caption("Diseña la sesión agregando bloques. Al finalizar, genera el texto para compartir en WhatsApp o correo.")
            
            # 1. Inicializar la pizarra en la memoria de sesión si no existe
            if "pizarra_entrenamiento" not in st.session_state:
                st.session_state.pizarra_entrenamiento = []

            # 2. Formulario de ingreso rápido (El "Carrito de Compras")
            with st.expander("➕ Añadir nueva serie al entrenamiento", expanded=True):
                c_rep, c_dist, c_est = st.columns(3)
                with c_rep:
                    repeticiones = st.number_input("Repeticiones", min_value=1, value=1, step=1)
                with c_dist:
                    distancia = st.number_input("Distancia (m)", min_value=15, value=100, step=25)
                with c_est:
                    estilo = st.selectbox("Estilo / Foco", ["Libre", "Espalda", "Pecho", "Mariposa", "Combinado", "Piernas", "Brazos", "Técnica / Drills", "Afloje"])
                    
                c_int, c_imp, c_not = st.columns(3)
                with c_int:
                    intensidad = st.selectbox("Intensidad / Ritmo", ["Suave (Aeróbico Ligero 3-4)", "Medio (Aeróbico Medio 5-6)", "Fuerte (Umbral 7-8)", "Sprint (Máximo 9-10)", "Ritmo de Competencia"])
                with c_imp:
                    implementos = st.multiselect("Implementos", ["Aletas", "Paletas", "Tabla", "Pullbuoy", "Snorkel", "Paracaídas", "Ligas"])
                with c_not:
                    notas = st.text_input("Instrucciones breves (Opcional)", placeholder="Ej: Respiración c/3, Descanso 20s, c/1:30 min")

                if st.button("Añadir a la sesión", use_container_width=True):
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

            # 3. Procesamiento y Estadísticas de la Pizarra Actual
            if st.session_state.pizarra_entrenamiento:
                st.markdown("---")
                
                volumen_total = 0
                texto_exportacion = f"🏊‍♂️ *Entrenamiento del Día - Club de Natación Centro Gallego*\n📅 Fecha: {datetime.date.today().strftime('%d/%m/%Y')}\n\n*RUTINA:*\n"
                
                # Recorremos la pizarra para calcular y generar texto
                for i, blk in enumerate(st.session_state.pizarra_entrenamiento):
                    subtotal = blk['reps'] * blk['dist']
                    volumen_total += subtotal
                    
                    # Formateo de elementos opcionales
                    txt_impl = f" [{', '.join(blk['implementos'])}]" if blk['implementos'] else ""
                    txt_not = f" - _{blk['notas']}_" if blk['notas'] else ""
                    
                    linea = f"• {blk['reps']} x {blk['dist']}m {blk['estilo']} | {blk['intensidad']}{txt_impl}{txt_not}"
                    texto_exportacion += linea + "\n"

                texto_exportacion += f"\n📊 *Volumen Total:* {volumen_total} metros\n💪 ¡A darle con todo!"

                # 4. Lienzo Visual y Botones de Control
                c_lienzo, c_stats = st.columns([2, 1])
                
                with c_lienzo:
                    st.info(texto_exportacion.replace('\n', '  \n')) # Renderizado visual para la pantalla
                    
                    c_btn1, c_btn2 = st.columns(2)
                    with c_btn1:
                        if st.button("⏪ Deshacer último bloque", use_container_width=True):
                            st.session_state.pizarra_entrenamiento.pop()
                            st.rerun()
                    with c_btn2:
                        if st.button("🗑️ Limpiar pizarra completa", use_container_width=True):
                            st.session_state.pizarra_entrenamiento = []
                            st.rerun()
                            
                with c_stats:
                    st.metric("Volumen Total", f"{volumen_total} m")
                    # Analítica rápida en memoria
                    st.caption("Distribución por intensidad:")
                    conteos = {}
                    for b in st.session_state.pizarra_entrenamiento:
                        conteos[b['intensidad']] = conteos.get(b['intensidad'], 0) + (b['reps'] * b['dist'])
                    for k, v in conteos.items():
                        porcentaje = (v / volumen_total) * 100
                        st.progress(int(porcentaje), text=f"{k}: {v}m ({porcentaje:.1f}%)")

# 5. Exportación a WhatsApp
                st.markdown("📲 **Exportar a WhatsApp o Correo**")
                st.text_area("Copia el texto listo para enviar:", value=texto_exportacion, height=200, label_visibility="collapsed")
                # -------------------------------------------------------------
                # MOTOR DE CONSOLIDACIÓN Y RESPALDO DIARIO (EVALUACIÓN Y PROYECCIÓN)
                # -------------------------------------------------------------
                st.markdown("---")
                st.markdown("### 💾 Respaldo de la Jornada de Entrenamiento")
                st.caption("Consolida los datos de hoy para sumarlos al historial de reportes mensuales y trimestrales (necesario para verificar cumplimiento de marcas y becas).")
                
                # Campos para asociar el entrenamiento a un atleta o categoría
                c_grupo, c_fecha = st.columns(2)
                with c_grupo:
                    grupo_asociado = st.text_input("Atleta, Categoría o Grupo de Entrenamiento", value=f"{st.session_state.get('nadador_seleccionado_categoria', 'General')}", help="Identificador para agrupar este volumen.")
                with c_fecha:
                    fecha_jornada = st.date_input("Fecha de la sesión", value=datetime.date.today())

                if st.button("💾 Guardar y Consolidar Jornada", type="primary", use_container_width=True):
                    # Recopilar desglose de estilos
                    desglose_estilos = {}
                    for blk in st.session_state.pizarra_entrenamiento:
                        est = blk['estilo']
                        mts = blk['reps'] * blk['dist']
                        desglose_estilos[est] = desglose_estilos.get(est, 0) + mts
                        
                    # Recopilar desglose de intensidades
                    desglose_intensidad = {}
                    for blk in st.session_state.pizarra_entrenamiento:
                        inte = blk['intensidad']
                        mts = blk['reps'] * blk['dist']
                        desglose_intensidad[inte] = desglose_intensidad.get(inte, 0) + mts

                    # Estructura del registro diario consolidado
                    registro_diario = {
                        "fecha": str(fecha_jornada),
                        "grupo": grupo_asociado,
                        "metros_totales": volumen_total,
                        "desglose_estilos": desglose_estilos,
                        "desglose_intensidad": desglose_intensidad,
                        "implementos_usados": list(set([imp for blk in st.session_state.pizarra_entrenamiento for imp in blk['implementos']]))
                    }

                    if "bitacora_historica" not in st.session_state:
                        st.session_state.bitacora_historica = []
                        
                    st.session_state.bitacora_historica.append(registro_diario)
                    st.success(f"¡Jornada guardada exitosamente! Se han consolidado {volumen_total} metros para `{grupo_asociado}`.")
                    st.balloons()

        else:
            st.warning("🔒 Esta función está reservada para el equipo técnico (Entrenadores y Administradores).")

                # -------------------------------------------------------------
                # MOTOR DE CONSOLIDACIÓN Y RESPALDO DIARIO (EVALUACIÓN Y PROYECCIÓN)
                # -------------------------------------------------------------
                st.markdown("---")
                st.markdown("### 💾 Respaldo de la Jornada de Entrenamiento")
                st.caption("Consolida los datos de hoy para sumarlos al historial de reportes mensuales y trimestrales (necesario para verificar cumplimiento de marcas y becas).")
                
                # Campos para asociar el entrenamiento a un atleta o categoría
                c_grupo, c_fecha = st.columns(2)
                with c_grupo:
                    grupo_asociado = st.text_input("Atleta, Categoría o Grupo de Entrenamiento", value=f"{st.session_state.get('nadador_seleccionado_categoria', 'General')}", help="Identificador para agrupar este volumen.")
                with c_fecha:
                    fecha_jornada = st.date_input("Fecha de la sesión", value=datetime.date.today())

                if st.button("💾 Guardar y Consolidar Jornada", type="primary", use_container_width=True):
                    # Recopilar desglose de estilos
                    desglose_estilos = {}
                    for blk in st.session_state.pizarra_entrenamiento:
                        est = blk['estilo']
                        mts = blk['reps'] * blk['dist']
                        desglose_estilos[est] = desglose_estilos.get(est, 0) + mts
                        
                    # Recopilar desglose de intensidades
                    desglose_intensidad = {}
                    for blk in st.session_state.pizarra_entrenamiento:
                        inte = blk['intensidad']
                        mts = blk['reps'] * blk['dist']
                        desglose_intensidad[inte] = desglose_intensidad.get(inte, 0) + mts

                    # Estructura del registro diario consolidado
                    registro_diario = {
                        "fecha": str(fecha_jornada),
                        "grupo": grupo_asociado,
                        "metros_totales": volumen_total,
                        "desglose_estilos": desglose_estilos,
                        "desglose_intensidad": desglose_intensidad,
                        "implementos_usados": list(set([imp for blk in st.session_state.pizarra_entrenamiento for imp in blk['implementos']]))
                    }

                    # Inicializar el acumulador histórico en sesión si no existe
                    if "bitacora_historica" not in st.session_state:
                        st.session_state.bitacora_historica = []
                        
                    st.session_state.bitacora_historica.append(registro_diario)
                    st.success(f"¡Jornada guardada exitosamente! Se han consolidado {volumen_total} metros para `{grupo_asociado}`.")
                    st.balloons()

        else:
            st.warning("🔒 Esta función está reservada para el equipo técnico (Entrenadores y Administradores).")
# -------------------------------------------------------------
# PESTAÑA: REPORTES Y ENVÍO (ETAPA 2)
# -------------------------------------------------------------
with tab_reportes:
    if st.session_state.rol in ["Entrenador", "Administrador"]:
        st.markdown("### 📊 Centro de Reportes y Proyecciones de Temporada")
        st.caption("Filtra y procesa el volumen acumulado mensual o trimestral para verificar el cumplimiento de marcas competitivas.")
        
        # 1. Filtros de consulta
        c_fil1, c_fil2, c_fil3 = st.columns(3)
        with c_fil1:
            filtro_periodo = st.selectbox("Seleccionar Período", ["Últimos 30 días", "Trimestral (Últimos 90 días)", "Semestral", "Anual", "Todo el histórico"])
        with c_fil2:
            filtro_grupo = st.text_input("Filtrar por Atleta o Categoría", placeholder="Ej: Infantil B o Juan Pérez", value=f"{st.session_state.get('nadador_seleccionado_categoria', '')}")
        with c_fil3:
            modo_envio = st.selectbox("Acción rápida", ["Visualizar reporte", "Preparar envío por WhatsApp", "Enviar por Correo Electrónico"])

        st.markdown("---")

        # Verificar si existen datos en la bitácora
        if "bitacora_historica" not in st.session_state or not st.session_state.bitacora_historica:
            st.info("No hay jornadas de entrenamiento guardadas aún. Ve a la 'Pizarra Diaria' y consolida una jornada para generar reportes.")
        else:
            # Filtrar registros en memoria según grupo/atleta
            registros_filtrados = [
                reg for reg in st.session_state.bitacora_historica 
                if filtro_grupo.lower() in reg['grupo'].lower() or filtro_grupo == ""
            ]

            if not registros_filtrados:
                st.warning(f"No se encontraron registros para el grupo o atleta: `{filtro_grupo}`")
            else:
                # Consolidar métricas del conjunto filtrado
                mts_totales_periodo = sum(r['metros_totales'] for r in registros_filtrados)
                
                estilos_periodo = {}
                for r in registros_filtrados:
                    for est, mts in r['desglose_estilos'].items():
                        estilos_periodo[est] = estilos_periodo.get(est, 0) + mts
                        
                intensidades_periodo = {}
                for r in registros_filtrados:
                    for inte, mts in r['desglose_intensidad'].items():
                        intensidades_periodo[inte] = intensidades_periodo.get(inte, 0) + mts

                # Armar el texto estructurado del reporte
                texto_reporte = f"📈 *REPORTE DE ENTRENAMIENTO Y VOLUMEN*\n"
                texto_reporte += f"👤 *Atleta/Categoría:* {filtro_grupo if filtro_grupo else 'General'}\n"
                texto_reporte += f"📅 *Período:* {filtro_periodo}\n\n"
                texto_reporte += f"🏊‍♂️ *Volumen Total Acumulado:* {mts_totales_periodo:,} metros\n\n"
                
                texto_reporte += f"*Desglose por Estilos:*\n"
                for est, mts in estilos_periodo.items():
                    pct = (mts / mts_totales_periodo) * 100 if mts_totales_periodo > 0 else 0
                    texto_reporte += f"• {est}: {mts:,}m ({pct:.1f}%)\n"
                    
                texto_reporte += f"\n*Distribución de Intensidad:*\n"
                for inte, mts in intensidades_periodo.items():
                    pct = (mts / mts_totales_periodo) * 100 if mts_totales_periodo > 0 else 0
                    texto_reporte += f"• {inte}: {mts:,}m ({pct:.1f}%)\n"
                
                texto_reporte += f"\n💪 ¡Constancia para cumplir con los objetivos del ciclo!"

                # 2. Manejo de vistas según acción seleccionada
                if modo_envio == "Visualizar reporte":
                    st.success("Reporte procesado correctamente en base al volumen acumulado.")
                    st.markdown("### 📄 Lienzo del Informe")
                    st.text_area("Copia este resumen tabulado:", value=texto_reporte, height=300)
                    
                    st.markdown("#### Análisis visual de acumulación")
                    c_est_viz, c_int_viz = st.columns(2)
                    with c_est_viz:
                        st.caption("Metros por Estilo")
                        for est, mts in estilos_periodo.items():
                            pct = (mts / mts_totales_periodo) * 100 if mts_totales_periodo > 0 else 0
                            st.progress(int(pct), text=f"{est}: {mts}m ({pct:.1f}%)")
                    with c_int_viz:
                        st.caption("Intensidad de Trabajo")
                        for inte, mts in intensidades_periodo.items():
                            pct = (mts / mts_totales_periodo) * 100 if mts_totales_periodo > 0 else 0
                            st.progress(int(pct), text=f"{inte}: {mts}m ({pct:.1f}%)")

                elif modo_envio == "Preparar envío por WhatsApp":
                    st.markdown("### 📲 Enlace directo para WhatsApp")
                    st.caption("Haz clic en el botón inferior para abrir WhatsApp Web / App con el reporte precargado y enviarlo a tu grupo.")
                    
                    # Codificar el texto para URL de WhatsApp
                    import urllib.parse
                    texto_url = urllib.parse.quote(texto_reporte)
                    link_whatsapp = f"https://wa.me/?text={texto_url}"
                    
                    st.link_button("Enviar reporte por WhatsApp 🚀", url=link_whatsapp, use_container_width=True)
                    st.divider()
                    st.text_area("Copia el texto por si falla el enlace:", value=texto_reporte, height=200)

                elif modo_envio == "Enviar por Correo Electrónico":
                    st.markdown("### ✉️ Envío por Correo Electrónico")
                    st.caption("Utiliza el servidor SMTP configurado en la app para enviar este reporte de forma masiva o directa.")
                    
                    destinatarios_input = st.text_input("Destinatarios (Separados por comas)", placeholder="entrenador@club.com, atleta@gmail.com")
                    asunto_correo = st.text_input("Asunto del correo", value=f"Reporte de Volumen Acumulado - {filtro_grupo}")
                    
                    if st.button("📧 Enviar Correo Electrónico", type="primary", use_container_width=True):
                        if not destinatarios_input:
                            st.error("Por favor ingresa al menos un correo electrónico de destino.")
                        else:
                            lista_correos = [c.strip() for c in destinatarios_input.split(',')]
                            try:
                                # Configuración servidor SMTP (heredada de la app principal)
                                remitente = "notificaciones@natacion.com" # Ajusta si tienes una variable de entorno o config específica
                                
                                msg = MIMEMultipart()
                                msg['From'] = remitente
                                msg['Subject'] = asunto_correo
                                msg.attach(MIMEText(texto_reporte, 'plain'))
                                
                                # Servidor SMTP de prueba/ejemplo integrado en tu app (reemplazar por servidor real si aplica)
                                server = smtplib.SMTP('smtp.gmail.com', 587)
                                server.starttls()
                                # server.login("tucorreo@gmail.com", "tu-app-password")
                                server.sendmail(remitente, lista_correos, msg.as_string())
                                server.quit()
                                
                                st.success(f"¡Reporte enviado por correo a {len(lista_correos)} destinatario(s) exitosamente!")
                            except Exception as e:
                                st.warning(f"No se pudo conectar con el servidor SMTP automáticamente. Te dejamos el texto plano para respaldar:")
                                st.text_area("Respaldo de correo:", value=texto_reporte, height=200)
    else:
        st.warning("🔒 Sección restringida al equipo técnico.")
