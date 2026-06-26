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
        if edad_tecnica < 14:
            return False, f"Edad técnica insuficiente ({edad_tecnica} años). Mínimo requerido: 14 años."
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
            nuevo_rol = st.selectbox("Seleccione el Rol para la nueva cuenta:", options=["Nadador", "Head Coach", "Entrenador", "Administrador"], key="reg_rol_selector")
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
                                status_inicial = "Pendiente" if nuevo_rol in ["Head Coach", "Entrenador", "Administrador"] else "Activo"
                                
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
            ax = fig.add_axes([0.14, 0.52, 0.72, 0.33])
            
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
                ins_tiempo = st.number_input("Tiempo Oficial (seg):", min_value=20.0,  max_value=1800.0, step=0.01)
                ins_nota = st.text_input("Evento / Fecha:")
                
                if st.form_submit_button("💾 Guardar Registro"):
                    if st.session_state.rol in ["Head Coach", "Entrenador", "Administrador"] or st.session_state.usuario_id == st.session_state.nadador_seleccionado_id:
                        try:
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
                    intensidad = st.selectbox("Intensidad / Ritmo", ["Suave (Aeróbico Ligero 3-4)", "Medio (Aeróbico Medio 5-6)", "Fuerte (Umbral 7-8)", "Sprint (Máximo 9-10)", "Ritmo de Competencia"], key="piz_int")
                with c_imp:
                    implementos = st.multiselect("Implementos", ["Aletas", "Paletas", "Tabla", "Pullbuoy", "Snorkel", "Paracaídas", "Ligas"], key="piz_imp")
                with c_not:
                    notas = st.text_input("Instrucciones breves (Opcional)", placeholder="Ej: Respiración c/3, Descanso 20s", key="piz_not")

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
                        resp_sb = ctx_supabase.table("usuarios").select("id, nombre, email, genero, fecha_nacimiento").eq("rol", "Nadador").eq("estatus", "Activo").execute()
                        if resp_sb.data:
                            atletas_pool = resp_sb.data
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
    # PESTAÑA: REPORTES Y RENDIMIENTO HISTÓRICO (SOLUCIÓN DE FLUJO CONTINUO)
    # -------------------------------------------------------------
    with tab_reportes:
        if st.session_state.rol in ["Head Coach", "Entrenador", "Administrador"]:        
            st.markdown("### 📊 Panel de Control y Análisis de Carga")
            st.caption("Filtra la nómina de la misma forma que en la pizarra y define la ventana temporal para evaluar el volumen acumulado y el modelo matemático de Bannister.")

            # Extracción del cliente de base de datos de forma directa
            supabase = st.session_state.get("supabase_client")

            # =============================================================================
            # ESTILOS CSS INYECTADOS PARA IMPRESIÓN LIMPIA EN 8.5 x 11 (CARTA)
            # =============================================================================
            st.markdown("""
                <style>
                /* Clase global para estilizar las tablas de auditoría en pantalla */
                .tabla-estilizada {
                    width: 100%;
                    border-collapse: collapse;
                    margin: 15px 0;
                    font-size: 13px;
                    font-family: sans-serif;
                }
                .tabla-estilizada th {
                    background-color: #f2f2f2;
                    color: #333333;
                    font-weight: bold;
                    padding: 8px;
                    border: 1px solid #dddddd;
                    text-align: center;
                }
                .tabla-estilizada td {
                    padding: 6px 8px;
                    border: 1px solid #dddddd;
                    text-align: center;
                }
                
                /* REGLAS DE OPTIMIZACIÓN MULTIMEDIA PARA IMPRESIÓN REAL */
                @media print {
                    /* Ocultar barra lateral, barra superior de Streamlit y botones de control */
                    [data-testid="stSidebar"], header, [data-testid="stHeader"], .stButton, button, .stSelectbox {
                        display: none !important;
                    }
                    /* Forzar que el contenedor principal use todo el ancho disponible */
                    .main .block-container {
                        padding-top: 1rem !important;
                        padding-bottom: 1rem !important;
                        max-width: 100% !important;
                        width: 100% !important;
                    }
                    /* Evitar rupturas huérfanas de gráficos y tablas a mitad de página */
                    .stMarkdown, .stPlotlyChart, div.stMatplotlib {
                        page-break-inside: avoid !important;
                    }
                    body {
                        color: #000000 !important;
                        background-color: #ffffff !important;
                    }
                }
                </style>
            """, unsafe_allow_html=True)

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
                index=3,  # Defecto en 42 días por su relevancia científica en el rendimiento
                key="rep_selectbox_temporalidad"
            )
            
            dias_atras = opciones_tiempo[ventana_sel]
            
            # =============================================================================
            # 2. SELECTORES DE FILTRADO COHERENTES CON LA PIZARRA
            # =============================================================================
            col_rep1, col_rep2, col_rep3 = st.columns(3)
            
            with col_rep1:
                sedes_disponibles = []
                if supabase:
                    try:
                        res_sedes = supabase.table("usuarios").select("sede").execute()
                        sedes_disponibles = sorted(list(set([u["sede"] for u in res_sedes.data if u.get("sede")]))) if res_sedes.data else []
                    except:
                        pass
                sedes_opciones = ["Todas"] + sedes_disponibles
                sede_rep = st.selectbox("📍 Filtrar por Sede:", sedes_opciones, key="rep_filtro_sede")
                
            with col_rep2:
                categorias_opciones = ["Todas", "Infantil A", "Infantil B", "Juvenil A", "Juvenil B", "Máxima"]
                cat_rep = st.selectbox("🏊‍♂️ Filtrar por Categoría:", categorias_opciones, key="rep_filtro_categoria")
                
            with col_rep3:
                genero_opciones = ["Todos", "Masculino", "Femenino"]
                gen_rep = st.selectbox("🧬 Filtrar por Género:", genero_opciones, key="rep_filtro_genero")
                
            # =============================================================================
            # 3. CARGA DE ATLETAS FILTRADOS Y CÓMPUTO DE BANNISTER (LÓGICA ORIGINAL INTEGRAL)
            # =============================================================================
            if not supabase:
                st.warning("🔌 Sincronizando enlace de datos con el ecosistema Supabase... Si este mensaje persiste por más de 3 segundos, interactúa con cualquier filtro superior para despertar la sesión.")
            else:
                atleta_ids = []
                if st.session_state.rol == "Entrenador":
                    try:
                        res_asig = supabase.table("asignaciones_entrenador").select("nadador_id").eq("entrenador_id", st.session_state.usuario_id).execute()
                        if res_asig.data:
                            atleta_ids = [r["nadador_id"] for r in res_asig.data]
                    except Exception as e:
                        st.error(f"Error al cargar atletas asignados: {e}")
                
                query_atlt = supabase.table("usuarios").select("id, nombre, apellido").eq("rol", "Nadador")
                
                if st.session_state.rol == "Entrenador":
                    if atleta_ids:
                        query_atlt = query_atlt.in_("id", atleta_ids)
                    else:
                        query_atlt = query_atlt.eq("id", "00000000-0000-0000-0000-000000000000")
                        
                if sede_rep != "Todas":
                    query_atlt = query_atlt.eq("sede", sede_rep)
                if cat_rep != "Todas":
                    query_atlt = query_atlt.eq("categoria", cat_rep)
                if gen_rep != "Todos":
                    query_atlt = query_atlt.eq("genero", gen_rep)
                    
                res_atlt = query_atlt.execute()
                
                if not res_atlt.data:
                    st.info("No se encontraron nadadores bajo los filtros seleccionados.")
                else:
                    atletas_opciones_carga = {a["id"]: f"{a['nombre']} {a['apellido']}" for a in res_atlt.data}
                    atleta_sel_id = st.selectbox(
                        "🎯 Seleccione el Nadador para el Reporte Analítico:",
                        options=list(atletas_opciones_carga.keys()),
                        format_func=lambda x: atletas_opciones_carga[x],
                        key="rep_atleta_analisis_id"
                    )
                    
                    if atleta_sel_id:
                        try:
                            query_bit = supabase.table("bitacora_nadador").select("*").eq("nadador_id", atleta_sel_id).order("fecha", ascending=True)
                            res_bit = query_bit.execute()
                            
                            if not res_bit.data:
                                st.warning(f"El nadador {atletas_opciones_carga[atleta_sel_id]} no posee registros de volumen en su bitácora.")
                            else:
                                df_bit = pd.DataFrame(res_bit.data)
                                df_bit["fecha"] = pd.to_datetime(df_bit["fecha"])
                                
                                df_diario = df_bit.groupby("fecha")["volumen_metros"].sum().reset_index()
                                df_diario.columns = ["Fecha", "Volumen"]
                                
                                fecha_min = df_diario["Fecha"].min()
                                fecha_max = datetime.date.today()
                                fecha_max = pd.to_datetime(fecha_max)
                                
                                rango_fechas = pd.date_range(start=fecha_min, end=fecha_max, freq="D")
                                df_cargas = pd.DataFrame({"Fecha": rango_fechas})
                                df_cargas = df_cargas.merge(df_diario, on="Fecha", how="left")
                                df_cargas["Volumen"] = df_cargas["Volumen"].fillna(0)
                                
                                # --- CÓMPUTO MATEMÁTICO DEL MODELO BANNISTER ---
                                tau_ctl, tau_atl = 42, 7
                                k1, k2 = 1.0, 2.0
                                
                                ctl_vals, atl_vals, tsb_vals = [], [], []
                                ctl_ant, atl_ant = 0.0, 0.0
                                
                                for idx, row in df_cargas.iterrows():
                                    w = row["Volumen"]
                                    ctl_actual = ctl_ant * np.exp(-1.0 / tau_ctl) + w
                                    atl_actual = atl_ant * np.exp(-1.0 / tau_atl) + w
                                    tsb_actual = (ctl_ant * k1) - (atl_ant * k2)
                                    
                                    ctl_vals.append(ctl_actual)
                                    atl_vals.append(atl_actual)
                                    tsb_vals.append(tsb_actual)
                                    
                                    ctl_ant, atl_ant = ctl_actual, atl_actual
                                    
                                df_cargas["CTL"] = ctl_vals
                                df_cargas["ATL"] = atl_vals
                                df_cargas["TSB"] = tsb_vals
                                
                                if dias_atras:
                                    fecha_corte = pd.to_datetime(datetime.date.today() - datetime.timedelta(days=dias_atras))
                                    df_cargas = df_cargas[df_cargas["Fecha"] >= fecha_corte].copy()
                                
                                if df_cargas.empty:
                                    st.info("No existen métricas acumuladas en la ventana de tiempo seleccionada.")
                                else:
                                    # Gráfico original estable
                                    fig_ban, ax = plt.subplots(figsize=(10, 4.5))
                                    ax.plot(df_cargas["Fecha"], df_cargas["CTL"], label="Fitness / Capacidad Crónica (CTL)", color="#1f77b4", linewidth=2.5)
                                    ax.plot(df_cargas["Fecha"], df_cargas["ATL"], label="Respuesta Aguda / Fatiga (ATL)", color="#d62728", linewidth=1.5, linestyle="--")
                                    ax.bar(df_cargas["Fecha"], df_cargas["TSB"], label="Balance de Forma (TSB)", color="#2ca02c", alpha=0.35, width=1.0)
                                    
                                    ax.set_title(f"Evolución del Perfil Fisiológico: {atletas_opciones_carga[atleta_sel_id]}", fontsize=11, fontweight="bold")
                                    ax.grid(True, linestyle=":", alpha=0.4)
                                    ax.legend(loc="upper left", fontsize=8)
                                    plt.xticks(rotation=25, fontsize=8)
                                    plt.tight_layout()
                                    
                                    st.pyplot(fig_ban)
                                    
                                    # =============================================================================
                                    # BOTÓN DE IMPRESIÓN JAVASCRIPT ACTIVO Y SEGURO
                                    # =============================================================================
                                    st.markdown(f"""
                                        <div style="margin-top: 10px; margin-bottom: 25px;">
                                            <button onclick="window.print()" style="width: 100%; background-color: #007A87; color: white; border: none; padding: 12px; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: bold;">
                                                🖨️ Imprimir Perfil Fisiológico Bannister (8.5 x 11 / PDF)
                                            </button>
                                        </div>
                                    """, unsafe_allow_html=True)
                                    
                                    st.markdown("##### 📋 Tabla de Valores Diarios y Métricas de Estado")
                                    df_tabla_ban = df_cargas.copy()
                                    df_tabla_ban["Fecha"] = df_tabla_ban["Fecha"].dt.strftime("%Y-%m-%d")
                                    
                                    csv_ban_data = df_tabla_ban.to_csv(index=False).encode('utf-8')
                                    
                                    txt_ban_buffer = io.StringIO()
                                    txt_ban_buffer.write("=========================================================\n")
                                    txt_ban_buffer.write(f" HISTÓRICO DIARIO DE CARGAS E ÍNDICES - ATLETA: {atletas_opciones_carga[atleta_sel_id].upper()}\n")
                                    txt_ban_buffer.write(f" Generado el: {datetime.date.today()} | Ventana: {ventana_sel}\n")
                                    txt_ban_buffer.write("=========================================================\n\n")
                                    txt_ban_buffer.write(df_tabla_ban.to_string(index=False))
                                    txt_ban_data = txt_ban_buffer.getvalue().encode('utf-8')
                                    
                                    fila_tot_ban = {
                                        "Fecha": "TOTAL ACUMULADO",
                                        "Volumen": df_tabla_ban["Volumen"].sum(),
                                        "CTL": "", "ATL": "", "TSB": ""
                                    }
                                    df_tabla_visual = pd.concat([df_tabla_ban, pd.DataFrame([fila_tot_ban])], ignore_index=True)
                                    st.write(df_tabla_visual.to_html(index=False, classes="tabla-estilizada"), unsafe_allow_html=True)
                                    
                                    # Botones tradicionales de descarga al final de la matriz
                                    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
                                    col_down_ban1, col_down_ban2 = st.columns(2)
                                    
                                    with col_down_ban1:
                                        st.download_button(
                                            label="📥 Descargar Histórico Diario (CSV)",
                                            data=csv_ban_data,
                                            file_name=f"historico_bannister_{atleta_sel_id}_{datetime.date.today()}.csv",
                                            mime="text/csv",
                                            key=f"btn_csv_ban_{atleta_sel_id}",
                                            use_container_width=True
                                        )
                                        
                                    with col_down_ban2:
                                        st.download_button(
                                            label="📄 Descargar Histórico Diario (TXT)",
                                            data=txt_ban_data,
                                            file_name=f"historico_bannister_{atleta_sel_id}_{datetime.date.today()}.txt",
                                            mime="text/plain",
                                            key=f"btn_txt_ban_{atleta_sel_id}",
                                            use_container_width=True
                                        )
                                    
                        except Exception as e:
                            st.error(f"Error al computar el reporte analítico avanzado: {e}")             
        else:
            st.warning("🔒 Esta función está reservada para el equipo técnico (Entrenadores y Administradores).")
