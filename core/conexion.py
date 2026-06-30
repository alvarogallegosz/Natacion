# =============================================================================
# 📁 core/conexion.py - INFRAESTRUCTURA, CACHÉ, SEGURIDAD Y SERVICIOS DE CORREO
# =============================================================================
import streamlit as st
import hashlib
import pandas as pd
from supabase import create_client, Client

# Módulos para la infraestructura del servidor de correos (Protocolo SMTP)
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# -----------------------------------------------------------------------------
# 🎯 1. GESTIÓN DE INFRAESTRUCTURA Y BASE DE DATOS (SUPABASE)
# -----------------------------------------------------------------------------

def obtener_cliente_supabase() -> Client:
    """
    Garantiza un único punto de acceso al cliente de Supabase en el session_state.
    Si las credenciales no existen en los secretos del entorno, detiene la app.
    """
    if "supabase_client" not in st.session_state:
        try:
            url: str = st.secrets["SUPABASE_URL"]
            key: str = st.secrets["SUPABASE_KEY"]
            st.session_state["supabase_client"] = create_client(url, key)
        except Exception as e:
            st.error("❌ Error Crítico de Infraestructura: Faltan credenciales en Secrets (SUPABASE_URL / SUPABASE_KEY).")
            st.stop()
    return st.session_state["supabase_client"]


# -----------------------------------------------------------------------------
# 🔒 2. SEGURIDAD, ENCRIPTACIÓN Y CONTROL DE ACCESO
# -----------------------------------------------------------------------------

def generar_hash_sha256(contrasena: str) -> str:
    """
    Genera un hash SHA-256 seguro a partir de una cadena de texto plano.
    Se utiliza para el resguardo y verificación de credenciales de usuarios.
    """
    return hashlib.sha256(contrasena.encode('utf-8')).hexdigest()


def autenticar_usuario(usuario_input: str, contrasena_input: str) -> bool:
    """
    Valida las credenciales comparando el hash de la contraseña ingresada
    con el registro de la base de datos. Inicializa el entorno de sesión si es exitoso.
    """
    supabase = obtener_cliente_supabase()
    try:
        respuesta = supabase.table("usuarios").select("*").eq("usuario", usuario_input).execute()
        
        if respuesta.data and len(respuesta.data) > 0:
            usuario_db = respuesta.data[0]
            hash_ingresado = generar_hash_sha256(contrasena_input)
            
            if usuario_db["contrasena"] == hash_ingresado:
                if usuario_db.get("estatus") != "Activo":
                    st.error(f"🔒 El usuario se encuentra en estado: '{usuario_db.get('estatus')}'. Contacte al Administrador.")
                    return False
                
                # Inicialización segura del Estado de Sesión con datos completos
                st.session_state.autenticado = True
                st.session_state.usuario_id = usuario_db["id"]
                st.session_state.usuario = usuario_db["usuario"]
                st.session_state.nombre = usuario_db["nombre"]
                st.session_state.rol = usuario_db["rol"]
                st.session_state.genero_usuario = usuario_db["genero"]
                st.session_state.fecha_nacimiento_usuario = usuario_db["fecha_nacimiento"]
                return True
            else:
                st.error("❌ Contraseña incorrecta. Inténtalo de nuevo.")
                return False
        else:
            st.error("❌ El nombre de usuario especificado no existe.")
            return False
    except Exception as e:
        st.error(f"Error crítico en el proceso de autenticación: {e}")
        return False


# -----------------------------------------------------------------------------
# 📧 3. SERVICIO POSTAL Y NOTIFICACIONES AUTOMÁTICAS (SMTP)
# -----------------------------------------------------------------------------

def enviar_email(asunto: str, cuerpo: str, destinatario: str) -> bool:
    """
    Orquesta y despacha correos electrónicos informativos a través del servidor
    SMTP seguro (SSL). Consume de manera estricta los secretos de la aplicación.
    """
    try:
        msg = MIMEMultipart()
        msg['From'] = st.secrets["EMAIL_REMITE"]
        msg['To'] = destinatario
        msg['Subject'] = asunto
        msg.attach(MIMEText(cuerpo, 'plain'))

        # Conexión cifrada directa al servidor SMTP configurado
        servidor = st.secrets["EMAIL_SMTP_SERVER"]
        puerto = int(st.secrets["EMAIL_SMTP_PORT"])
        cuenta_remite = st.secrets["EMAIL_REMITE"]
        credencial_remite = st.secrets["EMAIL_PASSWORD"]

        with smtplib.SMTP_SSL(servidor, puerto) as server:
            server.login(cuenta_remite, credencial_remite)
            server.sendmail(cuenta_remite, destinatario, msg.as_string())
        return True
    except Exception as e:
        print(f"Error interno al despachar correo electrónico: {e}")
        return False


# -----------------------------------------------------------------------------
# 🎯 4. SISTEMA DE CACHÉ INTELIGENTE Y RESTRICCIONES DE TIEMPO (TTL) - OPTIMIZADO
# -----------------------------------------------------------------------------

def limpiar_todo_el_cache():
    """
    Función comodín drástica para invalidar de inmediato toda la memoria temporal.
    Fuerza a la aplicación a consultar datos frescos directamente de Supabase.
    """
    st.cache_data.clear()

# --- FUNCIONES DE INVALIDACIÓN EN CALIENTE SELECTIVAS ---

def invalidar_cache_marcas():
    """Limpia en caliente únicamente las consultas asociadas a marcas e hitos."""
    obtener_marcas_historicas_cache.clear()
    obtener_marcas_atleta.clear()

