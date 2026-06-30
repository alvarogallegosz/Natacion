# =============================================================================
# 📁 views/rendimiento.py - CONTROLADOR DE RENDIMIENTO VISUAL Y EXPORTACIÓN
# =============================================================================
import streamlit as st
import pandas as pd
import numpy as np
import datetime
import io
import matplotlib.pyplot as plt
import matplotlib.table as mpl_table
from core.conexion import obtener_cliente_supabase
from core.formulas import (
    calcular_edad_decimal,
    resolver_k_individual, 
    calcular_curva_atleta,
    generar_malla_edades
)

def estilizar_tabla_nativo(tabla_mpl):
    """
    [Lógica Original Estricta]
    Aplica el esquema estético institucional a las tablas de marcas incrustadas en el reporte.
    """
    for (fila, col), celda in tabla_mpl.get_celld().items():
        celda.set_text_props(fontsize=8, fontname="Arial")
        if fila == 0:
            celda.set_text_props(weight='bold', color='white', fontsize=8.5)
            celda.set_facecolor('#1F4E79')  # Azul Institucional
        else:
            if fila % 2 == 0:
                celda.set_facecolor('#F2F4F7')  # Filas alternas
            else:
                celda.set_facecolor('white')
        celda.set_linewidth(0.4)
        celda.set_edgecolor('#D0D5DD')


def renderizar_centro_exportacion(fig, df_datos: pd.DataFrame, sufijo_archivo: str, modo_equipo: bool, atletas_filtrados: list):
    """
    [Módulo de Exportación e Impresión - Archivo 13]
    Genera la sección de descarga de reportes en formatos estructurados y la captura PNG del lienzo.
    """
    st.markdown("---")
    st.markdown("### 🖨️ Centro de Exportación de Reportes y Gráficos")
    
    if not df_datos.empty or modo_equipo:
        export_df = df_datos.drop(columns=["id", "usuario_id"], errors="ignore")
        csv_data = export_df.to_csv(index=False).encode('utf-8')
        txt_string = export_df.to_string(index=False)
        
        img_buffer = None
        
        if modo_equipo and not atletas_filtrados:
            st.warning("No se encontraron atletas activos con los criterios de segmentación elegidos.")
        else:
            if fig is not None:
                img_buffer = io.BytesIO()
                fig.savefig(img_buffer, format="png", bbox_inches=None, dpi=300)
                img_buffer.seek(0)
         
        c_exp1, c_exp2, c_exp3 = st.columns(3)
        with c_exp1:
            st.download_button(
                label="📥 Descargar Historial (CSV)", 
                data=csv_data, 
                file_name=f"marcas_rendimiento_{sufijo_archivo}.csv", 
                mime="text/csv",
                use_container_width=True
            )
        with c_exp2:
            st.download_button(
                label="📄 Descargar Datos (TXT)", 
                data=txt_string, 
                file_name=f"reporte_analisis_{sufijo_archivo}.txt", 
                mime="text/plain",
                use_container_width=True
            )
        with c_exp3:
            if img_buffer is not None:
                st.download_button(
                    label="🖼️ Descargar Gráfico (PNG 300dpi)", 
                    data=img_buffer, 
                    file_name=f"lienzo_grafico_{sufijo_archivo}.png", 
                    mime="image/png",
                    use_container_width=True
                )
            else:
                st.button("🖼️ Descargar Gráfico (PNG)", disabled=True, use_container_width=True)


