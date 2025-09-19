import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
# --- Importaciones modificadas ---
from database import init_db, DatabaseManager, get_engine
from scraper import Scraper
from utils import format_caratula, generate_report, load_juzgados_data
import time

# --- INICIALIZACIÓN Y CONFIGURACIÓN ---
st.set_page_config(layout="wide", page_title="Gestor de Expedientes CAYT", page_icon="⚖️")

# --- LÓGICA DE CONEXIÓN EXPLÍCITA ---
# 1. Obtenemos el motor de la base de datos y el tipo de conexión.
#    Esta función también establece st.session_state['db_connection_type'].
engine = get_engine()

# 2. Inicializamos la base de datos y el gestor con el motor obtenido.
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

# (El resto del código no cambia)
@st.cache_data(ttl=300)
def load_data():
    return db_manager.get_all_data()

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

juzgados_data = load_juzgados_data()
expedientes_df, tareas_df, notas_df, movimientos_df = load_data()

# (El resto del código de la interfaz no necesita cambios)
if opcion_menu == "📈 Dashboard":
    st.title("📈 Panel de Control")
    # ...
elif opcion_menu == "🗂️ Mis Expedientes":
    st.title("🗂️ Mis Expedientes")
    # ...
# (etc.)

