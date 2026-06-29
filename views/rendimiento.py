# =============================================================================
# 📁 views/rendimiento.py - INTERFAZ HORIZONTAL CON DIVISORES COMPACTOS
# =============================================================================
import streamlit as st

def renderizar_pestana_rendimiento(simulacion_activa_global: bool):
    """
    Renderiza la sección blanca utilizando divs CSS personalizados para separar
    de forma ultra delgada y no desplazar el gráfico principal.
    """
    modo_activo = st.session_state.get("modo_operacion", "Individual")
    
    # CSS inyectado para reducir la separación excesiva en los bloques horizontales de la zona blanca
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
    # 🔭 LÓGICA DE DISTRIBUCIÓN HORIZONTAL EN ZONA BLANCA (MÁXIMA ERGONOMÍA)
    # -------------------------------------------------------------------------
    c_col1, c_col2 = st.columns([1, 2])
    
    with c_col1:
        tipo_vista = st.radio(
            "🔭 Escala del Gráfico:", 
            ["Macro (Historial Completo)", "Micro (Ventana Anual)"],
            horizontal=False
        )
        st.session_state["tipo_vista"] = tipo_vista

    with c_col2:
        pruebas_ordenadas_fina = [
            "50m Libre", "100m Libre", "200m Libre", "400m Libre", "800m Libre", "1500m Libre",
            "50m Espalda", "100m Espalda", "200m Espalda",
            "50m Mariposa", "100m Mariposa", "200m Mariposa",
            "50m Pecho", "100m Pecho", "200m Pecho",
            "200m CI", "400m CI"
        ]
        
        prueba_sel = st.selectbox(
            "🏊 Catálogo de Pruebas Oficiales (Orden FINA):",
            options=pruebas_ordenadas_fina,
            index=1
        )
        st.session_state["prueba_seleccionada"] = prueba_sel

    # Zoom de rango de edades en fila horizontal compacta si es Micro
    edad_min_zoom, edad_max_zoom = 8.0, 22.0
    if "Micro" in tipo_vista:
        edad_min_zoom, edad_max_zoom = st.slider(
            "🔎 Ventana Enfocada (Edad):",
            min_value=8.0, max_value=22.0, value=(11.0, 16.0), step=0.1, format="%.1f años"
        )
    
    st.session_state["zoom_edades"] = (edad_min_zoom, edad_max_zoom)

    # Divisor ultra delgado estilizado
    st.markdown('<div class="divisor-blanco"></div>', unsafe_allow_html=True)
    
    # Bloque informativo provisional alineado con el estado síncrono de los controles
    st.info(f"Visualización activa: **Modo {modo_activo}** | **Prueba:** {prueba_sel} | **Escala:** {tipo_vista}")
    st.caption("Los controles superiores y laterales ya se comunican en tiempo real sin desperdiciar píxeles verticales.")
