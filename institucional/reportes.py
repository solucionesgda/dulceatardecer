from datetime import datetime
from io import BytesIO
from pathlib import Path

from django.http import HttpResponse
from django.core.mail import EmailMessage, get_connection
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape, letter
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from django.conf import settings
from django.utils.html import escape
from .moneda import decimal_importe, es_columna_monetaria, formatear_moneda


def excel_response(titulo, columnas, filas):
    libro = Workbook(); hoja = libro.active; hoja.title = titulo[:31]
    hoja.append(columnas)
    columnas_monetarias = {indice for indice, columna in enumerate(columnas) if es_columna_monetaria(columna)}
    for fila in filas:
        hoja.append([decimal_importe(valor) if indice in columnas_monetarias and valor is not None else ("" if valor is None else str(valor)) for indice, valor in enumerate(fila)])
    for fila in hoja.iter_rows(min_row=2):
        for indice in columnas_monetarias:
            fila[indice].number_format = '"$" #,##0.00'
    salida = BytesIO(); libro.save(salida)
    respuesta = HttpResponse(salida.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    respuesta["Content-Disposition"] = f'attachment; filename="{titulo}.xlsx"'
    return respuesta


def pdf_response(titulo, columnas, filas, institucion, usuario, textos_adicionales=(), anchos_columnas=None, tamano_fuente=7):
    salida = BytesIO(); documento = SimpleDocTemplate(salida, pagesize=landscape(letter), leftMargin=24, rightMargin=24, topMargin=24, pageCompression=0)
    estilos = getSampleStyleSheet(); contenido = []
    try:
        ruta_logo = institucion.logo.path if institucion.logo else None
        if ruta_logo and Path(ruta_logo).is_file():
            contenido.extend([Image(ruta_logo, width=55, height=55), Spacer(1, 6)])
    except (AttributeError, OSError, ValueError):
        pass
    contenido.extend([Paragraph(institucion.nombre_institucion, estilos["Title"]), Paragraph(titulo, estilos["Heading2"]), Paragraph(f"Emitido: {datetime.now():%d/%m/%Y %H:%M} - Usuario: {usuario}", estilos["Normal"])])
    contenido.extend(Paragraph(texto, estilos["Normal"]) for texto in textos_adicionales)
    contenido.append(Spacer(1, 12))
    columnas_monetarias = {indice for indice, columna in enumerate(columnas) if es_columna_monetaria(columna)}
    datos = [[formatear_moneda(valor) if indice in columnas_monetarias else str(valor or "") for indice, valor in enumerate(fila)] for fila in filas]
    tabla = Table([columnas] + datos, repeatRows=1, colWidths=anchos_columnas)
    tabla.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#243b53")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .25, colors.grey), ("FONTSIZE", (0,0), (-1,-1), tamano_fuente), ("VALIGN", (0,0), (-1,-1), "TOP")]))
    contenido.append(tabla); documento.build(contenido)
    respuesta = HttpResponse(salida.getvalue(), content_type="application/pdf"); respuesta["Content-Disposition"] = f'attachment; filename="{titulo}.pdf"'; return respuesta


def comprobante_pago_pdf(pago, institucion, usuario):
    """Generador único usado tanto por descarga como por envío de comprobantes."""
    salida = BytesIO()
    documento = SimpleDocTemplate(salida, pagesize=A4, leftMargin=48, rightMargin=48, topMargin=46, bottomMargin=66, pageCompression=0)
    estilos = getSampleStyleSheet()
    estilos["Title"].fontName = "Helvetica-Bold"; estilos["Title"].fontSize = 20; estilos["Title"].textColor = colors.HexColor("#20242c")
    estilos["Heading2"].textColor = colors.HexColor("#526b85")
    estilos["Normal"].fontSize = 9; estilos["Normal"].leading = 13
    contenido = []
    ruta_logo = None
    try:
        ruta_logo = institucion.logo.path if institucion.logo else None
    except (AttributeError, OSError, ValueError):
        pass
    if not ruta_logo or not Path(ruta_logo).is_file():
        alternativa = Path(settings.BASE_DIR) / "static" / "img" / "dulce-atardecer-logo.jpg"
        ruta_logo = alternativa if alternativa.is_file() else None
    encabezado = []
    if ruta_logo:
        encabezado.append(Image(str(ruta_logo), width=54, height=54))
    encabezado.append(Paragraph(f"<b>{escape(institucion.nombre_institucion)}</b><br/><font size=9>{escape(pago.residente.geriatrico.nombre)}</font>", estilos["Normal"]))
    encabezado.append(Paragraph("<b>COMPROBANTE DE PAGO</b><br/><font size=8>Emitido: %s<br/>Usuario: %s</font>" % (datetime.now().strftime("%d/%m/%Y %H:%M"), escape(str(usuario))), estilos["Normal"]))
    contenido.append(Table([encabezado], colWidths=[64, 270, 150], style=[("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (2, 0), (2, 0), "RIGHT"), ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#526b85")), ("BOTTOMPADDING", (0, 0), (-1, -1), 14)]))
    contenido.append(Spacer(1, 18))
    ultimo_abono = pago.abonos.order_by("-fecha_pago", "-pk").first()
    fecha_pago = pago.fecha_pago or (ultimo_abono.fecha_pago if ultimo_abono else None)
    medio_pago = pago.medio_pago or (ultimo_abono.medio_pago if ultimo_abono else "")
    datos = [
        ("Residente", str(pago.residente)), ("Período", pago.periodo), ("Concepto", pago.concepto),
        ("Fecha de pago", fecha_pago.strftime("%d/%m/%Y") if fecha_pago else "No registrada"),
        ("Medio de pago", medio_pago or "No registrado"), ("Importe", formatear_moneda(pago.monto)),
        ("Total abonado", formatear_moneda(pago.total_abonado)), ("Saldo pendiente", formatear_moneda(pago.saldo_pendiente)),
    ]
    filas = [[Paragraph(f"<b>{etiqueta}</b>", estilos["Normal"]), Paragraph(escape(valor), estilos["Normal"])] for etiqueta, valor in datos]
    tabla = Table(filas, colWidths=[150, 334], hAlign="LEFT")
    tabla.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f4f7")), ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#d6dbe2")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    contenido.extend([Paragraph("Detalle del comprobante", estilos["Heading2"]), Spacer(1, 6), tabla])

    def pie(canvas, doc):
        canvas.saveState(); canvas.setStrokeColor(colors.HexColor("#d6dbe2")); canvas.line(48, 43, A4[0] - 48, 43)
        canvas.setFillColor(colors.HexColor("#687385")); canvas.setFont("Helvetica", 7); canvas.drawCentredString(A4[0] / 2, 31, "Documento generado automáticamente por")
        canvas.setFont("Helvetica-Bold", 7); canvas.drawCentredString(A4[0] / 2, 20, "Datanova IT Solutions · www.datanovait.com"); canvas.restoreState()

    documento.build(contenido, onFirstPage=pie, onLaterPages=pie)
    return salida.getvalue()


def validar_configuracion_smtp(institucion):
    if institucion.smtp_tls and institucion.smtp_ssl:
        raise ValueError("La configuración SMTP no puede usar TLS y SSL al mismo tiempo.")
    if not all((institucion.smtp_servidor, institucion.smtp_puerto, institucion.smtp_usuario, institucion.smtp_contrasena)):
        raise ValueError("La configuración SMTP está incompleta.")


def enviar_pdf(institucion, destinatario, asunto, pdf, nombre, mensaje_texto="Adjuntamos el documento solicitado."):
    validar_configuracion_smtp(institucion)
    conexion = get_connection(host=institucion.smtp_servidor, port=institucion.smtp_puerto, username=institucion.smtp_usuario, password=institucion.smtp_contrasena, use_tls=institucion.smtp_tls, use_ssl=institucion.smtp_ssl)
    remitente = institucion.smtp_remitente or institucion.smtp_usuario
    if institucion.smtp_nombre_remitente: remitente = f"{institucion.smtp_nombre_remitente} <{remitente}>"
    mensaje = EmailMessage(asunto, mensaje_texto, remitente, [destinatario], connection=conexion)
    mensaje.attach(nombre, pdf, "application/pdf"); mensaje.send(fail_silently=False)
