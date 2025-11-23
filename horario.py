import streamlit as st
import pandas as pd
import io
from datetime import datetime, time
from typing import List, Dict, Optional, Any

# ==============================================================================
# 1. CONFIGURACIÓN Y CONSTANTES (DATA LAYER)
# ==============================================================================

CONFIG = {
    "TURNOS": {
        "Mañana": {"inicio": "08:30", "fin": "16:30"},
        "Tarde":  {"inicio": "16:00", "fin": "23:59"}, # 23:59 = Cierre técnico
        "Partido": {"bloque1": "12:00-16:00", "bloque2": "20:00-23:59"}
    },
    "DIAS": ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"],
    "ROLES_CRITICOS": ["J. Cocina", "Lavaplatos"],
    "DEFAULT_STAFF": [
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
# 2. UTILIDADES Y LÓGICA (BUSINESS LOGIC LAYER)
# ==============================================================================

class TimeUtils:
    """Manejo centralizado de conversiones de tiempo."""
    
    @staticmethod
    def str_to_time(hora_str: str) -> Optional[time]:
        if not hora_str or hora_str == "-": return None
        if hora_str.upper() == "CIERRE": return time(23, 59)
        try:
            return datetime.strptime(hora_str, "%H:%M").time()
        except ValueError:
            return None

class ConstraintValidator:
    """Evaluador de reglas y restricciones de disponibilidad."""

    def __init__(self, excepciones: List[Dict]):
        self.excepciones = excepciones

    def validar(self, empleado: Dict, dia: str, turno_nombre: str) -> bool:
        nombre = empleado["Nombre"]
        
        # Buscar regla específica
        regla = next((x for x in self.excepciones if x["Nombre"] == nombre and x["Día"] == dia), None)
        
        # Si no hay regla, está disponible
        if not regla: 
            return True

        tipo = regla["Tipo"]
        hora_limite_str = regla.get("Hora", "-")
        hora_limite = TimeUtils.str_to_time(hora_limite_str)

        # Regla 1: Bloqueo Total
        if tipo == "Día Libre Completo":
            return False

        # Obtener horarios del turno propuesto
        inicio_turno = TimeUtils.str_to_time(CONFIG["TURNOS"][turno_nombre]["inicio"])
        fin_turno = TimeUtils.str_to_time(CONFIG["TURNOS"][turno_nombre]["fin"])

        # Regla 2: Entrada Tardía
        if tipo == "Entrada Mínima":
            if hora_limite and inicio_turno < hora_limite:
                return False

        # Regla 3: Salida Temprana
        if tipo == "Salida Máxima":
            if hora_limite and fin_turno > hora_limite:
                return False

        return True

class SchedulerEngine:
    """Motor principal de generación de horarios."""

    def __init__(self, staff: List[Dict], excepciones: List[Dict], objetivos: Dict):
        self.staff = staff
        self.validator = ConstraintValidator(excepciones)
        self.objetivos = objetivos
        self.dias = CONFIG["DIAS"]
        self.logs = []
        self.schedule = [] # Lista plana de asignaciones
        self.kpi_data = []

    def run(self):
        """Ejecuta el algoritmo de asignación."""
        for dia in self.dias:
            self._procesar_dia(dia)
        return pd.DataFrame(self.schedule), pd.DataFrame(self.kpi_data), self.logs

    def _procesar_dia(self, dia: str):
        # 1. Definir metas
        es_finde = dia in ["Viernes", "Sábado", "Domingo"]
        meta_m = self.objetivos["VD_M"] if es_finde else self.objetivos["LJ_M"]
        meta_t = self.objetivos["VD_T"] if es_finde else self.objetivos["LJ_T"]

        # 2. Filtrar Pool Disponible (Quien no tiene Día Libre Total)
        pool = [e for e in self.staff if self.validator.validar(e, dia, "Mañana") or self.validator.validar(e, dia, "Tarde")]
        
        asignados_m = []
        asignados_t = []

        # --- FASE 1: ROLES CRÍTICOS ---
        self._asignar_rol_critico(dia, "Mañana", pool, asignados_m, asignados_t)
        self._asignar_rol_critico(dia, "Tarde", pool, asignados_m, asignados_t) # Nota: Corregido para usar listas separadas si es necesario

        # --- FASE 2: RELLENO GENERAL ---
        self._rellenar_turno(dia, "Mañana", meta_m, pool, asignados_m, asignados_t)
        self._rellenar_turno(dia, "Tarde", meta_t, pool, asignados_m, asignados_t)

        # --- FASE 3: RECUPERACIÓN (Extras y Partidos) ---
        self._gestionar_deficit(dia, meta_m, meta_t, pool, asignados_m, asignados_t)

        # --- GUARDAR RESULTADOS ---
        for p in asignados_m:
            self.schedule.append({"Día": dia, "Turno": "Mañana", "Horario": "08:30-16:30", "Nombre": p["Nombre"], "Rol": p["Rol"]})
        for p in asignados_t:
            self.schedule.append({"Día": dia, "Turno": "Tarde", "Horario": "16:00-CIERRE", "Nombre": p["Nombre"], "Rol": p["Rol"]})

        # --- KPIS ---
        self.kpi_data.append({
            "Día": dia,
            "Meta M": meta_m, "Real M": len(asignados_m), "Gap M": len(asignados_m) - meta_m,
            "Meta T": meta_t, "Real T": len(asignados_t), "Gap T": len(asignados_t) - meta_t
        })

    def _asignar_rol_critico(self, dia, turno_nom, pool, asig_m, asig_t):
        target_list = asig_m if turno_nom == "Mañana" else asig_t
        excluidos = asig_m + asig_t
        
        for rol in CONFIG["ROLES_CRITICOS"]:
            candidatos = [e for e in pool if e["Rol"] == rol and e not in excluidos]
            for c in candidatos:
                if self.validator.validar(c, dia, turno_nom):
                    target_list.append(c)
                    break # Solo 1 por rol crítico

    def _rellenar_turno(self, dia, turno_nom, meta, pool, asig_m, asig_t):
        target_list = asig_m if turno_nom == "Mañana" else asig_t
        
        while len(target_list) < meta:
            excluidos = asig_m + asig_t
            # Prioridad: Eq General -> Luego cualquiera disponible
            candidatos = [e for e in pool if e not in excluidos]
            if not candidatos: break
            
            seleccionado = None
            for c in candidatos:
                if self.validator.validar(c, dia, turno_nom):
                    seleccionado = c
                    break
            
            if seleccionado: target_list.append(seleccionado)
            else: break

    def _gestionar_deficit(self, dia, meta_m, meta_t, pool, asig_m, asig_t):
        falta_m = meta_m - len(asig_m)
        falta_t = meta_t - len(asig_t)

        # 1. Horas Extra
        if falta_m > 0 or falta_t > 0:
            extras = [e for e in pool if e["Extra"] and e not in asig_m + asig_t]
            for e in extras:
                if falta_m > 0 and self.validator.validar(e, dia, "Mañana"):
                    asig_m.append(e)
                    falta_m -= 1
                    self.logs.append(f"⚠️ {dia}: {e['Nombre']} asignado H. Extra (Mañana)")
                elif falta_t > 0 and self.validator.validar(e, dia, "Tarde"):
                    asig_t.append(e)
                    falta_t -= 1
                    self.logs.append(f"⚠️ {dia}: {e['Nombre']} asignado H. Extra (Tarde)")

        # 2. Turno Partido
        if falta_m > 0 and falta_t > 0:
            partidos = [e for e in pool if e["Partido"] and e not in asig_m + asig_t]
            for p in partidos:
                # Validar disponibilidad en AMBOS turnos
                if self.validator.validar(p, dia, "Mañana") and self.validator.validar(p, dia, "Tarde"):
                    p_copy = p.copy()
                    p_copy["Rol"] = f"{p['Rol']} (PARTIDO)"
                    asig_m.append(p_copy)
                    asig_t.append(p_copy)
                    falta_m -= 1
                    falta_t -= 1
                    self.logs.append(f"🔄 {dia}: {p['Nombre']} cubre Turno Partido.")

class ExcelExporter:
    """Manejo de exportación a Excel."""
    
    @staticmethod
    def generate(df_matrix: pd.DataFrame, df_kpis: pd.DataFrame, logs: List[str]) -> bytes:
        output = io.BytesIO()
        try:
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_matrix.to_excel(writer, sheet_name='Horario Semanal')
                df_kpis.to_excel(writer, sheet_name='Control Objetivos', index=False)
                
                # Formatear Logs
                df_logs = pd.DataFrame(logs, columns=["Eventos del Sistema"])
                df_logs.to_excel(writer, sheet_name='Logs', index=False)
                
                # Ajuste de columnas automático (básico)
                workbook = writer.book
                worksheet = writer.sheets['Horario Semanal']
                format1 = workbook.add_format({'text_wrap': True, 'valign': 'top'})
                worksheet.set_column('A:Z', 20, format1)

        except Exception as e:
            st.error(f"Error generando Excel: {e}")
            return b""
            
        return output.getvalue()

# ==============================================================================
# 3. INTERFAZ DE USUARIO (PRESENTATION LAYER)
# ==============================================================================

def main():
    st.set_page_config(page_title="Doña Rufina Planificador", layout="wide", page_icon="🍽️")

    # --- Sidebar: Configuración ---
    st.sidebar.title("⚙️ Configuración")
    
    st.sidebar.markdown("### 🎯 Objetivos Lunes-Jueves")
    col_lj1, col_lj2 = st.sidebar.columns(2)
    obj_lj_m = col_lj1.number_input("Mañana (L-J)", 1, 10, 3)
    obj_lj_t = col_lj2.number_input("Tarde (L-J)", 1, 10, 4)

    st.sidebar.markdown("### 🎯 Objetivos Viernes-Domingo")
    col_vd1, col_vd2 = st.sidebar.columns(2)
    obj_vd_m = col_vd1.number_input("Mañana (V-D)", 1, 10, 4)
    obj_vd_t = col_vd2.number_input("Tarde (V-D)", 1, 10, 6)

    objetivos_dict = {
        "LJ_M": obj_lj_m, "LJ_T": obj_lj_t,
        "VD_M": obj_vd_m, "VD_T": obj_vd_t
    }

    # --- Main Area ---
    st.title("🍽️ Doña Rufina Scheduler Pro")
    
    tab1, tab2 = st.tabs(["👥 Equipo y Restricciones", "📅 Generador de Horarios"])

    # --- TAB 1: GESTIÓN DE DATOS ---
    with tab1:
        col_staff, col_rules = st.columns([1.5, 1])
        
        with col_staff:
            st.subheader("Planilla de Trabajadores")
            df_base = pd.DataFrame(CONFIG["DEFAULT_STAFF"])
            df_edited = st.data_editor(
                df_base,
                column_config={
                    "Activo": st.column_config.CheckboxColumn("Disp.", width="small"),
                    "Rol": st.column_config.SelectboxColumn("Rol Base", options=["J. Cocina", "Lavaplatos", "Eq. General"]),
                },
                disabled=["Nombre"],
                hide_index=True,
                num_rows="dynamic",
                key="editor_staff"
            )

        with col_rules:
            st.subheader("Excepciones y Permisos")
            if 'excepciones' not in st.session_state: st.session_state.excepciones = []

            with st.form("form_excep"):
                c1, c2 = st.columns(2)
                e_nom = c1.selectbox("Nombre", df_edited["Nombre"].unique())
                e_dia = c2.selectbox("Día", CONFIG["DIAS"])
                e_tipo = st.selectbox("Restricción", ["Día Libre Completo", "Entrada Mínima", "Salida Máxima"])
                e_hora = st.text_input("Hora (HH:MM)", placeholder="Solo si aplica", help="Ej: 11:30")
                
                if st.form_submit_button("Añadir Regla"):
                    st.session_state.excepciones.append({
                        "Nombre": e_nom, "Día": e_dia, "Tipo": e_tipo, "Hora": e_hora
                    })
                    st.success("Regla Guardada")

            if st.session_state.excepciones:
                st.dataframe(pd.DataFrame(st.session_state.excepciones), hide_index=True, use_container_width=True)
                if st.button("Limpiar Reglas"):
                    st.session_state.excepciones = []
                    st.rerun()

    # --- TAB 2: GENERACIÓN ---
    with tab2:
        st.write("Configura el equipo en la pestaña anterior y luego genera el horario.")
        
        if st.button("🚀 Calcular Horario Óptimo", type="primary"):
            # Preparar datos
            staff_list = df_edited[df_edited["Activo"] == True].to_dict('records')
            
            # Instanciar Motor
            engine = SchedulerEngine(staff_list, st.session_state.excepciones, objetivos_dict)
            
            # Ejecutar
            df_schedule, df_kpis, logs = engine.run()

            if not df_schedule.empty:
                st.success("Cálculo completado con éxito.")
                
                # 1. Transformar a Vista Matricial (Personas x Días)
                matrix = df_schedule.pivot_table(
                    index="Nombre", 
                    columns="Día", 
                    values="Horario", 
                    aggfunc=lambda x: " / ".join(x)
                ).reindex(df_edited["Nombre"].unique()).fillna("LIBRE")
                
                # Reordenar columnas de días
                dias_presentes = [d for d in CONFIG["DIAS"] if d in matrix.columns]
                matrix = matrix[dias_presentes]

                # 2. Visualización
                st.subheader("📅 Vista de Horarios")
                
                def style_schedule(val):
                    return 'background-color: #ffcccc; color: #333' if val == "LIBRE" else 'background-color: #e6f3ff; color: #000'
                
                st.dataframe(matrix.style.map(style_schedule), use_container_width=True)

                # 3. KPIs
                st.subheader("📊 Control de Cobertura")
                
                def style_kpi(val):
                    if isinstance(val, (int, float)):
                        return 'color: red; font-weight: bold' if val < 0 else 'color: green'
                    return ''

                st.dataframe(
                    df_kpis.style.map(style_kpi, subset=["Gap M", "Gap T"]),
                    use_container_width=True
                )

                # 4. Logs
                if logs:
                    with st.expander("📝 Ver Detalles y Alertas del Algoritmo"):
                        for log in logs:
                            st.write(log)

                # 5. Descarga
                excel_data = ExcelExporter.generate(matrix, df_kpis, logs)
                if excel_data:
                    st.download_button(
                        "📥 Descargar Excel para Imprimir",
                        data=excel_data,
                        file_name="horario_semanal_dona_rufina.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

            else:
                st.error("No se pudo generar el horario. Verifica que haya personal activo.")

if __name__ == "__main__":
    main()