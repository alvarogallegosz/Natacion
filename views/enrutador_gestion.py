# =============================================================================
# 📁 views/enrutador_gestion.py - ENRUTADOR TEMÁTICO Y MÓDULOS DE GESTIÓN
# =============================================================================
import streamlit as st
import pandas as pd
import datetime

# Importación directa y limpia
from core.formulas import computar_modelo_bannister, calcular_edad_decimal

def renderizar_modulos_gestion(simulacion_externa: bool):
    """Despliega el sistema modular inyectado según privilegios."""
    supabase = st.session_state["supabase_client"]
    rol_usuario = st.session_state.get("rol")
    usuario_id = st.session_state.get("usuario_id")
    
    st.markdown("---")
    
    if rol_usuario == "Nadador":
        tab_pizarra, tab_reportes, tab_resultados = st.tabs(["📝 Mi Pizarra", "📊 Mis Reportes", "📋 Mis Resultados"])
    else:
        tab_pizarra, tab_reportes, tab_resultados, tab_asignaciones, tab_calendario, tab_admin = st.tabs([
            "📝 Pizarra de Entrenamiento", "📊 Reportes (Bannister)", "📋 Resultados de Competencia",
            "🎯 Asignación de Carriles", "📅 Cartelera de Eventos", "🛡️ Consola de Respaldo Global"
        ])

    # --- PIZARRA ---
    with tab_pizarra:
        if rol_usuario == "Nadador":
            st.info("🏊‍♂️ Módulo de Visualización de Cargas personales.")
            try:
                res_bit = supabase.table("bitacora_entrenamientos").select("*").eq("atleta_id", usuario_id).order("fecha", desc=True).execute()
                if res_bit.data:
                    df_bit_nad = pd.DataFrame(res_bit.data)
                    st.dataframe(df_bit_nad[["fecha", "identificador_carril", "metros_totales"]], use_container_width=True, hide_index=True)
                else:
                    st.caption("Aún no posees cargas de entrenamiento registradas.")
            except Exception as e:
                st.error(f"Error consultando bitácora: {e}")
        else:
            st.markdown("### 📝 Pizarra de Entrenamiento Diario")
            if "pizarra_entrenamiento" not in st.session_state:
                st.session_state.pizarra_entrenamiento = []

            with st.expander("➕ Añadir nueva serie", expanded=True):
                c_rep, c_dist, c_est = st.columns(3)
                with c_rep: repeticiones = st.number_input("Repeticiones", min_value=1, value=1, step=1)
                with c_dist: distancia = st.number_input("Distancia (m)", min_value=15, value=100, step=25)
                with c_est: estilo = st.selectbox("Estilo", ["Libre", "Espalda", "Pecho", "Mariposa", "Combinado"])
                intensidad = st.select_slider("Zona", options=["Z1", "Z2", "Z3", "Z4", "Z5"], value="Z2")
                
                if st.button("Añadir a la Pizarra"):
                    st.session_state.pizarra_entrenamiento.append({
                        "repeticiones": repeticiones, "distancia": distancia, "estilo": estilo, "metros": repeticiones * distancia, "intensidad": intensidad
                    })
                    st.rerun()

            if st.session_state.pizarra_entrenamiento:
                for idx, blk in enumerate(st.session_state.pizarra_entrenamiento):
                    st.markdown(f"**{idx+1}.** {blk['repeticiones']} x {blk['distancia']}m ({blk['estilo']}) — **Total:** {blk['metros']}m")
                
                if st.button("🗑️ Vaciar Pizarra"):
                    st.session_state.pizarra_entrenamiento = []
                    st.rerun()

    # --- BANNISTER ---
    with tab_reportes:
        st.markdown("### 📊 Laboratorio Fisiológico de Bannister")
        nad_obj_id = usuario_id if rol_usuario == "Nadador" else st.session_state.get("nadador_seleccionado_id")
        if nad_obj_id:
            try:
                r_cargas = supabase.table("bitacora_entrenamientos").select("fecha, metros_totales").eq("atleta_id", nad_obj_id).execute()
                if r_cargas.data:
                    df_cargas_atleta = pd.DataFrame(r_cargas.data)
                    df_cargas_atleta['fecha'] = pd.to_datetime(df_cargas_atleta['fecha']).dt.date
                    rango_diario = pd.date_range(end=datetime.date.today(), periods=90).date
                    df_diario_base = pd.DataFrame({'fecha': rango_diario})
                    
                    res_bannister = computar_modelo_bannister(df_cargas_atleta, df_diario_base, ventana_dias=42)
                    if not res_bannister.empty:
                        st.dataframe(res_bannister, use_container_width=True)
                else:
                    st.info("El atleta no posee registros de entrenamiento.")
            except Exception as e:
                st.error(f"Error cargando Bannister: {e}")

    # --- RESULTADOS ---
    with tab_resultados:
        st.markdown("### 📋 Resultados de Competencia")
        nad_id_consulta = usuario_id if rol_usuario == "Nadador" else st.session_state.get("nadador_seleccionado_id")
        if nad_id_consulta:
            try:
                res_hist_completo = supabase.table("marcas_historicas").select("prueba, edad, tiempo, nota").eq("usuario_id", nad_id_consulta).execute()
                if res_hist_completo.data:
                    st.dataframe(pd.DataFrame(res_hist_completo.data), use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"Error consultando historial: {e}")

    # --- PRIVILEGIOS DE ENTRENADOR/ADMIN ---
    if rol_usuario != "Nadador":
        with tab_asignaciones:
            st.subheader("🎯 Asignación de Carriles")
        with tab_calendario:
            st.subheader("📅 Cronograma de Eventos")
        with tab_admin:
            st.subheader("🛡️ Consola de Respaldo Global")