def renderizar_grafico_equipo(atletas_filtrados: list, tipo_vista: str, edad_min_zoom: float, edad_max_zoom: float, h_global: float):
    """
    [Sub-módulo Gráfico de Equipo - Corregido bajo criterio de Asíntota Abajo]
    """
    supabase = obtener_cliente_supabase()
    fig = plt.figure(figsize=(8.5, 11.0))
    ax = fig.add_axes([0.14, 0.52, 0.72, 0.38])
    
    todos_los_tiempos = []
    x_lim_min, x_lim_max = (edad_min_zoom, edad_max_zoom) if tipo_vista == "Micro (Ventana Anual)" else (10.0, 18.0)
    
    for atleta in atletas_filtrados:
        try:
            res_m = supabase.table("marcas_historicas").select("*").eq("atleta_id", atleta["id"]).order("edad", desc=False).execute()
            df_m = pd.DataFrame(res_m.data) if res_m.data else pd.DataFrame()
            
            if df_m.empty:
                continue
            
            t0 = 8.0
            T0 = float(df_m["tiempo"].max())
            
            idx_mej = df_m["tiempo"].idxmin()
            fecha_nac = atleta.get("fecha_nacimiento")
            t_pb = calcular_edad_decimal(fecha_nac, df_m.loc[idx_mej, "fecha"])
            T_pb = float(df_m["tiempo"].min())
            
            t_peak = 18.0
            T_target = T_pb * 0.95
            
            k = resolver_k_individual(t0, T0, t_pb, T_pb, t_peak, T_target)
            edades_malla = generar_malla_edades(t0, t_peak, 300)
            tiempos_proyeccion = calcular_curva_atleta(edades_malla, t0, T0, t_pb, T_pb, t_peak, T_target, k, h_global)
            
            puntos_visibles = [tiempos_proyeccion[i] for i in range(len(edades_malla)) if x_lim_min <= edades_malla[i] <= x_lim_max]
            if puntos_visibles:
                todos_los_tiempos.extend(puntos_visibles)
                
            ax.plot(edades_malla, tiempos_proyeccion, label=atleta["nombre"], linewidth=1.1, alpha=0.75)
        except Exception:
            continue
            
    if todos_los_tiempos:
        lim_y_inferior = min(todos_los_tiempos) - 1.5
        lim_y_superior = max(todos_los_tiempos) + 2.0
    else:
        lim_y_inferior, lim_y_superior = 22.0, 45.0
        
    ax.set_xlim(x_lim_min, x_lim_max)
    
    # CRITERIO PUNTO 1: Tiempos rápidos abajo (asíntota en la base). Menor tiempo abajo, mayor tiempo arriba.
    ax.set_ylim(lim_y_superior, lim_y_inferior)
    ax.grid(True, which="both", axis="both", linestyle=":", color="#CCD1D9", linewidth=0.5)
    
    marcas_reglamento = [
        {"lbl": "Mínima Nacional", "val": 25.80, "col": "#C00000", "va": "bottom"},
        {"lbl": "Mínima Transición", "val": 27.20, "col": "#E26B0A", "va": "top"}
    ]
    
    # PUNTO 2: El margen interno dinámico evita desbordes en modo Micro
    x_texto = x_lim_max - (x_lim_max - x_lim_min) * 0.01
    for r in marcas_reglamento:
        if min(lim_y_inferior, lim_y_superior) <= r["val"] <= max(lim_y_inferior, lim_y_superior):
            ax.axhline(y=r["val"], color=r["col"], linestyle=":", linewidth=0.8)
            desplazamiento_y = (lim_y_superior - lim_y_inferior) * 0.006 if r["va"] == "bottom" else -((lim_y_superior - lim_y_inferior) * 0.006)
            ax.text(x_texto, r["val"] + desplazamiento_y, f"{r['lbl']}: {r['val']:.2f}s", color=r["col"], fontsize=7.5, va=r["va"], ha="right")

    ax.set_title("Análisis Comparativo del Rendimiento de Equipo", fontsize=12, pad=12, weight="bold")
    ax.set_xlabel("Edad del Atleta (Años)", fontsize=9.5)
    ax.set_ylabel("Tiempo Proyectado (Segundos)", fontsize=9.5)
    
    st.pyplot(fig, clear_figure=True)
    renderizar_centro_exportacion(fig, pd.DataFrame(), "equipo", True, atletas_filtrados)


