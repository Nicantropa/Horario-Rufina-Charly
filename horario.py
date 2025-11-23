import streamlit as st
import pandas as pd
import io
import random
import copy
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

# --- 2. FUNCIONES BASE ---

def str_to_time(hora_str):
    if not hora_str or hora_str == "-": return None
    if str(hora_str).upper() == "CIERRE": return time(23, 59)
    try: return datetime.strptime(str(hora_str), "%H:%M").time()
    except: return None

def cumple_restricciones_duras(empleado, dia, turno_nombre, excepciones):
    nombre = empleado["Nombre"]
    regla = next((x for x in excepciones if x["Nombre"] == nombre and x["Día"] == dia), None)
    if not regla: return True 
    tipo = regla["Tipo"]
    hora_limite = str_to_time(regla.get("Hora", "-"))
    if tipo == "Día Libre Completo": return False
    inicio = str_to_time(CONFIG["TURNOS"][turno_nombre]["inicio"])
    fin = str_to_time(CONFIG["TURNOS"][turno_nombre]["fin"])
    if tipo == "Entrada Mínima" and hora_limite and inicio < hora_limite: return False
    if tipo == "Salida Máxima" and hora_limite and fin > hora_limite: return False
    return True

def esta_en_dia_libre(empleado, dia):
    return dia in empleado.get("Dias_Libres_Asignados", [])

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

# --- 3. MOTOR DE SIMULACIÓN ---

def asignar_dias_libres_aleatorio_controlado(staff_list, excepciones, libranzas_previas):
    staff_con_libres = copy.deepcopy(staff_list)
    pares = CONFIG["PARES_DIAS_LIBRES"]
    random.shuffle(staff_con_libres)
    idx_rol = {"J. Cocina": 0, "Lavaplatos": 0, "Eq. General": 0}
    
    for emp in staff_con_libres:
        nombre = emp["Nombre"]
        rol = emp["Rol"]
        emp["Dias_Libres_Asignados"] = []
        dias_manuales = [x["Día"] for x in excepciones if x["Nombre"] == nombre and x["Tipo"] == "Día Libre Completo"]
        
        if dias_manuales:
            emp["Dias_Libres_Asignados"] = dias_manuales
        elif nombre in libranzas_previas and random.random() > 0.2: 
            previos = libranzas_previas[nombre]
            if len(previos) > 0:
                primer_dia = previos[0]
                idx_encontrado = -1
                for i, pair in enumerate(pares):
                    if pair[0] == primer_dia: idx_encontrado = i; break
                if idx_encontrado != -1:
                    nuevo_idx = (idx_encontrado + 1) % len(pares)
                    emp["Dias_Libres_Asignados"] = list(pares[nuevo_idx])
                else:
                    emp["Dias_Libres_Asignados"] = list(pares[idx_rol.get(rol, 0) % len(pares)])
            else:
                emp["Dias_Libres_Asignados"] = list(pares[idx_rol.get(rol, 0) % len(pares)])
        else:
            if random.random() > 0.5:
                emp["Dias_Libres_Asignados"] = list(random.choice(pares))
            else:
                emp["Dias_Libres_Asignados"] = list(pares[idx_rol.get(rol, 0) % len(pares)])
        idx_rol[rol] = idx_rol.get(rol, 0) + 1
    return staff_con_libres

