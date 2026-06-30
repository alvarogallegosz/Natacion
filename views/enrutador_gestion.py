# =============================================================================
# 📁 views/enrutador_gestion.py - ENRUTADOR UNIFICADO DE OPERACIONES Y GESTIÓN
# =============================================================================
import streamlit as st
import pandas as pd
import datetime
import numpy as np

# Importaciones estrictas del ecosistema core
from core.conexion import (
    obtener_cliente_supabase,
    obtener_usuarios_cache,
    obtener_marcas_historicas_cache,
    obtener_asignaciones_cache
)
from core.formulas import (
    calcular_edad_decimal,
    resolver_k_individual,
    calcular_curva_atleta
)

def mostrar_enrutador_gestion():
    """
    [Módulo Unificado Definitivo - Auditoría de Pestañas y Gestión de Permisos]
    Orquesta y renderiza las 7 sub-pestañas operativas de la plataforma,
    aplicando las reglas de negocio y restricciones jerárquicas del club.
    """
    # 1. ESCUDO INICIAL: Verificación de Entorno Experimental / Simulación
    simulacion_activa = st.session_state.get("simulacion_externa", False)
    
    if simulacion_activa:
        st.info(
            "⚠️ **Modo Simulación Externa Activo.** El módulo de gestión operativa, "
            "configuración y control de marcas históricas se encuentra oculto para "
            "evitar alteraciones accidentales en la base de datos real del club."
        )
        return

    # 2. CAPTURA DE CONTEXTO GLOBAL (Variables de la Sidebar / Sesión)
    supabase = obtener_cliente_supabase()
    rol_usuario = st.session_state.get("rol", "Nadador")
    nadador_id = st.session_state.get("nadador_seleccionado_id")
    nadador_nombre = st.session_state.get("nadador_seleccionado_nombre", "Sin Selección")
    fecha_nac_atleta = st.session_state.get("fecha_nacimiento")
    titulo_grafico = st.session_state.get("prueba_activa", "50m Libre") 

    st.markdown("### 𗂾 Panel de Gestión Operativa y Marcas")
    
    # 3. DECLARACIÓN Y ORDEN ESTRICTO DE LAS 7 PESTAÑAS (Especificación 14)
    tab_pizarra, tab_reportes, tab_marcas, tab_entrenador, tab_asignaciones, tab_calendario, tab_admin = st.tabs([
        "📝 Pizarra Diaria", 
        "📊 Reportes de Entrenamiento", 
        "📋 Resultados de competencias", 
        "⏱️ Configurar Marcas Mínimas",
        "🎯 Asignaciones de Nadadores",
        "📅 Calendario Anual de Competencias", 
        "🛡️ Consola Global (Admin)"
    ])

    # -------------------------------------------------------------------------
    # 📝 PESTAÑA 1: PIZARRA DIARIA
    # -------------------------------------------------------------------------
    with tab_pizarra:
        st.markdown("##### 📝 Pizarra Diaria de Entrenamiento")
        st.caption("Registro diario de volúmenes, intensidades y cargas fisiológicas por carril.")

    # -------------------------------------------------------------------------
    # 📊 PESTAÑA 2: REPORTES DE ENTRENAMIENTO
    # -------------------------------------------------------------------------
    with tab_reportes:
        st.markdown("##### 📊 Reportes de Rendimiento y Asistencia")
        st.caption("Auditoría de volúmenes acumulados, asistencia y zonas de energía.")

    # -------------------------------------------------------------------------
    # 📋 PESTAÑA 3: RESULTADOS DE COMPETENCIAS (RESTAURADO COMPLETO)
    # -------------------------------------------------------------------------
