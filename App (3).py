import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import plotly.express as px
import datetime
import calendar
from io import BytesIO
from fpdf import FPDF

st.set_page_config(page_title="Dulce Atardecer — Panel", page_icon="🏥", layout="wide")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

NAVY = "#2B2825"   # carbón suave, para texto y títulos (antes marrón fuerte)
TEAL = "#C9A38C"   # blush/terracota suave, acento principal (antes terracota fuerte)
GREEN = "#A9AFA0"  # salvia apagado, acento secundario (antes dorado)
RUST = "#D8C3A5"   # arena suave (antes ladrillo)
CREAM = "#FAF7F2"  # blanco roto / crema, fondo

GERIATRICOS = ["Geri 1", "Geri 2", "Geri 3"]
CAPACIDAD_CAMAS = {"Geri 1": 10, "Geri 2": 10, "Geri 3": 10}  # <-- ajustar con la cantidad real de camas de cada uno
OBRAS_SOCIALES = ["PAMI", "OSDE", "Swiss Medical", "OSDEPYM", "IOMA", "Galeno", "Medife", "Otra"]

# ---------------------------------------------------------------- ESTILOS
st.markdown(
    f"""
    <style>
    .stApp {{ background-color: {CREAM}; }}
    section[data-testid="stSidebar"] {{ background-color: #F1E7DA; border-right: 1px solid #E8DFCF; }}
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] p {{ color: {NAVY} !important; }}
    section[data-testid="stSidebar"] .stButton>button {{
        background-color: {TEAL} !important; color: {NAVY} !important; border: 1px solid #C7A78C !important; font-weight: 600;
    }}
    section[data-testid="stSidebar"] .stButton>button:hover {{ background-color: #BD8F72 !important; color: #FFFFFF !important; }}
    div[data-testid="stTextInput"] input,
    div[data-testid="stTextArea"] textarea,
    div[data-testid="stNumberInput"] input,
    div[data-testid="stDateInput"] input,
    div[data-baseweb="select"] > div {{
        background-color: #FFFFFF !important;
        border: 1px solid #D8C9B8 !important;
        border-radius: 8px !important;
    }}
    div[data-testid="stTextInput"] input:focus,
    div[data-testid="stTextArea"] textarea:focus,
    div[data-testid="stNumberInput"] input:focus {{
        border: 1px solid {TEAL} !important;
        box-shadow: 0 0 0 1px {TEAL} !important;
    }}
    div[data-testid="stMetric"] {{
        background-color: #FFFFFF;
        border-radius: 14px;
        padding: 18px;
        border: 1px solid #EAE2D6;
        border-left: 3px solid {TEAL};
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }}
    h1, h2, h3 {{ color: {NAVY}; font-weight: 600; }}
    .stButton>button {{
        background-color: {NAVY}; color: white; border-radius: 6px; border: none;
    }}
    .stButton>button:hover {{ background-color: {TEAL}; color: white; }}
    div[data-testid="stForm"] {{
        background-color: #FFFFFF;
        border: 1px solid #EAE2D6;
        border-radius: 14px;
        padding: 20px;
    }}
    .stMarkdown table, .stMarkdown th, .stMarkdown td {{
        border: none !important;
    }}
    .stMarkdown thead tr {{ border-bottom: none !important; }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------- CONEXIÓN
import json
import base64
import re


def normalizar_pem(pk):
    """Corrige el caso en que el salto de línea justo después de BEGIN o antes de END
    haya quedado como espacio en vez de salto de línea real (típico al pegar en Secrets)."""
    if not pk:
        return pk
    pk = pk.strip()
    pk = re.sub(r"-----BEGIN PRIVATE KEY-----\s+", "-----BEGIN PRIVATE KEY-----\n", pk)
    pk = re.sub(r"\s+-----END PRIVATE KEY-----", "\n-----END PRIVATE KEY-----", pk)
    if not pk.endswith("\n"):
        pk += "\n"
    return pk


@st.cache_resource
def get_client():
    if "gcp_service_account_b64" in st.secrets:
        info = json.loads(base64.b64decode(st.secrets["gcp_service_account_b64"]).decode("utf-8"))
    elif "gcp_service_account_json" in st.secrets:
        info = json.loads(st.secrets["gcp_service_account_json"])
    else:
        info = dict(st.secrets["gcp_service_account"])
    info["private_key"] = normalizar_pem(info.get("private_key", ""))
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


@st.cache_resource
def get_sheet():
    return get_client().open_by_key(st.secrets["app"]["sheet_id"])


def uwrite(ws, rng, value):
    """Escribe una celda/rango dejando que Sheets interprete fechas y números (no como texto plano)."""
    ws.update(rng, [[value]], value_input_option="USER_ENTERED")


def find_next_empty_row(ws, col_index, start_row):
    values = ws.col_values(col_index)
    for i in range(start_row - 1, len(values)):
        if not values[i]:
            return i + 1
    return len(values) + 1


@st.cache_data(ttl=20, show_spinner=False)
def sheet_to_df(_ws, header_row, first_data_row, last_col_letter):
    all_values = _ws.get(f"A{header_row}:{last_col_letter}{_ws.row_count}")
    if not all_values:
        return pd.DataFrame()
    headers = all_values[0]
    largo = len(headers)
    rows = all_values[first_data_row - header_row:]
    rows = [r for r in rows if any(cell.strip() for cell in r if cell)]
    normalizadas = []
    for r in rows:
        if len(r) < largo:
            r = r + [""] * (largo - len(r))
        elif len(r) > largo:
            r = r[:largo]
        normalizadas.append(r)
    return pd.DataFrame(normalizadas, columns=headers)


def to_number(valor, default=0):
    """Convierte a número de forma segura, aunque venga con $, puntos de miles o vacío."""
    if valor is None:
        return default
    texto = str(valor).strip()
    if not texto:
        return default
    texto = texto.replace("$", "").replace(" ", "")
    # si tiene coma y punto, asumimos que el punto es separador de miles
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        return int(float(texto))
    except ValueError:
        return default


TURNOS_LEYENDA = {
    "M": "Mañana (7-15h)", "T": "Tarde (15-23h)", "N": "Noche (23-7h)",
    "F": "Franco", "L": "Licencia", "V": "Vacaciones",
}


def nombre_hoja_grilla(mes, anio):
    return f"Grilla {mes:02d}-{anio}"


def crear_grilla_mes(sheet, mes, anio):
    """Crea la hoja de turnos del mes, con la lista de personal activo y días vacíos."""
    nombre = nombre_hoja_grilla(mes, anio)
    dias_en_mes = calendar.monthrange(anio, mes)[1]
    ws_personal = sheet.worksheet("Personal y Turnos")
    df_personal = sheet_to_df(ws_personal, header_row=4, first_data_row=5, last_col_letter="J")
    activos = df_personal[df_personal["Estado"] == "Activo"]["Apellido y Nombre"].tolist()

    ws_nueva = sheet.add_worksheet(title=nombre, rows=str(len(activos) + 6), cols=str(dias_en_mes + 2))
    ws_nueva.update("A1", [["GRILLA MENSUAL DE TURNOS"]])
    ws_nueva.update("A2", [["MES:", mes, "AÑO:", anio, "", "M = Mañana (7-15h)", "", "T = Tarde (15-23h)", "", "C = Noche (23-7h)", "", "F = Franco", "", "L = Licencia", "", "V = Vacaciones"]])
    encabezado = ["Empleado"] + [str(d) for d in range(1, dias_en_mes + 1)]
    ws_nueva.update("A4", [encabezado])
    for i, empleado in enumerate(activos):
        ws_nueva.update(f"A{5 + i}", [[empleado]])
    return ws_nueva


def get_or_create_grilla(sheet, mes, anio):
    nombre = nombre_hoja_grilla(mes, anio)
    try:
        return sheet.worksheet(nombre), False
    except gspread.WorksheetNotFound:
        return None, True


def leer_grilla(ws):
    valores = ws.get_all_values()
    encabezado = valores[3] if len(valores) > 3 else []
    filas = valores[4:] if len(valores) > 4 else []
    filas = [f for f in filas if f and f[0]]
    return pd.DataFrame(filas, columns=encabezado[: len(filas[0])] if filas else encabezado)


def generar_excel_reporte(mes, anio, df_pagos_mes, df_caja_mes, resumen):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame([resumen]).to_excel(writer, sheet_name="Resumen", index=False)
        df_pagos_mes.to_excel(writer, sheet_name="Pagos", index=False)
        df_caja_mes.to_excel(writer, sheet_name="Caja", index=False)
    buffer.seek(0)
    return buffer


def generar_pdf_reporte(mes, anio, resumen, pendientes_df, egresos_cat_df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Dulce Atardecer - Resumen Mensual", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Período: {mes:02d}/{anio}", ln=True)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Resumen de Caja", ln=True)
    pdf.set_font("Helvetica", "", 11)
    for k, v in resumen.items():
        pdf.cell(0, 7, f"{k}: {v}", ln=True)
    pdf.ln(4)

    if not egresos_cat_df.empty:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Egresos por categoría", ln=True)
        pdf.set_font("Helvetica", "", 10)
        for _, row in egresos_cat_df.iterrows():
            pdf.cell(0, 6, f"{row['Categoría']}: ${row['Monto']:,.0f}", ln=True)
        pdf.ln(4)

    if not pendientes_df.empty:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Residentes con pago pendiente", ln=True)
        pdf.set_font("Helvetica", "", 10)
        for _, row in pendientes_df.iterrows():
            pdf.cell(0, 6, f"{row['Residente']} — Cuota ${row['Cuota']}", ln=True)

    return bytes(pdf.output())


import smtplib
from email.mime.text import MIMEText


def enviar_recibo(destinatario, residente, monto, fecha, medio, geriatrico):
    """Manda un mail de comprobante de pago a la familia. No rompe el flujo si falla."""
    if not destinatario or "@" not in destinatario:
        return False, "sin email cargado"
    try:
        cuerpo = (
            f"Hola,\n\n"
            f"Te confirmamos que se registró un pago para {residente} en {geriatrico}.\n\n"
            f"Fecha: {fecha.strftime('%d/%m/%Y')}\n"
            f"Monto: ${monto:,.0f}\n"
            f"Medio de pago: {medio}\n\n"
            f"Este es un mensaje automático de Dulce Atardecer.\n"
        )
        msg = MIMEText(cuerpo)
        msg["Subject"] = f"Comprobante de pago — {residente}"
        msg["From"] = st.secrets["email"]["remitente"]
        msg["To"] = destinatario

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(st.secrets["email"]["remitente"], st.secrets["email"]["app_password"])
            server.send_message(msg)
        return True, "enviado"
    except Exception as e:
        return False, str(e)


def registrar_en_caja(sheet, fecha, geriatrico, categoria, descripcion, monto, medio, responsable, tipo="Ingreso"):
    ws = sheet.worksheet("Caja")
    fila = find_next_empty_row(ws, col_index=2, start_row=2)
    if fila > 200:
        st.warning("Caja no tiene más filas preparadas — este movimiento no se pudo reflejar ahí automáticamente.")
        return
    uwrite(ws, f"B{fila}", fecha.strftime("%d/%m/%Y"))
    uwrite(ws, f"C{fila}", geriatrico)
    uwrite(ws, f"D{fila}", tipo)
    uwrite(ws, f"E{fila}", categoria)
    uwrite(ws, f"F{fila}", descripcion)
    uwrite(ws, f"G{fila}", monto)
    uwrite(ws, f"H{fila}", medio)
    uwrite(ws, f"I{fila}", responsable)


# ---------------------------------------------------------------- LOGIN
def render_tabla(df):
    """Tabla prolija: sin cuadrícula completa, solo una línea fina entre filas."""
    if df.empty:
        st.info("Todavía no hay datos cargados.")
        return
    filas_html = "".join(
        f"<tr style='border-bottom:1px solid #F0E9DF;'>" + "".join(f"<td style='padding:10px 14px;'>{v}</td>" for v in row) + "</tr>"
        for row in df.astype(str).values.tolist()
    )
    encabezado = "".join(f"<th style='text-align:left;padding:10px 14px;'>{c}</th>" for c in df.columns)
    html = f"""
    <div style="overflow-x:auto;border:1px solid #EAE2D6;border-radius:12px;background:#FFFFFF;">
    <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <thead><tr style="background:#F1E7DA;color:{NAVY};">{encabezado}</tr></thead>
        <tbody>{filas_html}</tbody>
    </table>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
    st.caption(f"{len(df)} registro(s)")


def get_logo_b64():
    try:
        with open("logo.jpg", "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except FileNotFoundError:
        return None


def check_login():
    if st.session_state.get("logged_in"):
        return True
    logo_b64 = get_logo_b64()
    if logo_b64:
        st.markdown(
            f"<div style='text-align:center'><img src='data:image/jpeg;base64,{logo_b64}' width='160'></div>",
            unsafe_allow_html=True,
        )
    st.markdown(f"<h1 style='text-align:center;color:{NAVY}'>Dulce Atardecer</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:gray'>Ingresá con tu usuario y contraseña</p>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        user = st.text_input("Usuario")
        pw = st.text_input("Contraseña", type="password")
        if st.button("Entrar", use_container_width=True):
            users = st.secrets["users"]
            if user in users and users[user] == pw:
                st.session_state["logged_in"] = True
                st.session_state["user"] = user
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")
    return False


if not check_login():
    st.stop()

sheet = get_sheet()

st.sidebar.markdown(f"### 👋 Hola, {st.session_state['user']}")
page = st.sidebar.radio(
    "Menú",
    ["📊 Dashboard", "👵 Residentes", "👩 Personal", "📅 Turnos", "💰 Pagos", "💵 Caja", "📄 Reportes"],
)
if st.sidebar.button("Cerrar sesión"):
    st.session_state.clear()
    st.rerun()

# ================================================================== DASHBOARD
if page == "📊 Dashboard":
    st.title("📊 Panel de control")
    colTitulo, colFiltro, colBoton = st.columns([2, 1, 1])
    filtro_geri = colFiltro.selectbox("Geriátrico", ["Todos"] + GERIATRICOS, key="filtro_geri_dash")
    if colBoton.button("🔄 Actualizar datos"):
        st.cache_data.clear()
        st.rerun()

    hoy = datetime.date.today()

    if filtro_geri == "Todos":
        ws = sheet.worksheet("Dashboards")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 Saldo actual", ws.acell("B6").value)
        c2.metric("📈 Ingresos del mes", ws.acell("D6").value)
        c3.metric("📉 Egresos del mes", ws.acell("F6").value)
        c4.metric("🧮 Resultado del mes", ws.acell("H6").value)
        st.write("")
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("👵 Residentes activos", ws.acell("B9").value)
        c6.metric("⏳ Pagos pendientes", ws.acell("D9").value)
        c7.metric("👩 Personal activo", ws.acell("F9").value)
        c8.metric("🏠 % Ocupación", ws.acell("H9").value)

        st.divider()
        colA, colB = st.columns(2)
        with colA:
            st.subheader("Ingresos vs Egresos — últimos 6 meses")
            tabla = ws.get("B13:D19")
            df_meses = pd.DataFrame(tabla[1:], columns=tabla[0]).set_index("Mes")
            for col in df_meses.columns:
                df_meses[col] = df_meses[col].replace("", "0").str.replace(r"[^\d.-]", "", regex=True).astype(float)
            st.bar_chart(df_meses, color=[TEAL, RUST])

        with colB:
            st.subheader("Estado de pagos")
            tabla2 = ws.get("F13:G17")
            df_estado = pd.DataFrame(tabla2[1:], columns=tabla2[0])
            df_estado["Cantidad"] = pd.to_numeric(df_estado["Cantidad"], errors="coerce").fillna(0)
            if df_estado["Cantidad"].sum() > 0:
                fig = px.pie(df_estado, names="Estado", values="Cantidad", hole=0.4,
                             color_discrete_sequence=[GREEN, RUST, TEAL, NAVY])
                fig.update_layout(paper_bgcolor=CREAM, plot_bgcolor=CREAM, font_color=NAVY)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Todavía no hay pagos cargados para graficar.")

        st.subheader("Egresos por categoría — mes actual")
        tabla3 = ws.get("I13:J20")
        df_cat = pd.DataFrame(tabla3[1:], columns=tabla3[0])
        df_cat["Monto (mes)"] = df_cat["Monto (mes)"].replace("", "0").str.replace(r"[^\d.-]", "", regex=True).astype(float)
        df_cat = df_cat[df_cat["Monto (mes)"] > 0]
        if not df_cat.empty:
            fig2 = px.bar(df_cat, x="Monto (mes)", y="Categoría", orientation="h", color_discrete_sequence=[TEAL])
            fig2.update_layout(paper_bgcolor=CREAM, plot_bgcolor=CREAM, font_color=NAVY)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Todavía no hay egresos cargados este mes.")

    else:
        # -------- KPIs y gráficos calculados en vivo, filtrados por geriátrico --------
        ws_caja = sheet.worksheet("Caja")
        df_caja = sheet_to_df(ws_caja, header_row=1, first_data_row=2, last_col_letter="J")
        ws_pagos = sheet.worksheet("Pagos y Facturación")
        df_pagos = sheet_to_df(ws_pagos, header_row=3, first_data_row=4, last_col_letter="L")

        if not df_caja.empty:
            df_caja = df_caja[df_caja["Geriátrico"] == filtro_geri].copy()
            df_caja["_fecha"] = pd.to_datetime(df_caja["Fecha"], format="%d/%m/%Y", errors="coerce")
            df_caja["_monto"] = pd.to_numeric(df_caja["Monto"].str.replace(r"[^\d.-]", "", regex=True), errors="coerce").fillna(0)
            del_mes = df_caja[(df_caja["_fecha"].dt.month == hoy.month) & (df_caja["_fecha"].dt.year == hoy.year)]
            ingresos_mes = del_mes[del_mes["Tipo"] == "Ingreso"]["_monto"].sum()
            egresos_mes = del_mes[del_mes["Tipo"] == "Egreso"]["_monto"].sum()
            saldo_hist = df_caja[df_caja["Tipo"] == "Ingreso"]["_monto"].sum() - df_caja[df_caja["Tipo"] == "Egreso"]["_monto"].sum()
        else:
            ingresos_mes = egresos_mes = saldo_hist = 0

        if not df_pagos.empty:
            df_pagos_geri = df_pagos[df_pagos["Geriátrico"] == filtro_geri]
        else:
            df_pagos_geri = df_pagos

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 Saldo histórico", f"${saldo_hist:,.0f}")
        c2.metric("📈 Ingresos del mes", f"${ingresos_mes:,.0f}")
        c3.metric("📉 Egresos del mes", f"${egresos_mes:,.0f}")
        c4.metric("🧮 Resultado del mes", f"${ingresos_mes - egresos_mes:,.0f}")

        st.divider()
        colA, colB = st.columns(2)
        with colA:
            st.subheader(f"Estado de pagos — {filtro_geri}")
            if not df_pagos_geri.empty:
                conteo = df_pagos_geri["Estado"].value_counts().reset_index()
                conteo.columns = ["Estado", "Cantidad"]
                fig = px.pie(conteo, names="Estado", values="Cantidad", hole=0.4,
                             color_discrete_sequence=[GREEN, RUST, TEAL, NAVY])
                fig.update_layout(paper_bgcolor=CREAM, plot_bgcolor=CREAM, font_color=NAVY)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Todavía no hay pagos cargados para este geriátrico.")

        with colB:
            st.subheader(f"Egresos por categoría — {filtro_geri}")
            if not df_caja.empty:
                egr_mes = del_mes[del_mes["Tipo"] == "Egreso"]
                if not egr_mes.empty:
                    cat = egr_mes.groupby("Categoría", as_index=False)["_monto"].sum()
                    fig2 = px.bar(cat, x="_monto", y="Categoría", orientation="h", color_discrete_sequence=[TEAL], labels={"_monto": "Monto"})
                    fig2.update_layout(paper_bgcolor=CREAM, plot_bgcolor=CREAM, font_color=NAVY)
                    st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.info("Todavía no hay egresos este mes en este geriátrico.")
            else:
                st.info("Todavía no hay movimientos en este geriátrico.")

    st.caption("Si acabás de cargar un pago o movimiento y no ves el cambio, apretá '🔄 Actualizar datos' arriba.")

# ================================================================== RESIDENTES
elif page == "👵 Residentes":
    tab1, tab2 = st.tabs(["📋 Listado", "➕ Nuevo residente"])

    with tab1:
        st.subheader("Residentes registrados")
        ws = sheet.worksheet("Residentes")
        df = sheet_to_df(ws, header_row=3, first_data_row=4, last_col_letter="R")
        filtro = st.selectbox("Filtrar por estado", ["Todos"] + sorted(df["Estado"].unique().tolist()) if not df.empty else ["Todos"])
        vista = df if filtro == "Todos" or df.empty else df[df["Estado"] == filtro]
        render_tabla(vista)

        st.divider()
        st.subheader("Cambiar estado de un residente")
        if not df.empty:
            nombres = df["Apellido y Nombre"].tolist()
            with st.form("cambiar_estado"):
                nombre_sel = st.selectbox("Residente", nombres)
                nuevo_estado = st.selectbox("Nuevo estado", ["Activo", "Alta", "Traslado", "Fallecido"])
                cambiar = st.form_submit_button("Actualizar estado")
            if cambiar:
                fila = df.index[df["Apellido y Nombre"] == nombre_sel][0] + 4
                uwrite(ws, f"O{fila}", nuevo_estado)
                st.success(f"Estado de {nombre_sel} actualizado a {nuevo_estado} ✅")
                st.rerun()

    with tab2:
        st.subheader("➕ Dar de alta un nuevo residente")

        if st.session_state.get("residente_alta_ok"):
            st.success(f"{st.session_state.pop('residente_alta_ok')} fue dado de alta ✅")
        st.caption("Los campos marcados con * son obligatorios.")

        df_activos_info = df[df["Estado"] == "Activo"] if not df.empty and "Geriátrico" in df.columns else pd.DataFrame()
        cols_info = st.columns(len(GERIATRICOS))
        for col, geri in zip(cols_info, GERIATRICOS):
            ocup = len(df_activos_info[df_activos_info["Geriátrico"] == geri]) if not df_activos_info.empty else 0
            tot = CAPACIDAD_CAMAS.get(geri, 10)
            col.metric(geri, f"{ocup}/{tot}", "lugares ocupados")

        if "residente_form_version" not in st.session_state:
            st.session_state.residente_form_version = 0
        v = st.session_state.residente_form_version

        with st.form(f"form_residente_{v}", clear_on_submit=False):
            c1, c2 = st.columns(2)
            with c1:
                nombre = st.text_input("Apellido y Nombre *", key=f"nombre_{v}")
                dni = st.text_input("DNI *", key=f"dni_{v}")
                nacimiento = st.date_input("Fecha de nacimiento", min_value=pd.Timestamp("1900-01-01"), key=f"nacimiento_{v}")
                ingreso = st.date_input("Fecha de ingreso", key=f"ingreso_{v}")
                geriatrico = st.selectbox("Geriátrico", GERIATRICOS, key=f"geriatrico_{v}")
                habitacion = st.text_input("Habitación / ubicación (opcional)", key=f"habitacion_{v}")
                obra_social = st.selectbox("Obra Social", OBRAS_SOCIALES, key=f"obra_social_{v}")
                obra_social_otra = st.text_input("Si elegiste 'Otra', escribí cuál", key=f"obra_social_otra_{v}") if obra_social == "Otra" else None
                n_afiliado = st.text_input("N° Afiliado", key=f"n_afiliado_{v}")
            with c2:
                contacto = st.text_input("Contacto Familiar *", key=f"contacto_{v}")
                email_contacto = st.text_input("Email de contacto (para recibos)", key=f"email_contacto_{v}")
                telefono = st.text_input("Teléfono (solo números)", key=f"telefono_{v}")
                medico = st.text_input("Médico Tratante", key=f"medico_{v}")
                diagnostico = st.text_area("Diagnóstico Principal", key=f"diagnostico_{v}")
                movilidad = st.selectbox("Movilidad", ["Independiente", "Asistida", "Silla de ruedas", "Rehabilitación"], key=f"movilidad_{v}")
                observaciones = st.text_area("Observaciones", key=f"observaciones_{v}")
            enviar = st.form_submit_button("Guardar residente")

        if enviar:
            telefono_limpio = telefono.replace(" ", "").replace("-", "")
            df_activos = df[df["Estado"] == "Activo"] if not df.empty and "Geriátrico" in df.columns else pd.DataFrame()
            ocupados = len(df_activos[df_activos["Geriátrico"] == geriatrico]) if not df_activos.empty else 0
            total_camas = CAPACIDAD_CAMAS.get(geriatrico, 10)
            dni_limpio = dni.replace(" ", "").replace(".", "").replace("-", "")

            if not nombre or not dni or not contacto:
                st.error("Apellido y Nombre, DNI y Contacto Familiar son obligatorios.")
            elif not dni_limpio.isdigit():
                st.error("El DNI solo puede contener números.")
            elif not df.empty and "DNI" in df.columns and dni_limpio in df["DNI"].astype(str).str.strip().tolist():
                st.error(f"Ya existe un residente registrado con el DNI {dni_limpio}.")
            elif ocupados >= total_camas:
                st.error(f"No hay lugar disponible en {geriatrico} ({ocupados}/{total_camas} ocupados) — no se puede dar de alta.")
            elif telefono_limpio and not telefono_limpio.isdigit():
                st.error("El teléfono solo puede contener números.")
            else:
                ws = sheet.worksheet("Residentes")
                fila = find_next_empty_row(ws, col_index=2, start_row=4)
                if fila > 1000:
                    st.error("No hay más filas preparadas. Avisale al administrador del sistema.")
                else:
                    obra_social_final = obra_social_otra if obra_social == "Otra" and obra_social_otra else obra_social
                    uwrite(ws, f"A{fila}", "=ROW()-3")
                    uwrite(ws, f"B{fila}", nombre)
                    uwrite(ws, f"C{fila}", dni_limpio)
                    uwrite(ws, f"D{fila}", nacimiento.strftime("%d/%m/%Y"))
                    uwrite(ws, f"F{fila}", ingreso.strftime("%d/%m/%Y"))
                    uwrite(ws, f"G{fila}", habitacion)
                    uwrite(ws, f"H{fila}", obra_social_final)
                    uwrite(ws, f"I{fila}", n_afiliado)
                    uwrite(ws, f"J{fila}", contacto)
                    uwrite(ws, f"K{fila}", telefono_limpio)
                    uwrite(ws, f"L{fila}", medico)
                    uwrite(ws, f"M{fila}", diagnostico)
                    uwrite(ws, f"N{fila}", movilidad)
                    uwrite(ws, f"O{fila}", "Activo")
                    uwrite(ws, f"P{fila}", observaciones)
                    uwrite(ws, f"Q{fila}", geriatrico)
                    uwrite(ws, f"R{fila}", email_contacto)
                    st.session_state.residente_form_version += 1
                    st.session_state["residente_alta_ok"] = nombre
                    st.rerun()

# ================================================================== PERSONAL
elif page == "👩 Personal":
    tab1, tab2 = st.tabs(["📋 Listado", "➕ Nuevo empleado/a"])

    with tab1:
        st.subheader("Personal registrado")
        ws = sheet.worksheet("Personal y Turnos")
        df = sheet_to_df(ws, header_row=4, first_data_row=5, last_col_letter="K")
        filtro = st.selectbox("Filtrar por estado", ["Todos"] + sorted(df["Estado"].unique().tolist()) if not df.empty else ["Todos"], key="filtro_personal")
        vista = df if filtro == "Todos" or df.empty else df[df["Estado"] == filtro]
        render_tabla(vista)

        st.divider()
        st.subheader("Cambiar estado de un empleado/a")
        if not df.empty:
            nombres = df["Apellido y Nombre"].tolist()
            with st.form("cambiar_estado_personal"):
                nombre_sel = st.selectbox("Empleado/a", nombres)
                nuevo_estado = st.selectbox("Nuevo estado", ["Activo", "Licencia", "Vacaciones", "Baja"])
                cambiar = st.form_submit_button("Actualizar estado")
            if cambiar:
                fila = df.index[df["Apellido y Nombre"] == nombre_sel][0] + 5
                uwrite(ws, f"I{fila}", nuevo_estado)
                st.success(f"Estado de {nombre_sel} actualizado a {nuevo_estado} ✅")
                st.rerun()

    with tab2:
        st.subheader("➕ Dar de alta un nuevo empleado/a")

        if st.session_state.get("personal_alta_ok"):
            st.success(f"{st.session_state.pop('personal_alta_ok')} fue dado de alta ✅")
        st.caption("Los campos marcados con * son obligatorios.")

        if "personal_form_version" not in st.session_state:
            st.session_state.personal_form_version = 0
        vp = st.session_state.personal_form_version

        with st.form(f"form_personal_{vp}", clear_on_submit=False):
            nombre = st.text_input("Apellido y Nombre *", key=f"p_nombre_{vp}")
            dni = st.text_input("DNI *", key=f"p_dni_{vp}")
            cargo = st.selectbox("Cargo", ["Enfermero/a", "Cuidador/a", "Mucama", "Cocinero/a", "Administrativo/a", "Otro"], key=f"p_cargo_{vp}")
            turno = st.selectbox("Turno Habitual", ["Mañana", "Tarde", "Noche"], key=f"p_turno_{vp}")
            telefono = st.text_input("Teléfono", key=f"p_telefono_{vp}")
            cuil = st.text_input("CUIL", key=f"p_cuil_{vp}")
            inicio = st.date_input("Inicio de Contrato", key=f"p_inicio_{vp}")
            observaciones = st.text_area("Observaciones", key=f"p_observaciones_{vp}")
            enviar = st.form_submit_button("Guardar empleado/a")

        if enviar:
            dni_limpio_personal = dni.replace(" ", "").replace(".", "").replace("-", "")
            if not nombre or not dni:
                st.error("Apellido y Nombre y DNI son obligatorios.")
            elif not dni_limpio_personal.isdigit():
                st.error("El DNI solo puede contener números.")
            elif not df.empty and "DNI" in df.columns and dni_limpio_personal in df["DNI"].astype(str).str.strip().tolist():
                st.error(f"Ya existe un empleado/a registrado con el DNI {dni_limpio_personal}.")
            else:
                ws = sheet.worksheet("Personal y Turnos")
                fila = find_next_empty_row(ws, col_index=2, start_row=5)
                if fila > 989:
                    st.error("No hay más filas preparadas. Avisale al administrador del sistema.")
                else:
                    uwrite(ws, f"B{fila}", nombre)
                    uwrite(ws, f"C{fila}", dni_limpio_personal)
                    uwrite(ws, f"D{fila}", cargo)
                    uwrite(ws, f"E{fila}", turno)
                    uwrite(ws, f"F{fila}", telefono)
                    uwrite(ws, f"G{fila}", cuil)
                    uwrite(ws, f"H{fila}", inicio.strftime("%d/%m/%Y"))
                    uwrite(ws, f"I{fila}", "Activo")
                    uwrite(ws, f"J{fila}", observaciones)
                    st.session_state.personal_form_version += 1
                    st.session_state["personal_alta_ok"] = nombre
                    st.rerun()

# ================================================================== TURNOS
elif page == "📅 Turnos":
    st.title("📅 Turnos del personal")
    hoy = datetime.date.today()
    c1, c2 = st.columns(2)
    mes = c1.selectbox("Mes", list(range(1, 13)), index=hoy.month - 1)
    anio = c2.selectbox("Año", [hoy.year - 1, hoy.year, hoy.year + 1], index=1)

    ws_grilla, no_existe = get_or_create_grilla(sheet, mes, anio)

    if no_existe:
        st.info(f"Todavía no existe la grilla de {mes:02d}/{anio}.")
        if st.button("➕ Crear grilla para este mes"):
            crear_grilla_mes(sheet, mes, anio)
            st.success("Grilla creada ✅")
            st.rerun()
    else:
        df_grilla = leer_grilla(ws_grilla)
        st.caption("Referencias: " + " · ".join(f"**{k}** = {v}" for k, v in TURNOS_LEYENDA.items()))

        if df_grilla.empty:
            st.info("No hay empleados cargados en esta grilla todavía.")
        else:
            st.caption("Hacé doble clic en cualquier celda para cambiar el turno, y después apretá 'Guardar cambios'.")
            columnas_dia = [c for c in df_grilla.columns if c != "Empleado"]
            config_columnas = {
                col: st.column_config.SelectboxColumn(col, options=list(TURNOS_LEYENDA.keys()), width="small")
                for col in columnas_dia
            }
            config_columnas["Empleado"] = st.column_config.TextColumn("Empleado", disabled=True)

            df_editado = st.data_editor(
                df_grilla,
                column_config=config_columnas,
                hide_index=True,
                use_container_width=True,
                key=f"editor_{mes}_{anio}",
            )

            if st.button("💾 Guardar cambios"):
                valores = [df_editado.columns.tolist()] + df_editado.astype(str).values.tolist()
                ws_grilla.update(f"A4", valores, value_input_option="USER_ENTERED")
                st.success("Turnos actualizados ✅")
                st.rerun()

# ================================================================== PAGOS
elif page == "💰 Pagos":
    tab1, tab2, tab3 = st.tabs(["📋 Listado", "➕ Registrar pago", "✏️ Modificar pago"])
    ws_pagos = sheet.worksheet("Pagos y Facturación")
    df_pagos = sheet_to_df(ws_pagos, header_row=3, first_data_row=4, last_col_letter="L")

    with tab1:
        st.subheader("Pagos registrados")
        filtro = st.selectbox("Filtrar por estado", ["Todos", "Pagado", "Pendiente", "Parcial", "Excedente"])
        vista = df_pagos if filtro == "Todos" or df_pagos.empty else df_pagos[df_pagos["Estado"] == filtro]
        render_tabla(vista)

    with tab2:
        st.subheader("➕ Registrar pago de residente")
        ws_res = sheet.worksheet("Residentes")
        residentes = [r for r in ws_res.col_values(2)[3:] if r]

        residente = st.selectbox("Residente", residentes, key="pago_residente")
        fecha = st.date_input("Fecha de pago", key="pago_fecha")

        ya_pago = False
        if not df_pagos.empty and residente:
            existentes = df_pagos[df_pagos["Residente"] == residente].copy()
            if not existentes.empty:
                existentes["_fecha"] = pd.to_datetime(existentes["Fecha Pago"], format="%d/%m/%Y", errors="coerce")
                mismo_mes = existentes[
                    (existentes["_fecha"].dt.month == fecha.month) & (existentes["_fecha"].dt.year == fecha.year)
                ]
                ya_pago = not mismo_mes.empty

        confirmar = True
        if ya_pago:
            st.warning(f"⚠️ {residente} ya tiene un pago cargado para {fecha.strftime('%m/%Y')}.")
            confirmar = st.checkbox("Confirmo que quiero registrarlo igual (es otro concepto o corresponde a otro período)")

        with st.form("form_pago", clear_on_submit=True):
            geriatrico = st.selectbox("Geriátrico", GERIATRICOS)
            cuota = st.number_input("Cuota mensual", min_value=0, step=1000)
            monto = st.number_input("Monto pagado", min_value=0, step=1000)
            medio = st.selectbox("Medio de pago", ["Efectivo", "Transferencia", "Débito automático", "Cheque"])
            enviar = st.form_submit_button("Guardar pago")

        if enviar:
            if ya_pago and not confirmar:
                st.error("Marcá la confirmación de arriba para poder registrar este pago repetido.")
            else:
                fila = find_next_empty_row(ws_pagos, col_index=4, start_row=4)
                if fila > 50:
                    st.error("Ya se llenaron las filas preparadas en Pagos y Facturación. Avisale al administrador del sistema.")
                else:
                    uwrite(ws_pagos, f"C{fila}", fecha.strftime("%d/%m/%Y"))
                    uwrite(ws_pagos, f"D{fila}", residente)
                    uwrite(ws_pagos, f"E{fila}", geriatrico)
                    uwrite(ws_pagos, f"G{fila}", cuota)
                    uwrite(ws_pagos, f"I{fila}", monto)
                    uwrite(ws_pagos, f"K{fila}", medio)
                    registrar_en_caja(
                        sheet, fecha, geriatrico, "Cuota residente",
                        f"Pago cuota - {residente}", monto, medio, st.session_state["user"],
                    )
                    st.success(f"Pago de {residente} guardado y reflejado en Caja ✅")

                    # Recibo automático por mail a la familia (si el residente tiene email cargado)
                    fila_residente = ws_res.col_values(2).index(residente) + 1 if residente in ws_res.col_values(2) else None
                    email_familia = None
                    if fila_residente:
                        valores_email = ws_res.get(f"R{fila_residente}")
                        email_familia = valores_email[0][0] if valores_email and valores_email[0] else None
                    if email_familia:
                        ok, detalle = enviar_recibo(email_familia, residente, monto, fecha, medio, geriatrico)
                        if ok:
                            st.info(f"📧 Comprobante enviado a {email_familia}")
                        else:
                            st.warning(f"No se pudo enviar el comprobante por mail ({detalle}).")

    with tab3:
        st.subheader("✏️ Modificar un pago existente")
        if df_pagos.empty:
            st.info("Todavía no hay pagos cargados.")
        else:
            opciones = [
                f"Fila {i+4} — {row['Residente']} — {row['Fecha Pago']} — ${row['Monto Pagado']}"
                for i, row in df_pagos.iterrows()
            ]
            seleccion = st.selectbox("Elegí el pago a modificar", opciones)
            fila_sel = int(seleccion.split(" ")[1]) if seleccion else None

            if fila_sel:
                idx = fila_sel - 4
                actual = df_pagos.iloc[idx]
                with st.form("form_editar_pago"):
                    nueva_fecha = st.text_input("Fecha de pago (dd/mm/aaaa)", value=actual["Fecha Pago"])
                    nueva_cuota = st.number_input("Cuota mensual", min_value=0, step=1000, value=to_number(actual["Cuota"]))
                    nuevo_monto = st.number_input("Monto pagado", min_value=0, step=1000, value=to_number(actual["Monto Pagado"]))
                    nuevo_medio = st.selectbox(
                        "Medio de pago", ["Efectivo", "Transferencia", "Débito automático", "Cheque"],
                        index=["Efectivo", "Transferencia", "Débito automático", "Cheque"].index(actual["Medio Pago"]) if actual["Medio Pago"] in ["Efectivo", "Transferencia", "Débito automático", "Cheque"] else 0,
                    )
                    guardar = st.form_submit_button("Guardar cambios")

                if guardar:
                    uwrite(ws_pagos, f"C{fila_sel}", nueva_fecha)
                    uwrite(ws_pagos, f"G{fila_sel}", nueva_cuota)
                    uwrite(ws_pagos, f"I{fila_sel}", nuevo_monto)
                    uwrite(ws_pagos, f"K{fila_sel}", nuevo_medio)
                    st.success("Pago actualizado ✅ (este cambio no se refleja automáticamente en Caja — si cambiaste el monto, revisá el movimiento correspondiente ahí a mano).")
                    st.rerun()

# ================================================================== CAJA
elif page == "💵 Caja":
    tab1, tab2 = st.tabs(["📋 Movimientos", "➕ Registrar movimiento"])

    with tab1:
        st.subheader("Movimientos de caja")
        ws = sheet.worksheet("Caja")
        df = sheet_to_df(ws, header_row=1, first_data_row=2, last_col_letter="J")
        filtro = st.selectbox("Filtrar por tipo", ["Todos", "Ingreso", "Egreso"])
        vista = df if filtro == "Todos" or df.empty else df[df["Tipo"] == filtro]
        render_tabla(vista)

    with tab2:
        st.subheader("➕ Registrar movimiento de caja")
        with st.form("form_caja", clear_on_submit=True):
            geriatrico = st.selectbox("Geriátrico", GERIATRICOS)
            tipo = st.selectbox("Tipo", ["Ingreso", "Egreso"])
            categoria = st.selectbox(
                "Categoría",
                ["Cuota residente", "Alimentación", "Farmacia", "Sueldos", "Servicios", "Mantenimiento", "Impuestos", "Otros"],
            )
            fecha = st.date_input("Fecha")
            descripcion = st.text_input("Descripción")
            monto = st.number_input("Monto", min_value=0, step=1000)
            medio = st.selectbox("Medio de pago", ["Efectivo", "Transferencia", "Débito", "Crédito", "Mercado Pago"])
            responsable = st.text_input("Responsable", value=st.session_state["user"])
            enviar = st.form_submit_button("Guardar movimiento")

        if enviar:
            registrar_en_caja(sheet, fecha, geriatrico, categoria, descripcion, monto, medio, responsable, tipo=tipo)
            st.success("Movimiento guardado ✅")

# ================================================================== REPORTES
elif page == "📄 Reportes":
    st.title("📄 Reportes mensuales")
    hoy = datetime.date.today()
    c1, c2 = st.columns(2)
    mes = c1.selectbox("Mes", list(range(1, 13)), index=hoy.month - 1, key="mes_reporte")
    anio = c2.selectbox("Año", [hoy.year - 1, hoy.year, hoy.year + 1], index=1, key="anio_reporte")

    ws_pagos = sheet.worksheet("Pagos y Facturación")
    df_pagos = sheet_to_df(ws_pagos, header_row=3, first_data_row=4, last_col_letter="L")
    ws_caja = sheet.worksheet("Caja")
    df_caja = sheet_to_df(ws_caja, header_row=1, first_data_row=2, last_col_letter="J")

    def es_del_mes(fecha_txt):
        try:
            f = pd.to_datetime(fecha_txt, format="%d/%m/%Y", errors="coerce")
            return f.month == mes and f.year == anio
        except Exception:
            return False

    df_pagos_mes = df_pagos[df_pagos["Fecha Pago"].apply(es_del_mes)] if not df_pagos.empty else df_pagos
    df_caja_mes = df_caja[df_caja["Fecha"].apply(es_del_mes)] if not df_caja.empty else df_caja

    if not df_caja_mes.empty:
        montos = pd.to_numeric(df_caja_mes["Monto"].str.replace(r"[^\d.-]", "", regex=True), errors="coerce").fillna(0)
        ingresos = montos[df_caja_mes["Tipo"] == "Ingreso"].sum()
        egresos = montos[df_caja_mes["Tipo"] == "Egreso"].sum()
    else:
        ingresos = egresos = 0

    resumen = {
        "Período": f"{mes:02d}/{anio}",
        "Ingresos": f"${ingresos:,.0f}",
        "Egresos": f"${egresos:,.0f}",
        "Resultado": f"${ingresos - egresos:,.0f}",
        "Pagos pendientes": int((df_pagos_mes["Estado"] == "Pendiente").sum()) if not df_pagos_mes.empty else 0,
    }

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ingresos", resumen["Ingresos"])
    c2.metric("Egresos", resumen["Egresos"])
    c3.metric("Resultado", resumen["Resultado"])
    c4.metric("Pagos pendientes", resumen["Pagos pendientes"])

    st.divider()
    st.subheader("Pagos del período")
    render_tabla(df_pagos_mes)
    st.subheader("Movimientos de caja del período")
    render_tabla(df_caja_mes)

    pendientes_df = pd.DataFrame()
    if not df_pagos_mes.empty:
        pend = df_pagos_mes[df_pagos_mes["Estado"] == "Pendiente"]
        if not pend.empty:
            pendientes_df = pend[["Residente", "Cuota"]]

    egresos_cat_df = pd.DataFrame()
    if not df_caja_mes.empty:
        egr = df_caja_mes[df_caja_mes["Tipo"] == "Egreso"].copy()
        if not egr.empty:
            egr["Monto"] = pd.to_numeric(egr["Monto"].str.replace(r"[^\d.-]", "", regex=True), errors="coerce").fillna(0)
            egresos_cat_df = egr.groupby("Categoría", as_index=False)["Monto"].sum()

    st.divider()
    st.subheader("⬇️ Descargar")
    colE, colP = st.columns(2)
    excel_buffer = generar_excel_reporte(mes, anio, df_pagos_mes, df_caja_mes, resumen)
    colE.download_button(
        "📊 Descargar Excel", data=excel_buffer,
        file_name=f"Reporte_{mes:02d}_{anio}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    pdf_bytes = generar_pdf_reporte(mes, anio, resumen, pendientes_df, egresos_cat_df)
    colP.download_button(
        "📄 Descargar PDF", data=pdf_bytes,
        file_name=f"Reporte_{mes:02d}_{anio}.pdf",
        mime="application/pdf",
    )
