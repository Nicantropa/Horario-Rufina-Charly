import streamlit as st
import pandas as pd
import io
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Doña Rufina Planificador", layout="wide")

# --- 1. DATOS MAESTROS (Estado Inicial) ---
TURNOS = {
    "Mañana": {"inicio": "08:30", "fin": "16:30"},
    "Tarde":  {"inicio": "16:00", "fin": "23:59"}, # Usamos 23:59 para representar CIERRE matemáticamente
    "Partido": {"bloque1": "12:00-16:00", "bloque2": "20:00-23:59"}
}

# Base de datos de empleados (Tu "Oferta")
DB_EMPLEADOS = [
    {"Nombre": "Olfa",         "Rol": "J. Cocina",      "Activo": True, "Extra": False, "Partido": False},
    {"Nombre": "Charly",       "Rol": "J. Cocina",      "Activo": True, "Extra": False, "Partido": False},
    {"Nombre": "Dieynaba",     "Rol": "Lavaplatos",     "Activo": True, "Extra": True,  "Partido": False},
    {"Nombre": "Miguel",       "Rol": "Lavaplatos",     "Activo": True, "Extra": True,  "Partido": True},
    {"Nombre": "Angel",        "Rol": "Lavaplatos",     "Activo": True, "Extra": True,  "Partido": False},
    {"Nombre": "José",         "Rol": "Eq. General",    "Activo": True, "Extra": True,  "Partido": True},
    {"Nombre": "Mohammed",     "Rol": "Eq. General",    "Activo": True, "Extra": False, "Partido": False},
    {"Nombre": "Auxiliadora",  "Rol": "Eq. General",    "Activo": True, "Extra": False, "Partido": False},
    {"Nombre": "Cristian",     "Rol": "Eq. General",    "Activo": True, "Extra": True,  "Partido": False},
    {"Nombre": "David",        "Rol": "Eq. General",    "Activo": True, "Extra": True,  "Partido": False},
    {"Nombre": "Adrian",       "Rol": "Eq. General",    "Activo": True, "Extra": False, "Partido": False},
    {"Nombre": "José Capitán", "Rol": "Eq. General",    "Activo": True, "Extra": False, "Partido": False},
    {"Nombre": "Felesia",      "Rol": "Eq. General",    "Activo": False, "Extra": False, "Partido": False},
]

# --- 2. FUNCIONES DE LÓGICA ---

def str_to_time(hora_str):
    """Convierte texto 'HH:MM' a objeto time para comparar"""
    if hora_str == "CIERRE": return datetime.strptime("23:59", "%H:%M").time()
    try:
        return datetime.strptime(hora_str, "%H:%M").time()
    except:
        return None

def validar_disponibilidad(empleado, dia, turno_nombre, lista_excepciones):
    """
    EL CORAZÓN DEL SISTEMA (Lógica de Tipos)
    Retorna: True (Disponible) / False (Conflicto)
    """
    # 1. Buscar si hay excepción para esta persona/día
    regla = next((x for x in lista_excepciones if x["Nombre"] == empleado and x["Día"] == dia), None)
    
    if not regla:
        return True # Sin restricciones
        
    tipo = regla["Tipo"]
    hora_limite = str_to_time(regla["Hora"])

    # 2. Lógica según el TIPO de restricción
    if tipo == "Día Libre Completo":
        return False # Bloqueo total
        
    # Definir horarios del turno a evaluar
    inicio_turno = str_to_time(TURNOS[turno_nombre]["inicio"])
    fin_turno = str_to_time(TURNOS[turno_nombre]["fin"])
    
    if tipo == "Entrada Mínima":
        # "No puedo llegar antes de las X"
        # Conflicto si: El turno empieza ANTES de la hora límite
        if inicio_turno < hora_limite:
            return False 
            
    if tipo == "Salida Máxima":
        # "Me tengo que ir a las Y"
        # Conflicto si: El turno termina DESPUÉS de la hora límite
        if fin_turno > hora_limite:
            return False
            
    return True # Si pasa los filtros, es válido

def generar_excel_descargable(df, logs):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Horario', index=False)
        pd.DataFrame(logs, columns=["Alertas"]).to_excel(writer, sheet_name='Reporte', index=False)
    return output.getvalue()

# --- 3. INTERFAZ: BARRA LATERAL (DEMANDA) ---
st.sidebar.title("⚙️ Configuración")
st.sidebar.info("Sube el Excel anterior para calcular rotación.")
archivo = st.sidebar.file_uploader("Cargar Semana Anterior", type=["xlsx"])

st.sidebar.markdown("---")
st.sidebar.header("Objetivos de Personal")

