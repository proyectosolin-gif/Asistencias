import urllib
from datetime import date, datetime, timedelta, timezone
import pandas as pd
import pyodbc

from sqlalchemy import create_engine, text
import streamlit as st

# ------------------------------------------------------------------
# 1. Configuración de página
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Control de Asistencia - CBTis 139",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------
# Estilos CSS Limpios con Semaforización
# ------------------------------------------------------------------
st.markdown(
    """
    <style>
    footer {visibility: hidden;}
    
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
    
    /* Estados de la clase actual */
    .est-asistencia { background-color: #DCFCE7; border: 1px solid #86EFAC; color: #14532D; }
    .est-falta { background-color: #FEE2E2; border: 1px solid #FCA5A5; color: #7F1D1D; }
    .est-retardo { background-color: #FFEDD5; border: 1px solid #FDBA74; color: #7C2D12; }
    .est-justificado { background-color: #E0F2FE; border: 1px solid #7DD3FC; color: #0C4A6E; }

    /* Banderas de Semáforo para el Nombre (Histórico de Faltas) */
    .badge-semaforo {
        padding: 4px 10px;
        border-radius: 6px;
        color: #FFFFFF;
        font-weight: bold;
        font-size: 0.85rem;
        margin-left: 8px;
        display: inline-block;
    }
    .sem-coral { background-color: #F87171; }    /* 1 falta previa */
    .sem-naranja { background-color: #FB923C; }  /* 2 faltas previas */
    .sem-rojo { background-color: #EF4444; }     /* 3+ faltas previas */
    </style>
""",
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------
# Configuración y Funciones Auxiliares
# ------------------------------------------------------------------
ESTADOS_ORDEN = [1, 0, 2, 3]
CONFIG_ESTADOS = {
    1: {
        "label": "✅ Asistencia",
        "type": "secondary",
        "clase_css": "est-asistencia",
        "texto_badge": "✅ Asistió",
    },
    0: {
        "label": "❌ Falta",
        "type": "primary",
        "clase_css": "est-falta",
        "texto_badge": "❌ Falta",
    },
    2: {
        "label": "⏳ Retardo",
        "type": "secondary",
        "clase_css": "est-retardo",
        "texto_badge": "⏳ Retardo",
    },
    3: {
        "label": "📋 Justificado",
        "type": "secondary",
        "clase_css": "est-justificado",
        "texto_badge": "📋 Justificado",
    },
}


def alternar_estado(id_alumno):
    clave = f"estado_alumno_{id_alumno}"
    estado_actual = st.session_state.get(clave, 1)
    idx_actual = ESTADOS_ORDEN.index(estado_actual)
    siguiente_idx = (idx_actual + 1) % len(ESTADOS_ORDEN)
    st.session_state[clave] = ESTADOS_ORDEN[siguiente_idx]


def obtener_tiempo_mexico():
    tz_mexico = timezone(timedelta(hours=-6))
    ahora = datetime.now(tz_mexico)
    fecha_sql = ahora.strftime("%Y-%m-%d")
    fecha_pantalla = ahora.strftime("%d/%m/%Y")
    hora_sql = ahora.strftime("%H:%M:%S")
    dia_semana = ahora.isoweekday()
    dias_nombre = {
        1: "Lunes",
        2: "Martes",
        3: "Miércoles",
        4: "Jueves",
        5: "Viernes",
        6: "Sábado",
        7: "Domingo",
    }
    return (
        fecha_sql,
        fecha_pantalla,
        hora_sql,
        dia_semana,
        dias_nombre.get(dia_semana, ""),
    )


@st.cache_resource
def obtener_conexion():
    drivers_instalados = pyodbc.drivers()
    driver_elegido = "SQL Server"
    for d in [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server Native Client 11.0",
        "SQL Server",
    ]:
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
        f"DRIVER={{{driver_elegido}}};SERVER={server};DATABASE={database};"
        f"UID={username};PWD={password};TrustServerCertificate=yes;"
    )
    params = urllib.parse.quote_plus(connection_string)
    return create_engine(f"mssql+pyodbc:///?odbc_connect={params}")


def cerrar_y_salir():
    st.session_state.clear()
    st.session_state["cerrado_definitivo"] = True


