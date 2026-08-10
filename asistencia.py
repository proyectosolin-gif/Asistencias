import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import urllib
import pyodbc
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="Pase de Lista - CBTis 139", layout="wide")

# ------------------------------------------------------------------
# 0. PANTALLA DE CIERRE DEFINITIVO (Bloquea cualquier interacción posterior)
# ------------------------------------------------------------------
if st.session_state.get("cerrado_definitivo", False):
    st.title("🔒 Control de Asistencia Escolar (CBTis 139)")
    st.success("### ✅ Sesión y Aplicación Cerradas Correctamente")
    st.info("La información fue guardada en el servidor de forma segura. Puedes cerrar esta pestaña de tu navegador.")
    
    # Intento automático por script para cerrar la pestaña si el navegador lo permite
    st.components.v1.html("""
        <script>
            window.close();
            setTimeout(function() {
                window.location.href = "about:blank";
            }, 500);
        </script>
    """, height=0)
    
    st.stop()  # Detiene la aplicación por completo

st.title("📋 Control de Asistencia Escolar (CBTis 139)")

# ------------------------------------------------------------------
# Función auxiliar para obtener Fecha y Hora exacta de México (UTC-6)
# ------------------------------------------------------------------
def obtener_fecha_hora_mexico():
    tz_mexico = timezone(timedelta(hours=-6))
    ahora = datetime.now(tz_mexico)
    return ahora.strftime("%Y-%m-%d"), ahora.strftime("%H:%M:%S"), ahora.strftime("%d/%m/%Y"), ahora.time()

# ------------------------------------------------------------------
# Configuración de Conexión a Base de Datos
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

# Función para cerrar y bloquear definitivamente la sesión
def cerrar_y_salir():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state["cerrado_definitivo"] = True

# Lista de estados y mapa de estilos
ESTADOS_ORDEN = ["Asistencia", "Falta", "Retardo", "Justificado"]

ESTILOS_ESTADO = {
    "Asistencia": {"label": "✅ Asistencia", "type": "secondary"},
    "Falta": {"label": "❌ Falta", "type": "primary"},
    "Retardo": {"label": "⏳ Retardo", "type": "secondary"},
    "Justificado": {"label": "📋 Justificado", "type": "secondary"}
}

def alternar_estado(id_alumno):
    """Avanza al siguiente estado en el ciclo"""
    clave_estado = f"estado_alumno_{id_alumno}"
    estado_actual = st.session_state.get(clave_estado, "Asistencia")
    idx_actual = ESTADOS_ORDEN.index(estado_actual)
    siguiente_idx = (idx_actual + 1) % len(ESTADOS_ORDEN)
    st.session_state[clave_estado] = ESTADOS_ORDEN[siguiente_idx]

