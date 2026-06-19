with col_vistas:
    st.markdown("**Historial Cronológico de Tiempos**")
    if len(df_procesado) > 0:
        if st.session_state.rol in ["Entrenador", "Administrador"]:
            # 1. Creamos un diccionario mapeando una etiqueta descriptiva al ID real
            opciones_eliminacion = {
                f"Edad: {row['Edad']} | Tiempo: {row['Tiempo']} | {row['Evento / Fecha']}": row['id']
                for _, row in df_procesado.iterrows()
            }
            
            # 2. Mostramos la descripción amigable en el selectbox
            seleccion_etiqueta = st.selectbox(
                "Seleccione el registro que desea eliminar:", 
                options=list(opciones_eliminacion.keys())
            )
            
            # 3. Recuperamos el ID interno asociado a esa selección
            id_del = opciones_eliminacion[seleccion_etiqueta]
            
            if st.button("🗑️ Eliminar Fila"):
                supabase.table("marcas_historicas").delete().eq("id", int(id_del)).execute()
                st.warning("Registro removido con éxito.")
                st.rerun()
                
        # Mostrar la tabla al usuario (eliminando columnas técnicas si es necesario)
        st.dataframe(df_procesado.drop(columns=["id"], errors="ignore"), use_container_width=True)