with tab_marcas:
        col_ins, col_vistas = st.columns([1, 2])
        with col_ins:
            st.markdown("**Ingresar Nueva Marca**")
            with st.form("form_insertar_marca", clear_on_submit=True):
                ins_fecha_evento = st.date_input("Fecha de la Competencia:", min_value=datetime.date(2020, 1, 1), max_value=datetime.date.today(), value=datetime.date.today())
                ins_tiempo = st.number_input("Tiempo Oficial (seg):", min_value=20.0,  max_value=1800.0, step=0.01)
                ins_nota = st.text_input("Evento / Sede:")
                
                if st.form_submit_button("💾 Guardar Registro"):
                    if rol_usuario in ["Head Coach", "Entrenador", "Administrador"] or st.session_state.usuario_id == nadador_id:
                        try:
                            id_atleta = nadador_id
                            fecha_nacimiento_atleta = fecha_nac_atleta
                            
                            if rol_usuario in ["Head Coach", "Entrenador", "Administrador"]:
                                atleta_query = supabase.table("usuarios").select("fecha_nacimiento").eq("id", id_atleta).execute()
                                if atleta_query.data:
                                    fecha_nacimiento_atleta = atleta_query.data[0]["fecha_nacimiento"]
                            
                            if not id_atleta or not fecha_nacimiento_atleta:
                                st.error("Error: No se pudo determinar el atleta o su fecha de nacimiento.")
                            else:
                                edad_en_evento = calcular_edad_decimal(fecha_nacimiento_atleta, ins_fecha_evento.isoformat())
                                
                                nueva_marca = {
                                    "atleta_id": id_atleta,
                                    "prueba": titulo_grafico,
                                    "fecha": ins_fecha_evento.isoformat(),
                                    "edad": float(f"{edad_en_evento:.4f}"),
                                    "tiempo": float(ins_tiempo),
                                    "nota": ins_nota
                                }
                                
                                resp_ins = supabase.table("marcas_historicas").insert(nueva_marca).execute()
                                if resp_ins.data:
                                    # SINCRONIZACIÓN EN CALIENTE SELECTIVA
                                    from core.conexion import invalidar_cache_marcas
                                    invalidar_cache_marcas()
                                    
                                    st.success("✅ Marca guardada con éxito en el historial.")
                                    st.rerun()
                        except Exception as e:
                            st.error(f"Error al insertar marca: {e}")
                    else:
                        st.error("Permiso denegado. No tienes autorización para registrar marcas de este atleta.")
                        
        with col_vistas:
            st.markdown("**Historial de Registros**")
            if nadador_id:
                try:
                    res_m = supabase.table("marcas_historicas").select("*").eq("atleta_id", nadador_id).eq("prueba", titulo_grafico).order("fecha", ascending=False).execute()
                    if res_m.data:
                        df_m = pd.DataFrame(res_m.data)
                        df_m["fecha_f"] = pd.to_datetime(df_m["fecha"]).dt.strftime('%d/%m/%Y')
                        df_show = df_m[["fecha_f", "edad", "tiempo", "nota"]].copy()
                        df_show.columns = ["Fecha Evento", "Edad (Años)", "Tiempo (seg)", "Detalle / Sede"]
                        st.dataframe(df_show, use_container_width=True, hide_index=True)
                        
                        st.markdown("**Eliminar Registro**")
                        # Armamos las opciones garantizando consistencia absoluta en el string
                        opciones_eliminar = []
                        for r in res_m.data:
                            f_formateada = pd.to_datetime(r["fecha"]).strftime('%d/%m/%Y')
                            opciones_eliminar.append({
                                "label": f"{f_formateada} - {float(r['tiempo']):.2f}s ({r['nota']})",
                                "id": r["id"]
                            })
                        
                        sel_eliminar = st.selectbox(
                            "Seleccione el registro que desea remover:", 
                            options=opciones_eliminar, 
                            format_func=lambda x: x["label"],
                            key="sel_eliminar_marca"
                        )
                        
                        if st.button("❌ Eliminar Marca Seleccionada"):
                            if rol_usuario in ["Head Coach", "Entrenador", "Administrador"]:
                                id_a_borrar = sel_eliminar["id"]
                                resp_del = supabase.table("marcas_historicas").delete().eq("id", id_a_borrar).execute()
                                if resp_del.data:
                                    # SINCRONIZACIÓN EN CALIENTE SELECTIVA
                                    from core.conexion import invalidar_cache_marcas
                                    invalidar_cache_marcas()
                                    
                                    st.success("Registro eliminado correctamente.")
                                    st.rerun()
                            else:
                                st.error("Acceso denegado. Solo los entrenadores o administradores pueden remover registros del historial.")
                    else:
                        st.info(f"No hay marcas registradas para {nadador_nombre} en la prueba {titulo_grafico}.")
                except Exception as e:
                    st.error(f"Error al cargar historial: {e}")
            else:
                st.warning("Seleccione un atleta en la barra lateral para visualizar su historial.")

    # -------------------------------------------------------------------------
    # ⏱️ PESTAÑA 4: CONFIGURAR MARCAS MÍNIMAS (RESTAURADO COMPLETO)
    # -------------------------------------------------------------------------
    with tab_entrenador:
        st.markdown("##### ⏱️ Configuración del Tabulador de Marcas Mínimas")
        if rol_usuario in ["Head Coach", "Entrenador", "Administrador"]:
            try:
                from core.formulas import determinar_categoria_fina
                u_cat, _ = determinar_categoria_fina(fecha_nac_atleta)
            except Exception:
                u_cat = "Juvenil A"
                
            try:
                genero_atleta = st.session_state.get("nadador_seleccionado_genero", "M")
                res_ref = supabase.table("marcas_referencia").select("*").eq("prueba", titulo_grafico).eq("genero", genero_atleta).eq("categoria", u_cat).execute()
                
                db_m_ano = res_ref.data[0]["m_ano"] if res_ref.data else None
                db_m_panam_b = res_ref.data[0]["m_panam_b"] if res_ref.data else None
                db_m_panam_a = res_ref.data[0]["m_panam_a"] if res_ref.data else None
                db_m_wa_b = res_ref.data[0]["m_wa_b"] if res_ref.data else None
                db_m_wa_a = res_ref.data[0]["m_wa_a"] if res_ref.data else None
                db_m_wr = res_ref.data[0]["m_wr"] if res_ref.data else None
                
            except Exception:
                db_m_ano = db_m_panam_b = db_m_panam_a = db_m_wa_b = db_m_wa_a = db_m_wr = None
                
            st.markdown(f"Ajuste de marcas de referencia para la prueba **{titulo_grafico}** | Género: **{genero_atleta}** | Categoría: **{u_cat}**")
            
            with st.form("form_marcas_referencia"):
                u_ano = st.number_input("Marca Mínima Nacional (seg):", value=db_m_ano if db_m_ano is not None else 27.20, disabled=(db_m_ano is None))
                u_panamb = st.number_input("Panamericano Marca B (seg):", value=db_m_panam_b if db_m_panam_b is not None else 0.0, disabled=(db_m_panam_b is None))
                u_panama = st.number_input("Panamericano Marca A (seg):", value=db_m_panam_a if db_m_panam_a is not None else 0.0, disabled=(db_m_panam_a is None))
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
                        try:
                            supabase.table("marcas_referencia").upsert({
                                "prueba": titulo_grafico, "genero": genero_atleta,
                                "categoria": u_cat, **up_data
                            }, on_conflict="prueba,genero,categoria").execute()
                            st.success("Tiempos límite actualizados en la base de datos.")
                            st.cache_data.clear()
                        except Exception as e:
                            st.error(f"Error al actualizar marcas de referencia: {e}")
        else:
            st.error("Acceso restringido. Solo los entrenadores autorizados pueden modificar los tabuladores técnicos.")

    # -------------------------------------------------------------------------
    # 🎯 PESTAÑA 5: ASIGNACIONES DE NADADORES (RESTAURADO COMPLETO CON CONTROL MASTER/HEAD COACH)
    # -------------------------------------------------------------------------
    with tab_asignaciones:
        if rol_usuario in ["Head Coach", "Administrador"]:
            st.markdown("### 📋 Panel de Gestión de Asignaciones (Exclusivo Head Coach / Admin Universal)")
            st.caption("Módulo de alta jerarquía para distribuir la supervisión técnica de la piscina y carriles.")
            
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
                        
                        dict_nadadores = {n["id"]: n["nombre"] for n in lista_todos_nadadores}
                        nadador_sel = st.selectbox("Nadador a asignar:", options=list(dict_nadadores.keys()), format_func=lambda x: dict_nadadores[x], key="asig_ind_nad")
                        
                        if st.button("🔗 Confirmar Asignación Individual"):
                            # Limpiar asignación previa del atleta seleccionado
                            supabase.table("asignaciones").delete().eq("atleta_id", nadador_sel).execute()
                            
                            # Insertar nueva relación estructurada
                            nueva_asig = {"entrenador_id": entrenador_sel, "atleta_id": nadador_sel}
                            supabase.table("asignaciones").insert(nueva_asig).execute()
                            
                            st.success(f"🎉 {dict_nadadores[nadador_sel]} ha sido asignado con éxito a {dict_entrenadores[entrenador_sel]}.")
                            st.cache_data.clear()
                            st.rerun()
                            
                    with col2:
                        st.markdown("##### 👥 Asignación Masiva por Categoría")
                        entrenador_cat_sel = st.selectbox("Asistente Destino:", options=list(dict_entrenadores.keys()), format_func=lambda x: dict_entrenadores[x], key="asig_cat_ent")
                        
                        from core.formulas import determinar_categoria_fina
                        categorias_set = set()
                        for nad in lista_todos_nadadores:
                            cat_n, _ = determinar_categoria_fina(nad["fecha_nacimiento"])
                            categorias_set.add(cat_n)
                            
                        categoria_sel = st.selectbox("Categoría Etaria de Origen:", options=sorted(list(categorias_set)), key="asig_cat_sel")
                        
                        if st.button("⚡ Procesar Asignación por Bloque"):
                            ids_categoria = []
                            for nad in lista_todos_nadadores:
                                c_fina, _ = determinar_categoria_fina(nad["fecha_nacimiento"])
                                if c_fina == categoria_sel:
                                    ids_categoria.append(nad["id"])
                            
                            if ids_categoria:
                                # 1. Limpiar asignaciones previas de estos atletas específicos
                                supabase.table("asignaciones").delete().in_("atleta_id", ids_categoria).execute()
                                
                                # 2. Inserción por lotes
                                nuevas_asig = [{"entrenador_id": entrenador_cat_sel, "atleta_id": nid} for nid in ids_categoria]
                                supabase.table("asignaciones").insert(nuevas_asig).execute()
                                
                                st.success(f"🎉 Se asignaron {len(ids_categoria)} nadadores de la categoría **{categoria_sel}** a {dict_entrenadores[entrenador_cat_sel]}.")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.warning("No se encontraron nadadores activos en la categoría seleccionada.")
                else:
                    st.info("Debe contar con Entrenadores y Nadadores activos en la base de datos para habilitar las opciones de asignación.")
            except Exception as e:
                st.error(f"Error operando la tabla de asignaciones: {e}")
                
            st.markdown("---")
            st.markdown("##### 🔍 Monitor de Asignaciones Vigentes en Sistema")
            asignaciones_datos = obtener_asignaciones_cache()
            if asignaciones_datos:
                st.dataframe(pd.DataFrame(asignaciones_datos), use_container_width=True)
            else:
                st.info("💡 No se registran asignaciones de carriles estructuradas en el sistema.")
        else:
            st.error("🔒 Acceso Denegado. Esta sección contiene funciones críticas de administración de base de datos y asignación de nómina. Requiere credenciales de Head Coach o Administrador Master.")

    # -------------------------------------------------------------------------
    # 📅 PESTAÑA 6: CALENDARIO ANUAL DE COMPETENCIAS
    # -------------------------------------------------------------------------
    with tab_calendario:
        st.markdown("##### 📅 Calendario Anual de Competencias, Copas e Hitos")
        st.caption("Planificación estratégica de macrociclos y fechas límite de inscripción.")

