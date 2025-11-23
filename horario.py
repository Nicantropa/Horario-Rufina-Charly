import streamlit as st
import pandas as pd
import io
from datetime import datetime, time

# --- 1. CONFIGURACIÓN INICIAL (Debe ir al principio) ---
st.set_page_config(page_title="Planificador Doña Rufina", layout="wide", page_icon="🍽️")

# --- 2. DATOS Y CONFIGURACIÓN ---
CONFIG = {
    "TURNOS": {
        "Mañana": {"inicio": "08:30", "fin": "16:30"},
        "Tarde":  {"inicio": "16:00", "fin": "23:59"},
        "Partido": {"bloque1": "12:00-16:00", "bloque2": "20:00-23:59"}
    },
    "DIAS": ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"],
    "ROLES_CRITICOS": ["J. Cocina", "Lavaplatos"],
    "STAFF_INIT": [
        {"Nombre": "Olfa", "Rol": "J. Cocina", "Activo": True, "Extra": False, "Partido": False},
        {"Nombre": "Charly", "Rol": "J. Cocina", "Activo": True, "Extra": False, "Partido": False},
        {"Nombre": "Dieynaba", "Rol": "Lavaplatos", "Activo": True, "Extra": True, "Partido": False},
        {"Nombre": "Miguel", "Rol": "Lavaplatos", "Activo": True, "Extra": True, "Partido": True},
        {"Nombre": "Angel", "Rol": "Lavaplatos", "Activo": True, "Extra": True, "Partido": False},
        {"Nombre": "José", "Rol": "Eq. General", "Activo": True, "Extra": True, "Partido": True},
        {"Nombre": "Mohammed", "Rol": "Eq. General", "Activo": True, "Extra": False, "Partido": False},
        {"Nombre": "Auxiliadora", "Rol": "Eq. General", "Activo": True, "Extra": False, "Partido": False},
        {"Nombre": "Cristian", "Rol": "Eq. General", "Activo": True, "Extra": True, "Partido": False},
        {"Nombre": "David", "Rol": "Eq. General", "Activo": True, "Extra": True, "Partido": False},
        {"Nombre": "Adrian", "Rol": "Eq. General", "Activo": True, "Extra": False, "Partido": False},
        {"Nombre": "José Capitán", "Rol": "Eq. General", "Activo": True, "Extra": False, "Partido": False},
        {"Nombre": "Felesia", "Rol": "Eq. General", "Activo": False, "Extra": False, "Partido": False},
    ]
}

# --- 3. FUNCIONES AUXILIARES ---

def str_to_time(hora_str):
    """Convierte texto HH:MM a objeto de tiempo de forma segura."""
    if not hora_str or hora_str == "-": return None
    if str(hora_str).upper() == "CIERRE": return time(23, 59)
    try:
        return datetime.strptime(str(hora_str), "%H:%M").time()
    except:
        return None

def validar_regla(empleado_dic, dia, turno_nombre, lista_excepciones):
    """Verifica si el empleado puede trabajar según las excepciones definidas."""
    nombre = empleado_dic["Nombre"]
    
    # Buscar si hay regla para esta persona y día
    regla = next((x for x in lista_excepciones if x["Nombre"] == nombre and x["Día"] == dia), None)
    
    if not regla: 
        return True # No hay restricciones

    tipo = regla["Tipo"]
    hora_limite = str_to_time(regla.get("Hora", "-"))
    
    # 1. Día Libre Completo
    if tipo == "Día Libre Completo":
        return False

    # Datos del turno
    inicio_turno = str_to_time(CONFIG["TURNOS"][turno_nombre]["inicio"])
    fin_turno = str_to_time(CONFIG["TURNOS"][turno_nombre]["fin"])

    # 2. Entrada Mínima (Llega tarde)
    if tipo == "Entrada Mínima" and hora_limite:
        # Si el turno empieza ANTES de la hora límite, no puede hacerlo
        if inicio_turno < hora_limite:
            return False

    # 3. Salida Máxima (Se va pronto)
    if tipo == "Salida Máxima" and hora_limite:
        # Si el turno termina DESPUÉS de la hora límite, no puede hacerlo
        if fin_turno > hora_limite:
            return False
            
    return True

