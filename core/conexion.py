# =============================================================================
# 📁 core/conexion.py - INFRAESTRUCTURA, DISEÑO, HASH Y CORTAFUEGOS GLOBAL
# =============================================================================
import streamlit as st
import pandas as pd
import hashlib
from supabase import create_client, Client

def obtener_cliente_supabase() -> Client:
    """Garantiza un único punto de acceso al cliente de Supabase en el session_state."""
    if "supabase_client" not in st.session_state:
        try:
            url: str = st.secrets["SUPABASE_URL"]
            key: str = st.secrets["SUPABASE_KEY"]
            st.session_state["supabase_client"] = create_client(url, key)
        except Exception as e:
            st.error("❌ Error Crítico de Infraestructura: Faltan credenciales en Secrets.")
            st.stop()
    return st.session_state["supabase_client"]

def generar_hash_sha256(contrasena: str) -> str:
    """Genera un hash SHA-256 seguro a partir de una cadena de texto plano."""
    return hashlib.sha256(contrasena.encode('utf-8')).hexdigest()

def autenticar_usuario(usuario_input: str, contrasena_input: str) -> bool:
    """Valida credenciales comparando el hash de la contraseña ingresada."""
    supabase = obtener_cliente_supabase()
    try:
        respuesta = supabase.table("usuarios")\
            .select("id, usuario, contrasena, nombre, rol, genero, estatus, fecha_nacimiento")\
            .eq("usuario", usuario_input.strip())\
            .execute()
            
        if respuesta.data:
            usuario_db = respuesta.data[0]
            hash_input = generar_hash_sha256(contrasena_input)
            
            # Validación por Hash SHA-256
            if usuario_db["contrasena"] == hash_input:
                if usuario_db["estatus"] != "Activo":
                    st.error(f"🔒 Acceso Denegado: Tu cuenta está en estado '{usuario_db['estatus']}'. Contacta al Administrador.")
                    return False
                
                # Inicialización segura del Estado de Sesión
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
        st.error(f"Error crítico en autenticación: {e}")
        return False

def inyectar_estilos_globales():
    """Inyecta el diseño CSS responsivo para el ecosistema visual de la plataforma."""
    st.markdown("""
        <style>
        .tabla-estilizada { width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 14px; }
        .tabla-estilizada th { background-color: #0F4C81; color: white; padding: 10px; text-align: left; }
        .tabla-estilizada td { padding: 8px; border-bottom: 1px solid #E0E0E0; }
        </style>
    """, unsafe_allow_html=True)