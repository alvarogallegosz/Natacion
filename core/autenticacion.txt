# =============================================================================
# 📁 views/autenticacion.py - INTERFAZ UNIFICADA DE ACCESO, REGISTRO Y CONFIG
# =============================================================================
import streamlit as st
import datetime
import re
import secrets  # Para la generación segura del token/clave temporal
from core.conexion import (
    obtener_cliente_supabase,
    generar_hash_sha256,
    autenticar_usuario,
    enviar_email
)
from core.formulas import calcular_categoria_competencia

def validar_formato_correo(correo: str) -> bool:
    """
    Valida mediante expresiones regulares que el string posea una estructura
    de correo electrónico legítima.
    """
    patron = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(patron, correo))


def mostrar_interfaz_autenticacion():
    """
    Renderiza el portal unificado (Login, Registro, Recuperación) con pestañas limpias.
    Garantiza el aislamiento de estados y variables insensibles a mayúsculas.
    """
    supabase = obtener_cliente_supabase()
    
    st.markdown("<h2 style='text-align: center; color: #2C3E50;'>🏊‍♂️ Sistema Integrado de Analítica - Club de Natación</h2>", unsafe_allowed_html=True)
    st.markdown("<p style='text-align: center; color: #7F8C8D;'>Gestión de marcas mínimas, entrenamientos y modelado fisiológico</p>", unsafe_allowed_html=True)
    st.write("")

    # Pestañas del portal de acceso
    tab_login, tab_registro, tab_recuperacion = st.tabs([
        "🔑 Iniciar Sesión", 
        "📝 Registro de Atletas/Personal", 
        "🛡️ Recuperar Contraseña"
    ])

    # -------------------------------------------------------------------------
    # 🔑 PESTAÑA 1: INICIO DE SESIÓN (LOGIN)
    # -------------------------------------------------------------------------
    with tab_login:
        st.markdown("### Acceso a la Plataforma")
        with st.form("form_login"):
            # Aplicamos minúsculas al usuario para remover sensibilidad a mayúsculas
            usuario_input = st.text_input("Usuario o Email:").strip().lower()
            contrasena_input = st.text_input("Contraseña:", type="password")
            boton_login = st.form_submit_button("Ingresar", use_container_width=True)
            
            if boton_login:
                if not usuario_input or not contrasena_input:
                    st.error("⚠️ Por favor introduzca sus credenciales completas.")
                else:
                    # Llama al cortafuegos central en core/conexion.py
                    exito = autenticar_usuario(usuario_input, contrasena_input)
                    if exito:
                        st.success(f"🔓 Bienvenido al sistema, {st.session_state.nombre}.")
                        st.rerun()

    # -------------------------------------------------------------------------
    # 📝 PESTAÑA 2: REGISTRO DE NUEVOS USUARIOS
    # -------------------------------------------------------------------------
    with tab_registro:
        st.markdown("### Formulario de Afiliación")
        with st.form("form_registro"):
            col1, col2 = st.columns(2)
            with col1:
                nuevo_usuario = st.text_input("Defina su Nombre de Usuario (Ej: carlos_perez):").strip().lower()
                nombre_real = st.text_input("Nombre y Apellido Completo:").strip()
                nuevo_email = st.text_input("Correo Electrónico Oficial:").strip().lower()
                genero = st.selectbox("Género Biológico:", ["M", "F"], format_func=lambda x: "Masculino" if x == "M" else "Femenino")
            
            with col2:
                fecha_nac = st.date_input("Fecha de Nacimiento:", min_value=datetime.date(1940, 1, 1), max_value=datetime.date.today())
                rol = st.selectbox("Rol en el Club:", ["Nadador", "Entrenador"])
                clave_1 = st.text_input("Establezca su Contraseña:", type="password")
                clave_2 = st.text_input("Confirme su Contraseña (Doble Paso):", type="password")
                
            boton_registro = st.form_submit_button("Registrar Cuenta", use_container_width=True)
            
            if boton_registro:
                if not (nuevo_usuario and nombre_real and nuevo_email and clave_1 and clave_2):
                    st.error("⚠️ Todos los campos son obligatorios para proceder con el registro.")
                elif not validar_formato_correo(nuevo_email):
                    st.error("❌ El correo electrónico introducido no tiene un formato válido (ejemplo@dominio.com).")
                elif clave_1 != clave_2:
                    st.error("❌ Las contraseñas introducidas no coinciden en el sistema de doble verificación.")
                else:
                    try:
                        # Verificación previa de disponibilidad de usuario/email
                        duplicado = supabase.table("usuarios").select("id").or_(f"usuario.eq.{nuevo_usuario},email.eq.{nuevo_email}").execute()
                        if duplicado.data:
                            st.error("❌ El nombre de usuario o el correo electrónico ya se encuentran registrados en la base de datos.")
                        else:
                            # Cifrado SHA-256 antes de subir
                            hash_seguro = generar_hash_sha256(clave_1)
                            
                            nuevo_registro = {
                                "usuario": nuevo_usuario,
                                "nombre": nombre_real,
                                "email": nuevo_email,
                                "genero": genero,
                                "rol": rol,
                                "contrasena": hash_seguro,
                                "fecha_nacimiento": fecha_nac.isoformat(),
                                "estatus": "Activo"  # Por defecto el usuario entra activo, modificable por admin
                            }
                            
                            supabase.table("usuarios").insert(nuevo_registro).execute()
                            st.success(f"🎉 ¡Registro Exitoso! La cuenta '{nuevo_usuario}' ha sido creada. Ya puede iniciar sesión.")
                    except Exception as err:
                        st.error(f"Error crítico durante el alta en la base de datos: {err}")

    # -------------------------------------------------------------------------
    # 🛡️ PESTAÑA 3: RECUPERACIÓN CON CONTROL DE IDENTIDAD Y OTP TEMPORAL
    # -------------------------------------------------------------------------
    with tab_recuperacion:
        st.markdown("### Restablecimiento Autónomo de Credenciales")
        
        # Flujo en dos pasos utilizando estados temporales de Streamlit
        if "otp_verificado" not in st.session_state:
            st.session_state.otp_verificado = False
            st.session_state.otp_token_generado = None
            st.session_state.otp_user_id = None

        if not st.session_state.otp_verificado:
            with st.form("form_identidad"):
                rec_usuario = st.text_input("Introduzca su Nombre de Usuario:").strip().lower()
                rec_email = st.text_input("Introduzca su Correo Registrado:").strip().lower()
                boton_enviar_token = st.form_submit_button("Solicitar Clave Temporal por Correo", use_container_width=True)
                
                if boton_enviar_token:
                    if not rec_usuario or not rec_email:
                        st.error("⚠️ Proporcione su usuario y correo electrónico corporativo.")
                    else:
                        # Buscar correspondencia exacta
                        usuario_validado = supabase.table("usuarios").select("id, nombre, estatus").eq("usuario", rec_usuario).eq("email", rec_email).execute()
                        if usuario_validado.data:
                            user_db = usuario_validado.data[0]
                            if user_db.get("estatus") in ["Suspendido", "Bloqueado"]:
                                st.error("❌ Esta cuenta se encuentra inactiva o bloqueada. Contacte a la dirección técnica.")
                            else:
                                # Generación del Token Temporal (Clave Alfanumérica de 8 caracteres)
                                token_temporal = secrets.token_hex(4).upper()
                                st.session_state.otp_token_generado = token_temporal
                                st.session_state.otp_user_id = user_db["id"]
                                
                                # Despacho automático de la clave vía SMTP
                                asunto_mail = "🏊‍♂️ CLAVE TEMPORAL - Sistema de Analítica"
                                cuerpo_mail = f"Estimado {user_db['nombre']},\n\nHa solicitado restablecer su contraseña. Su clave de identidad temporal es:\n\n👉  {token_temporal}  <-\n\nIntroduzca este código en la plataforma para definir su nueva contraseña de acceso seguro."
                                
                                if enviar_email(asunto_mail, cuerpo_mail, rec_email):
                                    st.info("📨 Se ha enviado una clave temporal a su correo electrónico. Verifique su bandeja de entrada.")
                                    st.session_state.otp_verificado = True
                                    st.rerun()
                                else:
                                    st.error("❌ Fallo en el servidor de correos (SMTP). No se pudo despachar el token.")
                        else:
                            st.error("❌ Los datos proporcionados no coinciden con ningún registro activo.")
        else:
            # Paso 2: Introducir el OTP y setear la nueva clave de forma segura
            with st.form("form_cambio_clave"):
                st.markdown("##### 🔐 Verificación de Token e Ingreso de Nueva Contraseña")
                token_ingresado = st.text_input("Introduzca la Clave Temporal recibida:").strip().upper()
                nueva_clave_1 = st.text_input("Nueva Contraseña:", type="password")
                nueva_clave_2 = st.text_input("Confirme Nueva Contraseña:", type="password")
                boton_confirmar_cambio = st.form_submit_button("Actualizar Credenciales", use_container_width=True)
                
                if boton_confirmar_cambio:
                    if token_ingresagedo != st.session_state.otp_token_generado:
                        st.error("❌ La clave temporal introducida es incorrecta o ha expirado.")
                    elif not nueva_clave_1 or not nueva_clave_2:
                        st.error("⚠️ Complete los campos de nueva contraseña.")
                    elif nueva_clave_1 != nueva_clave_2:
                        st.error("❌ Las contraseñas no coinciden.")
                    else:
                        try:
                            nuevo_hash = generar_hash_sha256(nueva_clave_1)
                            supabase.table("usuarios").update({"contrasena": nuevo_hash}).eq("id", st.session_state.otp_user_id).execute()
                            st.success("✅ Contraseña actualizada correctamente en Supabase. Ya puede iniciar sesión.")
                            
                            # Limpieza del estado de recuperación
                            del st.session_state.otp_verificado
                            del st.session_state.otp_token_generado
                            del st.session_state.otp_user_id
                        except Exception as e:
                            st.error(f"Error al impactar los cambios en la Base de Datos: {e}")