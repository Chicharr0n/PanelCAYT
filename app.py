import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database import init_db, DatabaseManager, get_engine
from scraper import Scraper
from utils import format_caratula, generate_report, load_juzgados_data
import time

# --- INICIALIZACIÓN Y CONFIGURACIÓN ---
st.set_page_config(layout="wide", page_title="Gestor de Expedientes CAYT", page_icon="⚖️")

# --- LÓGICA DE CONEXIÓN EXPLÍCITA ---
engine = get_engine()
init_db(engine)
db_manager = DatabaseManager(engine)

# --- LÓGICA DE LOGIN ---
def check_password():
    if st.session_state.get("authenticated", False):
        return True
    try:
        password_guardada = st.secrets["APP_PASSWORD"]
    except:
        st.error("No se ha configurado una contraseña para la aplicación en los 'Secrets'.")
        return False
    
    st.title("⚖️ Gestor de Expedientes CAYT")
    st.write("Acceso Protegido")
    with st.form("login_form"):
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Ingresar")
        if submitted:
            if password == password_guardada:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("La contraseña es incorrecta.")
    return False

if not check_password():
    st.stop()

# --- FUNCIÓN DE CARGA DE DATOS CON CACHÉ ---
@st.cache_data(ttl=300)
def load_data():
    return db_manager.get_all_data()

# --- BARRA LATERAL ---
with st.sidebar:
    st.title("⚖️ Gestor CAYT")
    opcion_menu = st.radio("Navegación", ["📈 Dashboard", "🗂️ Mis Expedientes", "🗓️ Agenda", "📝 Notas", "🔍 Búsqueda", "📄 Reportes"], label_visibility="hidden")
    st.markdown("---")
    if st.button("🔄 Sincronizar con Portal"):
        with st.spinner("Iniciando sesión y sincronizando..."):
            scraper_instance = Scraper()
            scraper_instance.login_and_sync()
        st.success("¡Sincronización completa!")
        st.cache_data.clear()
        st.rerun()
    if 'driver' in st.session_state and st.session_state.driver:
        if st.button("❌ Cerrar Navegador"):
            Scraper().close()
            st.rerun()
    st.markdown("---")
    st.caption(f"Última sync: {st.session_state.get('last_sync', 'N/A')}")
    st.caption(f"DB Conexión: {st.session_state.get('db_connection_type', 'N/A')}")

# --- CARGA DE DATOS GENERAL ---
juzgados_data = load_juzgados_data()
expedientes_df, tareas_df, notas_df, movimientos_df = load_data()

# --- PANEL DE CONTENIDO PRINCIPAL ---
if opcion_menu == "📈 Dashboard":
    st.title("📈 Panel de Control")
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
                    link = exp.get('link_portal', '#')
                    st.markdown(f"**<a href='{link}' target='_blank' style='text-decoration: none; color: inherit;'>{format_caratula(exp['caratula'])}</a>**", unsafe_allow_html=True)
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
            else:
                st.caption("No hay notas.")

