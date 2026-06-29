# =============================================================================
# 📁 views/rendimiento.py - CONTROLES HORIZONTALES SUPERIORES EN ZONA BLANCA
# =============================================================================
import streamlit as st
import pandas as pd
import numpy as np

def renderizar_pestana_rendimiento(simulacion_activa_global: bool):
    """
    Renderiza la zona blanca central distribuyendo los controles de interacción directa
    en la parte superior de la pantalla antes del gráfico.
    """
    # Leer el modo de operación dictado por la Sidebar
    modo_activo = st.session_state.get("modo_operacion", "Individual")
    
    # -------------------------------------------------------------------------
    # 🔭 DISTRIBUCIÓN HORIZONTAL EN EN ZONA BLANCA (COLUMNAS COMPACTAS)
    # -------------------------------------------------------------------------
    c_col1, c_col2 = st.columns([1, 2])
    
    with c_col1:
        # Columna 1: Selector Macro / Micro pegado al lente del gráfico
        tipo_vista = st.radio(
            "🔭 Escala del Gráfico:", 
            ["Macro (Historial Completo)", "Micro (Ventana Anual)"],
            horizontal=False
        )
        st.session_state["tipo_vista"] = tipo_vista

    with c_col2:
        # Columna 2: Catálogo de pruebas estructurado en estricto ORDEN REGLAMENTARIO FINA
        pruebas_ordenadas_fina = [
            # Estilo Libre (Crol)
            "50m Libre", "100m Libre", "200m Libre", "400m Libre", "800m Libre", "1500m Libre",
            # Estilo Espalda
            "50m Espalda", "100m Espalda", "200m Espalda",
            # Estilo Mariposa
            "50m Mariposa", "100m Mariposa", "200m Mariposa",
            # Estilo Pecho (Braza)
            "50m Pecho", "100m Pecho", "200m Pecho",
            # Estilos Combinados
            "200m CI", "400m CI"
        ]
        
        prueba_sel = st.selectbox(
            "🏊 Catálogo de Pruebas Oficiales (Orden FINA):",
            options=pruebas_ordenadas_fina,
            index=1 # Por defecto 100m Libre
        )
        st.session_state["prueba_seleccionada"] = prueba_sel

    # Fila Inferior de la Zona Blanca: Despliegue del slider de rango de edades SOLO si es Micro
    edad_min_zoom, edad_max_zoom = 8.0, 22.0
    if tipo_vista == "Micro (Ventana Anual)":
        st.markdown("") # Pequeño separador estético
        edad_min_zoom, edad_max_zoom = st.slider(
            "🔎 Rango de la Ventana Enfocada (Edad):",
            min_value=8.0,
            max_value=22.0,
            value=(11.0, 16.0),
            step=0.1,
            format="%.1f años"
        )
    
    st.session_state["zoom_edades"] = (edad_min_zoom, edad_max_zoom)

    # Separador visual antes del lienzo gráfico
    st.markdown("---")
    
    # -------------------------------------------------------------------------
    # 📊 ESPACIO DE RESERVA PARA EL LIENZO GRÁFICO (Temporal para evitar errores)
    # -------------------------------------------------------------------------
    st.info(f"Visualización activa: **Modo {modo_activo}** | **Prueba:** {prueba_sel} | **Escala:** {tipo_vista}")
    st.caption("Los controles superiores y laterales ya se comunican en tiempo real en la memoria de la aplicación.")
