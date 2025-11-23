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
    "PARES_DIAS_LIBRES": [
        ("Lunes", "Martes"), 
        ("Martes", "Miércoles"), 
        ("Miércoles", "Jueves"),
        ("Jueves", "Viernes"), 
        ("Viernes", "Sábado"), 
        ("Sábado", "Domingo")
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

# --- 3. LÓGICA DE ROTACIÓN ---

def detectar_libranza_anterior(uploaded_file):
    libranzas_previas = {}
    if uploaded_file is None:
        return {}
    try:
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
    staff_con_libres = []
    pares = CONFIG["PARES_DIAS_LIBRES"]
    idx_default = 0 
    
    for emp in staff_list:
        nombre = emp["Nombre"]
        emp["Dias_Libres_Asignados"] = []
        dias_manuales = [x["Día"] for x in excepciones if x["Nombre"] == nombre and x["Tipo"] == "Día Libre Completo"]
        
        if dias_manuales:
            emp["Dias_Libres_Asignados"] = dias_manuales
        elif nombre in libranzas_previas:
            previos = libranzas_previas[nombre]
            if len(previos) > 0:
                primer_dia_previo = previos[0]
                idx_encontrado = -1
                for i, pair in enumerate(pares):
                    if pair[0] == primer_dia_previo:
                        idx_encontrado = i; break
                if idx_encontrado != -1:
                    nuevo_idx = (idx_encontrado + 1) % len(pares)
                    emp["Dias_Libres_Asignados"] = list(pares[nuevo_idx])
                else:
                    emp["Dias_Libres_Asignados"] = list(pares[idx_default % len(pares)])
                    idx_default += 1
            else:
                emp["Dias_Libres_Asignados"] = list(pares[idx_default % len(pares)])
                idx_default += 1
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
    if dia in empleado_dic.get("Dias_Libres_Asignados", []): return False
    nombre = empleado_dic["Nombre"]
    regla = next((x for x in lista_excepciones if x["Nombre"] == nombre and x["Día"] == dia), None)
    if not regla: return True
    tipo = regla["Tipo"]
    hora_limite = str_to_time(regla.get("Hora", "-"))
    if tipo == "Día Libre Completo": return False 
    inicio_turno = str_to_time(CONFIG["TURNOS"][turno_nombre]["inicio"])
    fin_turno = str_to_time(CONFIG["TURNOS"][turno_nombre]["fin"])
    if tipo == "Entrada Mínima" and hora_limite and inicio_turno < hora_limite: return False
    if tipo == "Salida Máxima" and hora_limite and fin_turno > hora_limite: return False
    return True

def generar_excel(df_matrix, df_kpis, df_validacion, logs):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_matrix.to_excel(writer, sheet_name='Horario Semanal')
        df_validacion.to_excel(writer, sheet_name='Auditoría Roles', index=False)
        df_kpis.to_excel(writer, sheet_name='Faltantes', index=False)
        pd.DataFrame(logs, columns=["Detalle"]).to_excel(writer, sheet_name='Logs', index=False)
        writer.sheets['Horario Semanal'].set_column('A:Z', 20)
        writer.sheets['Auditoría Roles'].set_column('A:E', 15)
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
                
                staff_raw = df_edited[df_edited["Activo"]==True].to_dict('records')
                excepciones = st.session_state.excepciones
                historial = detectar_libranza_anterior(archivo)
                if historial: st.success(f"Histórico procesado para {len(historial)} empleados.")

                staff_pool = asignar_dias_libres_inteligente(staff_raw, excepciones, historial)

                for dia in CONFIG["DIAS"]:
                    es_finde = dia in ["Viernes", "Sábado", "Domingo"]
                    meta_m = vd_m if es_finde else lj_m
                    meta_t = vd_t if es_finde else lj_t
                    asig_m, asig_t = [], []
                    disponibles = [e for e in staff_pool if validar_regla(e, dia, "Mañana", excepciones) or validar_regla(e, dia, "Tarde", excepciones)]

                    # Roles Críticos
                    for rol in CONFIG["ROLES_CRITICOS"]:
                        cand = next((c for c in disponibles if c["Rol"] == rol and c not in asig_m + asig_t and validar_regla(c, dia, "Mañana", excepciones)), None)
                        if cand: asig_m.append(cand)
                        cand = next((c for c in disponibles if c["Rol"] == rol and c not in asig_m + asig_t and validar_regla(c, dia, "Tarde", excepciones)), None)
                        if cand: asig_t.append(cand)

                    # Relleno General
                    while len(asig_m) < meta_m:
                        cand = next((c for c in disponibles if c not in asig_m + asig_t and validar_regla(c, dia, "Mañana", excepciones)), None)
                        if cand: asig_m.append(cand)
                        else: break
                    while len(asig_t) < meta_t:
                        cand = next((c for c in disponibles if c not in asig_m + asig_t and validar_regla(c, dia, "Tarde", excepciones)), None)
                        if cand: asig_t.append(cand)
                        else: break

                    # Déficit
                    falta_m, falta_t = meta_m - len(asig_m), meta_t - len(asig_t)
                    if falta_m > 0 or falta_t > 0:
                        extras = [e for e in disponibles if e["Extra"] and e not in asig_m + asig_t]
                        for e in extras:
                            if falta_m > 0 and validar_regla(e, dia, "Mañana", excepciones):
                                asig_m.append(e); falta_m -= 1; logs.append(f"⚠️ {dia}: {e['Nombre']} (Extra M)")
                            elif falta_t > 0 and validar_regla(e, dia, "Tarde", excepciones):
                                asig_t.append(e); falta_t -= 1; logs.append(f"⚠️ {dia}: {e['Nombre']} (Extra T)")
                    
                    if falta_m > 0 and falta_t > 0:
                        partidos = [e for e in disponibles if e["Partido"] and e not in asig_m + asig_t]
                        for p in partidos:
                            if validar_regla(p, dia, "Mañana", excepciones) and validar_regla(p, dia, "Tarde", excepciones):
                                p_copy = p.copy(); p_copy["Rol"] += " (PARTIDO)"
                                asig_m.append(p_copy); asig_t.append(p_copy)
                                falta_m -= 1; falta_t -= 1; logs.append(f"🔄 {dia}: {p['Nombre']} (Partido)")

                    for x in asig_m: schedule.append({"Día": dia, "Turno": "Mañana", "Horario": "08:30-16:30", "Nombre": x["Nombre"], "Rol": x["Rol"]})
                    for x in asig_t: schedule.append({"Día": dia, "Turno": "Tarde", "Horario": "16:00-CIERRE", "Nombre": x["Nombre"], "Rol": x["Rol"]})
                    
                    gap_m = len(asig_m) - meta_m
                    gap_t = len(asig_t) - meta_t
                    kpis_simples.append({
                        "Día": dia, 
                        "Faltan Mañana": abs(gap_m) if gap_m < 0 else 0,
                        "Faltan Tarde": abs(gap_t) if gap_t < 0 else 0
                    })

                if schedule:
                    st.success("✅ Horario Generado")
                    
                    # 1. Matriz
                    df_sch = pd.DataFrame(schedule)
                    matrix = df_sch.pivot_table(index="Nombre", columns="Día", values="Horario", aggfunc=lambda x: " / ".join(x))
                    matrix = matrix.reindex(df_edited["Nombre"].unique()).reindex(columns=CONFIG["DIAS"]).fillna("LIBRE")
                    
                    def style_cells(val):
                        return 'background-color: #ffcccc; color: #555' if "LIBRE" in str(val) else 'background-color: #e6f3ff; color: #000'
                    st.dataframe(matrix.style.map(style_cells), use_container_width=True)
                    
                    # 2. VALIDACIÓN DE ROLES CRÍTICOS (NUEVO BLOQUE)
                    st.subheader("🛡️ Auditoría de Roles Críticos")
                    validacion_roles = []
                    for dia in CONFIG["DIAS"]:
                        # Filtrar datos de este día
                        ops_dia = [s for s in schedule if s['Día'] == dia]
                        
                        # Mañana
                        ops_m = [s for s in ops_dia if s['Turno'] == 'Mañana']
                        has_jefe_m = any("J. Cocina" in s['Rol'] for s in ops_m)
                        has_lava_m = any("Lavaplatos" in s['Rol'] for s in ops_m)
                        
                        # Tarde
                        ops_t = [s for s in ops_dia if s['Turno'] == 'Tarde']
                        has_jefe_t = any("J. Cocina" in s['Rol'] for s in ops_t)
                        has_lava_t = any("Lavaplatos" in s['Rol'] for s in ops_t)
                        
                        validacion_roles.append({
                            "Día": dia,
                            "Jefe Mañana": "✅" if has_jefe_m else "❌",
                            "Lava Mañana": "✅" if has_lava_m else "❌",
                            "Jefe Tarde": "✅" if has_jefe_t else "❌",
                            "Lava Tarde": "✅" if has_lava_t else "❌",
                        })
                    
                    df_validacion = pd.DataFrame(validacion_roles)
                    st.dataframe(df_validacion, use_container_width=True)

                    # 3. Resumen Faltantes
                    st.subheader("⚠️ Resumen de Personal Faltante")
                    df_kpi = pd.DataFrame(kpis_simples)
                    
                    def highlight_missing(val):
                        if isinstance(val, (int, float)):
                            return 'color: red; font-weight: bold' if val > 0 else 'color: lightgray'
                        return ''
                    
                    st.dataframe(df_kpi.style.map(highlight_missing, subset=["Faltan Mañana", "Faltan Tarde"]), use_container_width=True)
                    
                    # 4. Excel
                    excel_data = generar_excel(matrix, df_kpi, df_validacion, logs)
                    st.download_button("📥 Descargar Excel", excel_data, "horario.xlsx")
                else:
                    st.error("No se pudo generar nada. Revisa configuración.")

    except Exception as e:
        st.error("Error crítico en la aplicación:")
        st.exception(e)

if __name__ == "__main__":
    main()