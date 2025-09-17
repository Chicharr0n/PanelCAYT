import re
from urllib.parse import quote
import pandas as pd
import json

BASE_URL = "https://eje.juscaba.gob.ar"

# --- NUEVA FUNCIÓN ---
def load_juzgados_data():
    """Carga los datos de los juzgados desde el archivo JSON."""
    try:
        with open('data/juzgados_data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def format_caratula(caratula):
    if not isinstance(caratula, str): return "Carátula inválida"
    parts = caratula.split(' CONTRA ')
    actor = parts[0]
    demandado = parts[1].split(' SOBRE ')[0] if len(parts) > 1 and ' SOBRE ' in parts[1] else 'GCBA'
    return f"{actor} c/ {demandado}"

def create_expediente_link(numero):
    if not numero or not isinstance(numero, str): return None
    match = re.search(r'J-((?:\d{2}-){2}\d{5}-\d)\/(\d{4})-\d', numero)
    if not match: return None
    cuij, anio = match.group(1), match.group(2)
    return f"{BASE_URL}/iol-ui/p/expedientes?identificador={quote(numero)}&tipoBusqueda=CAU&open=true&cuij={cuij}&anio={anio}&desmontar=true"

def generate_report(expedientes_df, tareas_df, notas_df, movimientos_df, selected_exp_numeros):
    report_md = f"# Reporte de Expedientes\n*Generado el: {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}*\n\n"
    
    for numero in selected_exp_numeros:
        exp = expedientes_df[expedientes_df['numero'] == numero].iloc[0]
        report_md += f"---\n##  expediente: {exp['caratula']}\n"
        report_md += f"**Número:** {exp['numero']}  \n"
        report_md += f"**Juzgado:** {exp.get('juzgado_nombre', 'No especificado')} - {exp.get('secretaria_nombre', '')}  \n"
        report_md += f"**Estado Cautelar:** {exp.get('medida_cautelar_status', 'No especificado')}  \n\n"

        report_md += "### Tareas Pendientes\n"
        tareas_exp = tareas_df[(tareas_df['expediente_numero'] == numero) & (~tareas_df['completada'])]
        if not tareas_exp.empty:
            for _, t in tareas_exp.iterrows():
                report_md += f"- **{t['descripcion']}** (Vence: {t['fecha_vencimiento'].strftime('%d/%m/%Y')}, Prioridad: {t['prioridad']})\n"
        else:
            report_md += "_No hay tareas pendientes._\n"
        report_md += "\n"

        report_md += "### Historial de Movimientos\n"
        movimientos_exp = movimientos_df[movimientos_df['expediente_numero'] == numero].sort_values(by='fecha', ascending=False)
        if not movimientos_exp.empty:
            for _, m in movimientos_exp.iterrows():
                report_md += f"- **{m['fecha'].strftime('%d/%m/%Y')}:** {m['descripcion']}\n"
        else:
            report_md += "_No hay movimientos registrados._\n"
        report_md += "\n"
    return report_md
