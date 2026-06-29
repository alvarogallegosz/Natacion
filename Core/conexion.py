# =============================================================================
# 📁 core/conexion.py - INFRAESTRUCTURA, DISEÑO Y CORTAFUEGOS GLOBAL
# =============================================================================
import streamlit as st
import pandas as pd
from supabase import create_client, Client

# =============================================================================
# 📍 CHECKPOINT 1: INICIALIZACIÓN LIMPIA Y UNIFICADA DE SUPABASE
# =============================================================================
def obtener_cliente_supabase() -> Client:
    """
    Garantiza un único punto de acceso al cliente de Supabase en todo el ecosistema.
    Elimina conexiones duplicadas (como ctx_supabase) y previene la latencia.
    Actúa como disyuntor térmico deteniendo la app si faltan credenciales en secrets.
    """
    if "supabase_client" not in st.session_state:
        try:
            url: str = st.secrets["SUPABASE_URL"]
            key: str = st.secrets["SUPABASE_KEY"]
            # Inyección directa en el session_state para sincronía con la caché
            st.session_state["supabase_client"] = create_client(url, key)
        except Exception as e:
            st.error("❌ Error Crítico de Infraestructura: Faltan las credenciales de acceso 'SUPABASE_URL' o 'SUPABASE_KEY' en los Secrets de la aplicación.")
            st.stop()
            
    return st.session_state["supabase_client"]


# =============================================================================
# 📍 CHECKPOINT 2: INYECCIÓN DE ESTILOS E INMUNIZACIÓN VISUAL (CSS GLOBAL)
# =============================================================================
def inyectar_estilos_globales():
    """
    Inyecta la hoja de estilos centralizada para el club.
    Garantiza que todas las tablas, incluyendo el laboratorio de Bannister, 
    compartan la misma identidad visual limpia, adaptada y profesional.
    """
    css_club = """
    <style>
        /* Estilizado unificado para Tablas de Datos Federativos y Cargas */
        .tabla-estilizada {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            font-size: 0.95em;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            min-width: 400px;
            box-shadow: 0 0 12px rgba(0, 0, 0, 0.08);
            border-radius: 6px;
            overflow: hidden;
        }
        .tabla-estilizada thead tr {
            background-color: #0F4C81;
            color: #ffffff;
            text-align: left;
            font-weight: bold;
        }
        .tabla-estilizada th, .tabla-estilizada td {
            padding: 10px 12px;
            border-bottom: 1px solid #dddddd;
        }
        .tabla-estilizada tbody tr:nth-of-type(even) {
            background-color: #f8f9fa;
        }
        .tabla-estilizada tbody tr:last-of-type {
            border-bottom: 3px solid #0F4C81;
        }
        .tabla-estilizada tbody tr:hover {
            background-color: #f1f3f5;
            transition: background 0.2s ease;
        }
        /* Contenedores de KPIs y Fichas Técnicas */
        .metric-card {
            background-color: #ffffff;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.05);
            border-left: 5px solid #0F4C81;
        }
    </style>
    """
    st.markdown(css_club, unsafe_allow_html=True)


# =============================================================================
# 📍 CHECKPOINT 3: CORTAFUEGOS DE ACCESO Y VALIDACIÓN DE ESTATUS
# =============================================================================
def autenticar_usuario(usuario_input: str, contrasena_input: str) -> bool:
    """
    Ejecuta el control de acceso estricto a la base de datos de Supabase.
    Valida contraseñas de forma segura y aplica el cortafuegos de cuentas:
    Solo permite el ingreso si el estatus del registro es estrictamente 'Activo'.
    """
    supabase = obtener_cliente_supabase()
    
    try:
        # Consulta limpia apuntando a la tabla usuarios resguardada en el Archivo 21
        respuesta = supabase.table("usuarios")\
            .select("id, usuario, contrasena, nombre, rol, genero, estatus, fecha_nacimiento")\
            .eq("usuario", usuario_input)\
            .execute()
            
        if respuesta.data:
            usuario_db = respuesta.data[0]
            
            # 1. Validación de Credencial (Contraseña estándar del club)
            if usuario_db["contrasena"] == contrasena_input:
                
                # 2. CORTAFUEGOS DE SEGURIDAD MÁXIMA (Conexión con el Checkpoint 15 / Admin)
                if usuario_db["estatus"] != "Activo":
                    st.error(f"🔒 Acceso Denegado: Tu cuenta se encuentra en estado '{usuario_db['estatus']}'. Por favor, coordina con el Administrador o Head Coach del club.")
                    return False
                
                # 3. Inicialización segura del Estado de Sesión (Session State Global)
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
            st.error("❌ El nombre de usuario especificado no existe en el sistema.")
            return False
            
    except Exception as e:
        st.error(f"Error crítico en el proceso de autenticación: {e}")
        return False