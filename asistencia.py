import urllib
from datetime import date, datetime, timedelta, timezone
import pandas as pd
import pyodbc

from sqlalchemy import create_engine, text
import streamlit as st

# 1. Configuración de página con Sidebar forzado a estar expandido
st.set_page_config(
    page_title="Control de Asistencia - CBTis 139",
    layout="wide",
    initial_sidebar_state="expanded",  # Forzar despliegue del menú lateral
)

# ------------------------------------------------------------------
# Estilos CSS Limpios (Sin bloquear el header del sidebar)
# ------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Ocultar pie de página por defecto pero conservar el header funcional */
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
    .est-asistencia { background-color: #DCFCE7; border: 1px solid #86EFAC; color: #14532D; }
    .est-falta { background-color: #FEE2E2; border: 1px solid #FCA5A5; color: #7F1D1D; }
    .est-retardo { background-color: #FFEDD5; border: 1px solid #FDBA74; color: #7C2D12; }
    .est-justificado { background-color: #E0F2FE; border: 1px solid #7DD3FC; color: #0C4A6E; }
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
# 2. BARRA LATERAL (SIEMPRE ACTIVA TRAS LOGUEARSE)
# ------------------------------------------------------------------
fecha_sql, fecha_pantalla, hora_sql, dia_semana, nombre_dia = (
    obtener_tiempo_mexico()
)
id_docente = str(st.session_state["idmaestro"]).strip()

# Renderizado explícito de la barra lateral
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
    st.success("### ✅ Pase de Lista Finalizado y Guardado")
    st.markdown(f"""
        ---
        ### 📑 Comprobante de Registro
        * 📂 **Grupo:** `{resumen['grupo']}`
        * 📚 **Materia:** `{resumen['materia']}`
        * 📅 **Fecha:** `{resumen['fecha_pantalla']}`
        * ⏰ **Hora de firma:** `{resumen['hora_sql'][:5]} hrs`
        * 👤 **Clave Docente:** `{resumen['clave_docente']}`
        * ⚡ **Incidencias registradas:** `{resumen['total_incidencias']}`
        """)
    st.divider()
    if st.button("🚪 Salir del Sistema", type="primary", use_container_width=True):
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
                  '<div style="text-align: right; padding-top: 10px; font-weight:'
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

          query_alumnos = text(
              "SELECT idalumno, nombre FROM alumno WHERE LTRIM(RTRIM(grupo)) ="
              " :grp ORDER BY nombre"
          )
          df_alumnos = pd.read_sql(
              query_alumnos, engine, params={"grp": clase.grupo}
          )

          if not df_alumnos.empty:
            st.caption(
                "👆 **Toca el botón** de cualquier alumno para cambiar su"
                " estado si no asistió."
            )
            st.divider()

            for idx, row in df_alumnos.iterrows():
              id_al = row["idalumno"]
              clave_estado = f"estado_alumno_{id_al}"
              if clave_estado not in st.session_state:
                st.session_state[clave_estado] = 1

              cfg = CONFIG_ESTADOS[st.session_state[clave_estado]]
              c_nom, c_btn = st.columns([3, 2])
              with c_nom:
                st.markdown(
                    f'<div class="card-alumno {cfg["clase_css"]}"><span>{row["nombre"]}</span></div>',
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
                }
                st.session_state["registro_exitoso"] = True
                st.rerun()
              except Exception as e:
                st.error(f"❌ Error al guardar: {e}")

      else:
        # AVISO DE SIN CLASE ACTIVA
        st.info(
            f"⌛ **Sin clase asignada en este momento** ({nombre_dia} -"
            f" {hora_sql[:5]} hrs)."
        )
        st.markdown("""
                No hay ningún grupo programado para tu usuario en esta hora según el horario escolar.
                
                👈 **Utiliza el menú de la izquierda para:**
                * **📅 Mi Horario de Clases:** Ver tu carga horaria semanal completa.
                * **📊 Consulta Histórica:** Generar y descargar reportes de asistencia.
                """)

    except Exception as err_m1:
      st.error(f"⚠️ Error al consultar la base de datos: {err_m1}")

# === VISTA 2: MI HORARIO ===
elif modo_vista == "📅 Mi Horario de Clases":
  st.subheader("📅 Mi Horario Semanal de Clases")
  try:
    query_horario = text("""
            SELECT 
                h.dia_semana,
                h.inicio,
                h.fin,
                LTRIM(RTRIM(h.grupo)) AS grupo,
                ISNULL(m.nombre, 'Sin asignar') AS materia
            FROM Horario_Grupo h
            LEFT JOIN materia m ON h.idmateria = m.idmateria
            WHERE LTRIM(RTRIM(h.idmaestro)) = :id_m
            ORDER BY h.dia_semana, h.inicio
        """)

    with engine.connect() as conn:
      df_horario = pd.read_sql(query_horario, conn, params={"id_m": id_docente})

    if not df_horario.empty:
      dias_map = {
          1: "Lunes",
          2: "Martes",
          3: "Miércoles",
          4: "Jueves",
          5: "Viernes",
          6: "Sábado",
          7: "Domingo",
      }
      df_horario["Día"] = df_horario["dia_semana"].map(dias_map)
      df_horario["Horario"] = (
          df_horario["inicio"].astype(str).str[:5]
          + " - "
          + df_horario["fin"].astype(str).str[:5]
      )
      df_mostrar = df_horario[["Día", "Horario", "grupo", "materia"]].rename(
          columns={"grupo": "Grupo", "materia": "Materia"}
      )

      st.info(f"📊 **Bloques de clase asignados:** `{len(df_mostrar)}`")
      st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
    else:
      st.warning(
          "⚠️ No tienes bloques de clase asignados en la tabla `Horario_Grupo`."
      )
  except Exception as err_m2:
    st.error(f"⚠️ Error al consultar horario: {err_m2}")

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

          df_rep["Asistencias"] = (clases_total - df_rep["Faltas"]).clip(lower=0)
          df_rep["% Asistencia"] = (
              ((df_rep["Asistencias"] / clases_total) * 100).round(1).astype(str)
              + "%"
          )

          cols = [
              "ID",
              "Nombre del Alumno",
              "Asistencias",
              "Faltas",
              "Retardos",
              "Justificados",
              "% Asistencia",
          ]
          st.dataframe(df_rep[cols], use_container_width=True, hide_index=True)

          csv_data = df_rep[cols].to_csv(index=False).encode("utf-8")
          st.download_button(
              label="📥 Descargar Reporte en CSV",
              data=csv_data,
              file_name=(
                  f"Asistencia_{grupo_sel}_{f_inicio.strftime('%Y%m%d')}_{f_fin.strftime('%Y%m%d')}.csv"
              ),
              mime="text/csv",
              use_container_width=True,
          )
    else:
      st.warning("No tienes grupos asignados en `Horario_Grupo`.")
  except Exception as err_m3:
    st.error(f"⚠️ Error al consultar el historial: {err_m3}")
