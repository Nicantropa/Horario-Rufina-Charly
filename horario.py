import streamlit as st
import pandas as pd
import io
import random
from datetime import datetime, time

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Planificador Doña Rufina", layout="wide", page_icon="🍽️")

CONFIG = {
    "TURNOS": {
        "Mañana": {"inicio": "08:30", "fin": "16:30"},
        "Tarde":  {"inicio": "16:00", "fin": "23:59"},
        "Partido": {"bloque1": "12:00-16:00", "bloque2": "20:00-23:59"}
    },
    "DIAS": ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"],
    "PARES_DIAS_LIBRES": [
        ("Lunes", "Martes"), ("Martes", "Miércoles"), ("Miércoles", "Jueves"),
        ("Jueves", "Viernes"), ("Viernes", "Sábado"), ("Sábado", "Domingo")
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

# --- 2. LÓGICA DE DÍAS LIBRES ---

def detectar_libranza_anterior(uploaded_file):
    libranzas_previas = {}
    if uploaded_file is None: return {}
    try:
        df_prev = pd.read_excel(uploaded_file, sheet_name='Horario Semanal', index_col=0)
        for nombre, fila in df_prev.iterrows():
            dias_off = []
            for dia in CONFIG["DIAS"]:
                if dia in fila.index and "LIBRE" in str(fila[dia]).upper():
                    dias_off.append(dia)
            if dias_off: libranzas_previas[nombre] = dias_off
    except Exception: return {}
    return libranzas_previas

def asignar_dias_libres_inteligente(staff_list, excepciones, libranzas_previas):
    staff_con_libres = []
    pares = CONFIG["PARES_DIAS_LIBRES"]
    
    # Separamos contadores por ROL para intentar que no libren todos los jefes el mismo día
    idx_rol = {"J. Cocina": 0, "Lavaplatos": 0, "Eq. General": 0}
    
    for emp in staff_list:
        nombre = emp["Nombre"]
        rol = emp["Rol"]
        emp["Dias_Libres_Asignados"] = []
        
        # 1. Excepciones Manuales (Prioridad Absoluta)
        dias_manuales = [x["Día"] for x in excepciones if x["Nombre"] == nombre and x["Tipo"] == "Día Libre Completo"]
        
        if dias_manuales:
            emp["Dias_Libres_Asignados"] = dias_manuales
        elif nombre in libranzas_previas:
            # 2. Rotación Histórica
            previos = libranzas_previas[nombre]
            idx_encontrado = -1
            if len(previos) > 0:
                primer_dia = previos[0]
                for i, pair in enumerate(pares):
                    if pair[0] == primer_dia: idx_encontrado = i; break
            
            if idx_encontrado != -1:
                nuevo_idx = (idx_encontrado + 1) % len(pares)
                emp["Dias_Libres_Asignados"] = list(pares[nuevo_idx])
            else:
                emp["Dias_Libres_Asignados"] = list(pares[idx_rol.get(rol, 0) % len(pares)])
                idx_rol[rol] = idx_rol.get(rol, 0) + 1
        else:
            # 3. Asignación Staggered (Escalonada) por Rol
            emp["Dias_Libres_Asignados"] = list(pares[idx_rol.get(rol, 0) % len(pares)])
            idx_rol[rol] = idx_rol.get(rol, 0) + 1
            
        staff_con_libres.append(emp)
    return staff_con_libres

# --- 3. VALIDACIONES Y UTILIDADES ---

def str_to_time(hora_str):
    if not hora_str or hora_str == "-": return None
    if str(hora_str).upper() == "CIERRE": return time(23, 59)
    try: return datetime.strptime(str(hora_str), "%H:%M").time()
    except: return None

def cumple_restricciones_duras(empleado, dia, turno_nombre, excepciones):
    """Verifica SOLO restricciones inamovibles (Excepciones Manuales y Horarios). Ignora día libre calculado."""
    nombre = empleado["Nombre"]
    regla = next((x for x in excepciones if x["Nombre"] == nombre and x["Día"] == dia), None)
    
    if not regla: return True # No hay regla manual

    tipo = regla["Tipo"]
    hora_limite = str_to_time(regla.get("Hora", "-"))
    
    # Si el usuario puso MANUALMENTE "Día Libre Completo", eso es sagrado.
    if tipo == "Día Libre Completo": return False

    inicio = str_to_time(CONFIG["TURNOS"][turno_nombre]["inicio"])
    fin = str_to_time(CONFIG["TURNOS"][turno_nombre]["fin"])

    if tipo == "Entrada Mínima" and hora_limite and inicio < hora_limite: return False
    if tipo == "Salida Máxima" and hora_limite and fin > hora_limite: return False
    return True

def esta_en_dia_libre(empleado, dia):
    """Verifica si es su día libre calculado automáticamente."""
    return dia in empleado.get("Dias_Libres_Asignados", [])

def generar_excel(df_matrix, df_kpis, df_audit, logs):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_matrix.to_excel(writer, sheet_name='Horario Semanal')
        df_audit.to_excel(writer, sheet_name='Auditoría Roles', index=False)
        df_kpis.to_excel(writer, sheet_name='Faltantes', index=False)
        pd.DataFrame(logs, columns=["Eventos"]).to_excel(writer, sheet_name='Logs', index=False)
        writer.sheets['Horario Semanal'].set_column('A:Z', 20)
    return output.getvalue()

# --- 4. INTERFAZ PRINCIPAL ---

def main():
    try:
        st.sidebar.header("📂 Gestión")
        archivo = st.sidebar.file_uploader("Cargar Horario Anterior", type=["xlsx"])
        
        st.sidebar.markdown("---")
        st.sidebar.header("🎯 Objetivos")
        st.sidebar.subheader("Lunes - Jueves")
        lj_m = st.sidebar.slider("Mañana (L-J)", 0, 10, 3)
        lj_t = st.sidebar.slider("Tarde (L-J)", 0, 10, 4)
        st.sidebar.subheader("Viernes - Domingo")
        vd_m = st.sidebar.slider("Mañana (V-D)", 0, 10, 4)
        vd_t = st.sidebar.slider("Tarde (V-D)", 0, 10, 6)

        st.title("🍽️ Planificador Doña Rufina")
        tab1, tab2 = st.tabs(["👥 Equipo", "📅 Horario"])

        with tab1:
            c1, c2 = st.columns([1.5, 1])
            with c1:
                df_edited = st.data_editor(pd.DataFrame(CONFIG["STAFF_INIT"]), num_rows="dynamic", hide_index=True, key="edit_staff", column_config={"Activo": st.column_config.CheckboxColumn("Disp?", width="small")})
            with c2:
                if 'excepciones' not in st.session_state: st.session_state.excepciones = []
                with st.form("add"):
                    e_nom = st.selectbox("Nombre", df_edited["Nombre"].unique())
                    e_dia = st.selectbox("Día", CONFIG["DIAS"])
                    e_tipo = st.selectbox("Tipo", ["Día Libre Completo", "Entrada Mínima", "Salida Máxima"])
                    e_hora = st.text_input("Hora", placeholder="Ej: 11:30")
                    if st.form_submit_button("Guardar"):
                        st.session_state.excepciones.append({"Nombre": e_nom, "Día": e_dia, "Tipo": e_tipo, "Hora": e_hora})
                        st.success("Ok")
                if st.session_state.excepciones:
                    st.dataframe(pd.DataFrame(st.session_state.excepciones), hide_index=True)
                    if st.button("Limpiar"): st.session_state.excepciones = []; st.rerun()

        with tab2:
            if st.button("🚀 Calcular Horario", type="primary"):
                schedule, kpis_simples, logs = [], [], []
                
                # 1. Preparar Datos
                staff_raw = df_edited[df_edited["Activo"]==True].to_dict('records')
                excepciones = st.session_state.excepciones
                historial = detectar_libranza_anterior(archivo)
                
                # 2. Asignar Días Libres (Intento Inicial)
                staff_pool = asignar_dias_libres_inteligente(staff_raw, excepciones, historial)

                # 3. BUCLE DE GENERACIÓN DIARIA
                for dia in CONFIG["DIAS"]:
                    es_finde = dia in ["Viernes", "Sábado", "Domingo"]
                    meta_m = vd_m if es_finde else lj_m
                    meta_t = vd_t if es_finde else lj_t
                    
                    asig_m, asig_t = [], []
                    
                    # --- FASE 0: Definir Grupos de Disponibilidad ---
                    # Grupo A: Disponibles (No es su día libre + Cumple reglas duras)
                    grupo_a = [e for e in staff_pool if not esta_en_dia_libre(e, dia) and cumple_restricciones_duras(e, dia, "Mañana", excepciones)]
                    
                    # Grupo B: En Día Libre (Es su día libre calculado + Cumple reglas duras). RESERVA DE EMERGENCIA.
                    grupo_b = [e for e in staff_pool if esta_en_dia_libre(e, dia) and cumple_restricciones_duras(e, dia, "Mañana", excepciones)]

                    # --- FASE 1: ROLES CRÍTICOS (PRIORIDAD MAXIMA) ---
                    for rol in CONFIG["ROLES_CRITICOS"]:
                        # -- MAÑANA --
                        # 1. Intentar con Grupo A (Gente que le toca trabajar)
                        cand = next((c for c in grupo_a if c["Rol"] == rol and c not in asig_m + asig_t and cumple_restricciones_duras(c, dia, "Mañana", excepciones)), None)
                        
                        if cand:
                            asig_m.append(cand)
                        else:
                            # 2. EMERGENCIA: Buscar en Grupo B (Gente que libraba hoy)
                            # Filtramos el pool completo buscando alguien de este rol que cumpla restricciones duras
                            cand_rescue = next((c for c in staff_pool if c["Rol"] == rol and c not in asig_m + asig_t and cumple_restricciones_duras(c, dia, "Mañana", excepciones)), None)
                            
                            if cand_rescue:
                                asig_m.append(cand_rescue)
                                logs.append(f"🚨 {dia} (Mañana): {cand_rescue['Nombre']} recuperado de su día libre para cubrir {rol}.")
                            else:
                                logs.append(f"❌ {dia} (Mañana): IMPOSIBLE cubrir {rol}. Nadie disponible.")

                        # -- TARDE -- (Misma lógica)
                        # Recalcular disponibles (algunos ya entraron en Mañana)
                        cand_t = next((c for c in staff_pool if c["Rol"] == rol and c not in asig_m + asig_t and not esta_en_dia_libre(c, dia) and cumple_restricciones_duras(c, dia, "Tarde", excepciones)), None)
                        
                        if cand_t:
                            asig_t.append(cand_t)
                        else:
                            # Emergencia Tarde
                            cand_rescue_t = next((c for c in staff_pool if c["Rol"] == rol and c not in asig_m + asig_t and cumple_restricciones_duras(c, dia, "Tarde", excepciones)), None)
                            if cand_rescue_t:
                                asig_t.append(cand_rescue_t)
                                logs.append(f"🚨 {dia} (Tarde): {cand_rescue_t['Nombre']} recuperado de su día libre para cubrir {rol}.")
                            else:
                                logs.append(f"❌ {dia} (Tarde): IMPOSIBLE cubrir {rol}.")

                    # --- FASE 2: RELLENO GENERAL (Solo gente que le toca trabajar) ---
                    # Aquí NO usamos emergencia. Si falta gente, falta. Solo rompemos reglas para Jefes/Lavas.
                    pool_relleno = [e for e in staff_pool if not esta_en_dia_libre(e, dia)]
                    
                    while len(asig_m) < meta_m:
                        cand = next((c for c in pool_relleno if c not in asig_m + asig_t and cumple_restricciones_duras(c, dia, "Mañana", excepciones)), None)
                        if cand: asig_m.append(cand)
                        else: break
                    
                    while len(asig_t) < meta_t:
                        cand = next((c for c in pool_relleno if c not in asig_m + asig_t and cumple_restricciones_duras(c, dia, "Tarde", excepciones)), None)
                        if cand: asig_t.append(cand)
                        else: break

                    # --- FASE 3: DÉFICIT (Extras y Partidos) ---
                    # Solo tiramos de extras si faltan números (no roles críticos, esos ya están cubiertos o fallidos)
                    falta_m, falta_t = meta_m - len(asig_m), meta_t - len(asig_t)
                    
                    if falta_m > 0 or falta_t > 0:
                        extras = [e for e in pool_relleno if e["Extra"] and e not in asig_m + asig_t]
                        for e in extras:
                            if falta_m > 0 and cumple_restricciones_duras(e, dia, "Mañana", excepciones):
                                asig_m.append(e); falta_m -= 1; logs.append(f"⚠️ {dia}: {e['Nombre']} (Extra M)")
                            elif falta_t > 0 and cumple_restricciones_duras(e, dia, "Tarde", excepciones):
                                asig_t.append(e); falta_t -= 1; logs.append(f"⚠️ {dia}: {e['Nombre']} (Extra T)")

                    # Guardar
                    for x in asig_m: schedule.append({"Día": dia, "Turno": "Mañana", "Horario": "08:30-16:30", "Nombre": x["Nombre"], "Rol": x["Rol"]})
                    for x in asig_t: schedule.append({"Día": dia, "Turno": "Tarde", "Horario": "16:00-CIERRE", "Nombre": x["Nombre"], "Rol": x["Rol"]})
                    
                    kpis_simples.append({
                        "Día": dia, "Faltan Mañana": max(0, meta_m - len(asig_m)), "Faltan Tarde": max(0, meta_t - len(asig_t))
                    })

                # --- VISUALIZACIÓN ---
                if schedule:
                    st.success("✅ Horario Generado (Priorizando Roles Críticos)")
                    
                    # 1. Matriz
                    df_sch = pd.DataFrame(schedule)
                    matrix = df_sch.pivot_table(index="Nombre", columns="Día", values="Horario", aggfunc=lambda x: " / ".join(x))
                    matrix = matrix.reindex(df_edited["Nombre"].unique()).reindex(columns=CONFIG["DIAS"]).fillna("LIBRE")
                    def style_cells(val): return 'background-color: #ffcccc; color: #555' if "LIBRE" in str(val) else 'background-color: #e6f3ff; color: #000'
                    st.dataframe(matrix.style.map(style_cells), use_container_width=True)
                    
                    # 2. Auditoría Roles
                    st.subheader("🛡️ Auditoría de Roles Críticos")
                    audit_data = []
                    for dia in CONFIG["DIAS"]:
                        ops_dia = [s for s in schedule if s['Día'] == dia]
                        jefe_m = any("J. Cocina" in s['Rol'] for s in ops_dia if s['Turno'] == 'Mañana')
                        lava_m = any("Lavaplatos" in s['Rol'] for s in ops_dia if s['Turno'] == 'Mañana')
                        jefe_t = any("J. Cocina" in s['Rol'] for s in ops_dia if s['Turno'] == 'Tarde')
                        lava_t = any("Lavaplatos" in s['Rol'] for s in ops_dia if s['Turno'] == 'Tarde')
                        audit_data.append({
                            "Día": dia, 
                            "Jefe Mañana": "✅" if jefe_m else "❌", "Lava Mañana": "✅" if lava_m else "❌",
                            "Jefe Tarde": "✅" if jefe_t else "❌", "Lava Tarde": "✅" if lava_t else "❌"
                        })
                    st.dataframe(pd.DataFrame(audit_data), use_container_width=True)

                    # 3. Faltantes Numéricos
                    st.subheader("⚠️ Faltantes Numéricos")
                    def highlight(val): return 'color: red; font-weight: bold' if isinstance(val, (int, float)) and val > 0 else ''
                    st.dataframe(pd.DataFrame(kpis_simples).style.map(highlight, subset=["Faltan Mañana", "Faltan Tarde"]), use_container_width=True)
                    
                    # 4. Descarga
                    excel = generar_excel(matrix, pd.DataFrame(kpis_simples), pd.DataFrame(audit_data), logs)
                    st.download_button("📥 Excel", excel, "horario.xlsx")

    except Exception as e:
        st.error("Error:"); st.exception(e)

if __name__ == "__main__":
    main()