# -------------------------------------------------------------------------
    # 🛡️ PESTAÑA 7: CONSOLA GLOBAL (ADMIN) - AUDITADA CON RESPALDO TOTAL REAL
    # -------------------------------------------------------------------------
    with tab_admin:
        if st.session_state.rol == "Administrador":
            st.markdown("### 🛡️ Consola de Control de Usuarios e Integridad de Datos")
            
            # =========================================================================
            # SECCIÓN A: GESTIÓN DE PERFILES Y USUARIOS (CÓDIGO ORIGINAL PRESERVADO)
            # =========================================================================
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
                        idx_gen = 0
                        if user_actual["genero"] == "F": idx_gen = 1
                        nuevo_gen_user = st.selectbox("Género:", options=["Masculino (M)", "Femenino (F)"], index=idx_gen, disabled=campos_deshabilitados)
                    
                    f_nac_inicial = datetime.date.today()
                    if user_actual["fecha_nacimiento"]:
                        f_nac_inicial = datetime.date.fromisoformat(user_actual["fecha_nacimiento"])
                        
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
                            datos_update["genero"] = "M" if nuevo_gen_user == "Masculino (M)" else "F"
                            datos_update["fecha_nacimiento"] = nueva_f_nac_admin.isoformat()
                            
                        supabase.table("usuarios").update(datos_update).eq("id", int(id_mod)).execute()
                        st.success("Cambios aplicados con éxito.")
                        st.rerun()
            except Exception as e:
                st.error(f"Error en panel de control: {e}")

            # =========================================================================
            # SECCIÓN B: UTILERÍA DE RESPALDO LOCAL (CON BITÁCORA DE ENTRENAMIENTOS)
            # =========================================================================
            st.markdown("---")
            st.markdown("##### 💾 Respaldo Local de la Base de Datos (Backup)")
            st.caption("Extrae de forma segura copias de resguardo locales directamente en tu almacenamiento en formato JSON plano.")
            
            c_bk1, c_bk2 = st.columns([2, 1])
            
            with c_bk1:
                # Catálogo 100% real y verificado de las tablas operacionales del club
                opciones_backup = [
                    "Respaldo Total (Todas las tablas operativas)",
                    "Tabla: usuarios",
                    "Tabla: marcas_historicas",
                    "Tabla: bitacora_entrenamientos",
                    "Tabla: catalogo_competencias",
                    "Tabla: asignaciones",
                    "Tabla: marcas_referencia"
                ]
                seleccion_backup = st.selectbox("Seleccione el alcance del respaldo:", options=opciones_backup, key="bk_alcance_sel")
            
            with c_bk2:
                st.markdown("<div style='padding-top:28px;'></div>", unsafe_allow_html=True)
                try:
                    backup_data_str = ""
                    file_name_out = f"backup_{datetime.date.today().isoformat()}.json"
                    
                    if seleccion_backup == "Respaldo Total (Todas las tablas operativas)":
                        # Malla completa de extracción sin rastro de tablas obsoletas
                        tablas_vigentes = [
                            "usuarios", 
                            "marcas_historicas", 
                            "bitacora_entrenamientos", 
                            "catalogo_competencias", 
                            "asignaciones", 
                            "marcas_referencia"
                        ]
                        diccionario_total = {}
                        
                        for t in tablas_vigentes:
                            r_t = supabase.table(t).select("*").execute()
                            diccionario_total[t] = r_t.data if r_t.data else []
                            
                        df_temp = pd.DataFrame([diccionario_total])
                        backup_data_str = df_temp.to_json(orient="records", indent=4)
                        file_name_out = f"db_total_backup_{datetime.date.today().isoformat()}.json"
                    else:
                        tabla_objetivo = seleccion_backup.split(": ")[1]
                        r_t = supabase.table(tabla_objetivo).select("*").execute()
                        df_temp = pd.DataFrame(r_t.data) if r_t.data else pd.DataFrame()
                        backup_data_str = df_temp.to_json(orient="records", indent=4)
                        file_name_out = f"backup_tabla_{tabla_objetivo}_{datetime.date.today().isoformat()}.json"
                    
                    st.download_button(
                        label="📥 Ejecutar y Descargar",
                        data=backup_data_str,
                        file_name=file_name_out,
                        mime="application/json",
                        use_container_width=True
                    )
                except Exception as e_bk:
                    st.error(f"Error generando el respaldo de seguridad: {e_bk}")
        else:
            st.warning("🔒 Acceso restringido al Administrador.")