def invalidar_cache_nomina():
    """Limpia en caliente las nóminas, asignaciones y usuarios cuando hay cambios de personal."""
    obtener_usuarios_cache.clear()
    obtener_nomina_nadadores_activos.clear()
    obtener_asignaciones_cache.clear()


@st.cache_data(ttl=86400, show_spinner=False)
def obtener_marcas_referencia_cache() -> list:
    """
    Carga la tabla completa de marcas de referencia nacionales e internacionales.
    Estructura estática con persistencia en caché por 24 horas (86400 segundos).
    """
    try:
        supabase = obtener_cliente_supabase()
        response = supabase.table("marcas_referencia").select("*").execute()
        return response.data if response.data else []
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def obtener_marcas_historicas_cache(usuario_id: int = None) -> list:
    """
    Carga el historial de marcas registradas. Estructura volátil con caché de 5 minutos.
    Si se especifica un usuario_id, filtra los controles exclusivamente para ese atleta.
    """
    try:
        supabase = obtener_cliente_supabase()
        query = supabase.table("marcas_historicas").select("*")
        if usuario_id:
            query = query.eq("usuario_id", usuario_id)
        response = query.execute()
        return response.data if response.data else []
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def obtener_usuarios_cache(rol: str = None) -> list:
    """
    Carga la nómina completa de usuarios registrados. Caché de 5 minutos.
    Permite el filtrado opcional por jerarquía ('Nadador', 'Entrenador').
    """
    try:
        supabase = obtener_cliente_supabase()
        query = supabase.table("usuarios").select("*")
        if rol:
            query = query.eq("rol", rol)
        response = query.execute()
        return response.data if response.data else []
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def obtener_asignaciones_cache() -> list:
    """
    Carga el mapeo completo de asignaciones de carriles y atletas a entrenadores.
    Caché de 5 minutos para asimilar cambios estructurales de la nómina.
    """
    try:
        supabase = obtener_cliente_supabase()
        response = supabase.table("asignaciones").select("*").execute()
        return response.data if response.data else []
    except Exception:
        return []

# =============================================================================
# 📁 EXTENSIONES DE CONSULTA MAESTRA (MODO EQUIPO E INDIVIDUAL)
# =============================================================================

@st.cache_data(ttl=300, show_spinner=False)
def obtener_nomina_nadadores_activos():
    """
    Consulta la base de datos y extrae la nómina completa de nadadores 
    en estado 'Activo'. Almacena en caché por 5 minutos para agilizar el modo equipo.
    """
    try:
        supabase = obtener_cliente_supabase()
        response = (
            supabase.table("usuarios")
            .select("id, nombre, fecha_nacimiento, genero")
            .eq("rol", "Nadador")
            .eq("estatus", "Activo")
            .execute()
        )
        return response.data if response.data else []
    except Exception as e:
        st.error(f"❌ Error en core.conexion al obtener nómina activa: {e}")
        return []


@st.cache_data(ttl=120, show_spinner=False)
def obtener_marcas_atleta(atleta_id: str):
    """
    Extrae el histórico completo de marcas, tiempos oficiales e hitos de un 
    atleta específico en base a su ID único.
    """
    try:
        if not atleta_id:
            return []
        supabase = obtener_cliente_supabase()
        
        # NOTA: Asegúrate de que tus vistas apunten de forma consistente a 'historial_hitos' o 'marcas_historicas'
        response = (
            supabase.table("historial_hitos")
            .select("id, atleta_id, fecha, distancia, estilo, tiempo, tipo_piscina_metros")
            .eq("atleta_id", atleta_id)
            .order("fecha", ascending=True)
            .execute()
        )
        return response.data if response.data else []
    except Exception as e:
        st.error(f"❌ Error en core.conexion al obtener marcas del atleta [{atleta_id}]: {e}")
        return []

# -----------------------------------------------------------------------------
# 🎨 5. INTERFAZ Y ESTILIZACIÓN DE TABLAS HTML REPORTE
# -----------------------------------------------------------------------------

def inyectar_estilos_globales():
    """
    Inyecta el nuevo esquema de estilización global para todas las tablas de la
    plataforma (Reportes, Gestión e Historiales), garantizando el look elegante.
    """
    st.markdown("""
        <style>
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
            color: #111111 !important;
        }
        </style>
    """, unsafe_allowed_html=True)


def verificar_permiso_accion(rol_usuario: str, accion: str) -> bool:
    """
    Cortafuegos de operaciones en Supabase basado en el rol del usuario activo.
    Acciones: 'crear_competencia', 'gestionar_minimas', 'asignar_entrenadores', 
              'administrar_usuarios', 'crear_entrenamiento_global'
    """
    rol = str(rol_usuario).lower()
    
    if rol == "administrador":
        return True  # Acceso absoluto e irrestricto
        
    if rol == "head coach":
        # Puede hacer todo excepto funciones de IT (administrar perfiles/suspensiones)
        permisos_hc = ['crear_competencia', 'gestionar_minimas', 'asignar_entrenadores', 'crear_entrenamiento_global', 'ver_todo']
        return accion in permisos_hc
        
    if rol == "entrenador":
        # Solo gestiona lo propio de sus atletas asignados (controlado en las vistas)
        permisos_coach = ['crear_entrenamiento_propio', 'editar_marcas_propias']
        return accion in permisos_coach
        
    if rol == "nadador":
        # Permisos mínimos de lectura y simulación
        permisos_nadador = ['ver_marcas_propias', 'simular_local']
        return accion in permisos_nadador
        
    return False