elif opcion_menu == "🗂️ Mis Expedientes":
    st.title("🗂️ Mis Expedientes")
    for _, exp in expedientes_df.iterrows():
        exp_numero = exp['numero']
        badge_count = len(tareas_df[(tareas_df['expediente_numero'] == exp_numero) & (~tareas_df['completada'])])
        badge = f" `{badge_count} Tareas`" if badge_count > 0 else ""
        
        caratula_display = exp['caratula']
        cautelar_status = str(exp.get('medida_cautelar_status', '')).upper()
        if cautelar_status == 'CONCEDIDA' or cautelar_status == 'OTORGADA':
            caratula_display = f":green[{exp['caratula']}]"
        elif cautelar_status == 'PENDIENTE':
            caratula_display = f":red[{exp['caratula']}]"
        elif cautelar_status == 'PARCIALMENTE CONCEDIDA':
            caratula_display = f":orange[{exp['caratula']}]"
        
        with st.expander(f"**{exp_numero}** - {caratula_display}{badge}"):
            tab_ficha, tab_historial, tab_tareas, tab_notas = st.tabs(["Ficha Técnica", "Historial", "Tareas", "Notas"])
            with tab_ficha:
                with st.form(key=f"form_ficha_{exp_numero}"):
                    opciones_cautelar = ["", "PENDIENTE", "CONCEDIDA", "PARCIALMENTE CONCEDIDA", "DENEGADA"]
                    current_status = str(exp.get('medida_cautelar_status', '')).upper()
                    if current_status == "OTORGADA": current_status = "CONCEDIDA"
                    try:
                        indice_cautelar = opciones_cautelar.index(current_status)
                    except ValueError:
                        indice_cautelar = 0
                    
                    juzgados_nombres = [""] + [j['nombre'] for j in juzgados_data]
                    selected_juzgado_nombre = st.selectbox("Juzgado", options=juzgados_nombres, index=juzgados_nombres.index(exp.get('juzgado_nombre', '')) if exp.get('juzgado_nombre') in juzgados_nombres else 0, key=f"juzgado_{exp_numero}")
                    
                    secretarias_options = [""]
                    if selected_juzgado_nombre:
                        juzgado_obj = next((j for j in juzgados_data if j['nombre'] == selected_juzgado_nombre), None)
                        if juzgado_obj: secretarias_options.extend([s['nombre'] for s in juzgado_obj['secretarias']])
                    
                    selected_secretaria_nombre = st.selectbox("Secretaría", options=secretarias_options, index=secretarias_options.index(exp.get('secretaria_nombre', '')) if exp.get('secretaria_nombre') in secretarias_options else 0, key=f"secretaria_{exp_numero}")
                    st.selectbox("Estado Medida Cautelar", options=opciones_cautelar, key=f"mc_{exp_numero}", index=indice_cautelar)
                    st.text_area("Observaciones", value=exp.get('observaciones', ''), key=f"obs_{exp_numero}")

                    if st.form_submit_button("Guardar Ficha"):
                        db_manager.update_ficha_expediente(exp_numero, {
                            'juzgado_nombre': selected_juzgado_nombre,
                            'secretaria_nombre': selected_secretaria_nombre,
                            'medida_cautelar_status': st.session_state[f"mc_{exp_numero}"],
                            'observaciones': st.session_state[f"obs_{exp_numero}"]
                        })
                        st.success("Ficha actualizada.")
                        st.cache_data.clear()
                        st.rerun()
            with tab_historial:
                movs = movimientos_df[movimientos_df['expediente_numero'] == exp_numero].sort_values(by='fecha', ascending=False)
                for _, mov in movs.iterrows(): st.markdown(f"- **{mov['fecha'].strftime('%d/%m/%Y')}:** {mov['descripcion']}")
                with st.form(key=f"form_mov_{exp_numero}", clear_on_submit=True):
                    c1, c2 = st.columns([1, 3])
                    fecha_mov = c1.date_input("Fecha")
                    desc_mov = c2.text_input("Descripción")
                    if st.form_submit_button("Guardar Movimiento"):
                        db_manager.add_item('movimientos', {"expediente_numero": exp_numero, "fecha": fecha_mov, "descripcion": desc_mov})
                        st.cache_data.clear()
                        st.rerun()
            with tab_tareas:
                tareas_exp = tareas_df[tareas_df['expediente_numero'] == exp_numero].sort_values(by=['completada', 'fecha_vencimiento'])
                for _, t in tareas_exp.iterrows():
                    estado_actual = bool(t['completada'])
                    nuevo_estado = st.checkbox(f"{t['descripcion']} (Vence: {t['fecha_vencimiento'].strftime('%d/%m/%Y')})", value=estado_actual, key=f"chk_{t['id']}", disabled=estado_actual)
                    if nuevo_estado != estado_actual:
                        db_manager.update_tarea_status(t['id'], nuevo_estado)
                        st.cache_data.clear()
                        st.rerun()
                with st.form(key=f"form_tarea_{exp_numero}", clear_on_submit=True):
                    nueva_desc = st.text_input("Nueva Tarea")
                    c1, c2 = st.columns(2)
                    nueva_fecha = c1.date_input("Vencimiento", min_value=date.today())
                    nueva_prioridad = c2.selectbox("Prioridad", ["Alta", "Media", "Baja"])
                    if st.form_submit_button("Guardar Tarea"):
                        db_manager.add_item('tareas', {"expediente_numero": exp_numero, "descripcion": nueva_desc, "fecha_vencimiento": nueva_fecha, "prioridad": nueva_prioridad.lower()})
                        st.cache_data.clear()
                        st.rerun()
            with tab_notas:
                notas_exp = notas_df[notas_df['expediente_numero'] == exp_numero].sort_values(by='fecha_creacion', ascending=False)
                for _, n in notas_exp.iterrows():
                    with st.container(border=True):
                        st.markdown(n['contenido'])
                        st.caption(f"Añadida el {n['fecha_creacion'].strftime('%d/%m/%Y %H:%M')}")
                with st.form(key=f"form_nota_{exp_numero}", clear_on_submit=True):
                    nuevo_contenido = st.text_area("Nueva Nota:")
                    if st.form_submit_button("Guardar Nota"):
                        db_manager.add_item('notas', {"expediente_numero": exp_numero, "contenido": nuevo_contenido, "fecha_creacion": datetime.now()})
                        st.cache_data.clear()
                        st.rerun()