# ------------------------------------------------------------------
# Pantalla de Cierre Definitivo
# ------------------------------------------------------------------
if st.session_state.get("cerrado_definitivo", False):
    st.title("🔒 Control de Asistencia Escolar (CBTis 139)")
    st.success("### ✅ Sesión y Aplicación Cerradas Correctamente")
    st.info(
        "La información fue guardada en el servidor de forma segura. Puedes"
        " cerrar esta pestaña."
    )
    st.components.v1.html(
        """
        <script>
            window.close();
            setTimeout(function() { window.location.href = "about:blank"; }, 500);
        </script>
    """,
        height=0,
    )
    st.stop()

# Inicializar Session State
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["usuario_actual"] = ""
    st.session_state["idmaestro"] = None

if "registro_exitoso" not in st.session_state:
    st.session_state["registro_exitoso"] = False
    st.session_state["resumen_registro"] = {}

engine = obtener_conexion()

# ------------------------------------------------------------------
# 1. ACCESO Y AUTENTICACIÓN
# ------------------------------------------------------------------
if not st.session_state["autenticado"]:
    st.title("📋 Control de Asistencia Escolar (CBTis 139)")
    st.subheader("🔐 Acceso para Docentes")

    with st.form("form_login"):
        col_acc1, _ = st.columns([1, 2])
        with col_acc1:
            password_input = st.text_input(
                "🔑 Contraseña:", type="password", key="input_password"
            )
            btn_login = st.form_submit_button(
                "🔓 Entrar", type="primary", use_container_width=True
            )

        if btn_login:
            pwd_clean = password_input.strip()
            if not pwd_clean:
                st.warning("⚠️ Por favor ingrese su contraseña.")
            else:
                try:
                    query_valida = text("""
                        SELECT LTRIM(RTRIM(idmaestro)) AS idmaestro, LTRIM(RTRIM(usuario)) AS usuario 
                        FROM maestros WHERE LTRIM(RTRIM(password)) = :pwd
                    """)
                    with engine.connect() as conn:
                        resultado = conn.execute(query_valida, {"pwd": pwd_clean}).fetchone()
                        if resultado:
                            st.session_state["autenticado"] = True
                            st.session_state["usuario_actual"] = resultado[1]
                            st.session_state["idmaestro"] = resultado[0]
                            st.session_state["registro_exitoso"] = False
                            st.rerun()
                        else:
                            st.error("❌ Contraseña no válida. Verifique sus credenciales.")
                except Exception as err_login:
                    st.error(f"⚠️ Error de conexión: {err_login}")
    st.stop()

# ------------------------------------------------------------------
# 2. BARRA LATERAL (MENÚ PRINCIPAL)
# ------------------------------------------------------------------
fecha_sql, fecha_pantalla, hora_sql, dia_semana, nombre_dia = (
    obtener_tiempo_mexico()
)
id_docente = str(st.session_state["idmaestro"]).strip()

st.sidebar.title("📌 Menú Principal")
st.sidebar.write("👤 **Docente activo:**")
st.sidebar.info(f"**{st.session_state['usuario_actual']}** (ID: {id_docente})")
st.sidebar.divider()

modo_vista = st.sidebar.radio(
    "Selecciona una opción:",
    [
        "📝 Pase de Lista Activo",
        "📅 Mi Horario de Clases",
        "📊 Consulta Histórica",
    ],
    index=0,
)

st.sidebar.divider()
st.sidebar.caption(f"📅 **{nombre_dia} {fecha_pantalla}**")
st.sidebar.caption(f"⏰ **Hora:** {hora_sql[:5]} hrs")

if st.sidebar.button("🔒 Cerrar Sesión", use_container_width=True):
    cerrar_y_salir()
    st.rerun()

# ------------------------------------------------------------------
# 3. VISTAS Y NAVEGACIÓN
# ------------------------------------------------------------------
st.title("📋 Control de Asistencia Escolar (CBTis 139)")

