import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database import init_db, db_manager
from scraper import Scraper
# --- Importamos la nueva función ---
from utils import format_caratula, create_expediente_link, generate_report, load_juzgados_data

# --- INICIALIZACIÓN Y CONFIGURACIÓN ---
init_db()
st.set_page_config(layout="wide", page_title="Gestor de Expedientes CAYT")

# --- Cargar datos de juzgados una sola vez ---
juzgados_data = load_juzgados_data()
juzgados_nombres = [""] + [j['nombre'] for j in juzgados_data] # Añadir opción vacía

# (El resto de la app hasta la sección "Mis Expedientes" no cambia)
with st.sidebar:
    st.title("⚖️ Gestor CAYT")
    opcion_menu = st.radio("Navegación", ["📈 Dashboard", "🗂️ Mis Expedientes", "🗓️ Agenda", "📝 Notas", "🔍 Búsqueda", "📄 Reportes"], label_visibility="hidden")
    st.markdown("---")
    if st.button("🔄 Sincronizar con Portal"):
        with st.spinner("Iniciando sesión y sincronizando..."):
            scraper_instance = Scraper()
            scraper_instance.login_and_sync()
        st.success("¡Sincronización completa!")
        st.rerun()
    if 'driver' in st.session_state and st.session_state.driver:
        if st.button("❌ Cerrar Navegador"):
            Scraper().close()
            st.rerun()
    st.markdown("---")
    if 'last_sync' in st.session_state:
        st.sidebar.caption(f"Última sync: {st.session_state.get('last_sync', 'N/A')}")

expedientes_df, tareas_df, notas_df, movimientos_df = db_manager.get_all_data()

if opcion_menu == "📈 Dashboard":
    st.title("📈 Panel de Control")
    # ... (código del dashboard sin cambios)
    if expedientes_df.empty:
        st.info("Aún no se han cargado expedientes. Use 'Sincronizar con Portal' para comenzar.")
    else:
        tareas_pendientes = tareas_df[~tareas_df['completada']]
        vencen_7_dias = len(tareas_pendientes[tareas_pendientes['fecha_vencimiento'] <= (date.today() + timedelta(days=7))]) if not tareas_pendientes.empty else 0
        col1, col2, col3 = st.columns(3)
        col1.metric("Expedientes Activos", len(expedientes_df))
        col2.metric("Tareas Pendientes", len(tareas_pendientes))
        col3.metric("Vencen en 7 días", vencen_7_dias)
        st.markdown("---")
        st.subheader("Últimos Movimientos y Notas")
        col_mov, col_notas = st.columns(2)
        with col_mov:
            st.write("**Novedades Recientes del Portal**")
            expedientes_df['fecha_novedad_dt'] = pd.to_datetime(expedientes_df['fecha_novedad_portal'], format='%d/%m/%Y', errors='coerce')
            ultimos_movimientos = expedientes_df.sort_values(by='fecha_novedad_dt', ascending=False).head(5)
            for _, exp in ultimos_movimientos.iterrows():
                with st.container(border=True):
                    link = create_expediente_link(exp['numero'])
                    caratula_simple = format_caratula(exp['caratula'])
                    color = "blue"
                    st.markdown(f":{color}[**<a href='{link or '#'}' target='_blank' style='text-decoration: none; color: inherit;'>{caratula_simple}</a>**]", unsafe_allow_html=True)
                    st.caption(f"{exp['ultima_novedad_portal']} ({exp['fecha_novedad_portal']})")
        with col_notas:
            st.write("**Últimas Notas Agregadas**")
            if not notas_df.empty:
                ultimas_notas = notas_df.sort_values(by='fecha_creacion', ascending=False).head(5)
                notas_con_caratula = pd.merge(ultimas_notas, expedientes_df[['numero', 'caratula']], left_on='expediente_numero', right_on='numero', how='left').fillna({'caratula': 'N/A'})
                for _, nota in notas_con_caratula.iterrows():
                    with st.container(border=True):
                        st.markdown(f"**Nota en:** {format_caratula(nota['caratula'])}")
                        st.caption(f"{nota['contenido'][:100]}...")