# =============================================================================
# 🏊‍♂️ SUB-MÓDULO GRÁFICO INDIVIDUAL (REFACTORIZADO Y CONSOLIDADO)
# =============================================================================
def renderizar_grafico_individual(df_marcas: pd.DataFrame, t0: float, T0: float, t_pb: float, T_pb: float, t_peak: float, T_target: float, k: float, h: float, tipo_vista: str, edad_min_zoom: float, edad_max_zoom: float, simulacion_activa: bool, nombre_atleta: str):
    """
    [Sub-módulo Gráfico Individual Puro - Canvas 8.5x11 Estricto]
    PUNTO 3: Se rescata esta función pura para centralizar el renderizado eliminando la duplicidad.
    """
    fig = plt.figure(figsize=(8.5, 11.0))
    ax = fig.add_axes([0.14, 0.52, 0.72, 0.33])
    
    edades_curva = generar_malla_edades(t0, t_peak, 300)
    tiempos_curva = calcular_curva_atleta(edades_curva, t0, T0, t_pb, T_pb, t_peak, T_target, k, h)
    
    todos_los_tiempos_ind = [T0, T_pb, T_target]
    if not simulacion_activa and len(df_marcas) > 0:
        todos_los_tiempos_ind.extend(df_marcas["Tiempo"].tolist())
        
    if tipo_vista == "Micro (Ventana Anual)":
        ax.set_xlim(edad_min_zoom, edad_max_zoom)
        visibles = tiempos_curva[(edades_curva >= edad_min_zoom) & (edades_curva <= edad_max_zoom)]
        if len(visibles) > 0:
            ax.set_ylim(max(visibles) + 1.5, min(visibles) - 1.0)
        if not df_marcas.empty:
            df_vis = df_marcas[(df_marcas["Edad"] >= edad_min_zoom) & (df_marcas["Edad"] <= edad_max_zoom)]
            ax.scatter(df_vis["Edad"], df_vis["Tiempo"], color="#E26B0A", edgecolors='black', s=25, zorder=5, label="Marcas Reales")
    else:
        ax.set_xlim(t0 - 0.5, t_peak + 1.0)
        # PUNTO 1: Modificado para que la asíntota (T_target) quede abajo y T0 arriba de forma consistente
        ax.set_ylim(T0 + 2.0, T_target - 2.0)
        if not df_marcas.empty and not simulacion_activa:
            ax.scatter(df_marcas["Edad"], df_marcas["Tiempo"], color="#E26B0A", edgecolors='black', s=25, zorder=5, label="Marcas Reales")
            
    ax.plot(edades_curva, tiempos_curva, color="#1F4E79", linewidth=1.5, label="Modelo de Proyección Asintótica")
    ax.grid(True, which="both", linestyle=":", color="#CCD1D9", linewidth=0.5)
    ax.set_title(f"Lienzo Cinemático de Rendimiento - {nombre_atleta}", fontsize=11, weight="bold", pad=12)
    ax.set_xlabel("Edad Decimal (Años)", fontsize=9, fontname="Arial")
    ax.set_ylabel("Tiempo de Carrera (Segundos)", fontsize=9, fontname="Arial")
    ax.legend(loc="upper right", fontsize=8)
    
    # Hito objetivo vertical rígido a los 18 años
    ax.axvline(x=18.0, color="#D32F2F", linestyle="--", alpha=0.7, lw=1.5)
    
    # --- INCRASTACIÓN DE TABLAS OPERATIVAS EN EL CANVAS ---
    if not df_marcas.empty and not simulacion_activa:
        df_table_render = df_marcas[["Fecha_Txt", "Edad_Txt", "Tiempo_Txt"]].copy()
        df_table_render.columns = ["Fecha Competición", "Edad Decimal", "Tiempo Registrado"]
        
        total_filas = len(df_table_render)
        limite_filas_por_bloque = 16
        
        # PUNTO 4: Columnas estandarizadas proporcionales consistentes en todo escenario
        anchos_columnas = [0.22, 0.22, 0.56]
        es_modo_micro_tabla = (tipo_vista == "Micro (Ventana Anual)")
        anchos_doble = [0.25, 0.35, 0.40] if es_modo_micro_tabla else [0.25, 0.25, 0.50]
        
        if total_filas <= limite_filas_por_bloque:
            ax_table = fig.add_axes([0.14, 0.054, 0.72, 0.40])
            ax_table.axis('off')
            mpl_table = ax_table.table(cellText=df_table_render.values, colLabels=df_table_render.columns, cellLoc='center', loc='upper center', colWidths=anchos_columnas)
            estilizar_tabla_nativo(mpl_table)
        else:
            if total_filas > 32: 
                df_table_render = df_table_render.iloc[:32]
                
            df_bloque_izq = df_table_render.iloc[:limite_filas_por_bloque]
            df_bloque_der = df_table_render.iloc[limite_filas_por_bloque:]
            
            ax_table1 = fig.add_axes([0.10, 0.054, 0.38, 0.40])
            ax_table1.axis('off')
            mpl_table1 = ax_table1.table(cellText=df_bloque_izq.values, colLabels=df_bloque_izq.columns, cellLoc='center', loc='upper center', colWidths=anchos_doble)
            estilizar_tabla_nativo(mpl_table1)
            
            if not df_bloque_der.empty:
                ax_table2 = fig.add_axes([0.52, 0.054, 0.38, 0.40])
                ax_table2.axis('off')
                mpl_table2 = ax_table2.table(cellText=df_bloque_der.values, colLabels=df_bloque_der.columns, cellLoc='center', loc='upper center', colWidths=anchos_doble)
                estilizar_tabla_nativo(mpl_table2)
                
    st.pyplot(fig)

    # Buffer de exportación unificado de alta resolución
    sufijo_archivo = nombre_atleta.replace(" ", "_").lower()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=300, bbox_inches='tight')
    st.download_button(
        label="📥 Descargar Reporte en Alta Resolución (PNG)",
        data=buf.getvalue(),
        file_name=f"reporte_cinematico_{sufijo_archivo}.png",
        mime="image/png",
        use_container_width=True
    )


