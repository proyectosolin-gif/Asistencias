import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import urllib
import pyodbc
from datetime import datetime, timezone, timedelta, date

st.set_page_config(page_title="Control de Asistencia - CBTis 139", layout="wide")

# ------------------------------------------------------------------
# Estilos CSS
# ------------------------------------------------------------------
st.markdown("""
    <style>
    .card-alumno {
        padding: 10px 14px;
        border-radius: 8px;
        margin-bottom: 4px;
        font-weight: 600;
        font-size: 1.05rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .est-asistencia { background-color: #DCFCE7; border: 1px solid #86EFAC; color: #14532D; }
    .est-falta { background-color: #FEE2E2; border: 1px solid #FCA5A5; color: #7F1D1D; }
    .est-retardo { background-color: #FFEDD5; border: 1px solid #FDBA74; color: #7C2D12; }
    .est-justificado { background-color: #E0F2FE; border: 1px solid #7DD3FC; color: #0C4A6E; }
    </style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# 0. PANTALLA DE SALIDA DEFINITIVA
# ------------------------------------------------------------------
if st.session_state.get("cerrado_definitivo", False):
    st.title("🔒 Control de Asistencia Escolar (CBTis 139)")
    st.success("### ✅ Sesión y Aplicación Cerradas Correctamente")
    st.info("La información fue guardada en el servidor de forma segura. Puedes cerrar esta pestaña.")
    
    st.components.v1.html("""
        <script>
            window.close();
            setTimeout(function() {
                window.location.href = "about:blank";
            }, 500);
        </script>
    """, height=0)
    
    st.stop()

st.title("📋 Control de Asistencia Escolar (CBTis 139)")

# ------------------------------------------------------------------
# Configuración de Estados Numéricos
# ------------------------------------------------------------------
ESTADOS_ORDEN = [1, 0, 2, 3]

CONFIG_ESTADOS = {
    1: {"label": "✅ Asistencia", "type": "secondary", "clase_css": "est-asistencia", "texto_badge": "✅ Asistió"},
    0: {"label": "❌ Falta", "type": "primary", "clase_css": "est-falta", "texto_badge": "❌ Falta"},
    2: {"label": "⏳ Retardo", "type": "secondary", "clase_css": "est-retardo", "texto_badge": "⏳ Retardo"},
    3: {"label": "📋 Justificado", "type": "secondary", "clase_css": "est-justificado", "texto_badge": "📋 Justificado"}
}

def alternar_estado(id_alumno):
    clave = f"estado_alumno_{id_alumno}"
    estado_actual = st.session_state.get(clave, 1)
    idx_actual = ESTADOS_ORDEN.index(estado_actual)
    siguiente_idx = (idx_actual + 1) % len(ESTADOS_ORDEN)
    st.session_state[clave] = ESTADOS_ORDEN[siguiente_idx]

# ------------------------------------------------------------------
# Fecha y Hora México (UTC-6)
# ------------------------------------------------------------------
def obtener_tiempo_mexico():
    tz_mexico = timezone(timedelta(hours=-6))
    ahora = datetime.now(tz_mexico)
    
    fecha_sql = ahora.strftime("%Y-%m-%d")
    fecha_pantalla = ahora.strftime("%d/%m/%Y")
    hora_sql = ahora.strftime("%H:%M:%S")
    dia_semana = ahora.isoweekday()
    
    dias_nombre = {1: "Lunes", 2: "Martes", 3: "Miércoles", 4: "Jueves", 5: "Viernes", 6: "Sábado", 7: "Domingo"}
    nombre_dia = dias_nombre.get(dia_semana, "")
    
    return fecha_sql, fecha_pantalla, hora_sql, dia_semana, nombre_dia

# ------------------------------------------------------------------
# Conexión DB
# ------------------------------------------------------------------
drivers_instalados = pyodbc.drivers()
driver_elegido = "SQL Server"

for d in ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "SQL Server Native Client 11.0", "SQL Server"]:
    if d in drivers_instalados:
        driver_elegido = d
        break

try:
    server = st.secrets["db_credentials"]["SERVER"]
    database = st.secrets["db_credentials"]["DATABASE"]
    username = st.secrets["db_credentials"]["UID"]
    password = st.secrets["db_credentials"]["PWD"]
except Exception:
    server = "CBTis139.mssql.somee.com"
    database = "CBTis139"
    username = "TovarLara_SQLLogin_1"
    password = "1hmetvyyiv"

connection_string = (
    f"DRIVER={{{driver_elegido}}};"
    f"SERVER={server};"
    f"DATABASE={database};"
    f"UID={username};"
    f"PWD={password};"
    "TrustServerCertificate=yes;"
)

@st.cache_resource
def obtener_conexion():
    params = urllib.parse.quote_plus(connection_string)
    return create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

def cerrar_y_salir():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state["cerrado_definitivo"] = True

try:
    engine = obtener_conexion()

    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False
        st.session_state["usuario_actual"] = ""
        st.session_state["idmaestro"] = None

    if "registro_exitoso" not in st.session_state:
        st.session_state["registro_exitoso"] = False
        st.session_state["resumen_registro"] = {}

    # ------------------------------------------------------------------
    # 1. LOGIN
    # ------------------------------------------------------------------
    if not st.session_state["autenticado"]:
        st.subheader("🔐 Acceso para Docentes")
        col_acc1, _ = st.columns([1, 2])
        
        with col_acc1:
            password_input = st.text_input("🔑 Contraseña:", type="password", key="input_password")
            
            if st.button("🔓 Entrar", type="primary", use_container_width=True):
                if password_input.strip() == "":
                    st.warning("⚠️ Por favor ingrese su contraseña.")
                else:
                    try:
                        with engine.connect() as conn:
                            query_valida = text("SELECT idmaestro, usuario FROM maestros WHERE password = :pwd")
                            resultado = conn.execute(query_valida, {"pwd": password_input.strip()}).fetchone()

                            if resultado:
                                st.session_state["autenticado"] = True
                                st.session_state["usuario_actual"] = resultado.usuario
                                st.session_state["idmaestro"] = resultado.idmaestro
                                st.session_state["registro_exitoso"] = False
                                st.rerun()
                            else:
                                st.error("❌ Contraseña no válida.")
                    except Exception as err_login:
                        st.error(f"⚠️ Error de base de datos: {err_login}")

        st.stop()

    # ------------------------------------------------------------------
    # CONFIGURACIÓN BARRA LATERAL (OPCIÓN B: SELECTOR DE MODO)
    # ------------------------------------------------------------------
    fecha_sql, fecha_pantalla, hora_sql, dia_semana, nombre_dia = obtener_tiempo_mexico()
    id_docente = str(st.session_state["idmaestro"]).strip()

    with st.sidebar:
        st.write("👤 **Docente activo:**")
        st.info(f"**{st.session_state['usuario_actual']}** (ID: {id_docente})")
        
        st.divider()
        st.write("📌 **Menú de Operación**")
        modo_vista = st.radio(
            "Selecciona una acción:",
            ["📝 Pase de Lista Activo", "📊 Consulta Histórica"],
            index=0
        )
        st.divider()

        st.caption(f"📅 **{nombre_dia} {fecha_pantalla}**")
        st.caption(f"⏰ **Hora:** {hora_sql[:5]} hrs")
        
        if st.button("🔒 Cerrar Sesión", use_container_width=True):
            cerrar_y_salir()
            st.rerun()

    # ==================================================================
    # VISTA 1: PASE DE LISTA ACTIVO
    # ==================================================================
    if modo_vista == "📝 Pase de Lista Activo":
        
        # COMPROBANTE TRAS GUARDAR
        if st.session_state["registro_exitoso"]:
            resumen = st.session_state["resumen_registro"]
            st.success("### ✅ Pase de Lista Finalizado y Guardado Correctamente")
            st.markdown(f"""
            ---
            ### 📑 Comprobante de Registro
            * 📂 **Grupo:** `{resumen['grupo']}`
            * 📚 **Materia:** `{resumen['materia']}`
            * 📅 **Fecha:** `{resumen['fecha_pantalla']}`
            * ⏰ **Hora de firma:** `{resumen['hora_sql'][:5]} hrs`
            * 👤 **Clave Docente:** `{resumen['clave_docente']}`
            * ⚡ **Incidencias registradas (Faltas/Retardos):** `{resumen['total_incidencias']}`
            """)
            st.divider()
            if st.button("🚪 Salir del Sistema", type="primary", use_container_width=True):
                cerrar_y_salir()
                st.rerun()
            st.stop()

        # Consulta de la clase activa en Horario_Grupo
        query_clase_actual = text("""
            SELECT h.idhorario, h.grupo, h.inicio, h.fin, h.idmateria, m.nombre AS materia
            FROM Horario_Grupo h
            LEFT JOIN materia m ON h.idmateria = m.idmateria
            WHERE LTRIM(RTRIM(h.idmaestro)) = :id_m
              AND h.dia_semana = :dia
              AND :hora BETWEEN h.inicio AND h.fin
        """)

        with engine.connect() as conn:
            clase = conn.execute(query_clase_actual, {
                "id_m": id_docente,
                "dia": dia_semana,
                "hora": hora_sql
            }).fetchone()

        if clase:
            id_horario_str = str(clase.idhorario).strip()
            grupo_str = str(clase.grupo).strip()
            
            # Validación Docente + Grupo + Fecha
            query_firma_docente = text("""
                SELECT hora, estatus 
                FROM asistencia_docente 
                WHERE fecha = :fec 
                  AND LTRIM(RTRIM(clave_grupo)) = :grp 
                  AND LTRIM(RTRIM(clave_docente)) = :doc
            """)
            
            with engine.connect() as conn:
                firma = conn.execute(query_firma_docente, {
                    "fec": fecha_sql,
                    "grp": grupo_str,
                    "doc": id_docente
                }).fetchone()

            # CASO A: YA PASÓ LISTA -> MODO CONSULTA
            if firma:
                hora_firma_str = str(firma.hora)[:5]
                st.info(f"### 📋 Clase firmada a las {hora_firma_str} hrs (Modo Consulta)")
                st.markdown(f"🏫 **Grupo:** `{clase.grupo}` | 📚 **Materia:** `{clase.materia if clase.materia else 'Sin asignar'}` | ⏰ `{str(clase.inicio)[:5]} - {str(clase.fin)[:5]} hrs`")
                st.caption("🔒 Los datos de este grupo ya fueron guardados para tu sesión de hoy.")
                st.divider()

                query_reconstruir = text("""
                    SELECT al.idalumno, al.nombre, ISNULL(a.estado, 1) as estado
                    FROM alumno al
                    LEFT JOIN asistencia a ON al.idalumno = a.idalumno AND a.idhorario = :id_h AND a.fecha = :fec
                    WHERE al.grupo = :grp
                    ORDER BY al.nombre
                """)
                
                df_asistencia_reconstruida = pd.read_sql(query_reconstruir, engine, params={
                    "id_h": id_horario_str,
                    "fec": fecha_sql,
                    "grp": clase.grupo
                })

                for idx, row in df_asistencia_reconstruida.iterrows():
                    nombre_al = row["nombre"]
                    estado_val = int(row["estado"])
                    cfg = CONFIG_ESTADOS.get(estado_val, CONFIG_ESTADOS[1])

                    c_nom, c_est = st.columns([3, 2])
                    with c_nom:
                        st.markdown(f'<div class="card-alumno {cfg["clase_css"]}"><span>{nombre_al}</span></div>', unsafe_allow_html=True)
                    with c_est:
                        st.markdown(f'<div style="text-align: right; padding-top: 10px; font-weight: bold; font-size: 1.05rem;">{cfg["texto_badge"]}</div>', unsafe_allow_html=True)

                st.divider()
                if st.button("🚪 Salir del Sistema", type="primary", use_container_width=True):
                    cerrar_y_salir()
                    st.rerun()

            # CASO B: CAPTURA ACTIVA
            else:
                st.success(f"🏫 **Grupo:** `{clase.grupo}` | 📚 **Materia:** `{clase.materia if clase.materia else 'Sin asignar'}` | ⏰ `{str(clase.inicio)[:5]} - {str(clase.fin)[:5]} hrs`")
                
                query_alumnos = text("SELECT idalumno, nombre FROM alumno WHERE grupo = :grp ORDER BY nombre")
                df_alumnos = pd.read_sql(query_alumnos, engine, params={"grp": clase.grupo})

                if not df_alumnos.empty:
                    st.caption("👆 **Toca el botón** de cualquier alumno para cambiar su estado si no asistió.")
                    st.divider()

                    for idx, row in df_alumnos.iterrows():
                        id_al = row["idalumno"]
                        nombre_al = row["nombre"]
                        clave_estado = f"estado_alumno_{id_al}"

                        if clave_estado not in st.session_state:
                            st.session_state[clave_estado] = 1

                        estado_val = st.session_state[clave_estado]
                        cfg = CONFIG_ESTADOS[estado_val]

                        c_nom, c_btn = st.columns([3, 2])
                        with c_nom:
                            st.markdown(f'<div class="card-alumno {cfg["clase_css"]}"><span>{nombre_al}</span></div>', unsafe_allow_html=True)
                        with c_btn:
                            st.button(
                                label=cfg["label"],
                                type=cfg["type"],
                                key=f"btn_al_{id_al}",
                                use_container_width=True,
                                on_click=alternar_estado,
                                args=(id_al,)
                            )

                    st.divider()

                    if st.button("💾 Guardar Pase de Lista", type="primary", use_container_width=True):
                        fecha_sql, fecha_pantalla, hora_sql, dia_semana, nombre_dia = obtener_tiempo_mexico()

                        try:
                            incidencias_guardadas = 0
                            
                            with engine.begin() as conn:
                                query_insert_docente = text("""
                                    INSERT INTO asistencia_docente (clave_docente, clave_grupo, fecha, hora, estatus, idhorario, dia_semana)
                                    VALUES (:clave_docente, :clave_grupo, :fecha, :hora, :estatus, :idhorario, :dia_semana)
                                """)
                                conn.execute(query_insert_docente, {
                                    "clave_docente": id_docente,
                                    "clave_grupo": grupo_str,
                                    "fecha": fecha_sql,
                                    "hora": hora_sql,
                                    "estatus": "Presente",
                                    "idhorario": id_horario_str,
                                    "dia_semana": dia_semana
                                })

                                for idx, row in df_alumnos.iterrows():
                                    id_al = row["idalumno"]
                                    clave_estado = f"estado_alumno_{id_al}"
                                    estado_final = int(st.session_state.get(clave_estado, 1))

                                    if estado_final != 1:
                                        query_insert = text("""
                                            INSERT INTO asistencia (idalumno, fecha, idhorario, hora, estado)
                                            VALUES (:idalumno, :fecha, :idhorario, :hora, :estado)
                                        """)
                                        conn.execute(query_insert, {
                                            "idalumno": id_al,
                                            "fecha": fecha_sql,
                                            "idhorario": id_horario_str,
                                            "hora": hora_sql,
                                            "estado": estado_final
                                        })
                                        incidencias_guardadas += 1

                            st.session_state["resumen_registro"] = {
                                "grupo": clase.grupo,
                                "materia": clase.materia if clase.materia else "Sin asignar",
                                "fecha_pantalla": fecha_pantalla,
                                "hora_sql": hora_sql,
                                "clave_docente": id_docente,
                                "total_incidencias": incidencias_guardadas
                            }
                            st.session_state["registro_exitoso"] = True
                            st.rerun()

                        except Exception as err_guardado:
                            st.error("❌ Ocurrió un error al intentar guardar en la base de datos.")
                            st.error(f"Detalle técnico: {err_guardado}")

                else:
                    st.warning(f"No hay alumnos registrados en el grupo **{clase.grupo}**.")

        else:
            st.warning(f"⚠️ **Sin clase asignada actualmente** ({nombre_dia} a las {hora_sql[:5]} hrs).")
            st.info("No se encontró ningún bloque en `Horario_Grupo` que coincida con el día y hora exactos para tu usuario.")

    # ==================================================================
    # VISTA 2: CONSULTA HISTÓRICA POR RANGO DE FECHAS
    # ==================================================================
    elif modo_vista == "📊 Consulta Histórica":
        st.subheader("🔍 Consulta de Asistencia por Rango de Fechas")
        
        # Obtener los grupos asignados al docente
        query_mis_grupos = text("""
            SELECT DISTINCT LTRIM(RTRIM(grupo)) as grupo 
            FROM Horario_Grupo 
            WHERE LTRIM(RTRIM(idmaestro)) = :id_m
            ORDER BY grupo
        """)
        
        with engine.connect() as conn:
            df_grupos = pd.read_sql(query_mis_grupos, conn, params={"id_m": id_docente})

        if not df_grupos.empty:
            col_grp, col_f1, col_f2 = st.columns([2, 2, 2])
            
            with col_grp:
                grupo_sel = st.selectbox("🏫 Selecciona Grupo:", df_grupos["grupo"].tolist())
            
            with col_f1:
                f_inicio = st.date_input("📅 Desde:", value=date.today() - timedelta(days=15))
            
            with col_f2:
                f_fin = st.date_input("📅 Hasta:", value=date.today())

            if st.button("🔎 Generar Reporte", type="primary", use_container_width=True):
                
                # 1. Contar total de clases impartidas por el docente en el rango
                query_clases_impartidas = text("""
                    SELECT COUNT(*) as total
                    FROM asistencia_docente
                    WHERE LTRIM(RTRIM(clave_docente)) = :doc
                      AND LTRIM(RTRIM(clave_grupo)) = :grp
                      AND fecha BETWEEN :f_i AND :f_f
                """)
                
                with engine.connect() as conn:
                    clases_total = conn.execute(query_clases_impartidas, {
                        "doc": id_docente,
                        "grp": grupo_sel,
                        "f_i": f_inicio.strftime("%Y-%m-%d"),
                        "f_f": f_fin.strftime("%Y-%m-%d")
                    }).scalar()

                if clases_total == 0:
                    st.warning(f"⚠️ No hay registro de clases impartidas por el docente para el grupo **{grupo_sel}** entre {f_inicio.strftime('%d/%m/%Y')} y {f_fin.strftime('%d/%m/%Y')}.")
                else:
                    st.info(f"📌 **Total de clases impartidas en el periodo:** `{clases_total}`")

                    # 2. Consultar catálogo de alumnos y sumar sus incidencias
                    query_reporte = text("""
                        SELECT 
                            al.idalumno AS [ID],
                            al.nombre AS [Nombre del Alumno],
                            ISNULL(SUM(CASE WHEN a.estado = 0 THEN 1 ELSE 0 END), 0) AS [Faltas],
                            ISNULL(SUM(CASE WHEN a.estado = 2 THEN 1 ELSE 0 END), 0) AS [Retardos],
                            ISNULL(SUM(CASE WHEN a.estado = 3 THEN 1 ELSE 0 END), 0) AS [Justificados]
                        FROM alumno al
                        LEFT JOIN asistencia a ON al.idalumno = a.idalumno 
                                              AND a.fecha BETWEEN :f_i AND :f_f
                        WHERE LTRIM(RTRIM(al.grupo)) = :grp
                        GROUP BY al.idalumno, al.nombre
                        ORDER BY al.nombre
                    """)

                    df_reporte = pd.read_sql(query_reporte, engine, params={
                        "grp": grupo_sel,
                        "f_i": f_inicio.strftime("%Y-%m-%d"),
                        "f_f": f_fin.strftime("%Y-%m-%d")
                    })

                    # 3. Calcular Asistencias y Porcentaje
                    df_reporte["Asistencias"] = clases_total - df_reporte["Faltas"]
                    
                    # Evitar valores negativos si hubiese algún desfase
                    df_reporte["Asistencias"] = df_reporte["Asistencias"].apply(lambda x: max(0, x))
                    
                    # Cálculo de % Asistencia
                    df_reporte["% Asistencia"] = ((df_reporte["Asistencias"] / clases_total) * 100).round(1).astype(str) + "%"

                    # Reordenar columnas para la visualización
                    cols_orden = ["ID", "Nombre del Alumno", "Asistencias", "Faltas", "Retardos", "Justificados", "% Asistencia"]
                    df_reporte = df_reporte[cols_orden]

                    # Mostrar tabla estilizada
                    st.dataframe(df_reporte, use_container_width=True, hide_index=True)

                    # Botón para descargar en CSV
                    csv_data = df_reporte.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Descargar Reporte en CSV",
                        data=csv_data,
                        file_name=f"Asistencia_{grupo_sel}_{f_inicio.strftime('%Y%m%d')}_{f_fin.strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
        else:
            st.warning("No tienes grupos asignados en la tabla `Horario_Grupo`.")

except Exception as e:
    st.error("⚠️ Error de conexión.")
    st.error(f"Detalle: {e}")