# -------------------------------------------------------------------------
    # 📝 PESTAÑA 1: PIZARRA DE ENTRENAMIENTO DIARIO (CONSERVACIÓN ABSOLUTA)
    # -------------------------------------------------------------------------
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
                    estilo = st.selectbox("Estilo / Foco", ["Libre", "Espalda", "Pecho", "Mariposa", "Combinado", "Pateo", "Frecuencia", "Zonas Fisiológicas"], key="piz_est")
                
                c_int, c_pausa, c_imp = st.columns(3)
                with c_int:
                    intensidad = st.slider("Intensidad Objetivo (%)", min_value=50, max_value=100, value=75, step=5, key="piz_int")
                with c_pausa:
                    pausa = st.text_input("Pausa / Intervalo (ej. 15\", @1'45\")", value="15\"", key="piz_pau")
                with c_imp:
                    implementos = st.multiselect("Implementos", ["Aletas", "Paletas", "Snorkel", "Tabla", "Pull Buoy", "Ligas"], key="piz_imp")
                
                if st.button("🚀 Insertar Serie a la Pizarra", use_container_width=True):
                    nueva_serie = {
                        "id": len(st.session_state.pizarra_entrenamiento) + 1,
                        "repeticiones": repeticiones,
                        "distancia": distancia,
                        "estilo": estilo,
                        "intensidad": intensidad,
                        "pausa": pausa,
                        "implementos": implementos,
                        "volumen_parcial": repeticiones * distancia
                    }
                    st.session_state.pizarra_entrenamiento.append(nueva_serie)
                    st.success("Serie acoplada temporalmente.")
                    st.rerun()

            # 3. Visualización y Control de la Pizarra de Trabajo del Día
            if st.session_state.pizarra_entrenamiento:
                st.markdown("#### 🏊‍♂️ Series Estructuradas para la Sesión")
                
                volumen_total_sesion = sum(blk["volumen_parcial"] for blk in st.session_state.pizarra_entrenamiento)
                st.info(f"📊 **Volumen Total Programado:** {volumen_total_sesion} metros lineales.")
                
                # Renderizado limpio de la pizarra actual
                for blk in st.session_state.pizarra_entrenamiento:
                    with st.container():
                        c_txt, c_btn = st.columns([6, 1])
                        with c_txt:
                            impl_str = f" con {', '.join(blk['implementos'])}" if blk['implementos'] else ""
                            st.markdown(
                                f"**{blk['id']}.** {blk['repeticiones']} x {blk['distancia']}m en **{blk['estilo']}** "
                                f"al {blk['intensidad']}% (Pausa: {blk['pausa']}){impl_str} — *[{blk['volumen_parcial']}m]*"
                            )
                        with c_btn:
                            if st.button("🗑️", key=f"del_{blk['id']}"):
                                st.session_state.pizarra_entrenamiento.remove(blk)
                                # Reindexar para mantener orden secuencial limpio
                                for idx, item in enumerate(st.session_state.pizarra_entrenamiento):
                                    item["id"] = idx + 1
                                st.rerun()
                
                if st.button("❌ Vaciar Pizarra Completa", color="red"):
                    st.session_state.pizarra_entrenamiento = []
                    st.rerun()
                