# Sliders dobles
st.sidebar.subheader("Lunes a Jueves")
obj_lj_m = st.sidebar.slider("Mañana (L-J)", 1, 6, 3)
obj_lj_t = st.sidebar.slider("Tarde (L-J)", 1, 8, 4)

st.sidebar.subheader("Viernes a Domingo")
obj_vd_m = st.sidebar.slider("Mañana (V-D)", 1, 8, 4)
obj_vd_t = st.sidebar.slider("Tarde (V-D)", 1, 10, 6)

# --- 4. INTERFAZ: PRINCIPAL (OFERTA) ---
st.title("👨‍🍳 Planificador Doña Rufina")

col_izq, col_der = st.columns([1.5, 1])

with col_izq:
    st.subheader("1. Equipo Disponible")
    # Tabla Editable
    df_empleados = pd.DataFrame(DB_EMPLEADOS)
    df_editado = st.data_editor(
        df_empleados,
        column_config={
            "Activo": st.column_config.CheckboxColumn("¿Está?", width="small"),
            "Rol": st.column_config.SelectboxColumn("Rol Base", options=["J. Cocina", "Lavaplatos", "Eq. General"]),
            "Extra": st.column_config.CheckboxColumn("Acepta Extras?"),
            "Partido": st.column_config.CheckboxColumn("Acepta Partido?"),
        },
        disabled=["Nombre"],
        hide_index=True,
        num_rows="dynamic"
    )