# === VISTA 1: PASE DE LISTA ===
if modo_vista == "📝 Pase de Lista Activo":

    if st.session_state["registro_exitoso"]:
        resumen = st.session_state["resumen_registro"]

        st.success(
            f"✅ **Pase de Lista Guardado exitosamente** ({resumen['hora_sql'][:5]}"
            " hrs)"
        )
        st.markdown(
            f"🏫 **Grupo:** `{resumen['grupo']}` | 📚 **Materia:**"
            f" `{resumen['materia']}` | ⚡ **Incidencias:**"
            f" `{resumen['total_incidencias']}`"
        )
        st.caption(
            "🔒 Los estados han sido guardados en la base de datos. La lista"
            " permanecerá visible en modo lectura durante tu clase."
        )
        st.divider()

        for al in resumen["alumnos_guardados"]:
            cfg = CONFIG_ESTADOS.get(al["estado"], CONFIG_ESTADOS[1])

            badge_html = ""
            if al["faltas_previas"] == 1:
                badge_html = (
                    '<span class="badge-semaforo sem-coral">⚠️ Faltó clase'
                    " anterior</span>"
                )
            elif al["faltas_previas"] == 2:
                badge_html = (
                    '<span class="badge-semaforo sem-naranja">⚠️ Faltó 2 clases'
                    " anteriores</span>"
                )
            elif al["faltas_previas"] >= 3:
                badge_html = (
                    f'<span class="badge-semaforo sem-rojo">🚨 Faltó'
                    f' {al["faltas_previas"]} clases anteriores</span>'
                )

            c_nom, c_est = st.columns([3, 2])
            with c_nom:
                st.markdown(
                    f'<div class="card-alumno {cfg["clase_css"]}"><span>{al["nombre"]}'
                    f" {badge_html}</span></div>",
                    unsafe_allow_html=True,
                )
            with c_est:
                st.markdown(
                    f'<div style="text-align: right; padding-top: 10px; font-weight:'
                    f' bold; font-size: 1.05rem;">{cfg["texto_badge"]}</div>',
                    unsafe_allow_html=True,
                )

        st.divider()
        if st.button(
            "🚪 Salir / Cerrar Sesión", type="primary", use_container_width=True
        ):
            cerrar_y_salir()
            st.rerun()

    else:
        try:
            query_clase_actual = text("""
                SELECT h.idhorario, h.grupo, h.inicio, h.fin, h.idmateria, m.nombre AS materia
                FROM Horario_Grupo h
                LEFT JOIN materia m ON h.idmateria = m.idmateria
                WHERE LTRIM(RTRIM(h.idmaestro)) = :id_m
                  AND h.dia_semana = :dia
                  AND :hora BETWEEN h.inicio AND h.fin
            """)

            with engine.connect() as conn:
                clase = conn.execute(
                    query_clase_actual,
                    {"id_m": id_docente, "dia": dia_semana, "hora": hora_sql},
                ).fetchone()

            if clase:
                id_horario_str = str(clase.idhorario).strip()
                grupo_str = str(clase.grupo).strip()

                # --- CONSULTAR LA ÚLTIMA NOTA REGISTRADA PARA ESTE HORARIO ---
                query_nota_hoy = text("""
                    SELECT TOP 1 CAST(nota AS VARCHAR(MAX)) AS texto_nota, fecha
                    FROM Nota
                    WHERE LTRIM(RTRIM(CAST(idhorario AS VARCHAR(50)))) = :id_h
                    ORDER BY fecha DESC
                """)
                with engine.connect() as conn:
                    nota_hoy = conn.execute(query_nota_hoy, {
                        "id_h": id_horario_str
                    }).fetchone()

                query_firma_docente = text("""
                    SELECT hora, estatus 
                    FROM asistencia_docente 
                    WHERE fecha = :fec 
                      AND LTRIM(RTRIM(clave_grupo)) = :grp 
                      AND LTRIM(RTRIM(clave_docente)) = :doc
                """)

                with engine.connect() as conn:
                    firma = conn.execute(
                        query_firma_docente,
                        {"fec": fecha_sql, "grp": grupo_str, "doc": id_docente},
                    ).fetchone()

                if firma:
                    hora_firma_str = str(firma.hora)[:5]
                    st.info(
                        f"### 📋 Clase firmada a las {hora_firma_str} hrs (Modo Consulta)"
                    )
                    st.markdown(
                        f"🏫 **Grupo:** `{clase.grupo}` | 📚 **Materia:**"
                        f" `{clase.materia if clase.materia else 'Sin asignar'}` | ⏰"
                        f" `{str(clase.inicio)[:5]} - {str(clase.fin)[:5]} hrs`"
                    )

                    # Mostrar última nota registrada
                    if nota_hoy and nota_hoy.texto_nota:
                        f_nota = nota_hoy.fecha.strftime("%d/%m/%Y") if hasattr(nota_hoy.fecha, 'strftime') else str(nota_hoy.fecha)
                        st.warning(f"📌 **Última nota ({f_nota}):** {nota_hoy.texto_nota}")

                    st.caption(
                        "🔒 Los datos de este grupo ya fueron guardados para tu sesión de"
                        " hoy."
                    )
                    st.divider()

                    query_reconstruir = text("""
                        SELECT al.idalumno, al.nombre, ISNULL(a.estado, 1) as estado
                        FROM alumno al
                        LEFT JOIN asistencia a ON al.idalumno = a.idalumno AND a.idhorario = :id_h AND a.fecha = :fec
                        WHERE LTRIM(RTRIM(al.grupo)) = :grp
                        ORDER BY al.nombre
                    """)

                    df_asistencia = pd.read_sql(
                        query_reconstruir,
                        engine,
                        params={
                            "id_h": id_horario_str,
                            "fec": fecha_sql,
                            "grp": clase.grupo,
                        },
                    )

                    for idx, row in df_asistencia.iterrows():
                        cfg = CONFIG_ESTADOS.get(int(row["estado"]), CONFIG_ESTADOS[1])
                        c_nom, c_est = st.columns([3, 2])
                        with c_nom:
                            st.markdown(
                                f'<div class="card-alumno {cfg["clase_css"]}"><span>{row["nombre"]}</span></div>',
                                unsafe_allow_html=True,
                            )
                        with c_est:
                            st.markdown(
                                f'<div style="text-align: right; padding-top: 10px; font-weight:'
                                f' bold; font-size: 1.05rem;">{cfg["texto_badge"]}</div>',
                                unsafe_allow_html=True,
                            )

                    st.divider()
                    if st.button(
                        "🚪 Salir del Sistema", type="primary", use_container_width=True
                    ):
                        cerrar_y_salir()
                        st.rerun()

                else:
                    st.success(
                        f"🏫 **Grupo:** `{clase.grupo}` | 📚 **Materia:**"
                        f" `{clase.materia if clase.materia else 'Sin asignar'}` | ⏰"
                        f" `{str(clase.inicio)[:5]} - {str(clase.fin)[:5]} hrs`"
                    )

                    # Mostrar última nota registrada prominente
                    if nota_hoy and nota_hoy.texto_nota:
                        f_nota = nota_hoy.fecha.strftime("%d/%m/%Y") if hasattr(nota_hoy.fecha, 'strftime') else str(nota_hoy.fecha)
                        st.warning(f"📌 **Última nota registrada ({f_nota}):**\n\n_{nota_hoy.texto_nota}_")

                    query_alumnos_semaforo = text("""
                        WITH AsistenciasOrdenadas AS (
                            SELECT 
                                a.idalumno,
                                a.estado,
                                ROW_NUMBER() OVER (PARTITION BY a.idalumno ORDER BY a.fecha DESC, a.hora DESC) AS rn
                            FROM asistencia a
                            INNER JOIN alumno al ON a.idalumno = al.idalumno
                            WHERE LTRIM(RTRIM(al.grupo)) = :grp 
                              AND a.idhorario = :id_h
                              AND a.fecha < :fec
                        ),
                        FaltasConsecutivas AS (
                            SELECT 
                                idalumno,
                                COUNT(*) as total_faltas
                            FROM AsistenciasOrdenadas
                            WHERE rn <= 5
                            GROUP BY idalumno
                            HAVING MIN(CASE WHEN rn <= 3 THEN estado ELSE 1 END) = 0
                        )
                        SELECT 
                            al.idalumno, 
                            al.nombre,
                            ISNULL((
                                SELECT 
                                    CASE 
                                        WHEN a1.estado = 0 AND ISNULL(a2.estado, 1) <> 0 THEN 1
                                        WHEN a1.estado = 0 AND a2.estado = 0 AND ISNULL(a3.estado, 1) <> 0 THEN 2
                                        WHEN a1.estado = 0 AND a2.estado = 0 AND a3.estado = 0 THEN 3
                                        ELSE 0 
                                    END
                                FROM AsistenciasOrdenadas a1
                                LEFT JOIN AsistenciasOrdenadas a2 ON a1.idalumno = a2.idalumno AND a2.rn = 2
                                LEFT JOIN AsistenciasOrdenadas a3 ON a1.idalumno = a3.idalumno AND a3.rn = 3
                                WHERE a1.idalumno = al.idalumno AND a1.rn = 1
                            ), 0) AS faltas_previas
                        FROM alumno al
                        WHERE LTRIM(RTRIM(al.grupo)) = :grp
                        ORDER BY al.nombre
                    """)

                    df_alumnos = pd.read_sql(
                        query_alumnos_semaforo,
                        engine,
                        params={"grp": clase.grupo, "fec": fecha_sql, "id_h": id_horario_str},
                    )

                    if not df_alumnos.empty:
                        st.caption(
                            "👆 **Toca el botón** de cualquier alumno para cambiar su"
                            " estado si no asistió. Observa la insignia de faltas previas."
                        )
                        st.divider()

                        for idx, row in df_alumnos.iterrows():
                            id_al = row["idalumno"]
                            faltas_previas = int(row["faltas_previas"])

                            clave_estado = f"estado_alumno_{id_al}"
                            if clave_estado not in st.session_state:
                                st.session_state[clave_estado] = 1

                            cfg = CONFIG_ESTADOS[st.session_state[clave_estado]]

                            badge_html = ""
                            if faltas_previas == 1:
                                badge_html = (
                                    '<span class="badge-semaforo sem-coral">⚠️ Faltó clase'
                                    " anterior</span>"
                                )
                            elif faltas_previas == 2:
                                badge_html = (
                                    '<span class="badge-semaforo sem-naranja">⚠️ Faltó 2 clases'
                                    " anteriores</span>"
                                )
                            elif faltas_previas >= 3:
                                badge_html = (
                                    f'<span class="badge-semaforo sem-rojo">🚨 Faltó'
                                    f" {faltas_previas} clases anteriores</span>"
                                )

                            c_nom, c_btn = st.columns([3, 2])
                            with c_nom:
                                st.markdown(
                                    f'<div class="card-alumno {cfg["clase_css"]}"><span>{row["nombre"]}'
                                    f" {badge_html}</span></div>",
                                    unsafe_allow_html=True,
                                )
                            with c_btn:
                                st.button(
                                    label=cfg["label"],
                                    type=cfg["type"],
                                    key=f"btn_al_{id_al}",
                                    use_container_width=True,
                                    on_click=alternar_estado,
                                    args=(id_al,),
                                )

                        st.divider()

                        if st.button(
                            "💾 Guardar Pase de Lista",
                            type="primary",
                            use_container_width=True,
                        ):
                            try:
                                incidencias = 0
                                alumnos_registro = []

                                with engine.begin() as conn:
                                    conn.execute(
                                        text("""
                                            INSERT INTO asistencia_docente (clave_docente, clave_grupo, fecha, hora, estatus, idhorario, dia_semana)
                                            VALUES (:clave_docente, :clave_grupo, :fecha, :hora, :estatus, :idhorario, :dia_semana)
                                        """),
                                        {
                                            "clave_docente": id_docente,
                                            "clave_grupo": grupo_str,
                                            "fecha": fecha_sql,
                                            "hora": hora_sql,
                                            "estatus": "Presente",
                                            "idhorario": id_horario_str,
                                            "dia_semana": dia_semana,
                                        },
                                    )

                                    for idx, row in df_alumnos.iterrows():
                                        id_al = row["idalumno"]
                                        est_fin = int(
                                            st.session_state.get(f"estado_alumno_{id_al}", 1)
                                        )

                                        alumnos_registro.append({
                                            "nombre": row["nombre"],
                                            "estado": est_fin,
                                            "faltas_previas": int(row["faltas_previas"]),
                                        })

                                        if est_fin != 1:
                                            conn.execute(
                                                text("""
                                                    INSERT INTO asistencia (idalumno, fecha, idhorario, hora, estado)
                                                    VALUES (:idalumno, :fecha, :idhorario, :hora, :estado)
                                                """),
                                                {
                                                    "idalumno": id_al,
                                                    "fecha": fecha_sql,
                                                    "idhorario": id_horario_str,
                                                    "hora": hora_sql,
                                                    "estado": est_fin,
                                                },
                                            )
                                            incidencias += 1

                                st.session_state["resumen_registro"] = {
                                    "grupo": clase.grupo,
                                    "materia": (
                                        clase.materia if clase.materia else "Sin asignar"
                                    ),
                                    "fecha_pantalla": fecha_pantalla,
                                    "hora_sql": hora_sql,
                                    "clave_docente": id_docente,
                                    "total_incidencias": incidencias,
                                    "alumnos_guardados": alumnos_registro,
                                }
                                st.session_state["registro_exitoso"] = True
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error al guardar: {e}")

            else:
                st.info(
                    f"⌛ **Sin clase asignada en este momento** ({nombre_dia} -"
                    f" {hora_sql[:5]} hrs)."
                )
                st.markdown("""
                    No hay ningún grupo programado para tu usuario en esta hora según el horario escolar.
                    
                    👈 **Utiliza el menú de la izquierda para:**
                    * **📅 Mi Horario de Clases:** Ver tu carga horaria semanal personal y registrar/consultar notas por bloque de horario.
                    * **📊 Consulta Histórica:** Generar y descargar reportes de asistencia.
                    """)

        except Exception as err_m1:
            st.error(f"⚠️ Error al consultar la base de datos: {err_m1}")

