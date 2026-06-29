# =============================================================================
# 📁 views/rendimiento.py - ZONA BLANCA CENTRAL CON SELECTOR DE MODO Y CATÁLOGO FINA
# =============================================================================
import streamlit as st
import pandas as pd

def renderizar_pestana_rendimiento(simulacion_activa_global: bool):
    supabase = st.session_state["supabase_client"]
    modo_sidebar = st.session_state.get("modo_operacion", "Individual")
    
    # Si la barra lateral activó simulación externa, se respeta ese modo
    if modo_sidebar == "Visitante (Simulación Externa)":
        modo_activo = "Visitante (Simulación Externa)"
    else:
        # En caso contrario, el usuario decide en la zona blanca si es Individual o Equipo
        modo_activo = "Individual"
        
    st.markdown(
        """
        <style>
            .divisor-blanco { margin-top: 4px !important; margin-bottom: 12px !important; border-bottom: 1px solid #eaeaea; }
            [data-testid="stHorizontalBlock"] { gap: 1rem !important; }
        </style>
        """, 
        unsafe_allow_html=True
    )
    
    # -------------------------------------------------------------------------
    # 🔭 ZONA BLANCA SUPERIOR: DISTRIBUCIÓN HORIZONTAL COMPACTA
    # -------------------------------------------------------------------------
    c_col_modo, c_col_escala, c_col_prueba = st.columns([1, 1, 2])
    
    with c_col_modo:
        if modo_sidebar != "Visitante (Simulación Externa)":
            eleccion_analisis = st.radio(
                "📋 Tipo de Análisis:", 
                ["Individual", "Equipo"],
                horizontal=False,
                key="eleccion_analisis_radio"
            )
            st.session_state["modo_operacion"] = eleccion_analisis
            modo_actual_render = eleccion_analisis
        else:
            st.markdown("**Modo Activo:**")
            st.info("🧪 Simulación Externa")
            modo_actual_render = "Visitante"

    with c_col_escala:
        tipo_vista = st.radio(
            "🔭 Escala del Gráfico:", 
            ["Macro (Historial Completo)", "Micro (Ventana Anual)"],
            horizontal=False,
            key="escala_grafico_radio"
        )
        st.session_state["tipo_vista"] = tipo_vista

    with c_col_prueba:
        # Catálogo estricto indexado (Inalterable)
        CATALOGO_OFICIAL_FINA = (
            "50m Libre", "100m Libre", "200m Libre", "400m Libre", "800m Libre", "1500m Libre",
            "50m Espalda", "100m Espalda", "200m Espalda",
            "50m Mariposa", "100m Mariposa", "200m Mariposa",
            "50m Pecho", "100m Pecho", "200m Pecho",
            "200m CI", "400m CI"
        )
        prueba_sel = st.selectbox(
            "🏊 Catálogo de Pruebas Oficiales (Orden FINA):",
            options=CATALOGO_OFICIAL_FINA,
            index=1,
            key="selector_fina_permanente"
        )
        st.session_state["prueba_seleccionada"] = prueba_sel

    # -------------------------------------------------------------------------
    # 🔎 LÓGICA DE CÁLCULOS AUTOMÁTICOS (PREDETERMINADOS)
    # -------------------------------------------------------------------------
    genero_atleta = st.session_state.get("nadador_seleccionado_genero", "F")
    atleta_id = st.session_state.get("nadador_seleccionado_id")
    
    # 1. Récord mundial y Target +5%
    record_mundial = 50.0
    try:
        r_rm = supabase.table("marcas_referencia").select("record_mundial").eq("prueba", prueba_sel).eq("genero", genero_atleta).execute()
        if r_rm.data and r_rm.data[0].get("record_mundial"):
            record_mundial = float(r_rm.data[0]["record_mundial"])
    except Exception:
        pass
    
    target_5_porciento = round(record_mundial * 1.05, 2)
    st.session_state["target_calculado_rm"] = target_5_porciento

    # 2. Edad PB para ventana Micro (+1 año por defecto)
    t_pb_real = 11.33
    if modo_actual_render == "Visitante":
        v_hitos = st.session_state.get("visitante_hitos", {"t_pb": 11.33})
        t_pb_real = float(v_hitos.get("t_pb", 11.33))
    elif atleta_id:
        try:
            r_pb = supabase.table("marcas_historicas").select("edad").eq("usuario_id", atleta_id).eq("prueba", prueba_sel).order("tiempo", ascending=True).limit(1).execute()
            if r_pb.data:
                t_pb_real = float(r_pb.data[0]["edad"])
        except Exception:
            pass

    # Slider de Zoom dependiente del modo Micro
    edad_min_zoom, edad_max_zoom = 8.0, 22.0
    if "Micro" in tipo_vista:
        val_inicial = float(round(t_pb_real, 2))
        val_final = float(round(t_pb_real + 1.0, 2))
        st.markdown("")
        edad_min_zoom, edad_max_zoom = st.slider(
            "🔎 Ventana Enfocada (Predeterminada: +1 Año desde Marca Personal):",
            min_value=8.0, max_value=26.0, value=(val_inicial, val_final), step=0.01, format="%.2f años"
        )
    
    st.session_state["zoom_edades"] = (edad_min_zoom, edad_max_zoom)

    st.markdown('<div class="divisor-blanco"></div>', unsafe_allow_html=True)
    
    # Panel Informativo provisional
    st.info(f"Modo: **{modo_actual_render}** | **Prueba:** {prueba_sel} | **Escala:** {tipo_vista.split(' ')[0]}")