elif opcion_menu == "🗓️ Agenda":
    st.title("🗓️ Agenda de Vencimientos")
    tareas_pendientes = tareas_df[~tareas_df['completada']].sort_values(by='fecha_vencimiento')
    if tareas_pendientes.empty:
        st.success("¡No hay tareas pendientes! 🎉")
    else:
        for _, t in tareas_pendientes.iterrows():
            dias_restantes = (t['fecha_vencimiento'] - date.today()).days
            color = "red" if dias_restantes < 3 else "orange" if dias_restantes < 7 else "blue"
            with st.container(border=True):
                st.markdown(f"##### :{color}[{t['descripcion']}]")
                exp_asociado_df = expedientes_df[expedientes_df['numero'] == t['expediente_numero']]
                if not exp_asociado_df.empty:
                    st.markdown(f"**Expediente:** {format_caratula(exp_asociado_df.iloc[0]['caratula'])}")
                else:
                    st.markdown(f"**Expediente:** {t['expediente_numero']}")
                st.markdown(f"**Vence:** {t['fecha_vencimiento'].strftime('%d/%m/%Y')} (**{dias_restantes} días restantes**)")

elif opcion_menu == "📝 Notas":
    st.title("📝 Resumen de Notas")
    if notas_df.empty:
        st.info("Aún no has añadido ninguna nota.")
    else:
        notas_con_caratula = pd.merge(notas_df.sort_values(by='fecha_creacion', ascending=False), expedientes_df[['numero', 'caratula']], left_on='expediente_numero', right_on='numero', how='left')
        for _, n in notas_con_caratula.iterrows():
            with st.container(border=True):
                st.markdown(f"**Nota en:** {format_caratula(n.get('caratula', n['expediente_numero']))}")
                st.write(n['contenido'])
                st.caption(f"Añadido el {n['fecha_creacion'].strftime('%d/%m/%Y %H:%M')}")

elif opcion_menu == "🔍 Búsqueda":
    st.title("🔍 Búsqueda General en Portal CAYT")
    if 'driver' not in st.session_state or st.session_state.driver is None:
        st.warning("⚠️ Para buscar, primero debe 'Sincronizar con Portal'.")
    else:
        query = st.text_input("Ingrese su búsqueda", key="search_query")
        if st.button("Buscar en Portal"):
            with st.spinner(f"Buscando '{query}'..."):
                search_results = Scraper().search_on_portal(query)
            if not search_results.empty:
                st.dataframe(search_results, column_config={"Enlace": st.column_config.LinkColumn("Abrir", display_text="↗️")}, hide_index=True)
            else:
                st.info("No se encontraron resultados.")

elif opcion_menu == "📄 Reportes":
    st.title("📄 Generador de Informes")
    if not expedientes_df.empty:
        options = st.multiselect("Seleccione los expedientes para incluir en el reporte:", options=expedientes_df['numero'], format_func=lambda x: format_caratula(expedientes_df[expedientes_df['numero'] == x].iloc[0]['caratula']))
        if st.button("Generar Reporte"):
            if options:
                reporte = generate_report(expedientes_df, tareas_df, notas_df, movimientos_df, options)
                st.markdown(reporte)
                st.download_button("Descargar Reporte (.md)", reporte, file_name="Reporte_Expedientes.md")
            else:
                st.warning("Debe seleccionar al menos un expediente.")