# === VISTA 2: MI HORARIO Y NOTAS ===
elif modo_vista == "📅 Mi Horario de Clases":
    st.subheader("📅 Mi Horario Semanal de Clases")
    
    try:
        ahora = datetime.now()
        hoy = ahora.date()
        dia_semana_hoy = hoy.isoweekday()  # 1 = Lunes, ..., 7 = Domingo
        hora_actual_str = ahora.strftime("%H:%M:%S")

        inicio_semana = hoy - timedelta(days=hoy.weekday())  # Lunes de esta semana
        fin_semana = inicio_semana + timedelta(days=6)       # Domingo de esta semana

        query_horario = text("""
            SELECT 
                h.idhorario,
                h.dia_semana,
                h.inicio,
                h.fin,
                LTRIM(RTRIM(h.grupo)) AS grupo,
                ISNULL(m.nombre, 'Sin asignar') AS materia,
                ISNULL(CAST(h.aula AS VARCHAR(50)), 'Sin asignar') AS aula,
                COUNT(n.idnota) AS notas_semana_actual
            FROM Horario_Grupo h
            LEFT JOIN materia m ON h.idmateria = m.idmateria
            LEFT JOIN Nota n ON LTRIM(RTRIM(CAST(h.idhorario AS VARCHAR(50)))) = LTRIM(RTRIM(CAST(n.idhorario AS VARCHAR(50))))
                            AND n.fecha BETWEEN :f_inicio AND :f_fin
            WHERE LTRIM(RTRIM(CAST(h.idmaestro AS VARCHAR(50)))) = :id_m
            GROUP BY h.idhorario, h.dia_semana, h.inicio, h.fin, h.grupo, m.nombre, h.aula
            ORDER BY h.dia_semana, h.inicio
        """)

        with engine.connect() as conn:
            df_horario = pd.read_sql(
                query_horario, 
                conn, 
                params={
                    "id_m": str(id_docente).strip(),
                    "f_inicio": inicio_semana.strftime("%Y-%m-%d"),
                    "f_fin": fin_semana.strftime("%Y-%m-%d")
                }
            )

        if not df_horario.empty:
            dias_map = {
                1: "Lunes", 2: "Martes", 3: "Miércoles",
                4: "Jueves", 5: "Viernes", 6: "Sábado", 7: "Domingo"
            }
            
            df_horario["Día"] = df_horario["dia_semana"].map(dias_map)
            df_horario["Horario"] = (
                df_horario["inicio"].astype(str).str[:5]
                + " - "
                + df_horario["fin"].astype(str).str[:5]
            )

            # --- EVALUACIÓN EXACTA DE ESTADO POR DÍA Y HORA ---
            def determinar_estado_tiempo(row):
                dia_clase = int(row["dia_semana"])
                hora_inicio = str(row["inicio"])
                hora_fin = str(row["fin"])

                if dia_clase < dia_semana_hoy:
                    return "pasada"
                elif dia_clase == dia_semana_hoy:
                    if hora_actual_str >= hora_fin:
                        return "pasada"
                    elif hora_inicio <= hora_actual_str < hora_fin:
                        return "en_curso"
                    else:
                        return "futura"
                else:
                    return "futura"

            df_horario["estado_tiempo"] = df_horario.apply(determinar_estado_tiempo, axis=1)

            df_horario["Estatus"] = df_horario.apply(
                lambda r: "📌 Nota guardada" if r["notas_semana_actual"] > 0 
                else ("⚡ En Curso" if r["estado_tiempo"] == "en_curso"
                      else ("✔️ Concluida" if r["estado_tiempo"] == "pasada" else "⏳ Pendiente")),
                axis=1
            )

            # --- REORDENAMIENTO DE COLUMNAS A MOSTRAR ---
            df_mostrar = df_horario[[
                "Estatus", 
                "Día", 
                "grupo", 
                "Horario", 
                "materia", 
                "aula", 
                "idhorario"
            ]].rename(
                columns={
                    "grupo": "Grupo",
                    "materia": "Materia", 
                    "aula": "Aula",
                    "idhorario": "ID Horario"
                }
            )

            # --- APLICACIÓN RIGUROSA DE COLORES DE FONDO A TODA LA TABLA ---
            def estilar_tabla_matriz(df):
                styles = pd.DataFrame('', index=df.index, columns=df.columns)
                
                for idx in df.index:
                    est_tiempo = df_horario.loc[idx, "estado_tiempo"]
                    tiene_nota = df_horario.loc[idx, "notas_semana_actual"] > 0
                    
                    # 1. Día y Hora Vencida: Azul bajito (#E0F2FE)
                    if est_tiempo == "pasada":
                        estilo_base = "background-color: #E0F2FE; color: #0369A1;"
                    # 2. Hora Actual (En Curso): Azul fuerte (#0284C7) con letras blancas
                    elif est_tiempo == "en_curso":
                        estilo_base = "background-color: #0284C7; color: #FFFFFF; font-weight: bold;"
                    # 3. Hora/Día Futuro: Fondo Blanco (#FFFFFF)
                    else:
                        estilo_base = "background-color: #FFFFFF; color: #0F172A;"
                        
                    styles.loc[idx, :] = estilo_base
                    
                    if tiene_nota:
                        styles.loc[idx, "Estatus"] = "background-color: #FEF08A; color: #854D0E; font-weight: bold;"

                return styles

            df_styled = df_mostrar.style.apply(estilar_tabla_matriz, axis=None)

            st.caption("👆 **Toca o selecciona una fila** para consultar el historial de observaciones o registrar una nueva nota.")

            evento_seleccion = st.dataframe(
                df_styled,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row"
            )

            filas_seleccionadas = evento_seleccion.selection.rows

            # --- DETALLE Y ADMINISTRACIÓN DE LA CLASE SELECCIONADA ---
            if filas_seleccionadas:
                idx_sel = filas_seleccionadas[0]
                datos_clase = df_horario.iloc[idx_sel]
                id_horario_str = str(datos_clase["idhorario"]).strip()

                st.divider()
                st.subheader(f"📌 Administrar Notas: {datos_clase['materia']} ({datos_clase['grupo']})")
                st.caption(f"⏰ **Horario habitual:** {datos_clase['Día']} de {datos_clase['Horario']} | **Aula:** {datos_clase['aula']}")

                col_cap, col_hist = st.columns([1, 1])

                # COLUMNA IZQUIERDA: Registro / Edición de Nota por Fecha
                with col_cap:
                    st.markdown("### ✍️ Registrar / Actualizar Nota")
                    fecha_nota = st.date_input("📅 Fecha de la clase:", value=date.today())

                    query_nota_fecha = text("""
                        SELECT idnota, CAST(nota AS VARCHAR(MAX)) AS texto_nota
                        FROM Nota
                        WHERE LTRIM(RTRIM(CAST(idhorario AS VARCHAR(50)))) = :id_h
                          AND fecha = :fecha
                    """)
                    with engine.connect() as conn:
                        nota_fecha = conn.execute(query_nota_fecha, {
                            "id_h": id_horario_str,
                            "fecha": fecha_nota.strftime("%Y-%m-%d")
                        }).fetchone()

                    texto_existente = nota_fecha.texto_nota if nota_fecha else ""
                    
                    texto_nota = st.text_area("Observación / Bitácora del día:", value=texto_existente, height=130)

                    if st.button("💾 Guardar Nota para esta Fecha", type="primary", use_container_width=True):
                        if texto_nota.strip():
                            try:
                                with engine.begin() as conn:
                                    if nota_fecha:
                                        conn.execute(text("UPDATE Nota SET nota = :n WHERE idnota = :id"), {
                                            "n": texto_nota.strip(),
                                            "id": nota_fecha.idnota
                                        })
                                    else:
                                        conn.execute(text("INSERT INTO Nota (fecha, idhorario, nota) VALUES (:f, :h, :n)"), {
                                            "f": fecha_nota.strftime("%Y-%m-%d"),
                                            "h": id_horario_str,
                                            "n": texto_nota.strip()
                                        })
                                st.success("✅ Nota guardada correctamente.")
                                st.rerun()
                            except Exception as e_sav:
                                st.error(f"❌ Error al guardar en la base de datos: {e_sav}")
                        else:
                            st.warning("⚠️ Ingresa una observación antes de guardar.")

                # COLUMNA DERECHA: Histórico Completo de Notas
                with col_hist:
                    st.markdown("### 📚 Histórico de Notas (Todas las fechas)")
                    
                    query_historico = text("""
                        SELECT 
                            CONVERT(VARCHAR(10), fecha, 103) AS fecha_formato,
                            CAST(nota AS VARCHAR(MAX)) AS texto_nota
                        FROM Nota
                        WHERE LTRIM(RTRIM(CAST(idhorario AS VARCHAR(50)))) = :id_h
                        ORDER BY fecha DESC
                    """)
                    
                    with engine.connect() as conn:
                        df_historico = pd.read_sql(query_historico, conn, params={"id_h": id_horario_str})

                    if not df_historico.empty:
                        for _, r_hist in df_historico.iterrows():
                            with st.expander(f"📅 Fecha: {r_hist['fecha_formato']}"):
                                st.write(r_hist["texto_nota"])
                    else:
                        st.info("ℹ️ Este bloque de horario aún no cuenta con notas registradas en el histórico.")

        else:
            st.warning("⚠️ No se encontraron clases asignadas para el docente seleccionado.")

    except Exception as err_m2:
        st.error(f"⚠️ Se produjo un error al consultar el horario: {err_m2}")

