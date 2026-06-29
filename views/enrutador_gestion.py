# =============================================================================
# 📁 views/enrutador_gestion.py - ENRUTADOR TEMÁTICO Y MÓDULOS DE GESTIÓN
# =============================================================================
import streamlit as st
import pandas as pd
import datetime
from core.formulas import computar_modelo_bannister, calcular_edad_decimal

def renderizar_modulos_gestion(simulacion_externa: bool):
    """
    Despliega el sistema modular inyectado según los privilegios del usuario autenticado.
    Oculta o restringe vistas, protege la base de datos e instancia botones de soberanía de datos.
    """
    supabase = st.session_state["supabase_client"]
    rol_usuario = st.session_state.get("rol")
    usuario_id = st.session_state.get("usuario_id")
    
    st.markdown("---")
    
    # =========================================================================
    # 📍 CHECKPOINT 9: CONMUTADOR DE PESTAÑAS REACTIVO POR ROLES
    # =========================================================================
    if rol_usuario == "Nadador":
        # Restricción absoluta de pestañas técnicas, administrativas o de control de carriles
        tab_pizarra, tab_reportes, tab_resultados = st.tabs([
            "📝 Mi Pizarra", 
            "📊 Mis Reportes", 
            "📋 Mis Resultados"
        ])
    else:
        # Visualización completa para Equipo Técnico, Entrenadores, Head Coach y Admin
        tab_pizarra, tab_reportes, tab_resultados, tab_asignaciones, tab_calendario, tab_admin = st.tabs([
            "📝 Pizarra de Entrenamiento", 
            "📊 Reportes (Bannister)", 
            "📋 Resultados de Competencia",
            "🎯 Asignación de Carriles",
            "📅 Cartelera de Eventos", 
            "🛡️ Consola de Respaldo Global"
        ])

    # =========================================================================
    # 📍 CHECKPOINT 10: PIZARRA DE ENTRENAMIENTO DIARIO Y REGISTRO DE CARGAS
    # =========================================================================
    with tab_pizarra:
        if rol_usuario == "Nadador":
            st.info("🏊‍♂️ Módulo de Visualización de Cargas. En esta sección consultarás tus entrenamientos al ser procesados por el cuerpo técnico.")
            # Consulta de la bitácora personal en modo solo lectura
            try:
                res_bit = supabase.table("bitacora_entrenamientos").select("*")\
                    .eq("atleta_id", usuario_id)\
                    .order("fecha", desc=True)\
                    .execute()
                if res_bit.data:
                    df_bit_nad = pd.DataFrame(res_bit.data)
                    st.dataframe(df_bit_nad[["fecha", "identificador_carril", "metros_totales"]], use_container_width=True, hide_index=True)
                else:
                    st.caption("Aún no posees cargas de entrenamiento registradas en la bitácora.")
            except Exception as e:
                st.error(f"Error consultando bitácora personal: {e}")
        
        else:
            st.markdown("### 📝 Pizarra de Entrenamiento Diario")
            st.caption("Diseña la sesión agregando bloques. Al finalizar, controla la asistencia para imputar la carga individual.")
            
            if "pizarra_entrenamiento" not in st.session_state:
                st.session_state.pizarra_entrenamiento = []

            with st.expander("➕ Añadir nueva serie al entrenamiento", expanded=True):
                c_rep, c_dist, c_est = st.columns(3)
                with c_rep:
                    repeticiones = st.number_input("Repeticiones", min_value=1, value=1, step=1, key="piz_rep")
                with c_dist:
                    distancia = st.number_input("Distancia (m)", min_value=15, value=100, step=25, key="piz_dist")
                with c_est:
                    estilo = st.selectbox("Estilo / Foco", ["Libre", "Espalda", "Pecho", "Mariposa", "Combinado", "Pierna", "Brazo"])
                
                intensidad = st.select_slider("Zona de Intensidad", options=["Z1 (Recuperación)", "Z2 (Aeróbico Ligero)", "Z3 (Aeróbico Medio)", "Z4 (Umbral Anaeróbico)", "Z5 (VO2 Máximo)"], value="Z2 (Aeróbico Ligero)")
                implemento = st.multiselect("Implementos Usados", ["Tabla", "Pullbuoy", "Paletas", "Aletas", "Snorkel", "Ninguno"])
                
                if st.form_submit_button("Añadir a la Pizarra de la Sesión"):
                    meta_serie = repeticiones * distancia
                    st.session_state.pizarra_entrenamiento.append({
                        "repeticiones": repeticiones,
                        "distancia": distancia,
                        "estilo": estilo,
                        "metros": meta_serie,
                        "intensidad": intensidad,
                        "implementos": implemento
                    })
                    st.rerun()

            st.markdown("##### Estructura Actual de la Sesión")
            if st.session_state.pizarra_entrenamiento:
                for idx, blk in enumerate(st.session_state.pizarra_entrenamiento):
                    st.markdown(f"**{idx+1}.** {blk['repeticiones']} x {blk['distancia']}m ({blk['estilo']}) — **Total:** {blk['metros']}m | Intensidad: `{blk['intensidad']}`")
                
                if st.button("🗑️ Vaciar Pizarra", type="primary"):
                    st.session_state.pizarra_entrenamiento = []
                    st.rerun()
                
                st.markdown("---")
                st.markdown("##### 👥 Control de Asistencia e Imputación de Carga")
                
                # Listado de atletas disponibles para control de asistencia
                atletas_activos = []
                try:
                    r_hc = supabase.table("usuarios").select("id, nombre, genero, fecha_nacimiento").eq("rol", "Nadador").execute()
                    atletas_activos = r_hc.data if r_hc.data else []
                except Exception as e:
                    st.error(f"Error cargando nómina de atletas: {e}")

                if atletas_activos:
                    dict_asist = {n["id"]: n["nombre"] for n in atletas_activos}
                    asistentes_sel = st.multiselect("Selecciona los atletas presentes en esta sesión:", options=list(dict_asist.keys()), format_func=lambda x: dict_asist[x])
                    carril_imputar = st.text_input("Identificador de Carril o Grupo de Trabajo:", "Carril Principal")
                    
                    if st.button("💾 Consolidar y Expandir Transacción en BD"):
                        if not simulacion_externa:
                            if asistentes_sel and st.session_state.pizarra_entrenamiento:
                                metros_sesion = sum([b["metros"] for b in st.session_state.pizarra_entrenamiento])
                                
                                # Consolidación del desglose de estilos e intensidades
                                desglose_est = {}
                                desglose_int = {}
                                implementos_lista = set()
                                
                                for b in st.session_state.pizarra_entrenamiento:
                                    est = b["estilo"]
                                    d_est = b["metros"]
                                    desglose_est[est] = desglose_est.get(est, 0) + d_est
                                    
                                    inte = b["intensidad"]
                                    d_int = b["metros"]
                                    desglose_int[inte] = desglose_int.get(inte, 0) + d_int
                                    
                                    for imp in b["implementos"]:
                                        implementos_lista.add(imp)

                                # Expansión transaccional por lotes (N series x M atletas)
                                registros_transaccionales = []
                                for atleta_id_item in asistentes_sel:
                                    registros_transaccionales.append({
                                        "fecha": datetime.date.today().isoformat(),
                                        "atleta_id": atleta_id_item,
                                        "identificador_carril": carril_imputar,
                                        "metros_totales": metros_sesion,
                                        "desglose_estilos": desglose_est,
                                        "desglose_intensidad": desglose_int,
                                        "implementos_usados": list(implementos_lista)
                                    })
                                    
                                try:
                                    supabase.table("bitacora_entrenamientos").insert(registros_transaccionales).execute()
                                    st.success(f"💥 ¡Lotes transaccionales insertados con éxito! Cargas registradas para {len(asistentes_sel)} atleta(s).")
                                except Exception as e:
                                    st.error(f"Error al ejecutar la expansión transaccional: {e}")
                            else:
                                st.warning("⚠️ La pizarra está vacía o no se seleccionaron atletas para imputar asistencia.")
                        else:
                            st.info("🔒 Modo Simulación Activo. Las inserciones en la base de datos se encuentran bloqueadas.")
            else:
                st.info("La pizarra se encuentra vacía. Añade series para continuar.")

    # =========================================================================
    # 📍 CHECKPOINT 11: LABORATORIO FISIOLÓGICO (MODELO DE BANNISTER)
    # =========================================================================
    with tab_reportes:
        if rol_usuario == "Nadador":
            st.markdown("### 📊 Mis Reportes Fisiológicos (Modelo de Bannister - Solo Lectura)")
            st.caption("Evolución de tu estado físico (CTL), fatiga (ATL) y forma deportiva (TSB).")
        else:
            st.markdown("### 📊 Laboratorio Fisiológico de Bannister")
            st.caption("Visualiza el modelo impulso-respuesta analítico computado a 42 días.")

        nad_obj_id = usuario_id if rol_usuario == "Nadador" else st.session_state.get("nadador_seleccionado_id")
        
        if nad_obj_id:
            try:
                # Obtenemos la carga histórica del atleta
                r_cargas = supabase.table("bitacora_entrenamientos").select("fecha, metros_totales")\
                    .eq("atleta_id", nad_obj_id)\
                    .execute()
                
                if r_cargas.data:
                    df_cargas_atleta = pd.DataFrame(r_cargas.data)
                    df_cargas_atleta['fecha'] = pd.to_datetime(df_cargas_atleta['fecha']).dt.date
                    
                    # Generamos el rango de los últimos 90 días para el cálculo secuencial diario
                    rango_diario = pd.date_range(end=datetime.date.today(), periods=90).date
                    df_diario_base = pd.DataFrame({'fecha': rango_diario})
                    df_diario_base.columns = ['fecha']
                    
                    # Computamos la analítica utilizando la función del Checkpoint 4
                    res_bannister = computar_modelo_bannister(df_cargas_atleta, df_diario_base, ventana_dias=42)
                    
                    if not res_bannister.empty:
                        # Limpieza y estructuración en formato de tabla html con el CSS global
                        res_bannister.columns = ["Fecha", "Metros Ponderados (Día)", "CTL (Fitness)", "ATL (Fatiga)", "TSB (Forma)", "TSB Relativo (%)"]
                        st.write(res_bannister.to_html(index=False, classes="tabla-estilizada"), unsafe_allow_html=True)
                        
                        # Generación de botones de soberanía de descarga para el centro de reportes
                        csv_ban = res_bannister.to_csv(index=False).encode('utf-8')
                        txt_ban = res_bannister.to_string(index=False)
                        
                        b1, b2 = st.columns(2)
                        with b1:
                            st.download_button("📥 Descargar Métricas (CSV)", data=csv_ban, file_name="metricas_bannister.csv", mime="text/csv", use_container_width=True)
                        with b2:
                            st.download_button("📄 Descargar Reporte (TXT)", data=txt_ban, file_name="reporte_bannister.txt", mime="text/plain", use_container_width=True)
                    else:
                        st.info("Insuficiente densidad de datos para diagramar el modelo de Bannister en este rango.")
                else:
                    st.info("El atleta seleccionado no posee registros de entrenamiento en la bitácora.")
            except Exception as e:
                st.error(f"Error cargando modelo de Bannister: {e}")
        else:
            st.warning("⚠️ Selecciona un atleta en la barra lateral para desplegar el laboratorio.")

    # =========================================================================
    # 📍 CHECKPOINT 12: RESULTADOS DE COMPETENCIA Y SOBERANÍA DE DATOS
    # =========================================================================
    with tab_resultados:
        st.markdown("### 📋 Resultados de Competencia y Carga Federativa")
        
        # Formulario para inserción quirúrgica de marcas
        if rol_usuario != "Nadador":
            st.markdown("**Ingresar Marca Oficial al Historial**")
            with st.form("form_insertar_marca", clear_on_submit=True):
                ins_fecha = st.date_input("Fecha de la Competencia:", value=datetime.date.today(), max_value=datetime.date.today())
                ins_tiempo = st.number_input("Tiempo Oficial (seg):", min_value=10.0, max_value=600.0, step=0.01)
                ins_nota = st.text_input("Nombre del Evento o Nota de Referencia:")
                
                if st.form_submit_button("💾 Guardar Registro Histórico"):
                    if not simulacion_externa:
                        id_atleta = st.session_state.get("nadador_seleccionado_id")
                        f_nac_atleta = st.session_state.get("fecha_nacimiento")
                        prueba_foco = st.session_state.get("prueba_rendimiento_foco", "50 Libre") # Respaldo por si no se ha seleccionado prueba en el lienzo
                        
                        if id_atleta and f_nac_atleta:
                            # Cálculo de edad decimal histórica en tiempo real (Checkpoint 4)
                            edad_decimal_marca = calcular_edad_decimal(f_nac_atleta, ins_fecha)
                            
                            dic_nueva_marca = {
                                "usuario_id": id_atleta,
                                "prueba": "50 Libre", # Estandarizado para evitar nulos
                                "tiempo": ins_tiempo,
                                "edad": edad_decimal_marca,
                                "nota": ins_nota
                            }
                            
                            try:
                                supabase.table("marcas_historicas").insert(dic_nueva_marca).execute()
                                st.success("🎉 ¡Marca histórica registrada de forma quirúrgica en la bitácora del atleta!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al insertar marca histórica: {e}")
                        else:
                            st.warning("Selecciona un atleta válido y verifica que su fecha de nacimiento esté registrada.")
                    else:
                        st.info("🔒 Modo Simulación Activo. No se permiten escrituras en la base de datos real.")
        
        st.markdown("---")
        st.markdown("##### 📥 Soberanía de Datos del Atleta")
        nad_id_consulta = usuario_id if rol_usuario == "Nadador" else st.session_state.get("nadador_seleccionado_id")
        
        if nad_id_consulta:
            try:
                res_hist_completo = supabase.table("marcas_historicas").select("prueba, edad, tiempo, nota")\
                    .eq("usuario_id", nad_id_consulta)\
                    .execute()
                if res_hist_completo.data:
                    df_hist = pd.DataFrame(res_hist_completo.data)
                    st.dataframe(df_hist, use_container_width=True, hide_index=True)
                    
                    # Botón de respaldo local CSV personalizado para el atleta o entrenador
                    csv_vida_deportiva = df_hist.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="💾 Descargar Respaldo de mi Vida Deportiva (CSV)",
                        data=csv_vida_deportiva,
                        file_name=f"historial_completo_{st.session_state.get('nombre')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("No existen marcas oficiales almacenadas en la bitácora para este perfil.")
            except Exception as e:
                st.error(f"Error consultando historial de competencias: {e}")

    # =========================================================================
    # PESTAÑAS TÉCNICAS Y ADMINISTRATIVAS (VISIBILIDAD EXCLUYENTE)
    # =========================================================================
    if rol_usuario != "Nadador":
        
        # =====================================================================
        # 📍 CHECKPOINT 13: CONFIGURACIÓN DE UMBRALES TÉCNICOS Y CALENDARIO
        # =====================================================================
        with tab_asignaciones:
            if rol_usuario in ["Head Coach", "Administrador"]:
                st.subheader("🎯 Asignación Quirúrgica de Carriles")
                
                try:
                    # Obtenemos entrenadores y nadadores activos (Checkpoints 5 & 14)
                    r_ent = supabase.table("usuarios").select("id, nombre").eq("rol", "Entrenador").eq("estatus", "Activo").execute()
                    l_ent = r_ent.data if r_ent.data else []
                    
                    r_nad = supabase.table("usuarios").select("id, nombre").eq("rol", "Nadador").eq("estatus", "Activo").execute()
                    l_nad = r_nad.data if r_nad.data else []
                    
                    if l_ent and l_nad:
                        dict_ents = {e["id"]: e["nombre"] for e in l_ent}
                        dict_nads = {n["id"]: n["nombre"] for n in l_nad}
                        
                        st.markdown("##### 👤 Asignación Individual Uno a Uno")
                        asig_ent = st.selectbox("Seleccionar Asistente:", options=list(dict_ents.keys()), format_func=lambda x: dict_ents[x])
                        asig_nad = st.selectbox("Seleccionar Atleta:", options=list(dict_nads.keys()), format_func=lambda x: dict_nads[x])
                        
                        if st.button("🔗 Enlazar Atleta a Asistente"):
                            if not simulacion_externa:
                                # Eliminamos asignación previa de este atleta de manera quirúrgica para evitar duplicados
                                supabase.table("asignaciones").delete().eq("atleta_id", asig_nad).execute()
                                # Registramos la nueva asignación
                                supabase.table("asignaciones").insert({"entrenador_id": asig_ent, "atleta_id": asig_nad}).execute()
                                st.success(f"Asignado correctamente: **{dict_nads[asig_nad]}** bajo la tutela de **{dict_ents[asig_ent]}**.")
                                st.rerun()
                            else:
                                st.info("🔒 Modo Simulación Activo. Esta acción se encuentra inhabilitada.")
                                
                        st.markdown("---")
                        st.markdown("##### ✂️ Desasignación Quirúrgica")
                        # Botón fulminante de borrado masivo borrado; solo se desasigna de forma unitaria
                        r_actuales = supabase.table("asignaciones").select("id, entrenador_id, atleta_id").execute()
                        l_actuales = r_actuales.data if r_actuales.data else []
                        
                        if l_actuales:
                            dict_asig_display = {a["id"]: f"{dict_nads.get(a['atleta_id'], 'Desconocido')} ➔ {dict_ents.get(a['entrenador_id'], 'Desconocido')}" for a in l_actuales}
                            asig_a_borrar = st.selectbox("Selecciona la tuición a disolver:", options=list(dict_asig_display.keys()), format_func=lambda x: dict_asig_display[x])
                            
                            if st.button("❌ Disolver Tuición Seleccionada (Uno a Uno)"):
                                if not simulacion_externa:
                                    supabase.table("asignaciones").delete().eq("id", asig_a_borrar).execute()
                                    st.success("Tuición disuelta de forma limpia y quirúrgica.")
                                    st.rerun()
                                else:
                                    st.info("🔒 Modo Simulación Activo.")
                        else:
                            st.caption("No existen tuiciones o asignaciones de carriles enlazadas actualmente.")
                    else:
                        st.info("Se requiere personal técnico (Entrenadores) y deportivo (Nadadores) activos para gestionar carriles.")
                except Exception as e:
                    st.error(f"Error operando el panel de carriles: {e}")
            else:
                st.warning("🔒 Espacio restringido al Head Coach o Administrador.")

        # =====================================================================
        # 📍 CHECKPOINT 14: AGENDA Y PURGA DE HITOS (ELIMINACIÓN HISTORIAL_HITOS)
        # =====================================================================
        with tab_calendario:
            st.markdown("### 📅 Cronograma y Cartelera de Eventos")
            temporada_actual = datetime.date.today().year
            
            # 1. Calendario de consulta pública (Erradicación total de la tabla rota de hitos)
            try:
                resp_comp = supabase.table("catalogo_competencias").select("*")\
                    .eq("temporada", temporada_actual)\
                    .order("fecha_inicio", desc=False)\
                    .execute()
                if resp_comp.data:
                    df_comp = pd.DataFrame(resp_comp.data)
                    df_comp["fecha_inicio"] = pd.to_datetime(df_comp["fecha_inicio"]).dt.strftime('%d-%m-%Y')
                    df_comp["fecha_fin"] = pd.to_datetime(df_comp["fecha_fin"]).dt.strftime('%d-%m-%Y')
                    
                    st.dataframe(df_comp[["nombre_evento", "ente_rector", "categoria_evento", "fecha_inicio", "fecha_fin"]], use_container_width=True, hide_index=True)
                    
                    csv_cal = df_comp.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Descargar Cronograma (CSV)", data=csv_cal, file_name=f"cronograma_{temporada_actual}.csv", mime="text/csv")
                else:
                    st.info(f"No hay eventos programados en el catálogo para la temporada {temporada_actual}.")
            except Exception as e:
                st.error(f"Error cargando calendario: {e}")

            # 2. Sección para añadir nuevas competencias (Solo personal autorizado)
            if rol_usuario in ["Head Coach", "Administrador"]:
                st.markdown("---")
                st.markdown("**Añadir Evento al Cronograma**")
                with st.form("form_add_comp", clear_on_submit=True):
                    nombre_ev = st.text_input("Nombre del Evento:")
                    rector_ev = st.text_input("Ente Rector (Ej: FEVEDA, World Aquatics):")
                    cat_ev = st.text_input("Categoría del Evento (Ej: Juvenil, Abierto):")
                    f_ini = st.date_input("Fecha de Inicio:")
                    f_fin = st.date_input("Fecha de Finalización:")
                    
                    if st.form_submit_button("➕ Registrar Evento"):
                        if not simulacion_externa:
                            if nombre_ev:
                                supabase.table("catalogo_competencias").insert({
                                    "nombre_evento": nombre_ev,
                                    "ente_rector": rector_ev,
                                    "categoria_evento": cat_ev,
                                    "fecha_inicio": f_ini.isoformat(),
                                    "fecha_fin": f_fin.isoformat(),
                                    "temporada": temporada_actual
                                }).execute()
                                st.success("Evento programado satisfactoriamente.")
                                st.rerun()
                            else:
                                st.warning("El nombre del evento es obligatorio.")
                        else:
                            st.info("🔒 Modo Simulación Activo.")

        # =====================================================================
        # 📍 CHECKPOINT 15: CONSOLIDA ADMIN Y MASTER BACKUP
        # =====================================================================
        with tab_admin:
            if rol_usuario == "Administrador":
                st.markdown("### 🛡️ Bóveda de Salvaguarda y Respaldo Local (Master Backup)")
                st.caption("Panel blindado exclusivo para la gestión de respaldos e integridad de los datos del club.")
                
                # Tablas del sistema a respaldar
                tablas_respaldo = ["usuarios", "marcas_historicas", "marcas_referencia", "bitacora_entrenamientos", "catalogo_competencias", "asignaciones"]
                tabla_sel = st.selectbox("Seleccionar tabla a auditar o descargar:", options=tablas_respaldo)
                
                try:
                    r_tabla = supabase.table(tabla_sel).select("*").execute()
                    if r_tabla.data:
                        df_tabla = pd.DataFrame(r_tabla.data)
                        st.dataframe(df_tabla, use_container_width=True)
                        
                        csv_respaldo = df_tabla.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label=f"📥 Descargar Tabla '{tabla_sel}' (CSV)",
                            data=csv_respaldo,
                            file_name=f"respaldo_{tabla_sel}_{datetime.date.today().isoformat()}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                    else:
                        st.info(f"La tabla '{tabla_sel}' se encuentra vacía actualmente.")
                except Exception as e:
                    st.error(f"Error al procesar el respaldo de la tabla: {e}")
            else:
                st.warning("🔒 Consola Global de Respaldo exclusiva para Administradores.")