# 4. Bloque de Consolidación e Imputación Individual a la Base de Datos
                st.markdown("---")
                st.markdown("#### 🏁 Cierre de Sesión y Control de Cargas de Trabajo")
                st.caption("Selecciona el grupo de atletas que ejecutaron esta pizarra para grabar su bitácora en Supabase.")
                
                try:
                    # Traer nómina de nadadores activos vinculados para procesar la asistencia
                    resp_atletas = supabase.table("usuarios").select("id, nombre").eq("rol", "Nadador").eq("estatus", "Activo").execute()
                    
                    if resp_atletas.data:
                        dict_atletas = {a["id"]: a["nombre"] for a in resp_atletas.data}
                        atletas_asistieron = st.multiselect(
                            "Nadadores que completaron el entrenamiento:",
                            options=list(dict_atletas.keys()),
                            format_func=lambda x: dict_atletas[x]
                        )
                        
                        fecha_entrenamiento = st.date_input("Fecha de Imputación:", value=datetime.date.today())
                        
                        if st.button("💥 Consolidar Asistencia y Grabar Cargas", type="primary", use_container_width=True):
                            if atletas_asistieron:
                                registros_supabase = []
                                
                                # Se itera sobre cada atleta seleccionado conservando intacta tu estructura de datos
                                for atleta_id in atletas_asistieron:
                                    for blk in st.session_state.pizarra_entrenamiento:
                                        fila_bitacora = {
                                            "atleta_id": atleta_id,
                                            "fecha": fecha_entrenamiento.isoformat(),
                                            "repeticiones": int(blk["repeticiones"]),
                                            "distancia": int(blk["distancia"]),
                                            "estilo_foco": blk["estilo"],
                                            "intensidad_porcentaje": float(blk["intensidad"]),
                                            # CORRECCIÓN MAESTRA: Se extraen únicamente los implementos de este bloque específico
                                            "implementos_usados": list(set(blk["implementos"]))
                                        }
                                        registros_supabase.append(fila_bitacora)
                                
                                # Inserción masiva limpia a través de la instancia global unificada de Supabase
                                if registros_supabase:
                                    try:
                                        # 1. Intentar la inserción masiva en Supabase
                                        supabase.table("bitacora_entrenamientos").insert(registros_supabase).execute()
                                        
                                        # 2. LIMPIEZA DE CACHÉ EN CALIENTE SELECTIVA
                                        # Al refrescar las marcas e hitos, forzamos a que Bannister tome las nuevas cargas inmediatamente
                                        from core.conexion import invalidar_cache_marcas
                                        invalidar_cache_marcas()
                                        
                                        # 3. Notificación de éxito y re-enrutado fluido de la interfaz
                                        st.success(f"💥 ¡Base de datos actualizada! Se grabaron con éxito las cargas individuales para los {len(atletas_asistieron)} atleta(s) en Supabase.")
                                        st.balloons()
                                        st.session_state.pizarra_entrenamiento = []  # Liberar pizarra tras el éxito
                                        st.rerun()
                                        
                                    except Exception as e:
                                        st.error(f"❌ Error crítico de comunicación con Supabase al consolidar cargas: {e}")                            else:
                                st.warning("⚠️ No hay atletas seleccionados en el grupo para consolidar.")
                    else:
                        st.info("No se registran nadadores activos en la plataforma para imputar asistencia.")
                except Exception as e:
                    st.error(f"Error crítico de sincronización en la bitácora: {e}")
            else:
                st.info("💡 La pizarra está vacía. Añade series de trabajo en el formulario superior para comenzar a armar el entrenamiento.")
        else:
            st.warning("🔒 Sección restringida al equipo técnico.")
