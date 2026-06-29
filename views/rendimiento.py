# =============================================================================
# 📁 views/rendimiento.py - LIENZO GRÁFICO ESTÁNDAR Y PROYECCIÓN DE ATLETAS
# =============================================================================
import streamlit as st
import pandas as pd
import numpy as np
import datetime
import io
import matplotlib.pyplot as plt
import sys
import os

# Asegura que el hilo de la vista conozca la raíz antes de llamar a core
ruta_raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ruta_raiz not in sys.path:
    sys.path.insert(0, ruta_raiz)

from core.formulas import calcular_edad_decimal, calcular_curva_atleta, resolver_k_individual

def renderizar_pestana_rendimiento(simulacion_activa: bool):
    """Renderiza la pestaña de Rendimiento Histórico y Proyección."""
    supabase = st.session_state["supabase_client"]
    atleta_id = st.session_state.get("nadador_seleccionado_id")
    genero_atleta = st.session_state.get("nadador_seleccionado_genero", "F")
    f_nac = st.session_state.get("fecha_nacimiento")
    
    if not atleta_id:
        st.warning("⚠️ Selecciona un atleta en la barra lateral para visualizar su gráfica.")
        return

    st.markdown("### 📊 Evolución Histórica y Proyección Matemática")
    st.caption("Visualiza el comportamiento histórico de las marcas frente a los umbrales de referencia.")

    with st.expander("⚙️ Calibración de Parámetros del Modelo (Coeficientes de Crecimiento)", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            # Quitamos el slider de k. Ahora h_val es el protagonista de la deriva.
            h_val = st.slider("Rapidez de la deriva de seguridad (h):", 0.0, 2.0, 0.1, 0.01)
        with c2:
            t_peak_val = st.slider("Edad pico madurativo (t_peak):", 14.0, 22.0, 18.0, 0.5)
            t0_val = st.slider("Edad inicial de referencia (t0):", 8.0, 14.0, 11.0, 0.5)

    lista_pruebas = []
    try:
        res_ref = supabase.table("marcas_referencia").select("prueba").execute()
        if res_ref.data:
            lista_pruebas = sorted(list(set([r["prueba"] for r in res_ref.data])))
    except Exception as e:
        st.error(f"Error cargando catálogo de pruebas: {e}")

    if not lista_pruebas:
        st.info("No hay pruebas configuradas en las marcas de referencia.")
        return

    prueba_sel = st.selectbox("Seleccionar Prueba para Análisis:", options=lista_pruebas)

    umbral_ano, umbral_panamb, umbral_panama, umbral_wab, umbral_waa = None, None, None, None, None
    try:
        r_umb = supabase.table("marcas_referencia").select("*")\
            .eq("prueba", prueba_sel)\
            .eq("genero", genero_atleta)\
            .execute()
        if r_umb.data:
            u_data = r_umb.data[0]
            umbral_ano = u_data.get("m_ano")
            umbral_panamb = u_data.get("m_panam_b")
            umbral_panama = u_data.get("m_panam_a")
            umbral_wab = u_data.get("m_wa_b")
            umbral_waa = u_data.get("m_wa_a")
    except Exception as e:
        st.warning(f"No se pudieron extraer umbrales: {e}")

    df_procesado = pd.DataFrame()
    try:
        r_hist = supabase.table("marcas_historicas").select("*")\
            .eq("usuario_id", atleta_id)\
            .eq("prueba", prueba_sel)\
            .execute()
        if r_hist.data:
            df_procesado = pd.DataFrame(r_hist.data)
    except Exception as e:
        st.error(f"Error leyendo matriz histórica: {e}")

    temporada_actual = datetime.date.today().year
    fechas_competencias = []
    nombres_competencias = []
    try:
        r_comp = supabase.table("catalogo_competencias").select("nombre_evento, fecha_inicio")\
            .eq("temporada", temporada_actual)\
            .execute()
        if r_comp.data:
            for c in r_comp.data:
                f_inicio_dt = datetime.date.fromisoformat(c["fecha_inicio"])
                edad_comp = calcular_edad_decimal(f_nac, f_inicio_dt)
                fechas_competencias.append(edad_comp)
                nombres_competencias.append(c["nombre_evento"])
    except Exception as e:
        st.warning(f"Problema al enlazar competencias: {e}")

    fig = None
    if not df_procesado.empty or fechas_competencias:
        fig, ax = plt.subplots(figsize=(11.69, 8.27))
        edades_plot = np.linspace(8, 22, 150)
        
        t0 = t0_val
        T0 = 120.0
        t_pb = 13.0
        T_pb = 65.0
        T_target = 52.0
        k_calculada = resolver_k_individual(t0, T0, t_pb, T_pb, t_peak_val, T_target)
        st.metric(label="Factor de Ajuste Fisiológico Calculado (k)", value=f"{k_calculada:.4f}")
        
        curva_modelo = calcular_curva_atleta(edades_plot, t0, T0, t_pb, T_pb, t_peak_val, T_target, k_calculada, h_val)
    
        ax.plot(edades_plot, curva_modelo, color="#0F4C81", linestyle="--", linewidth=2.5, label="Proyección Matemática")
        
        colores_marcas = ["#E67E22", "#27AE60", "#8E44AD", "#C0392B", "#2980B9"]
        nombres_marcas = ["Marca Nacional (M.AñO)", "Panam B", "Panam A", "World Aquatics B", "World Aquatics A"]
        umbrales = [umbral_ano, umbral_panamb, umbral_panama, umbral_wab, umbral_waa]
        
        for umb, nom, col in zip(umbrales, nombres_marcas, colores_marcas):
            if umb is not None:
                ax.axhline(umb, color=col, linestyle=":", linewidth=2.0, label=f"{nom} ({umb:.2f}s)")
        
        if not df_procesado.empty:
            ax.scatter(df_procesado['edad'], df_procesado['tiempo'], color="#D32F2F", s=120, zorder=5, label="Marcas Oficiales")
            for idx, row in df_procesado.iterrows():
                ax.annotate(f"{row['tiempo']:.2f}s", (row['edad'], row['tiempo']), textcoords="offset points", xytext=(0,10), ha='center', fontsize=9, color="#333333")

        for ed_c, nom_c in zip(fechas_competencias, nombres_competencias):
            ax.axvline(ed_c, color="#7F8C8D", linestyle="-.", linewidth=1.5, alpha=0.7)
            ax.text(ed_c, ax.get_ylim()[0] + 2, nom_c, rotation=90, va='bottom', ha='right', fontsize=8, color="#7F8C8D")

        ax.set_title(f"Análisis de Proyección de Rendimiento - Prueba: {prueba_sel}", fontsize=16, fontweight='bold', pad=15)
        ax.set_xlabel("Edad Decimal (Años)", fontsize=12)
        ax.set_ylabel("Tiempo de Carrera (Segundos)", fontsize=12)
        ax.grid(True, linestyle=":", alpha=0.6)
        ax.legend(loc="upper right", frameon=True, facecolor="#FFFFFF", fontsize=10)
        ax.set_xlim(8, 22)
        
        plt.tight_layout()
        st.pyplot(fig)
    else:
        st.info("No existen datos históricos o competencias para diagramar la curva.")

    st.markdown("---")
    st.markdown("### 🖨️ Centro de Exportación Vectorial")

    if not df_procesado.empty:
        export_df = df_procesado.drop(columns=["id", "usuario_id"], errors="ignore")
        csv_data = export_df.to_csv(index=False).encode('utf-8')
        
        img_buffer = io.BytesIO() if fig is not None else None
        if img_buffer:
            fig.savefig(img_buffer, format="pdf", bbox_inches='tight', dpi=300)
            img_buffer.seek(0)
        
        c_exp1, _, c_exp3 = st.columns(3)
        with c_exp1:
            st.download_button(label="📥 Descargar Historial (CSV)", data=csv_data, file_name="marcas.csv", mime="text/csv", use_container_width=True)
        with c_exp3:
            if img_buffer:
                st.download_button(label="🖼️ Exportar Gráfico (PDF Vectorial)", data=img_buffer, file_name="diagrama.pdf", mime="application/pdf", use_container_width=True)
