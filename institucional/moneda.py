from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


CENTAVOS = Decimal("0.01")


def decimal_importe(valor):
    """Convierte entradas con coma o punto a Decimal, sin pasar por float."""
    if valor in (None, ""):
        return None
    if isinstance(valor, Decimal):
        return valor
    texto = str(valor).strip().replace("$", "").replace(" ", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif texto.count(".") > 1:
        texto = texto.replace(".", "")
    try:
        return Decimal(texto)
    except (InvalidOperation, ValueError) as error:
        raise ValueError("Ingresá un importe válido.") from error


def formatear_moneda(valor):
    importe = decimal_importe(valor) if valor is not None else Decimal("0")
    importe = (importe or Decimal("0")).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
    texto = f"{importe:,.2f}"
    return "$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def es_columna_monetaria(nombre):
    nombre = str(nombre).lower()
    return any(palabra in nombre for palabra in ("monto", "importe", "abonado", "saldo", "facturado", "cobrado", "deuda", "ingreso", "egreso", "resultado", "total"))
