import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import fsolve
import pandas as pd
import datetime
import io
import hashlib
from supabase import create_client, Client

# --- IMPORTS PARA EL ENVÍO DE CORREOS ---
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
    Verifica si el nadador cumple con la edad mínima 
    para eventos internacionales según el ente rector.
    """
    if ente_rector == "PANAM SPORTS":
        return edad_tecnica >= 14
    elif ente_rector == "WORLD AQUATICS":
        return edad_tecnica >= 15
    elif ente_rector == "SURAMERICANA":
        return edad_tecnica >= 13
    return False

# Funciones matemáticas para la proyección de marcas
def modelo_marcas(t, v0, k):
    return v0 * np.exp(-k * t)

def sistema_ecuaciones(vars, t1, m1, t2, m2):
    v0, k = vars
    eq1 = modelo_marcas(t1, v0, k) - m1
    eq2 = modelo_marcas(t2, v0, k) - m2
    return [eq1, eq2]

def ajustar_modelo(t1, m1, t2, m2):
    v0_inicial = m1
    k_inicial = 0.05
    v0, k = fsolve(sistema_ecuaciones, [v0_inicial, k_inicial], args=(t1, m1, t2, m2))
    return v0, k

# -------------------------------------------------------------------------
# CONFIGURACIÓN DE LA CONEXIÓN A SUPABASE
# -------------------------------------------------------------------------
@st.cache_resource
def init_supabase():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

try:
    supabase = init_supabase()
    st.session_state["supabase_client"] = supabase
except Exception as e:
    st.error("Error al inicializar la conexión con Supabase. Verifica tus credenciales en st.secrets.")
    st.stop()

# Inicialización de variables de sesión
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.rol = None
    st.session_state.usuario = None
    st.session_state.usuario_id = None

# =========================================================================
# INTERFAZ DE USUARIO - PÁGINA PRINCIPAL
# =========================================================================
st.set_page_config(page_title="Sistema de Proyección y Seguimiento de Natación", layout="wide")

st.title("🏊‍♂️ Sistema de Proyección y Seguimiento de Natación")
st.markdown("Plataforma de control técnico, marcas y gestión de atletas.")

# --- BARRA LATERAL: AUTENTICACIÓN Y NAVEGACIÓN ---
st.sidebar.image("https://img.freepik.com/vector-premium/icono-natacion-estilo-plano-nadador-vector-deporte_601200-247.jpg", width=100)
st.sidebar.markdown("### Control de Acceso")

if not st.session_state.logged_in:
    menu_acceso = st.sidebar.radio("Seleccione opción:", ["Iniciar Sesión", "Registrarse", "Recuperar Contraseña"])
    
    if menu_acceso == "Iniciar Sesión":
        st.subheader("🔑 Iniciar Sesión")
        user_input = st.sidebar.text_input("Usuario o Correo")
        pass_input = st.sidebar.text_input("Contraseña", type="password")
        
        if st.sidebar.button("Acceder"):
            if user_input and pass_input:
                hashed_pass = hash_password(pass_input)
                try:
                    res = supabase.table("usuarios").select("*").eq("usuario", user_input).eq("password", hashed_pass).execute()
                    if res.data:
                        usuario_data = res.data[0]
                        if usuario_data.get("estatus") == "Pendiente":
                            st.warning("Tu cuenta está pendiente de aprobación por el Administrador.")
                        else:
                            st.session_state.logged_in = True
                            st.session_state.rol = usuario_data["rol"]
                            st.session_state.usuario = usuario_data["usuario"]
                            st.session_state.usuario_id = usuario_data["id"]
                            st.success(f"Bienvenido {st.session_state.usuario} ({st.session_state.rol})")
                            st.rerun()
                    else:
                        st.error("Usuario, correo o contraseña incorrectos.")
                except Exception as e:
                    st.error(f"Error al conectar con la base de datos: {e}")
            else:
                st.warning("Por favor ingrese ambos campos.")

    elif menu_acceso == "Registrarse":
        st.subheader("📝 Registro de Usuario")
        reg_user = st.text_input("Nombre de Usuario")
        reg_email = st.text_input("Correo Electrónico")
        reg_pass = st.text_input("Contraseña", type="password")
        reg_rol = st.selectbox("Rol Solicitado", ["Nadador", "Entrenador"])
        
        if st.button("Registrar Solicitud"):
            if reg_user and reg_email and reg_pass:
                hashed_pass = hash_password(reg_pass)
                try:
                    # Verificar si el usuario ya existe
                    existe = supabase.table("usuarios").select("id").eq("usuario", reg_user).execute()
                    if existe.data:
                        st.warning("El nombre de usuario ya está registrado.")
                    else:
                        supabase.table("usuarios").insert({
                            "usuario": reg_user,
                            "email": reg_email,
                            "password": hashed_pass,
                            "rol": reg_rol,
                            "estatus": "Pendiente"
                        }).execute()
                        st.success("Solicitud enviada al administrador. Queda a la espera de aprobación.")
                except Exception as e:
                    st.error(f"Error al registrar: {e}")
            else:
                st.warning("Complete todos los campos obligatorios.")

    elif menu_acceso == "Recuperar Contraseña":
        st.subheader("🔄 Recuperación de Contraseña")
        rec_email = st.text_input("Ingrese su correo electrónico registrado")
        if st.button("Enviar nueva contraseña temporal"):
            if rec_email:
                try:
                    res = supabase.table("usuarios").select("*").eq("email", rec_email).execute()
                    if res.data:
                        # Generar contraseña temporal
                        temp_pass = "Temp" + str(np.random.randint(1000, 9999))
                        hashed_temp = hash_password(temp_pass)
                        
                        supabase.table("usuarios").update({"password": hashed_temp}).eq("email", rec_email).execute()
                        
                        # Lógica de envío de correo (SMTP Gmail)
                        remitente = "sistema.natacion.proyeccion@gmail.com"
                        contrasena_correo = "dqnb uoev rkyh ofvq"
                        destinatario = rec_email
                        
                        msg = MIMEMultipart()
                        msg['From'] = remitente
                        msg['To'] = destinatario
                        msg['Subject'] = "Recuperación de Contraseña - App Natación"
                        
                        cuerpo = f"Hola, tu contraseña ha sido reseteada. Tu nueva contraseña temporal es: {temp_pass}\nPor favor cámbiala al ingresar."
                        msg.attach(MIMEText(cuerpo, 'plain'))
                        
                        server = smtplib.SMTP('smtp.gmail.com', 587)
                        server.starttls()
                        server.login(remitente, contrasena_correo)
                        server.send_message(msg)
                        server.quit()
                        
                        st.success("Se ha enviado una contraseña temporal a su correo.")
                    else:
                        st.error("El correo no se encuentra registrado en el sistema.")
                except Exception as e:
                    st.error(f"Error en el proceso de recuperación: {e}")
            else:
                st.warning("Ingrese un correo electrónico.")

else:
    # --- SESIÓN INICIADA: MENÚ DE USUARIO ---
    st.sidebar.markdown(f"**Usuario:** {st.session_state.usuario}")
    st.sidebar.markdown(f"**Rol:** {st.session_state.rol}")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.logged_in = False
        st.session_state.rol = None
        st.session_state.usuario = None
        st.session_state.usuario_id = None
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Módulos de Operación")
    
    # Cargar catálogos de nadadores
    nadadores_disponibles = []
    nadador_map = {}
    try:
        if st.session_state.rol in ["Entrenador", "Administrador"]:
            res_nadadores = supabase.table("nadadores").select("id, nombre, apellido").execute()
            for n in res_nadadores.data:
                nombre_completo = f"{n['nombre']} {n['apellido']}"
                nadadores_disponibles.append(nombre_completo)
                nadador_map[nombre_completo] = n['id']
        elif st.session_state.rol == "Nadador":
            res_n = supabase.table("nadadores").select("id, nombre, apellido").eq("usuario_id", st.session_state.usuario_id).execute()
            if res_n.data:
                n = res_n.data[0]
                nombre_completo = f"{n['nombre']} {n['apellido']}"
                nadadores_disponibles = [nombre_completo]
                nadador_map[nombre_completo] = n['id']
    except Exception as e:
        st.sidebar.error(f"Error cargando nadadores: {e}")

    if nadadores_disponibles:
        nad_sel = st.sidebar.selectbox("Seleccionar Atleta:", nadadores_disponibles)
        st.session_state.nadador_seleccionado_id = nadador_map[nad_sel]
        st.session_state.nadador_seleccionado_nombre = nad_sel
        
        try:
            nad_info = supabase.table("nadadores").select("*").eq("id", st.session_state.nadador_seleccionado_id).execute()
            if nad_info.data:
                st.session_state.nadador_info = nad_info.data[0]
        except Exception:
            pass

        modulo_activo = st.sidebar.radio("Ir a:", ["Análisis y Proyecciones", "Simulador y Comparativa de Equipo", "Gestión de Registros"])
    else:
        st.sidebar.warning("No hay perfiles de nadador asociados a esta cuenta.")
        modulo_activo = "Gestión de Registros"

    # =========================================================================
    # MÓDULO 1: ANÁLISIS DE MARCAS Y PROYECCIONES
    # =========================================================================
    if modulo_activo == "Análisis y Proyecciones" and "nadador_info" in st.session_state:
        st.header("📈 Análisis de Progresión y Proyecciones de Rendimiento")
        
        info_nad = st.session_state.nadador_info
        temporada = st.number_input("Año de Temporada Activa", min_value=2020, max_value=2050, value=2026, step=1)
        
        edad_tech = calcular_edad_tecnica_al_31_dic(info_nad["fecha_nacimiento"], temporada)
        st.info(f"**Edad Técnica de {st.session_state.nadador_seleccionado_nombre}:** {edad_tech} años (al 31 de diciembre de {temporada}).")
        
        c1, c2 = st.columns(2)
        with c1:
            ente = st.selectbox("Ente Rector de Referencia", ["WORLD AQUATICS", "PANAM SPORTS", "SURAMERICANA"])
            elegible = evaluar_elegibilidad_internacional(edad_tech, ente)
            if elegible:
                st.success(f"✅ El atleta cumple con la edad mínima para eventos de {ente}.")
            else:
                st.warning(f"❌ El atleta NO cumple con la edad mínima para eventos de {ente}.")
        
        with c2:
            st.markdown("### Requisitos de proyección trianual")
            st.caption("Verificación de proyección cada 3 meses hasta los 18 años para becas, torneos nacionales e internacionales.")
            meses_proy = [0, 3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36]
            st.write(f"Proyecciones configuradas para seguimiento de cumplimiento de marcas mínimas.")

        # Cargar marcas del nadador
        try:
            marcas_res = supabase.table("marcas_nadadores").select("*").eq("nadador_id", info_nad["id"]).order("fecha", desc=False).execute()
            df_marcas = pd.DataFrame(marcas_res.data)
        except Exception as e:
            st.error(f"Error cargando marcas: {e}")
            df_marcas = pd.DataFrame()

        df_procesado = pd.DataFrame()
        fig = plt.figure()
        titulo_grafico = ""
        
        if not df_marcas.empty and len(df_marcas) >= 2:
            st.subheader("Cálculo de Proyección Matemática")
            df_marcas["fecha"] = pd.to_datetime(df_marcas["fecha"])
            df_marcas["dias"] = (df_marcas["fecha"] - df_marcas["fecha"].min()).dt.days
            
            lista_fechas = df_marcas["fecha"].dt.strftime('%Y-%m-%d').tolist()
            ref1 = st.selectbox("Fecha de referencia 1 (Marca inicial)", lista_fechas, index=0)
            ref2 = st.selectbox("Fecha de referencia 2 (Marca final)", lista_fechas, index=len(lista_fechas)-1)
            
            if ref1 != ref2:
                m1_row = df_marcas[df_marcas["fecha"].dt.strftime('%Y-%m-%d') == ref1].iloc[0]
                m2_row = df_marcas[df_marcas["fecha"].dt.strftime('%Y-%m-%d') == ref2].iloc[0]
                
                if m1_row["dias"] < m2_row["dias"]:
                    t1, m1 = m1_row["dias"], m1_row["marca_segundos"]
                    t2, m2 = m2_row["dias"], m2_row["marca_segundos"]
                    
                    v0, k = ajustar_modelo(t1, m1, t2, m2)
                    st.success(f"Modelo ajustado: V0 = {v0:.3f}, k = {k:.5f}")
                    
                    dias_futuros = np.array([m2_row["dias"] + m for m in meses_proy])
                    marcas_proyectadas = modelo_marcas(dias_futuros - t1, v0, k)
                    
                    fechas_proy = [m2_row["fecha"] + pd.Timedelta(days=int(m)) for m in meses_proy]
                    
                    df_proy = pd.DataFrame({
                        "Meses Proyecto": meses_proy,
                        "Fecha": [f.strftime('%Y-%m-%d') for f in fechas_proy],
                        "Marca Proyectada (s)": marcas_proyectadas
                    })
                    df_proy["Min:Seg"] = df_proy["Marca Proyectada (s)"].apply(lambda x: f"{int(x)//60}:{x%60:05.2f}")
                    
                    st.dataframe(df_proy, use_container_width=True)
                    
                    fig, ax = plt.subplots(figsize=(10, 5))
                    ax.scatter([m1_row["fecha"], m2_row["fecha"]], [m1, m2], color='red', zorder=5, label='Marcas Históricas')
                    ax.plot(fechas_proy, marcas_proyectadas, linestyle='--', marker='o', color='blue', label='Proyección Modelo')
                    ax.set_title(f"Proyección de Rendimiento para {info_nad['nombre']}")
                    ax.set_xlabel("Fecha")
                    ax.set_ylabel("Marca (Segundos)")
                    ax.grid(True)
                    ax.legend()
                    st.pyplot(fig)
                    
                    df_procesado = df_proy
                    titulo_grafico = "proyeccion_rendimiento"
                else:
                    st.warning("La primera fecha de referencia debe ser anterior a la segunda fecha.")
            else:
                st.info("Selecciona dos fechas de referencia diferentes para proyectar.")
        else:
            st.warning("Se requieren al menos 2 marcas históricas registradas para este atleta para realizar el cálculo proyectivo.")

        # --- CENTRO DE EXPORTACIÓN ---
        st.markdown("---")
        st.markdown("### 🖨️ Centro de Exportación de Reportes y Gráficos")
        if not df_procesado.empty:
            export_df = df_procesado.drop(columns=["Meses Proyecto"], errors="ignore")
            csv_data = export_df.to_csv(index=False).encode('utf-8')
            txt_string = export_df.to_string(index=False)
            
            img_buffer = io.BytesIO()
            fig.savefig(img_buffer, format="png", bbox_inches='tight', dpi=300)
            img_buffer.seek(0)
            
            c_exp1, c_exp2, c_exp3 = st.columns(3)
            with c_exp1:
                st.download_button(label="📥 Descargar Historial (CSV)", data=csv_data, file_name=f"marcas_{titulo_grafico}_{st.session_state.nadador_seleccionado_nombre}.csv", mime="text/csv")
            with c_exp2:
                st.download_button(label="📄 Descargar Datos (TXT)", data=txt_string, file_name=f"reporte_{titulo_grafico}_{st.session_state.nadador_seleccionado_nombre}.txt", mime="text/plain")
            with c_exp3:
                st.download_button(label="🖼️ Guardar Gráfico (Imagen PNG)", data=img_buffer, file_name=f"grafico_{titulo_grafico}_{st.session_state.nadador_seleccionado_nombre}.png", mime="image/png")

    # =========================================================================
    # MÓDULO 2: SIMULADOR Y COMPARATIVA DE EQUIPO
    # =========================================================================
    elif modulo_activo == "Simulador y Comparativa de Equipo":
        st.header("📊 Simulador y Análisis Colectivo (Equipo)")
        
        try:
            res_equipo = supabase.table("nadadores").select("id, nombre, apellido, genero, categoria, fecha_nacimiento").execute()
            df_nadadores = pd.DataFrame(res_equipo.data)
            
            res_todas_marcas = supabase.table("marcas_nadadores").select("*").execute()
            df_todas_marcas = pd.DataFrame(res_todas_marcas.data)
        except Exception as e:
            df_nadadores = pd.DataFrame()
            df_todas_marcas = pd.DataFrame()
            st.error(f"Error al cargar datos del equipo: {e}")

        if not df_nadadores.empty and not df_todas_marcas.empty:
            st.subheader("Filtros de Análisis Colectivo")
            c_f1, c_f2, c_f3 = st.columns(3)
            with c_f1:
                filtro_genero = st.selectbox("Filtrar por Género", ["Todos", "Masculino", "Femenino"])
            with c_f2:
                cats = ["Todas"] + df_nadadores["categoria"].dropna().unique().tolist()
                filtro_cat = st.selectbox("Filtrar por Categoría", cats)
            with c_f3:
                estilos = ["Todos", "Libre", "Dorso", "Pecho", "Mariposa", "CI"]
                filtro_estilo = st.selectbox("Filtrar por Estilo/Prueba", estilos)

            dft = df_nadadores.copy()
            if filtro_genero != "Todos":
                dft = dft[dft["genero"] == filtro_genero]
            if filtro_cat != "Todas":
                dft = dft[dft["categoria"] == filtro_cat]

            ids_filtrados = dft["id"].tolist()
            df_marcas_filtradas = df_todas_marcas[df_todas_marcas["nadador_id"].isin(ids_filtrados)].copy()
            
            if filtro_estilo != "Todos":
                df_marcas_filtradas = df_marcas_filtradas[df_marcas_filtradas["estilo"] == filtro_estilo]

            if not df_marcas_filtradas.empty:
                df_merged = df_marcas_filtradas.merge(dft, left_on="nadador_id", right_on="id")
                df_merged["nombre_completo"] = df_merged["nombre"] + " " + df_merged["apellido"]
                
                st.subheader("Mejores Marcas del Colectivo / Equipo")
                df_resumen = df_merged[["nombre_completo", "categoria", "estilo", "distancia", "marca_segundos", "fecha"]].sort_values("marca_segundos")
                df_resumen["Min:Seg"] = df_resumen["marca_segundos"].apply(lambda x: f"{int(x)//60}:{x%60:05.2f}")
                st.dataframe(df_resumen, use_container_width=True)
                
                st.subheader("Gráfico Comparativo de Rendimiento por Atleta")
                fig, ax = plt.subplots(figsize=(10, 6))
                colores = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
                
                for i, (index, row) in enumerate(df_resumen.head(10).iterrows()):
                    ax.bar(row["nombre_completo"] + f"\n({row['estilo']})", row["marca_segundos"], color=colores[i % len(colores)])
                    
                ax.set_ylabel("Marca en Segundos")
                ax.set_title("Comparativa de atletas más rápidos (Top 10)")
                plt.xticks(rotation=45, ha='right')
                ax.grid(axis='y', linestyle='--', alpha=0.7)
                st.pyplot(fig, use_container_width=True)

                st.markdown("---")
                st.markdown("### 🖨️ Exportación de Reportes del Equipo")
                csv_data = df_resumen.to_csv(index=False).encode('utf-8')
                txt_string = df_resumen.to_string(index=False)
                
                img_buffer = io.BytesIO()
                fig.savefig(img_buffer, format="png", bbox_inches='tight', dpi=300)
                img_buffer.seek(0)
                
                c_exp1, c_exp2, c_exp3 = st.columns(3)
                with c_exp1:
                    st.download_button(label="📥 Descargar Reporte (CSV)", data=csv_data, file_name="reporte_equipo.csv", mime="text/csv")
                with c_exp2:
                    st.download_button(label="📄 Descargar Datos (TXT)", data=txt_string, file_name="reporte_equipo.txt", mime="text/plain")
                with c_exp3:
                    st.download_button(label="🖼️ Guardar Gráfico (Imagen PNG)", data=img_buffer, file_name="grafico_equipo.png", mime="image/png")
            else:
                st.warning("No hay registros de marcas que coincidan con los filtros aplicados.")
        else:
            st.info("No hay datos suficientes cargados en la base de datos para análisis comparativos.")

    # =========================================================================
    # MÓDULO 3: GESTIÓN DE REGISTROS (CRUD BÁSICO)
    # =========================================================================
    elif modulo_activo == "Gestión de Registros":
        st.header("📋 Gestión de Registros Históricos de Marcas")
        
        info_nad = st.session_state.nadador_info
        st.subheader(f"Registros de: {st.session_state.nadador_seleccionado_nombre}")
        
        try:
            marcas_res = supabase.table("marcas_nadadores").select("*").eq("nadador_id", info_nad["id"]).order("fecha", desc=True).execute()
            df_marcas = pd.DataFrame(marcas_res.data)
        except Exception as e:
            st.error(f"Error cargando marcas: {e}")
            df_marcas = pd.DataFrame()

        if not df_marcas.empty:
            df_mostrar = df_marcas[["estilo", "distancia", "marca_segundos", "fecha", "competencia", "piscina"]].copy()
            df_mostrar["Min:Seg"] = df_mostrar["marca_segundos"].apply(lambda x: f"{int(x)//60}:{x%60:05.2f}")
            st.dataframe(df_mostrar, use_container_width=True)
        else:
            st.info("No hay marcas registradas para este atleta.")

        st.markdown("---")
        st.subheader("➕ Agregar Nuevo Registro de Marca")
        with st.form("form_agregar_marca"):
            estilo = st.selectbox("Estilo", ["Libre", "Dorso", "Pecho", "Mariposa", "CI"])
            distancia = st.selectbox("Distancia (metros)", [50, 100, 200, 400, 800, 1500])
            minutos = st.number_input("Minutos", min_value=0, max_value=30, value=1, step=1)
            segundos = st.number_input("Segundos y milisegundos", min_value=0.00, max_value=59.99, value=5.50, step=0.01)
            fecha = st.date_input("Fecha de la competencia", datetime.date.today())
            competencia = st.text_input("Nombre del Torneo / Competencia")
            piscina = st.selectbox("Tipo de Piscina", ["Corta (25m)", "Larga (50m)"])
            
            submit_marca = st.form_submit_button("Guardar Marca")
            
            if submit_marca:
                marca_en_segundos = (minutos * 60) + segundos
                try:
                    supabase.table("marcas_nadadores").insert({
                        "nadador_id": info_nad["id"],
                        "estilo": estilo,
                        "distancia": distancia,
                        "marca_segundos": float(marca_en_segundos),
                        "fecha": str(fecha),
                        "competencia": competencia,
                        "piscina": piscina,
                        "usuario_id": st.session_state.usuario_id
                    }).execute()
                    st.success("¡Marca agregada exitosamente!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar la marca: {e}")

        if not df_marcas.empty:
            st.markdown("---")
            st.subheader("🗑️ Eliminar Registro de Marca")
            opciones_eliminar = {}
            for idx, row in df_marcas.iterrows():
                label = f"{row['estilo']} {row['distancia']}m - {row['fecha']} ({row['competencia']})"
                opciones_eliminar[label] = row['id']
            
            marca_a_borrar = st.selectbox("Seleccione la marca a eliminar:", list(opciones_eliminar.keys()))
            if st.button("Eliminar Marca Seleccionada", type="primary"):
                try:
                    id_borrar = opciones_eliminar[marca_a_borrar]
                    supabase.table("marcas_nadadores").delete().eq("id", id_borrar).execute()
                    st.success("Registro eliminado correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al eliminar el registro: {e}")

# =========================================================================
# MÓDULO DE ADMINISTRACIÓN DE DATOS Y SOFTWARE (RESTAURADO)
# =========================================================================
if st.session_state.get("logged_in") and st.session_state.rol == "Administrador":
    st.markdown("---")
    st.markdown("### ⚙️ Consola de Administración de Software y Datos")
    
    tab_admin_bd, tab_admin_sis = st.tabs(["🗄️ Gestión de Base de Datos", "🛠️ Configuración del Sistema"])
    
    with tab_admin_bd:
        st.write("Panel para depurar, actualizar o verificar la base de datos de usuarios y perfiles en Supabase.")
        try:
            res_users = supabase.table("usuarios").select("id, usuario, email, rol, estatus").execute()
            df_sys_users = pd.DataFrame(res_users.data)
            st.write("#### Usuarios Registrados en el Sistema")
            st.dataframe(df_sys_users, use_container_width=True)
        except Exception as e:
            st.error(f"No se pudieron cargar los datos de la base de datos: {e}")
            
    with tab_admin_sis:
        st.write("Revisión de perfiles pendientes, bloqueados o asignación de privilegios.")
        try:
            pendientes = supabase.table("usuarios").select("id, usuario, rol").eq("estatus", "Pendiente").execute()
            if pendientes.data:
                df_p = pd.DataFrame(pendientes.data)
                st.warning(f"Existen {len(df_p)} usuarios pendientes por aprobar.")
                st.dataframe(df_p)
                
                user_id_aprob = st.selectbox("Seleccione ID de usuario a aprobar", df_p["id"].tolist())
                if st.button("Aprobar Usuario"):
                    supabase.table("usuarios").update({"estatus": "Activo"}).eq("id", user_id_aprob).execute()
                    st.success("¡Usuario aprobado correctamente!")
                    st.rerun()
            else:
                st.info("No hay usuarios pendientes de aprobación.")
        except Exception as e:
            st.error(f"Error cargando administración del sistema: {e}")