# === VISTA 3: CONSULTA HISTÓRICA ===
elif modo_vista == "📊 Consulta Histórica":
    st.subheader("🔍 Consulta de Asistencia por Rango de Fechas")
    try:
        query_grupos = text("""
            SELECT DISTINCT LTRIM(RTRIM(grupo)) as grupo 
            FROM Horario_Grupo 
            WHERE LTRIM(RTRIM(idmaestro)) = :id_m
            ORDER BY grupo
        """)

        with engine.connect() as conn:
            df_grupos = pd.read_sql(query_grupos, conn, params={"id_m": id_docente})

        if not df_grupos.empty:
            col_grp, col_f1, col_f2 = st.columns([2, 2, 2])
            with col_grp:
                grupo_sel = st.selectbox(
                    "🏫 Selecciona Grupo:", df_grupos["grupo"].tolist()
                )
            with col_f1:
                f_inicio = st.date_input(
                    "📅 Desde:", value=date.today() - timedelta(days=15)
                )
            with col_f2:
                f_fin = st.date_input("📅 Hasta:", value=date.today())

            if st.button(
                "🔎 Generar Reporte", type="primary", use_container_width=True
            ):
                query_total_clases = text("""
                    SELECT COUNT(*) as total
                    FROM asistencia_docente
                    WHERE LTRIM(RTRIM(clave_docente)) = :doc
                      AND LTRIM(RTRIM(clave_grupo)) = :grp
                      AND fecha BETWEEN :f_i AND :f_f
                """)

                with engine.connect() as conn:
                    clases_total = conn.execute(
                        query_total_clases,
                        {
                            "doc": id_docente,
                            "grp": grupo_sel,
                            "f_i": f_inicio.strftime("%Y-%m-%d"),
                            "f_f": f_fin.strftime("%Y-%m-%d"),
                        },
                    ).scalar()

                if clases_total == 0:
                    st.warning(
                        f"⚠️ No hay registro de clases impartidas para el grupo"
                        f" **{grupo_sel}** en ese periodo."
                    )
                else:
                    st.info(
                        f"📌 **Total de clases impartidas en el periodo:** `{clases_total}`"
                    )
                    query_rep = text("""
                        SELECT 
                            al.idalumno AS [ID],
                            al.nombre AS [Nombre del Alumno],
                            ISNULL(SUM(CASE WHEN a.estado = 0 THEN 1 ELSE 0 END), 0) AS [Faltas],
                            ISNULL(SUM(CASE WHEN a.estado = 2 THEN 1 ELSE 0 END), 0) AS [Retardos],
                            ISNULL(SUM(CASE WHEN a.estado = 3 THEN 1 ELSE 0 END), 0) AS [Justificados]
                        FROM alumno al
                        LEFT JOIN asistencia a ON al.idalumno = a.idalumno AND a.fecha BETWEEN :f_i AND :f_f
                        WHERE LTRIM(RTRIM(al.grupo)) = :grp
                        GROUP BY al.idalumno, al.nombre
                        ORDER BY al.nombre
                    """)

                    df_rep = pd.read_sql(
                        query_rep,
                        engine,
                        params={
                            "grp": grupo_sel,
                            "f_i": f_inicio.strftime("%Y-%m-%d"),
                            "f_f": f_fin.strftime("%Y-%m-%d"),
                        },
                    )
                    st.dataframe(df_rep, use_container_width=True, hide_index=True)
        else:
            st.warning("⚠️ No se encontraron grupos asociados a tu usuario.")
    except Exception as err_m3:
        st.error(f"⚠️ Error al generar el reporte: {err_m3}")
