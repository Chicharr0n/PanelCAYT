import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
from urllib.parse import quote
import os
from database import db_manager
from utils import create_expediente_link

# Las credenciales se leen en app.py y se pasan a la clase
BASE_URL = "https://eje.juscaba.gob.ar"

class Scraper:
    def __init__(self):
        if 'driver' not in st.session_state or st.session_state.driver is None:
            options = webdriver.ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            service = Service(executable_path="/usr/bin/chromedriver")
            st.session_state.driver = webdriver.Chrome(service=service, options=options)
        self.driver = st.session_state.driver

    def login_and_sync(self):
        PJ_USER = st.secrets["PJ_USER"]
        PJ_PASS = st.secrets["PJ_PASS"]

        if not PJ_USER or not PJ_PASS:
            st.error("Error: Credenciales no configuradas en los secretos de Streamlit.")
            return

        self.driver.get(f"{BASE_URL}/iol-ui/u/inicio")
        try:
            user_field = WebDriverWait(self.driver, 20).until(EC.visibility_of_element_located((By.ID, "username")))
            user_field.send_keys(PJ_USER)
            self.driver.find_element(By.ID, "password").send_keys(PJ_PASS)
            self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            WebDriverWait(self.driver, 30).until(EC.url_contains("/u/inicio"))
        except TimeoutException:
            st.error("No se pudo iniciar sesión. Verifica tus credenciales.")
            return

        self.driver.get(f"{BASE_URL}/iol-ui/u/causas?causas=1&tipoBusqueda=CAU&tituloBusqueda=Mis%20Causas")
        try:
            WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "mat-select[aria-label='Registros por página:']"))).click()
            WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//mat-option/span[contains(text(), '50')]"))).click()
            time.sleep(5)
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            exp_data = []
            for t in soup.find_all('iol-expediente-tarjeta'):
                n, c, e, fn, un, link = t.find('p', class_='fontSizeEncabezadoCuij'), t.find('strong'), t.find('p', class_='badge'), None, None, None
                
                # --- CAPTURA DEL LINK DIRECTO ---
                link_tag = t.find('a', class_='textColorEncabezado')
                if link_tag and 'href' in link_tag.attrs:
                    link = link_tag['href']
                    if link.startswith('/'): link = BASE_URL + link
                
                nov = t.find('p', class_='fontSizePie')
                if nov:
                    parts = " ".join(nov.text.strip().split()).split('|', 1)
                    fn, un = (parts[0].strip(), parts[1].strip()) if len(parts) > 1 else (parts[0].strip(), "")
                
                exp_data.append({"Numero": n.text.strip() if n else "N/D", "Caratula": c.text.strip() if c else "N/D", "Estado": e.text.strip() if e else "N/D", "Fecha Novedad": fn, "Última Novedad": un, "Link": link})
            
            df = pd.DataFrame(exp_data)
            if not df.empty:
                db_manager.sync_expedientes(df)
                st.session_state['last_sync'] = time.strftime("%d/%m/%Y %H:%M:%S")
        except TimeoutException:
            st.error("Error al sincronizar: No se encontró el selector de paginación.")

    def search_on_portal(self, query):
        # (Sin cambios aquí)
        self.driver.get(f"{BASE_URL}/iol-ui/p/jurisprudencia?identificador={quote(query)}&open=false&tipoBusqueda=Actuaciones&tipoBusqueda=JUR")
        try:
            WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "mat-select[aria-label='Registros por página:']"))).click()
            WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//mat-option/span[contains(text(), '50')]"))).click()
            time.sleep(5)
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            results = []
            for card in soup.find_all('iol-actuacion-tarjeta'):
                c_elem, n_elem = card.find('strong'), card.find('p', class_='fontSizeEncabezadoCuij')
                c_text, n_text = (c_elem.text.strip() if c_elem else "N/D"), (n_elem.text.strip() if n_elem else None)
                link = create_expediente_link(n_text) if n_text else "#"
                details = card.find('p', class_='actuacion-texto')
                results.append({"Resultado": c_text, "Detalles": details.text.strip() if details else "", "Enlace": link})
            return pd.DataFrame(results)
        except Exception as e:
            st.error(f"Error en la búsqueda: {e}.")
            return pd.DataFrame()

    def close(self):
        if 'driver' in st.session_state and st.session_state.driver:
            st.session_state.driver.quit()
            st.session_state.driver = None
            st.info("Sesión y navegador cerrados.")