# -------------------------------------------------------------------------
    # 📊 PESTAÑA 2: REPORTES Y RENDIMIENTO HISTÓRICO - BANNISTER (LA JOYA DE LA CORONA)
    # -------------------------------------------------------------------------
    with tab_reportes:
        if st.session_state.rol in ["Head Coach", "Entrenador", "Administrador"]:        
            st.markdown("### 📊 Panel de Control y Análisis de Carga")
            st.caption("Filtra la nómina de la misma forma que en la pizarra y define la ventana temporal para evaluar el volumen acumulado y el modelo matemático de Bannister.")

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
                index=3,  # Default: 42 días (Carga Crónica)
                key="rep_ventana_temporal"
            )
            dias_ventana = opciones_tiempo[ventana_sel]

            # =============================================================================
            # 2. CAPTURA DE ATLETAS ACTIVOS PARA ANÁLISIS SINDICALIZADO
            # =============================================================================
            try:
                resp_atletas_rep = supabase.table("usuarios").select("id, nombre").eq("rol", "Nadador").eq("estatus", "Activo").execute()
                lista_atletas_rep = resp_atletas_rep.data if resp_atletas_rep.data else []
            except Exception as e_atl:
                st.error(f"Error al conectar con la nómina de nadadores: {e_atl}")
                lista_atletas_rep = []

            if lista_atletas_rep:
                dict_atletas_rep = {a["id"]: a["nombre"] for a in lista_atletas_rep}
                atleta_rep_sel = st.selectbox(
                    "👤 Seleccione Atleta para Auditoría Fisiológica:",
                    options=list(dict_atletas_rep.keys()),
                    format_func=lambda x: dict_atletas_rep[x],
                    key="rep_atleta_analizado"
                )
                
                # =============================================================================
                # 3. EXTRACCIÓN HISTÓRICA E IMPUTACIÓN DE ALGORITMOS DE BANNISTER
                # =============================================================================
                try:
                    # Consulta directa a la bitácora operacional de entrenamientos consolidada
                    query_rep = supabase.table("bitacora_entrenamientos").select("*").eq("atleta_id", atleta_rep_sel).order("fecha", desc=False)
                    resp_data_rep = query_rep.execute()
                    
                    if not resp_data_rep.data:
                        st.info(f"💡 El atleta {dict_atletas_rep[atleta_rep_sel]} no registra entrenamientos consolidados en la base de datos.")
                    else:
                        df_rep_raw = pd.DataFrame(resp_data_rep.data)
                        df_rep_raw["fecha"] = pd.to_datetime(df_rep_raw["fecha"]).dt.date
                        
                        # Agrupación diaria y ponderación matemática por volumen e intensidad
                        df_rep_raw["volumen_ponderado"] = df_rep_raw["repeticiones"] * df_rep_raw["distancia"] * (df_rep_raw["intensidad_porcentaje"] / 100.0)
                        df_diario = df_rep_raw.groupby("fecha")["volumen_ponderado"].sum().reset_index()
                        
                        # Generación de la serie de tiempo continua completa sin baches temporales
                        fecha_min = df_diario["fecha"].min()
                        fecha_max = datetime.date.today()
                        idx_fechas_completas = pd.date_range(start=fecha_min, end=fecha_max).date
                        
                        df_completo = pd.DataFrame({"fecha": idx_fechas_completas})
                        df_completo = pd.merge(df_completo, df_diario, on="fecha", how="left").fillna(0.0)
                        
                        # --- IMPLEMENTACIÓN DEL MODELO MATEMÁTICO DE BANNISTER ---
                        ctl_lista = []
                        atl_lista = []
                        
                        ctl_ant = 0.0
                        atl_ant = 0.0
                        
                        # Constantes biológicas de decaimiento estándar del modelo (42 días vs 7 días)
                        tau_ctl = 42.0
                        tau_atl = 7.0
                        
                        for i, fila in df_completo.iterrows():
                            p_dia = fila["volumen_ponderado"]
                            
                            # Ecuaciones diferenciales iterativas de Bannister (Fitness / Fatiga)
                            ctl_act = ctl_ant + (p_dia - ctl_ant) * (1.0 / tau_ctl)
                            atl_act = atl_ant + (p_dia - atl_ant) * (1.0 / tau_atl)
                            
                            ctl_lista.append(ctl_act)
                            atl_lista.append(atl_act)
                            
                            ctl_ant = ctl_act
                            atl_ant = atl_act
                            
                        df_completo["CTL"] = ctl_lista
                        df_completo["ATL"] = atl_lista
                        df_completo["TSB"] = df_completo["CTL"] - df_completo["ATL"]  # Balance de Estrés del Atleta
                        
                        # Filtrado dinámico de la ventana elegida por el Head Coach
                        if dias_ventana is not None:
                            fecha_corte = datetime.date.today() - datetime.timedelta(days=dias_ventana)
                            df_filtrado_rep = df_completo[df_completo["fecha"] >= fecha_corte].copy()
                        else:
                            df_filtrado_rep = df_completo.copy()
                            
                        # =============================================================================
                        # 4. RENDERIZADO VISUAL DEL LIENZO DE CONTROL BIOLÓGICO
                        # =============================================================================
                        st.markdown("#### 📈 Gráfico Evolutivo de Carga Fisiológica (Modelo TRIMP / Bannister)")
                        
                        fig_ban, ax1_ban = plt.subplots(figsize=(10, 4.5))
                        
                        # Eje principal: Volumen y Fitness/Fatiga
                        ax1_ban.plot(df_filtrado_rep["fecha"], df_filtrado_rep["CTL"], color="#2980B9", linewidth=2.5, label="Fitness (CTL - Crónica)")
                        ax1_ban.plot(df_filtrado_rep["fecha"], df_filtrado_rep["ATL"], color="#E74C3C", linewidth=1.8, linestyle="--", alpha=0.8, label="Fatiga (ATL - Aguda)")
                        ax1_ban.bar(df_filtrado_rep["fecha"], df_filtrado_rep["volumen_ponderado"], color="#BDC3C7", alpha=0.3, label="Carga Diaria (m Ponderados)")
                        
                        ax1_ban.set_ylabel("Carga de Entrenamiento (Metros / Puntos)", color="#2C3E50", fontsize=9)
                        ax1_ban.grid(True, linestyle=":", color="#E2E8F0", alpha=0.6)
                        
                        # Eje secundario: Balance de Forma (TSB)
                        ax2_ban = ax1_ban.twinx()
                        ax2_ban.plot(df_filtrado_rep["fecha"], df_filtrado_rep["TSB"], color="#27AE60", linewidth=2.0, label="Forma / Puesta a Punto (TSB)")
                        ax2_ban.axhline(y=0.0, color="#7F8C8D", linestyle="-", linewidth=0.7, alpha=0.5)
                        ax2_ban.set_ylabel("Balance de Estrés del Atleta (TSB)", color="#27AE60", fontsize=9)
                        
                        # Unificación de leyendas de ambos ejes coordenados
                        lines1, labels1 = ax1_ban.get_legend_handles_labels()
                        lines2, labels2 = ax2_ban.get_legend_handles_labels()
                        ax1_ban.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=8)
                        
                        ax1_ban.set_title(f"Dinámica de Carga y Transición de Forma: {dict_atletas_rep[atleta_rep_sel]}", fontsize=11, weight="bold", pad=10)
                        fig_ban.tight_layout()
                        st.pyplot(fig_ban)
                        
