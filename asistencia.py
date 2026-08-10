import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import urllib
import pyodbc
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="Pase de Lista - CBTis 139", layout="wide")
st.title("📋 Control de Asistencia Escolar (CBTis 139)")

# ------------------------------------------------------------------
# Función auxiliar para obtener Fecha y Hora exacta de México (UTC-6)
# ------------------------------------------------------------------
def obtener_fecha_hora_mexico():
    tz_mexico = timezone(timedelta(hours=-6))
    ahora = datetime.now(tz_mexico)
    return ahora.strftime("%Y-%m-%d"), ahora.strftime("%H:%M:%S"), ahora.strftime("%d/%m/%Y"), ahora.time()

# ------------------------------------------------------------------
# 1. Configuración de Conexión a Base de Datos
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
    engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")
    return engine

try:
    engine = obtener_conexion()

    # ------------------------------------------------------------------
    # 2. CONTROL DE ACCESO
    # ------------------------------------------------------------------
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False
        st.session_state["usuario_actual"] = ""
        st.session_state["id_maestro"] = None

    if not st.session_state["autenticado"]:
        st.subheader("🔐 Acceso para Docentes")
        st.info("Ingrese su contraseña para iniciar el pase de lista.")

        col_acc1, _ = st.columns([1, 2])
        with col_acc1:
            password_input = st.text_input("🔑 Contraseña:", type="password", key="input_password")
            
            if st.button("🔓 Entrar", type="primary", use_container_width=True):
                if password_input.strip() == "":
                    st.warning("⚠️ Por favor ingrese su contraseña.")
                else:
                    try:
                        with engine.connect() as conn:
                            query_valida = text("""
                                SELECT id_maestro, usuario 
                                FROM maestros 
                                WHERE password = :pwd
                            """)
                            resultado = conn.execute(query_valida, {
                                "pwd": password_input.strip()
                            }).fetchone()

                            if resultado:
                                st.session_state["autenticado"] = True
                                st.session_state["usuario_actual"] = resultado.usuario
                                st.session_state["id_maestro"] = resultado.id_maestro
                                st.success(f"¡Bienvenido(a), {resultado.usuario}!")
                                st.rerun()
                            else:
                                st.error("❌ Contraseña no válida o no encontrada.")
                    except Exception as err_login:
                        st.error(f"⚠️ Error al consultar la base de datos: {err_login}")

        st.stop()

    # Barra lateral
    with st.sidebar:
        st.write("👤 **Docente activo:**")
        st.info(f"**{st.session_state['usuario_actual']}** (ID: {st.session_state['id_maestro']})")
        if st.button("🔒 Cerrar Sesión", use_container_width=True):
            st.session_state["autenticado"] = False
            st.session_state["usuario_actual"] = ""
            st.session_state["id_maestro"] = None
            st.rerun()

    # ------------------------------------------------------------------
    # 3. Asegurar estructura de tablas
    # ------------------------------------------------------------------
    with engine.begin() as conn:
        conn.execute(text("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'asistencia')
            BEGIN
                CREATE TABLE asistencia (
                    idasistencia INT IDENTITY(1,1) PRIMARY KEY,
                    idalumno INT NOT NULL,
                    fecha DATE NOT NULL,
                    hora TIME NOT NULL,
                    estado VARCHAR(20) NOT NULL,
                    grupo VARCHAR(10) NOT NULL,
                    id_maestro INT NULL
                )
            END
        """))

    # ------------------------------------------------------------------
    # 4. Selección de Grupo y Hora Actual
    # ------------------------------------------------------------------
    df_grupos = pd.read_sql("SELECT DISTINCT grupo FROM alumno WHERE grupo IS NOT NULL ORDER BY grupo", engine)
    lista_grupos = df_grupos["grupo"].tolist() if not df_grupos.empty else ["1A", "1B", "2A"]

    col1, col2 = st.columns([1, 2])
    with col1:
        grupo_seleccionado = st.selectbox("📂 Selecciona el Grupo:", lista_grupos)
    with col2:
        fecha_str, hora_str, fecha_pantalla, hora_objeto = obtener_fecha_hora_mexico()
        st.info(f"📅 **Fecha:** {fecha_pantalla} | ⏰ **Hora actual:** {hora_str}")

    # ------------------------------------------------------------------
    # 5. Cargar alumnos del grupo
    # ------------------------------------------------------------------
    query_alumnos = f"SELECT idalumno, nombre, grupo FROM alumno WHERE grupo = '{grupo_seleccionado}' ORDER BY nombre"
    df_alumnos = pd.read_sql(query_alumnos, engine)

    if not df_alumnos.empty:
        st.subheader(f"Lista de Asistencia - Grupo {grupo_seleccionado}")
        st.caption("💡 Selecciona el estado de cada estudiante antes de guardar.")

        c_head_nom, c_head_btn = st.columns([3, 1.5])
        with c_head_nom:
            st.markdown("**Nombre del Alumno**")
        with c_head_btn:
            st.markdown("**Estado (Toca para cambiar)**")

        st.divider()

        ciclo_estados = ["Asistencia", "Falta", "Retardo", "Justificado"]

        for idx, row in df_alumnos.iterrows():
            id_al = row["idalumno"]
            clave_estado = f"estado_al_{grupo_seleccionado}_{id_al}"
            if clave_estado not in st.session_state:
                st.session_state[clave_estado] = "Asistencia"

        for idx, row in df_alumnos.iterrows():
            id_al = row["idalumno"]
            nombre_al = row["nombre"]
            clave_estado = f"estado_al_{grupo_seleccionado}_{id_al}"
            estado_actual = st.session_state[clave_estado]

            c_nom, c_btn = st.columns([3, 1.5])

            with c_nom:
                st.write(f"**{nombre_al}**")

            with c_btn:
                if estado_actual == "Asistencia":
                    label = "✅ Asistencia"
                elif estado_actual == "Falta":
                    label = "❌ Falta"
                elif estado_actual == "Retardo":
                    label = "⏰ Retardo"
                else:
                    label = "📝 Justificado"

                if st.button(label, key=f"btn_{clave_estado}", use_container_width=True):
                    idx_siguiente = (ciclo_estados.index(estado_actual) + 1) % len(ciclo_estados)
                    st.session_state[clave_estado] = ciclo_estados[idx_siguiente]
                    st.rerun()

        st.divider()

        # ------------------------------------------------------------------
        # 6. Guardar Pase de Lista con Validación de Rango y Duplicados
        # ------------------------------------------------------------------
        if st.button("💾 Guardar Pase de Lista", type="primary", use_container_width=True):
            fecha_str, hora_str, _, hora_objeto = obtener_fecha_hora_mexico()
            id_docente = st.session_state.get("id_maestro")

            # 🛑 VALIDACIÓN 1: Horario límite diario (Antes de las 2:30 PM = 14:30:00)
            hora_limite = datetime.strptime("14:30:00", "%H:%M:%S").time()
            if hora_objeto > hora_limite:
                st.error("⚠️ **Registro no permitido:** El horario límite para pasar lista (2:30 PM) ha concluido.")
                st.stop()

            # 🔍 CONSULTA DE RANGOS DE CLASE DESDE 'horamateria'
            with engine.connect() as conn:
                df_horarios = pd.read_sql("SELECT inicio, fin FROM horamateria", conn)

            bloque_actual = None

            # Identificar en qué rango/bloque cae la hora actual
            for _, h_row in df_horarios.iterrows():
                try:
                    h_inicio = datetime.strptime(str(h_row["inicio"]).strip(), "%H:%M:%S").time() if len(str(h_row["inicio"]).strip()) == 8 else datetime.strptime(str(h_row["inicio"]).strip(), "%H:%M").time()
                    h_fin = datetime.strptime(str(h_row["fin"]).strip(), "%H:%M:%S").time() if len(str(h_row["fin"]).strip()) == 8 else datetime.strptime(str(h_row["fin"]).strip(), "%H:%M").time()
                    
                    if h_inicio <= hora_objeto <= h_fin:
                        bloque_actual = (h_inicio, h_fin)
                        break
                except Exception:
                    continue

            # 🛑 VALIDACIÓN 2: Verificar si ya existe registro en este periodo
            if bloque_actual:
                h_ini_str = bloque_actual[0].strftime("%H:%M:%S")
                h_fin_str = bloque_actual[1].strftime("%H:%M:%S")

                query_existente = text("""
                    SELECT COUNT(*) as total 
                    FROM asistencia 
                    WHERE id_maestro = :id_m 
                      AND grupo = :grp 
                      AND fecha = :fec 
                      AND hora >= :h_ini 
                      AND hora <= :h_fin
                """)

                with engine.connect() as conn:
                    conteo = conn.execute(query_existente, {
                        "id_m": id_docente,
                        "grp": grupo_seleccionado,
                        "fec": fecha_str,
                        "h_ini": h_ini_str,
                        "h_fin": h_fin_str
                    }).fetchone().total

                if conteo > 0:
                    st.warning(f"🚫 **Atención:** Ya has registrado la asistencia para el grupo **{grupo_seleccionado}** en el módulo actual ({h_ini_str[:5]} - {h_fin_str[:5]}). No es posible duplicar el registro.")
                    st.stop()

            # 💾 SI PASA LAS VALIDACIONES, SE PROCEDE A GUARDAR
            registros_guardados = 0
            with engine.begin() as conn:
                for idx, row in df_alumnos.iterrows():
                    id_al = int(row['idalumno'])
                    grp = str(row['grupo'])
                    clave_estado = f"estado_al_{grupo_seleccionado}_{id_al}"
                    estado_final = st.session_state.get(clave_estado, "Asistencia")

                    query_insert = text("""
                        INSERT INTO asistencia (idalumno, fecha, hora, estado, grupo, id_maestro)
                        VALUES (:idalumno, :fecha, :hora, :estado, :grupo, :id_maestro)
                    """)
                    conn.execute(query_insert, {
                        "idalumno": id_al,
                        "fecha": fecha_str,
                        "hora": hora_str,
                        "estado": estado_final,
                        "grupo": grp,
                        "id_maestro": id_docente
                    })
                    registros_guardados += 1

            st.balloons()
            st.success(f"¡Pase de lista del grupo **{grupo_seleccionado}** guardado exitosamente a las **{hora_str}** ({registros_guardados} registros)!")

    else:
        st.warning(f"No se encontraron alumnos registrados para el grupo **{grupo_seleccionado}**.")

except Exception as e:
    st.error("⚠️ No se pudo conectar a la base de datos.")
    st.error(f"Detalle del error: {e}")
