import streamlit as st
import pandas as pd
import io
from datetime import datetime, time
from typing import List, Dict, Any, Optional

# ==============================================================================
# 1. CAPA DE DATOS Y CONFIGURACIÓN (DATA LAYER)
# ==============================================================================
st.set_page_config(page_title="Planificador Doña Rufina", layout="wide", page_icon="🍽️")

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

# ==============================================================================
# 2. CAPA LÓGICA (BUSINESS LOGIC LAYER)
# ==============================================================================

class TimeUtils:
    """Utilidades estáticas para manejo de tiempo."""
    @staticmethod
    def str_to_time(hora_str: str) -> Optional[time]:
        if not hora_str or hora_str == "-": return None
        if hora_str.upper() == "CIERRE": return time(23, 59)
        try:
            return datetime.strptime(hora_str, "%H:%M").time()
        except ValueError:
            return None

class ConstraintValidator:
    """Maneja la validación de reglas y excepciones."""
    def __init__(self, excepciones: List[Dict]):
        self.excepciones = excepciones

    def validar(self, empleado: Dict, dia: str, turno_nom: str) -> bool:
        nombre = empleado["Nombre"]
        regla = next((x for x in self.excepciones if x["Nombre"] == nombre and x["Día"] == dia), None)
        
        if not regla: return True # Sin reglas

        tipo = regla["Tipo"]
        hora_limite = TimeUtils.str_to_time(regla.get("Hora", "-"))
        
        # 1. Bloqueo Total
        if tipo == "Día Libre Completo": return False

        # Horarios del turno
        inicio_turno = TimeUtils.str_to_time(CONFIG["TURNOS"][turno_nom]["inicio"])
        fin_turno = TimeUtils.str_to_time(CONFIG["TURNOS"][turno_nom]["fin"])

        # 2. Restricciones Horarias
        if tipo == "Entrada Mínima" and hora_limite and inicio_turno < hora_limite:
            return False
        if tipo == "Salida Máxima" and hora_limite and fin_turno > hora_limite:
            return False
            
        return True

class SchedulerEngine:
    """Motor principal del algoritmo."""
    def __init__(self, staff: List[Dict], excepciones: List[Dict], objetivos: Dict):
        self.staff = staff
        self.validator = ConstraintValidator(excepciones)
        self.objetivos = objetivos # Diccionario con metas dinámicas
        self.logs = []
        self.schedule = []
        self.kpi_data = []

    def run(self):
        for dia in CONFIG["DIAS"]:
            self._procesar_dia(dia)
        return pd.DataFrame(self.schedule), pd.DataFrame(self.kpi_data), self.logs

    def _procesar_dia(self, dia: str):
        is_weekend = dia in ["Viernes", "Sábado", "Domingo"]
        
        # Obtener meta dinámica desde los sliders inyectados
        meta_m = self.objetivos["VD_M"] if is_weekend else self.objetivos["LJ_M"]
        meta_t = self.objetivos["VD_T"] if is_weekend else self.objetivos["LJ_T"]

        # Pool disponible (filtro inicial de reglas)
        pool = [e for e in self.staff if self.validator.validar(e, dia, "Mañana") or self.validator.validar(e, dia, "Tarde")]
        
        asig_m, asig_t = [], []

        # FASE 1: Roles Críticos
        self._asignar_roles(dia, "Mañana", CONFIG["ROLES_CRITICOS"], pool, asig_m, asig_t, limite=1)
        self._asignar_roles(dia, "Tarde", CONFIG["ROLES_CRITICOS"], pool, asig_m, asig_t, limite=1)

        # FASE 2: Relleno General (Hasta cumplir meta)
        self._rellenar(dia, "Mañana", meta_m, pool, asig_m, asig_t)
        self._rellenar(dia, "Tarde", meta_t, pool, asig_m, asig_t)

        # FASE 3: Déficit (Extras y Partidos)
        self._gestionar_deficit(dia, meta_m, meta_t, pool, asig_m, asig_t)

        # Guardar
        self._registrar_resultados(dia, asig_m, asig_t)
        self._calcular_kpis(dia, meta_m, meta_t, asig_m, asig_t)

    def _asignar_roles(self, dia, turno, roles, pool, asig_m, asig_t, limite):
        target = asig_m if turno == "Mañana" else asig_t
        for rol in roles:
            candidatos = [e for e in pool if e["Rol"] == rol and e not in asig_m + asig_t]
            count = 0
            for c in candidatos:
                if count >= limite: break
                if self.validator.validar(c, dia, turno):
                    target.append(c)
                    count += 1

    def _rellenar(self, dia, turno, meta, pool, asig_m, asig_t):
        target = asig_m if turno == "Mañana" else asig_t
        while len(target) < meta:
            cands = [e for e in pool if e not in asig_m + asig_t]
            if not cands: break
            
            seleccionado = None
            for c in cands:
                if self.validator.validar(c, dia, turno):
                    seleccionado = c; break
            
            if seleccionado: target.append(seleccionado)
            else: break

    def _gestionar_deficit(self, dia, meta_m, meta_t, pool, asig_m, asig_t):
        falta_m = meta_m - len(asig_m)
        falta_t = meta_t - len(asig_t)

        # Extras
        if falta_m > 0 or falta_t > 0:
            extras = [e for e in pool if e["Extra"] and e not in asig_m + asig_t]
            for e in extras:
                if falta_m > 0 and self.validator.validar(e, dia, "Mañana"):
                    asig_m.append(e); falta_m -= 1
                    self.logs.append(f"⚠️ {dia}: {e['Nombre']} -> H. Extra (Mañana)")
                elif falta_t > 0 and self.validator.validar(e, dia, "Tarde"):
                    asig_t.append(e); falta_t -= 1
                    self.logs.append(f"⚠️ {dia}: {e['Nombre']} -> H. Extra (Tarde)")

        # Partidos
        if falta_m > 0 and falta_t > 0:
            partidos = [e for e in pool if e["Partido"] and e not in asig_m + asig_t]
            for p in partidos:
                if self.validator.validar(p, dia, "Mañana") and self.validator.validar(p, dia, "Tarde"):
                    p_copy = p.copy()
                    p_copy["Rol"] = f"{p['Rol']} (PARTIDO)"
                    asig_m.append(p_copy); asig_t.append(p_copy)
                    falta_m -= 1; falta_t -= 1
                    self.logs.append(f"🔄 {dia}: {p['Nombre']} -> Turno Partido")

    def _registrar_resultados(self, dia, asig_m, asig_t):
        for x in asig_m: self.schedule.append({"Día": dia, "Turno": "Mañana", "Horario": "08:30-16:30", "Nombre": x["Nombre"], "Rol": x["Rol"]})
        for x in asig_t: self.schedule.append({"Día": dia, "Turno": "Tarde", "Horario": "16:00-CIERRE", "Nombre": x["Nombre"], "Rol": x["Rol"]})

    def _calcular_kpis(self, dia, meta_m, meta_t, asig_m, asig_t):
        self.kpi_data.append({
            "Día": dia,
            "Meta M": meta_m, "Real M": len(asig_m), "Gap M": len(asig_m) - meta_m,
            "Meta T": meta_t, "Real T": len(asig_t), "Gap T": len(asig_t) - meta_t
        })

