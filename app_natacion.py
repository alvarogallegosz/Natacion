# =============================================================================
# 📄 app_natacion.py - ORQUESTADOR CENTRAL (INYECCIÓN ABSOLUTA DE RUTAS)
# =============================================================================
import streamlit as st
import os
import sys
import datetime

# Blindaje Absoluto de Rutas: Asegura la raíz del proyecto antes de CUALQUIER importación externa
ruta_raiz = os.path.dirname(os.path.abspath(__file__))
if ruta_raiz not in sys.path:
    sys.path.insert(0, ruta_raiz)

st.set_page_config(
    page_title="Plataforma de Analítica - Club de Natación",
    page_icon="🏊‍♂️",
    layout="wide",
    initial_sidebar_state="expanded"
)
# =============================================================================
# Ahora los imports del Core están 100% protegidos y garantizados
from core.conexion import obtener_cliente_supabase, inyectar_estilos_globales, autenticar_usuario, generar_hash_sha256

obtener_cliente_supabase()
inyectar_estilos_globales()

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

# =============================================================================
# PORTAL DE ACCESO INTEGRADOR
# =============================================================================
if not st.session_state.autenticado:
    _, col_login, _ = st.columns([1, 1.8, 1])
    
    with col_login:
        st.markdown("## 🏊‍♂️ Sistema Técnico-Deportiva")
        st.caption("Ecosistema digital de rendimiento, bitácoras de entrenamiento y analítica.")
        
        opcion_portal = st.radio(
            "Selecciona una acción:",
            ["Ingresar", "Solicitar Registro", "Recuperar Contraseña"],
            horizontal=True,
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        supabase = st.session_state["supabase_client"]
        
        if opcion_portal == "Ingresar":
            with st.form("formulario_login"):
                usuario_input = st.text_input("Usuario:", placeholder="Ej: Alvaro_Gallegos")
                contrasena_input = st.text_input("Contraseña:", type="password")
                boton_ingresar = st.form_submit_button("🚀 Iniciar Sesión", use_container_width=True)
                
                if boton_ingresar:
                    if not usuario_input.strip() or not contrasena_input.strip():
                        st.warning("⚠️ Por favor, complete ambos campos.")
                    else:
                        if autenticar_usuario(usuario_input, contrasena_input):
                            st.rerun()
                            
        elif opcion_portal == "Solicitar Registro":
            st.markdown("##### 📝 Formulario de Inscripción de Nuevos Perfiles")
            st.caption("Las cuentas nuevas entran en estado 'Pendiente' hasta ser validadas por el Administrador.")
            
            with st.form("formulario_registro"):
                reg_nombre = st.text_input("Nombre Completo:", placeholder="Ej: Carlos Mendoza")
                reg_usuario = st.text_input("Nombre de Usuario (Único):", placeholder="Ej: Carlos_Mendoza")
                reg_email = st.text_input("Correo Electrónico:")
                reg_contrasena = st.text_input("Establecer Contraseña:", type="password")
                reg_genero = st.selectbox("Género Fisiológico:", ["F", "M"])
                reg_f_nac = st.date_input("Fecha de Nacimiento:", min_value=datetime.date(1940, 1, 1), max_value=datetime.date.today())
                
                boton_registrar = st.form_submit_button("💾 Enviar Solicitud de Alta", use_container_width=True)
                
                if boton_registrar:
                    if not reg_nombre or not reg_usuario or not reg_email or not reg_contrasena:
                        st.error("❌ Todos los campos son obligatorios para tramitar el registro.")
                    else:
                        try:
                            hash_seguro = generar_hash_sha256(reg_contrasena)
                            nuevo_perfil = {
                                "nombre": reg_nombre.strip(),
                                "usuario": reg_usuario.strip(),
                                "email": reg_email.strip(),
                                "contrasena": hash_seguro,
                                "genero": reg_genero,
                                "rol": "Nadador",
                                "estatus": "Pendiente",
                                "fecha_nacimiento": reg_f_nac.isoformat()
                            }
                            supabase.table("usuarios").insert(nuevo_perfil).execute()
                            st.success("🎉 ¡Solicitud recibida! Tu cuenta está bajo revisión del administrador en estado 'Pendiente'.")
                        except Exception as e:
                            st.error(f"Error al registrar la cuenta: {e}")

        elif opcion_portal == "Recuperar Contraseña":
            st.markdown("##### 🔑 Autogestión de Reestablecimiento de Clave")
            st.caption("Por seguridad federativa, ingresa tu usuario y correo oficial para forzar un cambio de clave.")
            
            with st.form("formulario_recuperacion"):
                rec_usuario = st.text_input("Tu Nombre de Usuario:")
                rec_email = st.text_input("Tu Correo Electrónico Registrado:")
                nueva_contrasena = st.text_input("Escribe tu Nueva Contraseña:", type="password")
                
                boton_recuperar = st.form_submit_button("🔄 Reestablecer Credenciales", use_container_width=True)
                
                if boton_recuperar:
                    if not rec_usuario or not rec_email or not nueva_contrasena:
                        st.error("❌ Debes rellenar todos los campos para verificar tu identidad.")
                    else:
                        try:
                            res_verif = supabase.table("usuarios").select("id")\
                                .eq("usuario", rec_usuario.strip())\
                                .eq("email", rec_email.strip())\
                                .execute()
                                
                            if res_verif.data:
                                user_id_encontrado = res_verif.data[0]["id"]
                                nuevo_hash = generar_hash_sha256(nueva_contrasena)
                                supabase.table("usuarios")\
                                    .update({"contrasena": nuevo_hash})\
                                    .eq("id", user_id_encontrado)\
                                    .execute()
                                st.success("💥 ¡Contraseña reestablecida con éxito! Ya puedes ingresar con tu nueva clave.")
                            else:
                                st.error("❌ Datos de validación incorrectos.")
                        except Exception as e:
                            st.error(f"Error en la recuperación: {e}")
else:
    # AREA DE LA PLATAFORMA (USUARIO AUTENTICADO)
    from views.sidebar import renderizar_sidebar
    from views.rendimiento import renderizar_pestana_rendimiento
    from views.enrutador_gestion import renderizar_modulos_gestion
    
    simulacion_activa = renderizar_sidebar()
    
    st.markdown(f"#### ¡Bienvenido, {st.session_state.nombre}! 👋")
    st.caption(f"Perfil de acceso: `{st.session_state.rol}` | Entorno: " + 
               ("`🔒 SIMULACIÓN ACTIVA (Lectura)`" if simulacion_activa else "`⚡ PRODUCCIÓN (BD Real)`"))
    
    renderizar_pestana_rendimiento(simulacion_activa)
    renderizar_modulos_gestion(simulacion_activa)

# UBICACIÓN: app.py (o archivo principal), sección de inicialización de variables de la prueba
def cargar_marcas_referencia_cache(prueba_seleccionada):
    """
# Inicializar variables globales en 0 para evitar fallos de renderizado
if "m_ano" not in st.session_state:
    st.session_state.m_ano = 0.0
    st.session_state.m_panam_b = 0.0
    st.session_state.m_panam_a = 0.0
    st.session_state.m_wa_b = 0.0
    st.session_state.m_wa_a = 0.0
    st.session_state.m_wr = 0.0

# Detectar cambio de prueba seleccionada en el catálogo para refrescar caché
prueba_actual = titulo_grafico  # Asegúrate de usar la variable que guarda la prueba activa (ej. '100m Libre')

if st.session_state.get("ultima_prueba_consultada") != prueba_actual:
    try:
        resp_ref = supabase.table("marcas_referencia").select("*").eq("prueba", prueba_actual).execute()
        if resp_ref.data:
            ref = resp_ref.data[0]
            st.session_state.m_ano = float(ref.get("min_ano", 0) or 0)
            st.session_state.m_panam_b = float(ref.get("panam_b", 0) or 0)
            st.session_state.m_panam_a = float(ref.get("panam_a", 0) or 0)
            st.session_state.m_wa_b = float(ref.get("wa_b", 0) or 0)
            st.session_state.m_wa_a = float(ref.get("wa_a", 0) or 0)
            st.session_state.m_wr = float(ref.get("world_record", 0) or 0)
        else:
            # Valores limpios si la prueba no tiene marcas cargadas
            st.session_state.m_ano = st.session_state.m_panam_b = st.session_state.m_panam_a = 0.0
            st.session_state.m_wa_b = st.session_state.m_wa_a = st.session_state.m_wr = 0.0
        
        st.session_state["ultima_prueba_consultada"] = prueba_actual
    except Exception as e:
        st.warning(f"No se pudieron sincronizar las marcas de referencia desde el servidor: {e}")

# Mapear las variables que consumen tus componentes de gráficos (Archivos 11 y 12)
m_ano = st.session_state.m_ano
m_panam_b = st.session_state.m_panam_b
m_panam_a = st.session_state.m_panam_a
m_wa_b = st.session_state.m_wa_b
m_wa_a = st.session_state.m_wa_a
m_wr = st.session_state.m_wr
