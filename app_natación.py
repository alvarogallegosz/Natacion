# =============================================================================
# 📄 app.py - ORQUESTADOR CENTRAL DEL SISTEMA (ACOPLE FINAL)
# =============================================================================
import streamlit as st

# Configuración obligatoria de la página (Debe ser la primera instrucción)
st.set_page_config(
    page_title="Plataforma de Analítica - Club de Natación",
    page_icon="🏊‍♂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Imports de la infraestructura del Core
from core.conexion import obtener_cliente_supabase, inyectar_estilos_globales, autenticar_usuario

# 1. Inicializar cimientos de datos e inyectar CSS global
obtener_cliente_supabase()
inyectar_estilos_globales()

# 2. Inicializar variables críticas del estado de sesión si no existen
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

# =============================================================================
# FLUJO DE CONTROL DE ACCESO (CORTAFUEGOS)
# =============================================================================
if not st.session_state.autenticado:
    # Centrar el formulario estéticamente en pantalla
    _, col_login, _ = st.columns([1, 1.5, 1])
    
    with col_login:
        st.markdown("## 🏊‍♂️ Sistema de Gestión Técnico-Deportiva")
        st.caption("Ingrese sus credenciales federativas para acceder a la plataforma analítica.")
        
        with st.form("formulario_login"):
            usuario_input = st.text_input("Usuario:", placeholder="Ej: Alvaro_Gallegos")
            contrasena_input = st.text_input("Contraseña:", type="password")
            boton_ingresar = st.form_submit_button("🚀 Iniciar Sesión", use_container_width=True)
            
            if boton_ingresar:
                if usuario_input.strip() == "" or contrasena_input.strip() == "":
                    st.warning("⚠️ Por favor, complete ambos campos.")
                else:
                    # Invoca la función defensiva que valida estatus e integridad
                    if autenticar_usuario(usuario_input, contrasena_input):
                        st.rerun()
else:
    # ------------------------------------------------------------------------
    # USUARIO AUTENTICADO -> CARGA DEL ENTORNO MODULAR DINÁMICO
    # ------------------------------------------------------------------------
    from views.sidebar import renderizar_sidebar
    from views.rendimiento import renderizar_pestana_rendimiento
    from views.enrutador_gestion import renderizar_modulos_gestion
    
    # 1. Renderizar la barra lateral (Sidebar) y capturar el estado del Escudo de Simulación
    simulacion_activa = renderizar_sidebar()
    
    # Encabezado principal dinámico de la interfaz activa
    st.markdown(f"#### ¡Bienvenido, {st.session_state.nombre}! 👋")
    st.caption(f"Perfil de acceso: `{st.session_state.rol}` | Entorno: " + 
               ("`🔒 SIMULACIÓN ACTIVA (Lectura)`" if simulacion_activa else "`⚡ PRODUCCIÓN (BD Real)`"))
    
    # 2. Renderizar el Lienzo Gráfico Estándar (Fase 3)
    renderizar_pestana_rendimiento(simulacion_activa)
    
    # 3. Renderizar el Enrutador Temático de Pestañas y Módulos de Gestión (Fase 4)
    renderizar_modulos_gestion(simulacion_activa)