def simular_semana(staff_base, excepciones, libranzas_previas, objetivos, usar_rescate):
    staff_pool = asignar_dias_libres_aleatorio_controlado(staff_base, excepciones, libranzas_previas)
    
    # Filtro de Muerte Súbita
    for dia in CONFIG["DIAS"]:
        jefes_libres = [e for e in staff_pool if e["Rol"] == "J. Cocina" and esta_en_dia_libre(e, dia)]
        total_jefes = [e for e in staff_pool if e["Rol"] == "J. Cocina"]
        if len(jefes_libres) == len(total_jefes) and not usar_rescate:
            return {"score": -1000000, "schedule": []}

    schedule, logs, score = [], [], 0
    kpis_simples, audit_data = [], []

    for dia in CONFIG["DIAS"]:
        es_finde = dia in ["Viernes", "Sábado", "Domingo"]
        meta_m = objetivos["vd_m"] if es_finde else objetivos["lj_m"]
        meta_t = objetivos["vd_t"] if es_finde else objetivos["lj_t"]
        
        asig_m, asig_t = [], []
        
        # Identificar plantilla disponible hoy (los que NO libran)
        # A diferencia de antes, ESTA LISTA DEBE ASIGNARSE COMPLETA (si es posible)
        trabajadores_hoy = [e for e in staff_pool if not esta_en_dia_libre(e, dia)]
        random.shuffle(trabajadores_hoy) # Barajar para reparto equitativo

        # --- FASE 1: ROLES CRÍTICOS (Prioridad Absoluta) ---
        # Los asignamos primero a sus huecos correspondientes
        for rol in CONFIG["ROLES_CRITICOS"]:
            # Mañana
            cand = next((c for c in trabajadores_hoy if c["Rol"] == rol and c not in asig_m and cumple_restricciones_duras(c, dia, "Mañana", excepciones)), None)
            if cand:
                asig_m.append(cand); score += 1000
            else:
                # Intento de Rescate (Día Libre)
                if usar_rescate:
                    rescuable = next((c for c in staff_pool if c["Rol"] == rol and esta_en_dia_libre(c, dia) and cumple_restricciones_duras(c, dia, "Mañana", excepciones)), None)
                    if rescuable:
                        asig_m.append(rescuable); score -= 10; logs.append(f"🚨 {dia} (M): {rescuable['Nombre']} recuperado ({rol})")
                    else:
                        score -= 100000; logs.append(f"❌ {dia} (M): {rol} VACANTE")
                else:
                    score -= 100000; logs.append(f"❌ {dia} (M): {rol} VACANTE")

            # Tarde
            cand_t = next((c for c in trabajadores_hoy if c["Rol"] == rol and c not in asig_t and c not in asig_m and cumple_restricciones_duras(c, dia, "Tarde", excepciones)), None)
            if cand_t:
                asig_t.append(cand_t); score += 1000
            else:
                if usar_rescate:
                    rescuable = next((c for c in staff_pool if c["Rol"] == rol and esta_en_dia_libre(c, dia) and cumple_restricciones_duras(c, dia, "Tarde", excepciones)), None)
                    if rescuable:
                        asig_t.append(rescuable); score -= 10; logs.append(f"🚨 {dia} (T): {rescuable['Nombre']} recuperado ({rol})")
                    else:
                        score -= 100000; logs.append(f"❌ {dia} (T): {rol} VACANTE")
                else:
                    score -= 100000; logs.append(f"❌ {dia} (T): {rol} VACANTE")

        # --- FASE 2: ASIGNACIÓN TOTAL (Garantizar 5 días de trabajo) ---
        # Recorremos a TODOS los trabajadores disponibles que aún no tienen turno hoy
        pendientes = [e for e in trabajadores_hoy if e not in asig_m and e not in asig_t]
        
        for p in pendientes:
            # Decidir dónde asignar: ¿Dónde falta más gente respecto a la meta?
            falta_m = meta_m - len(asig_m)
            falta_t = meta_t - len(asig_t)
            
            asignado = False
            
            # Prioridad: Donde haya más déficit
            if falta_m >= falta_t:
                # Intentar Mañana
                if cumple_restricciones_duras(p, dia, "Mañana", excepciones):
                    asig_m.append(p); asignado = True; score += 50
                elif cumple_restricciones_duras(p, dia, "Tarde", excepciones):
                    asig_t.append(p); asignado = True; score += 50
            else:
                # Intentar Tarde
                if cumple_restricciones_duras(p, dia, "Tarde", excepciones):
                    asig_t.append(p); asignado = True; score += 50
                elif cumple_restricciones_duras(p, dia, "Mañana", excepciones):
                    asig_m.append(p); asignado = True; score += 50
            
            if not asignado:
                # Si no pudo entrar por restricción horaria, no restamos score (es inevitable)
                pass

        # --- FASE 3: DÉFICIT (ORDEN RESTAURADO: EXTRAS > PARTIDOS) ---
        falta_m = meta_m - len(asig_m)
        falta_t = meta_t - len(asig_t)
        
        # Recuperamos a todos los disponibles (incluyendo los que ya trabajan, para doblar)
        # NOTA: "pool_relleno" ahora son los que NO están librando.
        pool_relleno = trabajadores_hoy

        # 3.1 PRIORIDAD: EXTRAS (Simple)
        if falta_m > 0 or falta_t > 0:
            extras = [e for e in pool_relleno if e["Extra"]]
            for e in extras:
                # Extra Mañana (Si no está ya en mañana)
                if falta_m > 0 and e not in asig_m and cumple_restricciones_duras(e, dia, "Mañana", excepciones):
                    # Evitar conflicto si ya está en tarde y no es partido (pero Extra suele implicar flexibilidad)
                    # Asumimos que Extra permite doblar turno como Hora Extra
                    asig_m.append(e); falta_m -= 1
                    score += 45 # Score positivo
                    logs.append(f"⚠️ {dia}: {e['Nombre']} (Extra M)")
                
                # Extra Tarde
                elif falta_t > 0 and e not in asig_t and cumple_restricciones_duras(e, dia, "Tarde", excepciones):
                    asig_t.append(e); falta_t -= 1
                    score += 45
                    logs.append(f"⚠️ {dia}: {e['Nombre']} (Extra T)")

        # 3.2 SECUNDARIA: PARTIDOS (Doble hueco)
        if falta_m > 0 and falta_t > 0:
             partidos = [e for e in pool_relleno if e["Partido"] and e not in asig_m and e not in asig_t]
             for p in partidos:
                 if falta_m > 0 and falta_t > 0:
                     if cumple_restricciones_duras(p, dia, "Mañana", excepciones) and cumple_restricciones_duras(p, dia, "Tarde", excepciones):
                         p_copy = p.copy(); p_copy["Rol"] += " (PARTIDO)"
                         asig_m.append(p_copy); asig_t.append(p_copy)
                         falta_m -= 1; falta_t -= 1
                         score += 40 # Menor que Extra individual, según tu preferencia
                         logs.append(f"🔄 {dia}: {p['Nombre']} (Partido)")

        # Guardar datos
        for x in asig_m: schedule.append({"Día": dia, "Turno": "Mañana", "Horario": "08:30-16:30", "Nombre": x["Nombre"], "Rol": x["Rol"]})
        for x in asig_t: schedule.append({"Día": dia, "Turno": "Tarde", "Horario": "16:00-CIERRE", "Nombre": x["Nombre"], "Rol": x["Rol"]})
        
        kpis_simples.append({"Día": dia, "Faltan Mañana": max(0, meta_m - len(asig_m)), "Faltan Tarde": max(0, meta_t - len(asig_t))})
        
        audit_data.append({
            "Día": dia, 
            "Jefe Mañana": "✅" if any("J. Cocina" in x['Rol'] for x in asig_m) else "❌",
            "Lava Mañana": "✅" if any("Lavaplatos" in x['Rol'] for x in asig_m) else "❌",
            "Jefe Tarde": "✅" if any("J. Cocina" in x['Rol'] for x in asig_t) else "❌",
            "Lava Tarde": "✅" if any("Lavaplatos" in x['Rol'] for x in asig_t) else "❌"
        })

    return {"schedule": schedule, "logs": logs, "score": score, "kpis": kpis_simples, "audit": audit_data}

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
        st.sidebar.subheader("🚨 Reglas de Emergencia")
        usar_rescate = st.sidebar.checkbox("Usar Días Libres para cubrir Roles Críticos", value=True)
        
        st.sidebar.markdown("---")
        st.sidebar.header("🎯 Objetivos (Mínimo Ideal)")
        objetivos = {}
        st.sidebar.subheader("Lunes - Jueves")
        objetivos["lj_m"] = st.sidebar.slider("Mañana (L-J)", 0, 10, 3)
        objetivos["lj_t"] = st.sidebar.slider("Tarde (L-J)", 0, 10, 4)
        st.sidebar.subheader("Viernes - Domingo")
        objetivos["vd_m"] = st.sidebar.slider("Mañana (V-D)", 0, 10, 4)
        objetivos["vd_t"] = st.sidebar.slider("Tarde (V-D)", 0, 10, 6)

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
            if st.button("🚀 Calcular Mejor Horario (5.000 Iteraciones)", type="primary"):
                staff_raw = df_edited[df_edited["Activo"]==True].to_dict('records')
                excepciones = st.session_state.excepciones
                historial = detectar_libranza_anterior(archivo)
                
                mejor_resultado = None
                mejor_score = -float('inf')
                
                barra_progreso = st.progress(0)
                num_simulaciones = 5000 
                
                for i in range(num_simulaciones):
                    resultado = simular_semana(staff_raw, excepciones, historial, objetivos, usar_rescate)
                    if resultado["score"] > mejor_score:
                        mejor_score = resultado["score"]
                        mejor_resultado = resultado
                    if i % 100 == 0: barra_progreso.progress((i + 1) / num_simulaciones)
                
                barra_progreso.progress(1.0)
                
                if mejor_resultado and mejor_resultado["schedule"]:
                    st.success(f"✅ Mejor Opción Encontrada (Puntuación: {mejor_score})")
                    schedule = mejor_resultado["schedule"]
                    
                    df_sch = pd.DataFrame(schedule)
                    matrix = df_sch.pivot_table(index="Nombre", columns="Día", values="Horario", aggfunc=lambda x: " / ".join(x))
                    matrix = matrix.reindex(df_edited["Nombre"].unique()).reindex(columns=CONFIG["DIAS"]).fillna("LIBRE")
                    def style_cells(val): return 'background-color: #ffcccc; color: #555' if "LIBRE" in str(val) else 'background-color: #e6f3ff; color: #000'
                    st.dataframe(matrix.style.map(style_cells), use_container_width=True)
                    
                    st.subheader("🛡️ Cobertura de Roles Críticos")
                    st.dataframe(pd.DataFrame(mejor_resultado["audit"]), use_container_width=True)

                    st.subheader("⚠️ Faltantes Numéricos")
                    def highlight(val): return 'color: red; font-weight: bold' if isinstance(val, (int, float)) and val > 0 else ''
                    st.dataframe(pd.DataFrame(mejor_resultado["kpis"]).style.map(highlight, subset=["Faltan Mañana", "Faltan Tarde"]), use_container_width=True)
                    
                    st.markdown("---")
                    st.subheader("🔔 Registro de Incidencias")
                    if mejor_resultado["logs"]:
                        for log in mejor_resultado["logs"]:
                            if "🚨" in log: st.error(log)
                            elif "⚠️" in log: st.warning(log)
                            elif "❌" in log: st.error(log)
                            else: st.info(log)
                    else: st.success("Horario limpio sin incidencias.")

                    excel = generar_excel(matrix, pd.DataFrame(mejor_resultado["kpis"]), pd.DataFrame(mejor_resultado["audit"]), mejor_resultado["logs"])
                    st.download_button("📥 Descargar Excel", excel, "horario_optimizado.xlsx")
                else:
                    st.error("No se pudo generar una solución válida.")

    except Exception as e:
        st.error("Error:"); st.exception(e)

if __name__ == "__main__":
    main()