with col_der:
    st.subheader("2. Excepciones (Tipos)")
    if 'excepciones' not in st.session_state: st.session_state.excepciones = []
    
    with st.expander("📍 Añadir Restricción", expanded=True):
        with st.form("form_restricciones"):
            e_nom = st.selectbox("Trabajador", df_editado["Nombre"].unique())
            e_dia = st.selectbox("Día", ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"])
            # AQUÍ ESTÁ TU LÓGICA DE TIPOS
            e_tipo = st.selectbox("Tipo de Problema", ["Día Libre Completo", "Entrada Mínima", "Salida Máxima"])
            e_hora = st.text_input("Hora Límite (HH:MM)", placeholder="Ej: 11:00 (Solo si aplica)")
            
            if st.form_submit_button("Guardar Regla"):
                st.session_state.excepciones.append({
                    "Nombre": e_nom, "Día": e_dia, "Tipo": e_tipo, 
                    "Hora": e_hora if e_tipo != "Día Libre Completo" else "-"
                })
                st.success("Regla añadida")

    if st.session_state.excepciones:
        st.write("Reglas Activas:")
        st.dataframe(pd.DataFrame(st.session_state.excepciones), hide_index=True)
        if st.button("Borrar Todo"):
            st.session_state.excepciones = []
            st.rerun()

# --- 5. ALGORITMO DE GENERACIÓN ---
st.markdown("---")
if st.button("🚀 CALCULAR HORARIO", type="primary"):
    
    resultados = []
    logs = []
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    
    # Preparamos listas de personal según dataframe editado
    staff = df_editado[df_editado["Activo"] == True].to_dict('records')
    
    for dia in dias:
        # 1. Definir objetivo numérico del día
        es_finde = dia in ["Viernes", "Sábado", "Domingo"]
        meta_manana = obj_vd_m if es_finde else obj_lj_m
        meta_tarde = obj_vd_t if es_finde else obj_lj_t
        
        asignados_m = []
        asignados_t = []
        
        # Pool de gente disponible (que no tenga Día Libre Completo hoy)
        pool_dia = [e for e in staff if validar_disponibilidad(e["Nombre"], dia, "Mañana", st.session_state.excepciones) or validar_disponibilidad(e["Nombre"], dia, "Tarde", st.session_state.excepciones)]
        
        # --- PASO A: ROLES CRÍTICOS (Jefe y Lava) ---
        for turno, lista_asignados in [("Mañana", asignados_m), ("Tarde", asignados_t)]:
            # Buscamos Jefe
            candidatos_jefe = [e for e in pool_dia if e["Rol"] == "J. Cocina" and e not in asignados_m + asignados_t]
            for c in candidatos_jefe:
                if validar_disponibilidad(c["Nombre"], dia, turno, st.session_state.excepciones):
                    lista_asignados.append(c)
                    break # Ya tenemos 1 jefe
            
            # Buscamos Lavaplatos
            candidatos_lava = [e for e in pool_dia if e["Rol"] == "Lavaplatos" and e not in asignados_m + asignados_t]
            for c in candidatos_lava:
                if validar_disponibilidad(c["Nombre"], dia, turno, st.session_state.excepciones):
                    lista_asignados.append(c)
                    break # Ya tenemos 1 lava

        # --- PASO B: RELLENO (Equipo General) ---
        # Llenar Mañana
        while len(asignados_m) < meta_manana:
            # Priorizamos Eq General, luego lo que sobre
            candidatos = [e for e in pool_dia if e not in asignados_m + asignados_t]
            if not candidatos: break
            
            seleccionado = None
            for c in candidatos:
                if validar_disponibilidad(c["Nombre"], dia, "Mañana", st.session_state.excepciones):
                    seleccionado = c
                    break
            
            if seleccionado: asignados_m.append(seleccionado)
            else: break
            
        # Llenar Tarde
        while len(asignados_t) < meta_tarde:
            candidatos = [e for e in pool_dia if e not in asignados_m + asignados_t]
            if not candidatos: break
            
            seleccionado = None
            for c in candidatos:
                if validar_disponibilidad(c["Nombre"], dia, "Tarde", st.session_state.excepciones):
                    seleccionado = c
                    break
            
            if seleccionado: asignados_t.append(seleccionado)
            else: break
            
        # --- PASO C: GESTIÓN DE DÉFICIT (Extras y Partidos) ---
        falta_m = meta_manana - len(asignados_m)
        falta_t = meta_tarde - len(asignados_t)
        
        # 1. Intentar cubrir con HORAS EXTRA (Gente que acepta Extra y no está asignada)
        if falta_m > 0 or falta_t > 0:
            libres = [e for e in pool_dia if e not in asignados_m + asignados_t and e["Extra"] == True]
            for l in libres:
                if falta_m > 0 and validar_disponibilidad(l["Nombre"], dia, "Mañana", st.session_state.excepciones):
                    asignados_m.append(l); falta_m -= 1; logs.append(f"⚠️ {dia}: {l['Nombre']} hace Horas Extra (Mañana)")
                elif falta_t > 0 and validar_disponibilidad(l["Nombre"], dia, "Tarde", st.session_state.excepciones):
                    asignados_t.append(l); falta_t -= 1; logs.append(f"⚠️ {dia}: {l['Nombre']} hace Horas Extra (Tarde)")
        
        # 2. Último Recurso: TURNO PARTIDO (Gente que acepta Partido y está libre)
        if falta_m > 0 and falta_t > 0: # Solo si falta en AMBOS lados tiene sentido el partido para cubrir huecos
            partidos = [e for e in pool_dia if e not in asignados_m + asignados_t and e["Partido"] == True]
            for p in partidos:
                # Verificar que no tenga restricción horaria que impida el partido
                # (Simplificamos: Si tiene restricción horaria, no hace partido por seguridad)
                if validar_disponibilidad(p["Nombre"], dia, "Mañana", st.session_state.excepciones) and \
                   validar_disponibilidad(p["Nombre"], dia, "Tarde", st.session_state.excepciones):
                    p_copy = p.copy()
                    p_copy["Rol"] = str(p["Rol"]) + " (PARTIDO)"
                    asignados_m.append(p_copy)
                    asignados_t.append(p_copy)
                    falta_m -= 1
                    falta_t -= 1
                    logs.append(f"🔄 {dia}: {p['Nombre']} asignado a Turno Partido.")

        # Guardar en lista final
        for x in asignados_m: resultados.append({"Día": dia, "Turno": "Mañana", "Horario": "08:30-16:30", "Nombre": x["Nombre"], "Rol": x["Rol"]})
        for x in asignados_t: resultados.append({"Día": dia, "Turno": "Tarde", "Horario": "16:00-CIERRE", "Nombre": x["Nombre"], "Rol": x["Rol"]})

    # --- 6. VISUALIZACIÓN ---
    if resultados:
        df_res = pd.DataFrame(resultados)
        
        # Vista Matricial (Pivot)
        st.success("✅ Horario Generado")
        
        if logs:
            with st.expander("Ver Reporte de Incidencias"):
                st.write(logs)

        # Crear matriz visual
        pivot = df_res.pivot_table(index=["Turno", "Horario"], columns="Día", values="Nombre", aggfunc=lambda x: ", ".join(x))
        # Ordenar columnas correctamente
        cols_orden = [d for d in dias if d in pivot.columns]
        st.dataframe(pivot[cols_orden], use_container_width=True)
        
        # Botón Descarga
        excel_bytes = generar_excel_descargable(df_res, logs)
        st.download_button("📥 Descargar Excel", excel_bytes, "horario_semanal.xlsx")
    else:
        st.error("No se pudo generar horario. Revisa disponibilidades.")