# =============================================================================
                        # 5. TABLA RESUMEN DE CONTROL CRÍTICO E HIGIENE IMPRESA (CORREGIDA Y SEGURA)
                        # =============================================================================
                        st.markdown("#### 📋 Matriz Numérica de Transición y Estado Actual")
                        
                        df_tabla_ban = df_filtrado_rep.sort_values(by="fecha", ascending=False).copy()
                        df_tabla_ban["tsb_relativo"] = (df_tabla_ban["TSB"] / df_tabla_ban["CTL"].replace(0.0, np.nan)) * 100.0
                        df_tabla_ban["tsb_relativo"] = df_tabla_ban["tsb_relativo"].fillna(0.0)
                        
                        # Formateo estricto string para conservar el nivel de reporte ejecutivo
                        df_tabla_ban["fecha_str"] = df_tabla_ban["fecha"].apply(lambda x: x.strftime("%d/%m/%Y"))
                        df_tabla_ban["volumen_ponderado_str"] = df_tabla_ban["volumen_ponderado"].map("{:,.1f}m".format)
                        df_tabla_ban["CTL_str"] = df_tabla_ban["CTL"].map("{:.1f}".format)
                        df_tabla_ban["ATL_str"] = df_tabla_ban["ATL"].map("{:.1f}".format)
                        df_tabla_ban["TSB_str"] = df_tabla_ban["TSB"].map("{:.1f}".format)
                        df_tabla_ban["tsb_relativo_str"] = df_tabla_ban["tsb_relativo"].map("{:.1f}%".format)
                        
                        # FILTRADO Y RENOMBRADO SEGURO DE COLUMNAS EXPLICITAS
                        df_tabla_render = df_tabla_ban[[
                            "fecha_str", "volumen_ponderado_str", "CTL_str", "ATL_str", "TSB_str", "tsb_relativo_str"
                        ]].copy()
                        
                        df_tabla_render.columns = [
                            "Fecha", "Metros Ponderados (Día)", "CTL (Fitness m)", "ATL (Fatiga m)", "TSB (Forma m)", "TSB Relativo (% del CTL)"
                        ]
                        
                        # Inyección HTML exacta con clases institucionales
                        st.write(df_tabla_render.to_html(index=False, classes="tabla-estilizada"), unsafe_allow_html=True)
                        
                        # Botonera de descargas asociadas utilizando el DataFrame formateado limpio
                        csv_ban_data = df_tabla_render.to_csv(index=False).encode('utf-8')
                        txt_ban_data = df_tabla_render.to_string(index=False).encode('utf-8')
                        
                        st.markdown("<div style='padding-top:15px;'></div>", unsafe_allow_html=True)
                        c_ban_exp1, c_ban_exp2 = st.columns(2)
                        with c_ban_exp1:
                            st.download_button(
                                label="📥 Descargar Métricas de Estado (CSV)", 
                                data=csv_ban_data, 
                                file_name=f"metricas_bannister_{dict_atletas_rep[atleta_rep_sel]}.csv", 
                                mime="text/csv", 
                                use_container_width=True
                            )
                        with c_ban_exp2:
                            st.download_button(
                                label="📄 Descargar Reporte de Carga (TXT)", 
                                data=txt_ban_data, 
                                file_name=f"reporte_carga_{dict_atletas_rep[atleta_rep_sel]}.txt", 
                                mime="text/plain", 
                                use_container_width=True
                            )         
                except Exception as e:
                    st.error(f"Error al computar el reporte analítico avanzado: {e}")             
            else:
                st.info("No se registran atletas activos para auditoría fisiológica en esta temporada.")
        else:
            st.warning("🔒 Esta función está reservada exclusivamente para el cuerpo técnico.")