# =============================================================================
# 📁 ORQUESTADOR MAESTRO DEL MÓDULO DE RENDIMIENTO (DRY COMPLETO)
# =============================================================================
def mostrar_modulo_rendimiento():
    """
    Orquestador de vista conectado a Supabase y Gestor de Parámetros Biológicos.
    """
    supabase = obtener_cliente_supabase()
    
    modo_equipo = st.session_state.get("modo_equipo", False)
    tipo_vista = st.session_state.get("tipo_vista", "Macro (Historial Completo)")
    edad_min = st.session_state.get("edad_min_zoom", 0.0)
    edad_max = st.session_state.get("edad_max_zoom", 100.0)
    h_factor = st.session_state.get("factor_h", 0.4)
    simulacion_activa = st.session_state.get("simulacion_externa", False)
    
    atleta_id = st.session_state.get("nadador_seleccionado_id")
    fecha_nac_atleta = st.session_state.get("fecha_nacimiento") or st.session_state.get("fecha_nacimiento_usuario")
    nombre_atleta = st.session_state.get("nadador_seleccionado_nombre", "Sin Atleta")
    
    if modo_equipo:
        st.subheader("🏊‍♂️ Panel de Control Comparativo: Rendimiento del Equipo")
        atletas = st.session_state.get("atletas_filtrados_equipo", [])
        if atletas:
            renderizar_grafico_equipo(atletas, tipo_vista, edad_min, edad_max, h_factor)
        else:
            st.warning("⚠️ Selecciona un grupo o atletas en la barra lateral para proyectar las curvas de equipo.")
            
    else:
        st.subheader(f"🏊‍♂️ Planificación y Control de Resultados: {nombre_atleta}")
        
        if not atleta_id:
            st.warning("⚠️ No se ha seleccionado ningún atleta en el foco actual de la Sidebar.")
            return

        try:
            res_marcas = supabase.table("marcas_historicas").select("*").eq("atleta_id", atleta_id).order("edad", desc=False).execute()
            marcas_data = res_marcas.data if res_marcas.data else []
        except Exception as e:
            st.error(f"Error al conectar con la tabla de marcas: {e}")
            return
            
        lista_procesada = []
        for m in marcas_data:
            fecha_raw = str(m["fecha"])
            fecha_limpia_str = fecha_raw.split("T")[0] if "T" in fecha_raw else fecha_raw
            
            try:
                fecha_obj = datetime.date.fromisoformat(fecha_limpia_str)
            except ValueError:
                fecha_obj = pd.to_datetime(fecha_limpia_str).date()
            
            edad_dec = calcular_edad_decimal(fecha_nac_atleta, fecha_obj)
            
            lista_procesada.append({
                "Fecha": fecha_obj,
                "Fecha_Txt": fecha_obj.strftime("%d/%m/%Y"),
                "Edad": edad_dec,
                "Edad_Txt": f"{edad_dec:.2f} años",
                "Tiempo": float(m["tiempo"]),
                "Tiempo_Txt": f"{float(m['tiempo']):.2f}s"
            })
            
        df_marcas = pd.DataFrame(lista_procesada)
        
        # --- ASIGNACIÓN DE HUNDIMIENTO BIOLÓGICO Y PARÁMETROS CINEMÁTICOS ---
        if not df_marcas.empty:
            t0 = 8.0
            T0 = float(df_marcas["Tiempo"].max())
            idx_mej = df_marcas["Tiempo"].idxmin()
            t_pb = float(df_marcas.loc[idx_mej, "Edad"])
            T_pb = float(df_marcas["Tiempo"].min())
            t_peak = 18.0
            T_target = T_pb * 0.95
        else:
            t0, T0 = 9.0, 42.0
            t_pb, T_pb = 14.5, 26.0
            t_peak, T_target = 18.0, 24.0

        # Captura de parámetros desde st.session_state
        k = st.session_state.get("factor_k", 0.28)
        
        # DELEGACIÓN TOTAL A LA FUNCIÓN REFACTORIZADA (Se eliminó el bloque duplicado)
        renderizar_grafico_individual(
            df_marcas=df_marcas,
            t0=t0, T0=T0,
            t_pb=t_pb, T_pb=T_pb,
            t_peak=t_peak, T_target=T_target,
            k=k, h=h_factor,
            tipo_vista=tipo_vista,
            edad_min_zoom=edad_min, edad_max_zoom=edad_max,
            simulacion_activa=simulacion_activa,
            nombre_atleta=nombre_atleta
        )
