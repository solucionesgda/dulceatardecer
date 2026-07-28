from datetime import datetime
from io import BytesIO
from pathlib import Path

from django.http import HttpResponse
from django.core.mail import EmailMessage, get_connection
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def excel_response(titulo, columnas, filas):
    libro = Workbook(); hoja = libro.active; hoja.title = titulo[:31]
    hoja.append(columnas)
    for fila in filas: hoja.append([str(valor or "") for valor in fila])
    salida = BytesIO(); libro.save(salida)
    respuesta = HttpResponse(salida.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    respuesta["Content-Disposition"] = f'attachment; filename="{titulo}.xlsx"'
    return respuesta


def pdf_response(titulo, columnas, filas, institucion, usuario, textos_adicionales=(), anchos_columnas=None, tamano_fuente=7):
    salida = BytesIO(); documento = SimpleDocTemplate(salida, pagesize=landscape(letter), leftMargin=24, rightMargin=24, topMargin=24)
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
    tabla = Table([columnas] + [[str(valor or "") for valor in fila] for fila in filas], repeatRows=1, colWidths=anchos_columnas)
    tabla.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#243b53")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .25, colors.grey), ("FONTSIZE", (0,0), (-1,-1), tamano_fuente), ("VALIGN", (0,0), (-1,-1), "TOP")]))
    contenido.append(tabla); documento.build(contenido)
    respuesta = HttpResponse(salida.getvalue(), content_type="application/pdf"); respuesta["Content-Disposition"] = f'attachment; filename="{titulo}.pdf"'; return respuesta


def enviar_pdf(institucion, destinatario, asunto, pdf, nombre):
    conexion = get_connection(host=institucion.smtp_servidor, port=institucion.smtp_puerto, username=institucion.smtp_usuario, password=institucion.smtp_contrasena, use_tls=institucion.smtp_tls, use_ssl=institucion.smtp_ssl)
    remitente = institucion.smtp_remitente or institucion.smtp_usuario
    if institucion.smtp_nombre_remitente: remitente = f"{institucion.smtp_nombre_remitente} <{remitente}>"
    mensaje = EmailMessage(asunto, "Adjuntamos el comprobante solicitado.", remitente, [destinatario], connection=conexion)
    mensaje.attach(nombre, pdf, "application/pdf"); mensaje.send(fail_silently=False)