elif opcion_menu == "🗂️ Mis Expedientes":
    st.title("🗂️ Mis Expedientes")
    for _, exp in expedientes_df.iterrows():
        exp_numero = exp['numero']
        badge_count = len(tareas_df[(tareas_df['expediente_numero'] == exp_numero) & (~tareas_df['completada'])])
        badge = f" `{badge_count} Tareas`" if badge_count > 0 else ""
        caratula_display = exp['caratula']
        cautelar_status = str(exp.get('medida_cautelar_status', '')).lower()
        if 'concedida' in cautelar_status or 'otorgada' in cautelar_status:
            caratula_display = f":yellow[{exp['caratula']}]"
        expander_title = f"**{exp_numero}** - {caratula_display}{badge}"
        
        with st.expander(expander_title):
            tab_ficha, tab_historial, tab_tareas, tab_notas = st.tabs(["Ficha Técnica", "Historial de Movimientos", "Tareas", "Notas"])
            
            # --- SECCIÓN DE FICHA TÉCNICA COMPLETAMENTE NUEVA ---
            with tab_ficha:
                with st.form(key=f"form_ficha_{exp_numero}"):
                    # --- SELECTORES DINÁMICOS ---
                    # 1. Selector de Juzgado
                    selected_juzgado_nombre = st.selectbox(
                        "Juzgado", options=juzgados_nombres, 
                        index=juzgados_nombres.index(exp.get('juzgado_nombre', '')) if exp.get('juzgado_nombre') in juzgados_nombres else 0,
                        key=f"juzgado_{exp_numero}"
                    )
                    
                    # 2. Selector de Secretaría (dependiente del juzgado)
                    secretarias_options = [""]
                    info_juzgado_seleccionado = None
                    if selected_juzgado_nombre:
                        juzgado_obj = next((j for j in juzgados_data if j['nombre'] == selected_juzgado_nombre), None)
                        if juzgado_obj:
                            secretarias_options.extend([s['nombre'] for s in juzgado_obj['secretarias']])
                            info_juzgado_seleccionado = juzgado_obj

                    selected_secretaria_nombre = st.selectbox(
                        "Secretaría", options=secretarias_options,
                        index=secretarias_options.index(exp.get('secretaria_nombre', '')) if exp.get('secretaria_nombre') in secretarias_options else 0,
                        key=f"secretaria_{exp_numero}"
                    )
                    
                    st.text_input("Estado Medida Cautelar", value=exp.get('medida_cautelar_status', ''), key=f"mc_{exp_numero}")

                    # 3. Mostrar información dinámica
                    if info_juzgado_seleccionado:
                        with st.container(border=True):
                            st.markdown(f"**Juez/a:** {info_juzgado_seleccionado.get('juez', 'N/A')}")
                            if selected_secretaria_nombre:
                                sec_obj = next((s for s in info_juzgado_seleccionado['secretarias'] if s['nombre'] == selected_secretaria_nombre), None)
                                if sec_obj:
                                    st.markdown(f"**Secretario/a:** {sec_obj.get('secretario', 'N/A')}")
                            st.markdown(f"**Dirección:** {info_juzgado_seleccionado.get('direccion', 'N/A')}")
                            st.markdown(f"**Email:** {info_juzgado_seleccionado.get('email', 'N/A')}")

                    if st.form_submit_button("Guardar Ficha"):
                        db_manager.update_ficha_expediente(exp_numero, {
                            'juzgado_nombre': st.session_state[f"juzgado_{exp_numero}"],
                            'secretaria_nombre': st.session_state[f"secretaria_{exp_numero}"],
                            'medida_cautelar_status': st.session_state[f"mc_{exp_numero}"]
                        })
                        st.success("Ficha actualizada.")
                        st.rerun()
            
            # (El resto de las tabs no cambian su lógica interna)
            with tab_historial:
                movs = movimientos_df[movimientos_df['expediente_numero'] == exp_numero].sort_values(by='fecha', ascending=False)
                for _, mov in movs.iterrows(): st.markdown(f"- **{mov['fecha'].strftime('%d/%m/%Y')}:** {mov['descripcion']}")
                with st.form(key=f"form_mov_{exp_numero}", clear_on_submit=True):
                    st.write("**Añadir Movimiento:**")
                    c1, c2 = st.columns([1, 3])
                    fecha_mov = c1.date_input("Fecha", key=f"fecha_mov_{exp_numero}")
                    desc_mov = c2.text_input("Descripción", key=f"desc_mov_{exp_numero}")
                    if st.form_submit_button("Guardar Movimiento"):
                        db_manager.add_item('movimientos', {"expediente_numero": exp_numero, "fecha": fecha_mov, "descripcion": desc_mov})
                        st.rerun()
            with tab_tareas:
                tareas_exp = tareas_df[tareas_df['expediente_numero'] == exp_numero]
                for _, t in tareas_exp.iterrows():
                    estado_actual = bool(t['completada'])
                    nuevo_estado = st.checkbox(f"{t['descripcion']} (Vence: {t['fecha_vencimiento'].strftime('%d/%m/%Y')})", value=estado_actual, key=f"chk_{t['id']}")
                    if nuevo_estado != estado_actual:
                        db_manager.update_tarea_status(t['id'], nuevo_estado)
                        st.rerun()
                with st.form(key=f"form_tarea_{exp_numero}", clear_on_submit=True):
                    st.write("**Añadir Tarea:**")
                    nueva_desc = st.text_input("Descripción")
                    c1, c2 = st.columns(2)
                    nueva_fecha = c1.date_input("Vencimiento", min_value=date.today())
                    nueva_prioridad = c2.selectbox("Prioridad", ["Baja", "Media", "Alta"])
                    if st.form_submit_button("Guardar Tarea"):
                        db_manager.add_item('tareas', {"expediente_numero": exp_numero, "descripcion": nueva_desc, "fecha_vencimiento": nueva_fecha, "prioridad": nueva_prioridad.lower()})
                        st.rerun()
            with tab_notas:
                notas_exp = notas_df[notas_df['expediente_numero'] == exp_numero]
                for _, n in notas_exp.iterrows(): st.markdown(f"> {n['contenido']}\n\n_{n['fecha_creacion'].strftime('%d/%m/%Y %H:%M')}_")
                with st.form(key=f"form_nota_{exp_numero}", clear_on_submit=True):
                    nuevo_contenido = st.text_area("Nueva Nota:")
                    if st.form_submit_button("Guardar Nota"):
                        db_manager.add_item('notas', {"expediente_numero": exp_numero, "contenido": nuevo_contenido, "fecha_creacion": datetime.now()})
                        st.rerun()

# (Las demás secciones no cambian)
elif opcion_menu == "🗓️ Agenda":
    st.title("🗓️ Agenda de Vencimientos")
    # ... (código de agenda sin cambios)
elif opcion_menu == "📝 Notas":
    st.title("📝 Resumen de Notas")
    # ... (código de notas sin cambios)
elif opcion_menu == "🔍 Búsqueda":
    st.title("🔍 Búsqueda General en Portal CAYT")
    # ... (código de búsqueda sin cambios)
elif opcion_menu == "📄 Reportes":
    st.title("📄 Generador de Informes")
    # ... (código de reportes sin cambios)