def generar_excel(df_matrix, df_kpis, logs):
    """Genera el archivo Excel para descargar."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_matrix.to_excel(writer, sheet_name='Horario Semanal')
        df_kpis.to_excel(writer, sheet_name='Control Objetivos', index=False)
        pd.DataFrame(logs, columns=["Log"]).to_excel(writer, sheet_name='Detalles', index=False)
        
        # Ajuste columnas
        worksheet = writer.sheets['Horario Semanal']
        worksheet.set_column('A:Z', 20)
    return output.getvalue()

# --- 4. INTERFAZ Y LÓGICA PRINCIPAL ---

def main():
    try:
        # --- SIDEBAR: OBJETIVOS ---
        st.sidebar.header("📂 Gestión")
        archivo = st.sidebar.file_uploader("Cargar Histórico (Rotación)", type=["xlsx"])
        if archivo:
            st.sidebar.success("Histórico cargado (Simulación de rotación activa)")

        st.sidebar.markdown("---")
        st.sidebar.header("🎯 Objetivos (Personas)")
        
        st.sidebar.subheader("Lunes - Jueves")
        lj_m = st.sidebar.slider("Mañana (L-J)", 1, 8, 3)
        lj_t = st.sidebar.slider("Tarde (L-J)", 1, 10, 4)

        st.sidebar.subheader("Viernes - Domingo")
        vd_m = st.sidebar.slider("Mañana (V-D)", 1, 8, 4)
        vd_t = st.sidebar.slider("Tarde (V-D)", 1, 12, 6)

        # --- ÁREA PRINCIPAL ---
        st.title("🍽️ Planificador Doña Rufina")
        
        tab1, tab2 = st.tabs(["👥 Equipo y Reglas", "📅 Generar Horario"])

        # PESTAÑA 1: CONFIGURACIÓN
        with tab1:
            col1, col2 = st.columns([1.5, 1])
            
            with col1:
                st.subheader("Plantilla")
                df_base = pd.DataFrame(CONFIG["STAFF_INIT"])
                df_edited = st.data_editor(
                    df_base, 
                    num_rows="dynamic",
                    hide_index=True,
                    key="editor_personal",
                    column_config={
                        "Activo": st.column_config.CheckboxColumn("¿Disponible?", width="small")
                    }
                )
            
            with col2:
                st.subheader("Excepciones")
                if 'excepciones' not in st.session_state: 
                    st.session_state.excepciones = []
                
                with st.form("form_excep"):
                    e_nom = st.selectbox("Nombre", df_edited["Nombre"].unique())
                    e_dia = st.selectbox("Día", CONFIG["DIAS"])
                    e_tipo = st.selectbox("Tipo", ["Día Libre Completo", "Entrada Mínima", "Salida Máxima"])
                    e_hora = st.text_input("Hora (HH:MM)", placeholder="Ej: 11:30")
                    
                    if st.form_submit_button("Añadir Regla"):
                        st.session_state.excepciones.append({
                            "Nombre": e_nom, "Día": e_dia, "Tipo": e_tipo, "Hora": e_hora
                        })
                        st.success("Regla guardada")
                
                if st.session_state.excepciones:
                    st.dataframe(pd.DataFrame(st.session_state.excepciones), hide_index=True)
                    if st.button("Borrar Reglas"):
                        st.session_state.excepciones = []
                        st.rerun()

        # PESTAÑA 2: CÁLCULO
        with tab2:
            st.write("Pulsa el botón para generar el turno basado en la configuración.")
            
            if st.button("🚀 Calcular Horario", type="primary"):
                # --- ALGORITMO ---
                schedule = []
                kpis = []
                logs = []
                
                # Convertimos el editor a lista de diccionarios
                staff_pool = df_edited[df_edited["Activo"]==True].to_dict('records')
                excepciones = st.session_state.excepciones

                for dia in CONFIG["DIAS"]:
                    es_finde = dia in ["Viernes", "Sábado", "Domingo"]
                    meta_m = vd_m if es_finde else lj_m
                    meta_t = vd_t if es_finde else lj_t
                    
                    # Listas de asignados hoy
                    asig_m = []
                    asig_t = []
                    
                    # Filtro Base: Quién está disponible (sin contar restricciones horarias aun)
                    disponibles = [e for e in staff_pool if validar_regla(e, dia, "Mañana", excepciones) or validar_regla(e, dia, "Tarde", excepciones)]

                    # 1. ROLES CRÍTICOS
                    for rol in CONFIG["ROLES_CRITICOS"]:
                        # Mañana
                        cands = [e for e in disponibles if e["Rol"] == rol and e not in asig_m + asig_t]
                        for c in cands:
                            if validar_regla(c, dia, "Mañana", excepciones):
                                asig_m.append(c); break
                        # Tarde
                        cands = [e for e in disponibles if e["Rol"] == rol and e not in asig_m + asig_t]
                        for c in cands:
                            if validar_regla(c, dia, "Tarde", excepciones):
                                asig_t.append(c); break
                    
                    # 2. RELLENO GENERAL
                    # Mañana
                    while len(asig_m) < meta_m:
                        cands = [e for e in disponibles if e not in asig_m + asig_t]
                        if not cands: break
                        cand = next((c for c in cands if validar_regla(c, dia, "Mañana", excepciones)), None)
                        if cand: asig_m.append(cand)
                        else: break
                    
                    # Tarde
                    while len(asig_t) < meta_t:
                        cands = [e for e in disponibles if e not in asig_m + asig_t]
                        if not cands: break
                        cand = next((c for c in cands if validar_regla(c, dia, "Tarde", excepciones)), None)
                        if cand: asig_t.append(cand)
                        else: break
                        
                    # 3. DÉFICIT (Extras y Partidos)
                    falta_m = meta_m - len(asig_m)
                    falta_t = meta_t - len(asig_t)
                    
                    # Extras
                    if falta_m > 0 or falta_t > 0:
                        extras = [e for e in disponibles if e["Extra"] and e not in asig_m + asig_t]
                        for e in extras:
                            if falta_m > 0 and validar_regla(e, dia, "Mañana", excepciones):
                                asig_m.append(e); falta_m -= 1
                                logs.append(f"⚠️ {dia}: {e['Nombre']} -> Extra Mañana")
                            elif falta_t > 0 and validar_regla(e, dia, "Tarde", excepciones):
                                asig_t.append(e); falta_t -= 1
                                logs.append(f"⚠️ {dia}: {e['Nombre']} -> Extra Tarde")
                    
                    # Partidos
                    if falta_m > 0 and falta_t > 0:
                        partidos = [e for e in disponibles if e["Partido"] and e not in asig_m + asig_t]
                        for p in partidos:
                            if validar_regla(p, dia, "Mañana", excepciones) and validar_regla(p, dia, "Tarde", excepciones):
                                p_copy = p.copy()
                                p_copy["Rol"] = f"{p['Rol']} (PARTIDO)"
                                asig_m.append(p_copy); asig_t.append(p_copy)
                                falta_m -= 1; falta_t -= 1
                                logs.append(f"🔄 {dia}: {p['Nombre']} -> Turno Partido")

                    # GUARDAR DATOS
                    for x in asig_m: schedule.append({"Día": dia, "Turno": "Mañana", "Horario": "08:30-16:30", "Nombre": x["Nombre"]})
                    for x in asig_t: schedule.append({"Día": dia, "Turno": "Tarde", "Horario": "16:00-CIERRE", "Nombre": x["Nombre"]})
                    
                    kpis.append({
                        "Día": dia, "Meta M": meta_m, "Real M": len(asig_m), "Gap M": len(asig_m)-meta_m,
                        "Meta T": meta_t, "Real T": len(asig_t), "Gap T": len(asig_t)-meta_t
                    })

                # --- RESULTADOS ---
                if schedule:
                    st.success("✅ Horario Generado")
                    
                    # Matriz Visual
                    df_sch = pd.DataFrame(schedule)
                    matrix = df_sch.pivot_table(index="Nombre", columns="Día", values="Horario", aggfunc=lambda x: " / ".join(x))
                    matrix = matrix.reindex(df_edited["Nombre"].unique()).reindex(columns=CONFIG["DIAS"]).fillna("LIBRE")
                    
                    def color_cells(val):
                        return 'background-color: #ffcccc; color: #555' if val == "LIBRE" else 'background-color: #e6f3ff; color: #000'
                    
                    st.dataframe(matrix.style.map(color_cells), use_container_width=True)
                    
                    # KPIs
                    st.subheader("Control de Objetivos")
                    df_kpi = pd.DataFrame(kpis)
                    
                    def color_kpi(val):
                        if isinstance(val, int): return 'color: red; font-weight: bold' if val < 0 else 'color: green'
                        return ''
                    
                    st.dataframe(df_kpi.style.map(color_kpi, subset=["Gap M", "Gap T"]), use_container_width=True)
                    
                    # Descarga
                    excel_data = generar_excel(matrix, df_kpi, logs)
                    st.download_button("📥 Descargar Excel", excel_data, "horario_rufina.xlsx")
                    
                    if logs:
                        with st.expander("Ver Logs del Sistema"):
                            st.write(logs)
                else:
                    st.error("No se pudo generar horario. Revisa disponibilidades.")

    except Exception as e:
        st.error("❌ Ocurrió un error inesperado en la aplicación.")
        st.exception(e)

if __name__ == "__main__":
    main()