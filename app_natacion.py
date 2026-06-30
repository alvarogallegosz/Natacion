# =============================================================================
# 📄 app_natacion.py - ORQUESTADOR CENTRAL (INYECCIÓN ABSOLUTA DE RUTAS)
# =============================================================================
import streamlit as st
import os
import sys

# 1. BLINDAJE ABSOLUTO DE RUTAS (Asegura la raíz antes de cualquier importación)
ruta_raiz = os.path.dirname(os.path.abspath(__file__))
if ruta_raiz not in sys.path:
    sys.path.insert(0, ruta_raiz)

# 2. CONFIGURACIÓN ESTRUCTURAL DE LA PÁGINA
st.set_page_config(
    page_title="Swimming Club Proyections, Schedules and Reports",
    page_icon="🏊‍♂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 3. IMPORTACIONES PROTEGIDAS DEL CORE DE INFRAESTRUCTURA
from core.conexion import (
    obtener_cliente_supabase, 
    autenticar_usuario, 
    inyectar_estilos_globales,
    limpiar_todo_el_cache
)
from views.sidebar import renderizar_sidebar
from views.rendimiento import mostrar_modulo_rendimiento
from views.enrutador_gestion import mostrar_enrutador_gestion

# Inicialización obligatoria del cliente de base de datos y estilos CSS estandarizados
supabase = obtener_cliente_supabase()
inyectar_estilos_globales()

# 4. INICIALIZACIÓN DE VARIABLES DE CONTROL GLOBAL DE SESIÓN
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_id" not in st.session_state:
    st.session_state.usuario_id = None
if "nombre" not in st.session_state:
    st.session_state.nombre = ""
if "rol" not in st.session_state:
    st.session_state.rol = ""
if "menu_actual" not in st.session_state:
    st.session_state.menu_actual = "📊 Rendimiento y Proyecciones"

# 5. PORTAL DE ACCESO SEGURO (FORMULARIO DE LOGIN)
from views.autenticacion import mostrar_interfaz_autenticacion

if not st.session_state.autenticado:
    mostrar_interfaz_autenticacion()
    st.stop()  # Frena el renderizado del resto de las pestañas si no está logueado

# 6. ENTORNO DE TRABAJO SEGURO (USUARIO AUTENTICADO)
else:
    # Carga y renderizado de la Barra Lateral. Retorna si el escudo de simulación está activo.
    simulacion_activa = renderizar_sidebar()
    
    # Selector de pestañas principales inyectado en el área superior central
    pestana_seleccionada = st.radio(
        label="Navegación del Ecosistema",
        options=["📊 Rendimiento y Proyecciones", "🗂️ Panel de Gestión Operativa"],
        index=0 if st.session_state.menu_actual == "📊 Rendimiento y Proyecciones" else 1,
        horizontal=True,
        label_visibility="collapsed"
    )
    st.session_state.menu_actual = pestana_seleccionada
    st.markdown("---")
    
    # Botón de control manual: Comodín de limpieza absoluta de Caché en sesión
    col_vacia, col_limpiar = st.columns([6, 1.2])
    with col_limpiar:
        if st.button("🧹 Limpiar Caché General", use_container_width=True, help="Forzar la recarga inmediata de todas las tablas desde Supabase"):
            limpiar_todo_el_cache()
            st.toast("⚡ Caché del sistema restablecido por completo.")
            st.rerun()

    # Enrutamiento modular hacia las vistas especializadas según la pestaña activa
    if st.session_state.menu_actual == "📊 Rendimiento y Proyecciones":
        mostrar_modulo_rendimiento(simulacion_externa=simulacion_activa)
    elif st.session_state.menu_actual == "🗂️ Panel de Gestión Operativa":
        mostrar_enrutador_gestion()