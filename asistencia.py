import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import urllib
import pyodbc
from datetime import datetime

st.set_page_config(page_title="Pase de Lista - CBTis 139", layout="wide")
st.title("📋 Control de Asistencia Escolar (CBTis 139)")

# ------------------------------------------------------------------
# 1. Detección automática del controlador ODBC de Windows
# ------------------------------------------------------------------
drivers_instalados = pyodbc.drivers()
driver_elegido = "SQL Server"  # Controlador predeterminado de Windows

# Priorizar el más moderno si está instalado, si no, usa el genérico 'SQL Server'
for d in ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "SQL Server Native Client 11.0", "SQL Server"]:
    if d in drivers_instalados:
        driver_elegido = d
        break

# Cadena de conexión dinámica
connection_string = (
    f"DRIVER={{{driver_elegido}}};"
    "SERVER=CBTis139.mssql.somee.com;"
    "DATABASE=CBTis139;"
    "UID=TovarLara_SQLLogin_1;"
    "PWD=1hmetvyyiv;"
    "TrustServerCertificate=yes;"
)

# Conexión persistente
@st.cache_resource
def obtener_conexion():
    params = urllib.parse.quote_plus(connection_string)
    engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")
    return engine

try:
    engine = obtener_conexion()

    # 2. Asegurar que la tabla 'asistencia' exista en SQL Server
    with engine.begin() as conn:
        conn.execute(text("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'asistencia')
            BEGIN
                CREATE TABLE asistencia (
                    idasistencia INT IDENTITY(1,1) PRIMARY KEY,
                    idalumno INT NOT NULL,
                    fecha DATE NOT NULL,
                    estado VARCHAR(20) NOT NULL,
                    grupo VARCHAR(10) NOT NULL
                )
            END
        """))

    # 3. Controles de Selección
    col1, col2 = st.columns(2)
    
    # Obtener los grupos existentes en la tabla 'alumno'
    df_grupos = pd.read_sql("SELECT DISTINCT grupo FROM alumno WHERE grupo IS NOT NULL ORDER BY grupo", engine)
    lista_grupos = df_grupos["grupo"].tolist() if not df_grupos.empty else ["1A", "1B", "2A"]

    with col1:
        grupo_seleccionado = st.selectbox("📂 Selecciona el Grupo:", lista_grupos)
    with col2:
        fecha_asistencia = st.date_input("📅 Fecha de clase:", datetime.now())

    # 4. Cargar alumnos del grupo seleccionado
    query_alumnos = f"SELECT idalumno, nombre, grupo FROM alumno WHERE grupo = '{grupo_seleccionado}' ORDER BY nombre"
    df_alumnos = pd.read_sql(query_alumnos, engine)

    if not df_alumnos.empty:
        st.subheader(f"Lista de Asistencia - Grupo {grupo_seleccionado}")
        st.info("💡 Por defecto todos están marcados con **Asistencia**. Cambia únicamente a los alumnos con Falta o Retardo.")

        # Añadir columna con opción por defecto 'Asistencia'
        df_alumnos["Estado"] = "Asistencia"

        # Editor de datos optimizado
        df_editado = st.data_editor(
            df_alumnos,
            column_config={
                "idalumno": None,  # Ocultar ID interno
                "nombre": st.column_config.Column("Nombre del Alumno", width="large", disabled=True),
                "grupo": st.column_config.Column("Grupo", width="small", disabled=True),
                "Estado": st.column_config.SelectboxColumn(
                    "Estado de Asistencia",
                    options=["Asistencia", "Falta", "Retardo", "Justificado"],
                    required=True,
                    width="medium"
                )
            },
            use_container_width=True,
            hide_index=True,
            key=f"editor_{grupo_seleccionado}"
        )

        # 5. Guardar Pase de Lista en SQL Server
        if st.button("💾 Guardar Pase de Lista", type="primary", use_container_width=True):
            fecha_str = fecha_asistencia.strftime("%Y-%m-%d")
            
            with engine.begin() as conn:
                for idx, row in df_editado.iterrows():
                    id_al = int(row['idalumno'])
                    est = str(row['Estado'])
                    
                    query_insert = text("""
                        INSERT INTO asistencia (idalumno, fecha, estado, grupo)
                        VALUES (:idalumno, :fecha, :estado, :grupo)
                    """)
                    conn.execute(query_insert, {
                        "idalumno": id_al,
                        "fecha": fecha_str,
                        "estado": est,
                        "grupo": grupo_seleccionado
                    })

            st.balloons()
            st.success(f"¡Pase de lista del grupo **{grupo_seleccionado}** guardado exitosamente en la base de datos `CBTis139`!")

    else:
        st.warning(f"No se encontraron alumnos registrados para el grupo **{grupo_seleccionado}** en la base de datos.")

except Exception as e:
    st.error("⚠️ No se pudo conectar a la base de datos de Somee.com.")
    st.error(f"Detalle del error: {e}")