try:
    engine = obtener_conexion()

    # ------------------------------------------------------------------
    # CONTROL DE ACCESO
    # ------------------------------------------------------------------
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False
        st.session_state["usuario_actual"] = ""
        st.session_state["id_maestro"] = None

    if "registro_exitoso" not in st.session_state:
        st.session_state["registro_exitoso"] = False
        st.session_state["resumen_registro"] = {}

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
                                st.session_state["registro_exitoso"] = False
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
            cerrar_y_salir()
            st.rerun()

    # ------------------------------------------------------------------
    # VISTA DE CONFIRMACIÓN FINAL Y SALIDA DEFINITIVA
    # ------------------------------------------------------------------
    if st.session_state["registro_exitoso"]:
        resumen = st.session_state["resumen_registro"]
        
        st.success("### ✅ Pase de Lista Finalizado Correctamente")
        st.markdown(f"""
        ---
        ### 📑 Comprobante de Registro Institucional

        * 📂 **Grupo registrado:** `{resumen['grupo']}`
        * 📅 **Fecha y Hora de Captura:** `{resumen['fecha_pantalla']}` a las `{resumen['hora_str']}` hrs
        * 👤 **Docente Responsable:** {resumen['docente']} (ID: {resumen['id_docente']})
        * ⏰ **Módulo Validado:** `{resumen['modulo']}`
        * 📊 **Total de Alumnos Procesados:** `{resumen['total_alumnos']}`

        ---
        *La información ha sido guardada de forma definitiva en el servidor de base de datos del CBTis 139.*
        """)

        st.divider()

        # Botón único que cierra la aplicación por completo
        if st.button("🚪 Salir del Sistema", type="primary", use_container_width=True):
            cerrar_y_salir()
            st.rerun()

        st.stop()

    # ------------------------------------------------------------------
    # Asegurar estructura de tablas
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
    # Selección de Grupo
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
    # Cargar Alumnos
    # ------------------------------------------------------------------
    query_alumnos = f"SELECT idalumno, nombre, grupo FROM alumno WHERE grupo = '{grupo_seleccionado}' ORDER BY nombre"
    df_alumnos = pd.read_sql(query_alumnos, engine)

    if not df_alumnos.empty:
        st.subheader(f"Lista de Asistencia - Grupo {grupo_seleccionado}")
        st.caption("👆 **Toca el botón de cualquier alumno** para alternar: Asistencia ➔ Falta ➔ Retardo ➔ Justificado.")

        st.divider()

        for idx, row in df_alumnos.iterrows():
            id_al = int(row["idalumno"])
            nombre_al = row["nombre"]
            clave_estado = f"estado_alumno_{id_al}"

            if clave_estado not in st.session_state:
                st.session_state[clave_estado] = "Asistencia"

            estado_actual = st.session_state[clave_estado]
            info_btn = ESTILOS_ESTADO[estado_actual]

            c_nom, c_btn = st.columns([3, 2])

            with c_nom:
                st.write(f"**{nombre_al}**")

            with c_btn:
                st.button(
                    label=info_btn["label"],
                    type=info_btn["type"],
                    key=f"btn_al_{id_al}",
                    use_container_width=True,
                    on_click=alternar_estado,
                    args=(id_al,)
                )

        st.divider()

        # ------------------------------------------------------------------
        # Guardar Pase de Lista con Validación Estricta de Horario
        # ------------------------------------------------------------------
        if st.button("💾 Guardar Pase de Lista", type="primary", use_container_width=True):
            fecha_str, hora_str, fecha_pantalla, hora_objeto = obtener_fecha_hora_mexico()
            id_docente = st.session_state.get("id_maestro")

            # 🛑 VALIDACIÓN 1: Horario límite diario (2:30 PM = 14:30:00)
            hora_limite = datetime.strptime("14:30:00", "%H:%M:%S").time()
            if hora_objeto > hora_limite:
                st.error("⚠️ **Registro no permitido:** El horario límite para pasar lista (2:30 PM) ha concluido.")
                st.stop()

            # 🔍 CONSULTA DE RANGOS DE CLASE DESDE 'horamateria'
            with engine.connect() as conn:
                df_horarios = pd.read_sql("SELECT inicio, fin FROM horamateria", conn)

            bloque_actual = None

            for _, h_row in df_horarios.iterrows():
                try:
                    str_ini = str(h_row["inicio"]).strip()
                    str_fin = str(h_row["fin"]).strip()

                    h_inicio = datetime.strptime(str_ini, "%H:%M:%S").time() if len(str_ini) == 8 else datetime.strptime(str_ini, "%H:%M").time()
                    h_fin = datetime.strptime(str_fin, "%H:%M:%S").time() if len(str_fin) == 8 else datetime.strptime(str_fin, "%H:%M").time()
                    
                    if h_inicio <= hora_objeto <= h_fin:
                        bloque_actual = (h_inicio, h_fin)
                        break
                except Exception:
                    continue

            # 🛑 VALIDACIÓN 2: Si no coincide con NINGÚN módulo de clase (ej. Receso de 10:00 a 10:30)
            if not bloque_actual:
                st.error(f"🚫 **Horario no permitido:** La hora actual (**{hora_str[:5]}**) no pertenece a ningún módulo de clase registrado en 'horamateria' (tiempo de receso o fuera de horario).")
                st.stop()

            # 🛑 VALIDACIÓN 3: Evitar duplicados si ya se pasó lista en este módulo
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

            # 💾 GUARDA EL ESTADO ACUMULADO PARA CADA ALUMNO
            registros_guardados = 0
            with engine.begin() as conn:
                for idx, row in df_alumnos.iterrows():
                    id_al = int(row['idalumno'])
                    grp = str(row['grupo'])
                    
                    clave_estado = f"estado_alumno_{id_al}"
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

            # ------------------------------------------------------------------
            # CAMBIO A VISTA LIMPIA DE CONFIRMACIÓN
            # ------------------------------------------------------------------
            st.session_state["resumen_registro"] = {
                "grupo": grupo_seleccionado,
                "fecha_pantalla": fecha_pantalla,
                "hora_str": hora_str,
                "docente": st.session_state['usuario_actual'],
                "id_docente": id_docente,
                "modulo": f"{h_ini_str[:5]} - {h_fin_str[:5]}",
                "total_alumnos": registros_guardados
            }
            st.session_state["registro_exitoso"] = True
            st.rerun()

    else:
        st.warning(f"No se encontraron alumnos registrados para el grupo **{grupo_seleccionado}**.")

except Exception as e:
    st.error("⚠️ No se pudo conectar a la base de datos.")
    st.error(f"Detalle del error: {e}")
