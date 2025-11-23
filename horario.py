import streamlit as st
import pandas as pd
import io
import random
from datetime import datetime, time

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Planificador Doña Rufina", layout="wide", page_icon="🍽️")

# --- 2. DATOS Y CONSTANTES ---
CONFIG = {
    "TURNOS": {
        "Mañana": {"inicio": "08:30", "fin": "16:30"},
        "Tarde":  {"inicio": "16:00", "fin": "23:59"},
        "Partido": {"bloque1": "12:00-16:00", "bloque2": "20:00-23:59"}
    },
    "DIAS": ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"],
    # Pares consecutivos para rotar
    "PARES_DIAS_LIBRES": [
        ("Lunes", "Martes"), ("Martes", "Miércoles"), ("Miércoles", "Jueves"),
        ("Jueves", "Viernes"), ("Viernes", "Sábado"), ("Sábado", "Domingo"),
        ("Domingo", "Lunes")
    ],
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

# --- 3. LÓGICA DE ROTACIÓN (NUEVO) ---

def detectar_libranza_anterior(uploaded_file):
    """
    Lee el Excel anterior y devuelve un diccionario:
    {'Olfa': ['Lunes', 'Martes'], 'Miguel': ['Sábado', 'Domingo']...}
    """
    libranzas_previas = {}
    if uploaded_file is None:
        return {}
    
    try:
        # Leemos el Excel. Asumimos que la primera columna es el Nombre
        df_prev = pd.read_excel(uploaded_file, sheet_name='Horario Semanal', index_col=0)
        
        for nombre, fila in df_prev.iterrows():
            dias_off = []
            for dia in CONFIG["DIAS"]:
                if dia in fila.index:
                    val = str(fila[dia]).upper()
                    if "LIBRE" in val:
                        dias_off.append(dia)
            
            if dias_off:
                libranzas_previas[nombre] = dias_off
                
    except Exception as e:
        st.error(f"Error leyendo el archivo de rotación: {e}")
        return {}
        
    return libranzas_previas

def asignar_dias_libres_inteligente(staff_list, excepciones, libranzas_previas):
    """
    Asigna días libres basándose en:
    1. Excepciones manuales (Prioridad absoluta).
    2. Rotación histórica (Si libró L-M, ahora toca M-X).
    3. Asignación por defecto (Si no hay histórico).
    """
    staff_con_libres = []
    pares = CONFIG["PARES_DIAS_LIBRES"]
    
    idx_default = 0 # Contador para los que no tienen histórico
    
    for emp in staff_list:
        nombre = emp["Nombre"]
        emp["Dias_Libres_Asignados"] = []
        
        # A. Chequear Excepciones Manuales (Usuario fuerza el día)
        dias_manuales = [x["Día"] for x in excepciones if x["Nombre"] == nombre and x["Tipo"] == "Día Libre Completo"]
        
        if dias_manuales:
            emp["Dias_Libres_Asignados"] = dias_manuales
        
        # B. Chequear Rotación Histórica
        elif nombre in libranzas_previas:
            previos = libranzas_previas[nombre]
            # Buscamos qué par coincide con sus días libres previos
            # (Simplificación: miramos el primer día libre previo para ubicarlo en la lista)
            if len(previos) > 0:
                primer_dia_previo = previos[0]
                # Buscar índice en nuestra lista de pares
                idx_encontrado = -1
                for i, pair in enumerate(pares):
                    if pair[0] == primer_dia_previo:
                        idx_encontrado = i
                        break
                
                if idx_encontrado != -1:
                    # ROTACIÓN: Le damos el SIGUIENTE par de la lista
                    nuevo_idx = (idx_encontrado + 1) % len(pares)
                    emp["Dias_Libres_Asignados"] = list(pares[nuevo_idx])
                else:
                    # Si sus días previos eran raros, le damos uno por defecto
                    emp["Dias_Libres_Asignados"] = list(pares[idx_default % len(pares)])
                    idx_default += 1
            else:
                emp["Dias_Libres_Asignados"] = list(pares[idx_default % len(pares)])
                idx_default += 1
                
        # C. Asignación por Defecto (Nuevo o sin datos)
        else:
            emp["Dias_Libres_Asignados"] = list(pares[idx_default % len(pares)])
            idx_default += 1
            
        staff_con_libres.append(emp)
        
    return staff_con_libres

# --- 4. FUNCIONES UTILITARIAS ---

def str_to_time(hora_str):
    if not hora_str or hora_str == "-": return None
    if str(hora_str).upper() == "CIERRE": return time(23, 59)
    try: return datetime.strptime(str(hora_str), "%H:%M").time()
    except: return None

def validar_regla(empleado_dic, dia, turno_nombre, lista_excepciones):
    # 1. ¿Es su día libre asignado?
    if dia in empleado_dic.get("Dias_Libres_Asignados", []): return False

    # 2. Validar Excepciones Horarias
    nombre = empleado_dic["Nombre"]
    regla = next((x for x in lista_excepciones if x["Nombre"] == nombre and x["Día"] == dia), None)
    
    if not regla: return True

    tipo = regla["Tipo"]
    hora_limite = str_to_time(regla.get("Hora", "-"))
    
    if tipo == "Día Libre Completo": return False # Redundante pero seguro

    inicio_turno = str_to_time(CONFIG["TURNOS"][turno_nombre]["inicio"])
    fin_turno = str_to_time(CONFIG["TURNOS"][turno_nombre]["fin"])

    if tipo == "Entrada Mínima" and hora_limite and inicio_turno < hora_limite: return False
    if tipo == "Salida Máxima" and hora_limite and fin_turno > hora_limite: return False
            
    return True

def generar_excel(df_matrix, df_kpis, logs):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_matrix.to_excel(writer, sheet_name='Horario Semanal')
        df_kpis.to_excel(writer, sheet_name='Faltantes', index=False)
        pd.DataFrame(logs, columns=["Detalle"]).to_excel(writer, sheet_name='Logs', index=False)
        writer.sheets['Horario Semanal'].set_column('A:Z', 20)
    return output.getvalue()

# --- 5. INTERFAZ PRINCIPAL ---

def main():
    try:
        # --- SIDEBAR ---
        st.sidebar.header("📂 Gestión")
        archivo = st.sidebar.file_uploader("Cargar Horario Anterior (Excel)", type=["xlsx"])
        
        st.sidebar.markdown("---")
        st.sidebar.header("🎯 Objetivos")
        
        st.sidebar.subheader("Lunes - Jueves")
        lj_m = st.sidebar.slider("Mañana (L-J)", 0, 10, 3)
        lj_t = st.sidebar.slider("Tarde (L-J)", 0, 10, 4)

        st.sidebar.subheader("Viernes - Domingo")
        vd_m = st.sidebar.slider("Mañana (V-D)", 0, 10, 4)
        vd_t = st.sidebar.slider("Tarde (V-D)", 0, 10, 6)

        # --- CONTENIDO ---
        st.title("🍽️ Planificador Doña Rufina")
        tab1, tab2 = st.tabs(["👥 Equipo", "📅 Horario"])

        with tab1:
            col1, col2 = st.columns([1.5, 1])
            with col1:
                st.subheader("Plantilla")
                df_base = pd.DataFrame(CONFIG["STAFF_INIT"])
                df_edited = st.data_editor(df_base, num_rows="dynamic", hide_index=True, key="edit_staff", column_config={"Activo": st.column_config.CheckboxColumn("Disp?", width="small")})
            
            with col2:
                st.subheader("Excepciones")
                if 'excepciones' not in st.session_state: st.session_state.excepciones = []
                with st.form("add_rule"):
                    e_nom = st.selectbox("Nombre", df_edited["Nombre"].unique())
                    e_dia = st.selectbox("Día", CONFIG["DIAS"])
                    e_tipo = st.selectbox("Tipo", ["Día Libre Completo", "Entrada Mínima", "Salida Máxima"])
                    e_hora = st.text_input("Hora (HH:MM)", placeholder="Ej: 11:30")
                    if st.form_submit_button("Añadir"):
                        st.session_state.excepciones.append({"Nombre": e_nom, "Día": e_dia, "Tipo": e_tipo, "Hora": e_hora})
                        st.success("Guardado")
                if st.session_state.excepciones:
                    st.dataframe(pd.DataFrame(st.session_state.excepciones), hide_index=True)
                    if st.button("Limpiar"): st.session_state.excepciones = []; st.rerun()

        with tab2:
            if st.button("🚀 Calcular Horario", type="primary"):
                schedule, kpis_simples, logs = [], [], []
                
                # 1. Leer Personal
                staff_raw = df_edited[df_edited["Activo"]==True].to_dict('records')
                excepciones = st.session_state.excepciones
                
                # 2. Leer Histórico (Si existe)
                historial = detectar_libranza_anterior(archivo)
                if historial: st.success(f"Histórico procesado para {len(historial)} empleados.")

                # 3. Asignar Días Libres (Con lógica de rotación)
                staff_pool = asignar_dias_libres_inteligente(staff_raw, excepciones, historial)

                # 4. Generar Días
                for dia in CONFIG["DIAS"]:
                    es_finde = dia in ["Viernes", "Sábado", "Domingo"]
                    meta_m = vd_m if es_finde else lj_m
                    meta_t = vd_t if es_finde else lj_t
                    
                    asig_m, asig_t = [], []
                    
                    # Filtro disponibilidad
                    disponibles = [e for e in staff_pool if validar_regla(e, dia, "Mañana", excepciones) or validar_regla(e, dia, "Tarde", excepciones)]

                    # A. Roles Críticos
                    for rol in CONFIG["ROLES_CRITICOS"]:
                        # Mañana
                        cand = next((c for c in disponibles if c["Rol"] == rol and c not in asig_m + asig_t and validar_regla(c, dia, "Mañana", excepciones)), None)
                        if cand: asig_m.append(cand)
                        # Tarde
                        cand = next((c for c in disponibles if c["Rol"] == rol and c not in asig_m + asig_t and validar_regla(c, dia, "Tarde", excepciones)), None)
                        if cand: asig_t.append(cand)

                    # B. Relleno General
                    while len(asig_m) < meta_m:
                        cand = next((c for c in disponibles if c not in asig_m + asig_t and validar_regla(c, dia, "Mañana", excepciones)), None)
                        if cand: asig_m.append(cand)
                        else: break
                    
                    while len(asig_t) < meta_t:
                        cand = next((c for c in disponibles if c not in asig_m + asig_t and validar_regla(c, dia, "Tarde", excepciones)), None)
                        if cand: asig_t.append(cand)
                        else: break

                    # C. Déficit (Extras y Partidos)
                    falta_m = meta_m - len(asig_m)
                    falta_t = meta_t - len(asig_t)
                    
                    if falta_m > 0 or falta_t > 0:
                        extras = [e for e in disponibles if e["Extra"] and e not in asig_m + asig_t]
                        for e in extras:
                            if falta_m > 0 and validar_regla(e, dia, "Mañana", excepciones):
                                asig_m.append(e); falta_m -= 1; logs.append(f"⚠️ {dia}: {e['Nombre']} (Extra Mañana)")
                            elif falta_t > 0 and validar_regla(e, dia, "Tarde", excepciones):
                                asig_t.append(e); falta_t -= 1; logs.append(f"⚠️ {dia}: {e['Nombre']} (Extra Tarde)")
                    
                    if falta_m > 0 and falta_t > 0:
                        partidos = [e for e in disponibles if e["Partido"] and e not in asig_m + asig_t]
                        for p in partidos:
                            if validar_regla(p, dia, "Mañana", excepciones) and validar_regla(p, dia, "Tarde", excepciones):
                                p_copy = p.copy(); p_copy["Rol"] += " (PARTIDO)"
                                asig_m.append(p_copy); asig_t.append(p_copy)
                                falta_m -= 1; falta_t -= 1; logs.append(f"🔄 {dia}: {p['Nombre']} (Turno Partido)")

                    # Resultados
                    for x in asig_m: schedule.append({"Día": dia, "Horario": "08:30-16:30", "Nombre": x["Nombre"]})
                    for x in asig_t: schedule.append({"Día": dia, "Horario": "16:00-CIERRE", "Nombre": x["Nombre"]})
                    
                    # KPI SIMPLE (Solo Faltantes)
                    gap_m = len(asig_m) - meta_m
                    gap_t = len(asig_t) - meta_t
                    kpis_simples.append({
                        "Día": dia, 
                        "Faltan Mañana": abs(gap_m) if gap_m < 0 else 0,
                        "Faltan Tarde": abs(gap_t) if gap_t < 0 else 0
                    })

                # --- VISUALIZACIÓN FINAL ---
                if schedule:
                    st.success("✅ Horario Generado")
                    
                    # 1. Matriz
                    df_sch = pd.DataFrame(schedule)
                    matrix = df_sch.pivot_table(index="Nombre", columns="Día", values="Horario", aggfunc=lambda x: " / ".join(x))
                    matrix = matrix.reindex(df_edited["Nombre"].unique()).reindex(columns=CONFIG["DIAS"]).fillna("LIBRE")
                    
                    def style_cells(val):
                        return 'background-color: #ffcccc; color: #555' if "LIBRE" in str(val) else 'background-color: #e6f3ff; color: #000'
                    st.dataframe(matrix.style.map(style_cells), use_container_width=True)
                    
                    # 2. Resumen Faltantes
                    st.subheader("⚠️ Resumen de Personal Faltante")
                    df_kpi = pd.DataFrame(kpis_simples)
                    
                    # Mostrar solo si hay faltantes > 0 para limpiar ruido, o mostrar todo coloreado
                    def highlight_missing(val):
                        return 'color: red; font-weight: bold' if val > 0 else 'color: lightgray'
                    st.dataframe(df_kpi.style.map(highlight_missing), use_container_width=True)

                    # 3. Excel
                    excel_data = generar_excel(matrix, df_kpi, logs)
                    st.download_button("📥 Descargar Excel", excel_data, "horario.xlsx")
                else:
                    st.error("No se pudo generar nada. Revisa configuración.")

    except Exception as e:
        st.error("Error crítico en la aplicación:")
        st.exception(e)

if __name__ == "__main__":
    main()