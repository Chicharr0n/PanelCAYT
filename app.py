import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database import init_db, DatabaseManager, get_engine, db_manager
from scraper import Scraper
from utils import format_caratula, generate_report, load_juzgados_data
import time

st.set_page_config(page_title="Panel CAYT", layout="wide")

st.title("⚖️ Panel de Gestión - Fuero CAYT")

# Inicializar DB (ya está hecho en database.py, pero aseguramos)
_engine = get_engine()
init_db(_engine)

# Instanciar scraper
scraper = Scraper()

menu = st.sidebar.radio("Menú", ["Inicio", "Expedientes", "Jurisprudencia", "Tareas", "Notas"])

if menu == "Inicio":
    st.subheader("Bienvenido al Panel de Gestión de Juicios CAYT")
    if st.button("🔄 Sincronizar expedientes"):
        scraper.login_and_sync()
    if 'last_sync' in st.session_state:
        st.info(f"Última sincronización: {st.session_state['last_sync']}")

elif menu == "Expedientes":
    expedientes, tareas, notas, movimientos = db_manager.get_all_data()
    st.subheader("📂 Expedientes")
    st.dataframe(expedientes)

elif menu == "Jurisprudencia":
    st.subheader("📚 Búsqueda de Jurisprudencia")
    query = st.text_input("Buscar por palabra clave:")
    if st.button("Buscar") and query:
        results = scraper.search_on_portal(query)
        st.dataframe(results)

elif menu == "Tareas":
    _, tareas, _, _ = db_manager.get_all_data()
    st.subheader("✅ Tareas")
    st.dataframe(tareas)

elif menu == "Notas":
    _, _, notas, _ = db_manager.get_all_data()
    st.subheader("📝 Notas")
    st.dataframe(notas)