class ExcelExporter:
    """Clase para manejar salidas a archivo."""
    @staticmethod
    def generate(df_matrix, df_kpis, logs):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_matrix.to_excel(writer, sheet_name='Horario Semanal')
            df_kpis.to_excel(writer, sheet_name='Control Objetivos', index=False)
            pd.DataFrame(logs, columns=["Eventos"]).to_excel(writer, sheet_name='Logs', index=False)
            
            # Formato
            workbook = writer.book
            ws = writer.sheets['Horario Semanal']
            fmt = workbook.add_format({'text_wrap': True, 'valign': 'top'})
            ws.set_column('A:Z', 18, fmt)
        return output.getvalue()

# ==============================================================================
# 3. INTERFAZ DE USUARIO (PRESENTATION LAYER)
# ==============================================================================

def main():
    # --- Sidebar ---
    st.sidebar.header("📂 Gestión Semanal")
    archivo = st.sidebar.file_uploader("Cargar Histórico (Rotación)", type=["xlsx"])
    if archivo: st.sidebar.success("Histórico cargado.")

    st.sidebar.markdown("---")
    st.sidebar.header("🎯 Objetivos (Sliders)")
    
    st.sidebar.subheader("Lunes - Jueves")
    lj_m = st.sidebar.slider("Mañana (L-J)", 1, 8, 3)
    lj_t = st.sidebar.slider("Tarde (L-J)", 1, 10, 4)
    
    st.sidebar.subheader("Viernes - Domingo")
    vd_m = st.sidebar.slider("Mañana (V-D)", 1, 8, 4)
    vd_t = st.sidebar.slider("Tarde (V-D)", 1, 12, 6)

    objetivos = {"LJ_M": lj_m, "LJ_T": lj_t, "VD_M": vd_m, "VD_T": vd_t}

    # --- Panel Principal ---
    st.title("🍽️ Planificador Doña Rufina (Pro)")
    
    tab1, tab2 = st.tabs(["👥 Equipo y Reglas", "📅 Resultados"])

    with tab1:
        c1, c2 = st.columns([1.5, 1])
        with c1:
            st.subheader("Plantilla")
            df_base = pd.DataFrame(CONFIG["STAFF_INIT"])
            df_edited = st.data_editor(df_base, hide_index=True, num_rows="dynamic", key="staff_editor",
                                      column_config={"Activo": st.column_config.CheckboxColumn("Disp?")})
        
        with c2:
            st.subheader("Excepciones")
            if 'excepciones' not in st.session_state: st.session_state.excepciones = []
            
            with st.form("add_excep"):
                e_nom = st.selectbox("Nombre", df_edited["Nombre"].unique())
                e_dia = st.selectbox("Día", CONFIG["DIAS"])
                e_tipo = st.selectbox("Tipo", ["Día Libre Completo", "Entrada Mínima", "Salida Máxima"])
                e_hora = st.text_input("Hora (HH:MM)", placeholder="Ej: 11:30")
                if st.form_submit_button("Guardar"):
                    st.session_state.excepciones.append({"Nombre": e_nom, "Día": e_dia, "Tipo": e_tipo, "Hora": e_hora})
                    st.success("Guardado")
            
            if st.session_state.excepciones:
                st.dataframe(pd.DataFrame(st.session_state.excepciones), hide_index=True)
                if st.button("Borrar Reglas"):
                    st.session_state.excepciones = []; st.rerun()

    with tab2:
        if st.button("🚀 Calcular Horario", type="primary"):
            # Preparar Datos
            staff_active = df_edited[df_edited["Activo"]==True].to_dict('records')
            
            # Instanciar Motor Modular
            engine = SchedulerEngine(staff_active, st.session_state.excepciones, objetivos)
            df_sch, df_kpi, logs = engine.run()

            if not df_sch.empty:
                st.success("Horario Generado")
                
                # Matriz Visual
                matrix = df_sch.pivot_table(index="Nombre", columns="Día", values="Horario", aggfunc=lambda x: " / ".join(x))
                matrix = matrix.reindex(df_edited["Nombre"].unique()).reindex(columns=CONFIG["DIAS"]).fillna("LIBRE")