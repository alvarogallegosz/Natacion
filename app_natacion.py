# =============================================================================
# 📄 app_natacion.py - ORQUESTADOR CENTRAL (LOGIN CON HASH, REGISTRO Y RECUPERACIÓN)
# =============================================================================
import streamlit as st
import os
import sys
import datetime

# Inyección defensiva de rutas para entornos cloud
ruta_raiz = os.path.dirname(os.path.abspath(__file__))
if ruta_raiz not in sys.path:
    sys.path.insert(0, ruta_raiz)

st.set_page_config(
    page_title="Plataforma de Analítica - Club de Natación",
    page_icon="🏊‍♂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
        
        # Conmutador visual mediante radio horizontal simulando sub-pestañas
        opcion_portal = st.radio(
            "Selecciona una acción:",
            ["Ingresar", "Solicitar Registro", "Recuperar Contraseña"],
            horizontal=True,
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        supabase = st.session_state["supabase_client"]
        
        # --- SUB-PESTAÑA 1: LOGIN ---
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
                            
        # --- SUB-PESTAÑA 2: REGISTRO ---
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
                            # Cifrado de seguridad SHA-256 inmediato antes de viajar a la BD
                            hash_seguro = generar_hash_sha256(reg_contrasena)
                            
                            nuevo_perfil = {
                                "nombre": reg_nombre.strip(),
                                "usuario": reg_usuario.strip(),
                                "email": reg_email.strip(),
                                "contrasena": hash_seguro,
                                "genero": reg_genero,
                                "rol": "Nadador",          # Rol por defecto de auto-registro
                                "estatus": "Pendiente",     # Requiere aprobación del Head Coach/Admin
                                "fecha_nacimiento": reg_f_nac.isoformat()
                            }
                            
                            supabase.table("usuarios").insert(nuevo_perfil).execute()
                            st.success("🎉 ¡Solicitud recibida! Tu cuenta está bajo revisión del administrador en estado 'Pendiente'.")
                        except Exception as e:
                            st.error(f"Error al registrar la cuenta (Es posible que el usuario ya exista): {e}")

        # --- SUB-PESTAÑA 3: RECUPERACIÓN ---
        elif opcion_portal == "Recuperar Contraseña":
            st.markdown("##### 🔑 Autogestión de Reestablecimiento de Clave")
            st.caption("Por seguridad federativa, ingresa tu usuario y correo oficial para forzar un cambio de clave instantáneo.")
            
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
                            # Verificación quirúrgica de correspondencia de cuenta
                            res_verif = supabase.table("usuarios").select("id")\
                                .eq("usuario", rec_usuario.strip())\
                                .eq("email", rec_email.strip())\
                                .execute()
                                
                            if res_verif.data:
                                user_id_encontrado = res_verif.data[0]["id"]
                                nuevo_hash = generar_hash_sha256(nueva_contrasena)
                                
                                # Actualización de la clave encriptada
                                supabase.table("usuarios")\
                                    .update({"contrasena": nuevo_hash})\
                                    .eq("id", user_id_encontrado)\
                                    .execute()
                                    
                                st.success("💥 ¡Contraseña reestablecida con éxito! Ya puedes alternar a la pestaña 'Ingresar' con tu nueva clave.")
                            else:
                                st.error("❌ Datos de validación incorrectos. El usuario y correo no coinciden.")
                        except Exception as e:
                            st.error(f"Error en la bóveda de recuperación: {e}")

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