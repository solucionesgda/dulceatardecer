from datetime import date, timedelta
from decimal import Decimal
import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models, transaction
from django.db.models import Sum
from django.conf import settings
from django.utils import timezone


class Geriatrico(models.Model):
    nombre = models.CharField(max_length=150)
    codigo = models.CharField(max_length=30, unique=True)
    direccion = models.CharField(max_length=255)
    capacidad_total = models.PositiveIntegerField()
    activo = models.BooleanField(default=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "geriátrico"
        verbose_name_plural = "geriátricos"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(capacidad_total__gt=0),
                name="capacidad_total_mayor_a_cero",
            ),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"

    @property
    def camas_ocupadas(self):
        return self.residentes.filter(estado=Residente.Estado.ACTIVO).count()

    @property
    def camas_disponibles(self):
        return self.capacidad_total - self.camas_ocupadas

    def clean(self):
        super().clean()
        if self.capacidad_total is not None and self.capacidad_total <= 0:
            raise ValidationError({"capacidad_total": "La capacidad total debe ser mayor que 0."})


class Residente(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = "Activo", "Activo"
        ALTA = "Alta", "Alta"
        TRASLADO = "Traslado", "Traslado"
        FALLECIDO = "Fallecido", "Fallecido"

    class Movilidad(models.TextChoices):
        INDEPENDIENTE = "Independiente", "Independiente"
        ASISTIDA = "Asistida", "Asistida"
        SILLA_RUEDAS = "Silla de ruedas", "Silla de ruedas"
        REHABILITACION = "Rehabilitación", "Rehabilitación"

    class ObraSocial(models.TextChoices):
        PAMI = "PAMI", "PAMI"
        IAPOS = "IAPOS", "IAPOS"
        OSDE = "OSDE", "OSDE"
        SWISS_MEDICAL = "Swiss Medical", "Swiss Medical"
        GALENO = "Galeno", "Galeno"
        SANCOR_SALUD = "Sancor Salud", "Sancor Salud"
        AVALIAN = "Avalian", "Avalian"
        FEDERADA_SALUD = "Federada Salud", "Federada Salud"
        PARTICULAR = "Particular", "Particular"
        OTRA = "Otra", "Otra"

    geriatrico = models.ForeignKey(Geriatrico, on_delete=models.PROTECT, related_name="residentes")
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    dni = models.CharField(max_length=8, unique=True, validators=[RegexValidator(r"^\d{8}$", "El DNI debe contener exactamente 8 números.")])
    fecha_nacimiento = models.DateField(blank=True, null=True)
    fecha_ingreso = models.DateField()
    habitacion = models.CharField(max_length=100, blank=True)
    obra_social = models.CharField(max_length=100, blank=True, choices=ObraSocial.choices)
    obra_social_otra = models.CharField(max_length=100, blank=True)
    numero_afiliado = models.CharField(max_length=100, blank=True, validators=[RegexValidator(r"^\d+$", "El número de afiliado debe contener solo números.")])
    contacto_familiar = models.CharField(max_length=150, validators=[RegexValidator(r"^[A-Za-zÁÉÍÓÚáéíóúÑñÜü' -]+$", "Ingrese nombre y apellido, sin números ni símbolos.")])
    email_contacto = models.EmailField(blank=True)
    telefono = models.CharField(max_length=30, blank=True, validators=[RegexValidator(r"^\d+$", "El teléfono solo puede contener números.")])
    medico_tratante = models.CharField(max_length=150, blank=True)
    diagnostico_principal = models.TextField(blank=True)
    movilidad = models.CharField(max_length=30, choices=Movilidad.choices, default=Movilidad.INDEPENDIENTE)
    observaciones = models.TextField(blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ACTIVO)
    monto_mensual = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(Decimal("0.01"))])

    class Meta:
        ordering = ["apellido", "nombre"]
        verbose_name = "residente"
        verbose_name_plural = "residentes"

    def __str__(self):
        return f"{self.apellido}, {self.nombre}"

    @staticmethod
    def normalizar_nombre(valor):
        """Elimina espacios accidentales y aplica formato de nombre uniforme."""
        return " ".join(valor.split()).title() if valor else valor

    def save(self, *args, **kwargs):
        nombres_modificados = set()
        for campo in ("nombre", "apellido"):
            valor_normalizado = self.normalizar_nombre(getattr(self, campo))
            if valor_normalizado != getattr(self, campo):
                setattr(self, campo, valor_normalizado)
                nombres_modificados.add(campo)
        if kwargs.get("update_fields") is not None and nombres_modificados:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | nombres_modificados
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.fecha_ingreso and self.fecha_ingreso > date.today():
            raise ValidationError({"fecha_ingreso": "La fecha de ingreso no puede ser posterior al día de hoy."})
        if self.obra_social == self.ObraSocial.OTRA and not self.obra_social_otra.strip():
            raise ValidationError({"obra_social_otra": "Indicá el nombre de la obra social o prepaga."})
        if self.obra_social != self.ObraSocial.OTRA:
            self.obra_social_otra = ""
        if self.habitacion and self.geriatrico_id:
            try:
                numero_habitacion = int(self.habitacion)
            except ValueError:
                raise ValidationError({"habitacion": "Seleccioná una habitación válida."})
            if not 1 <= numero_habitacion <= self.geriatrico.capacidad_total:
                raise ValidationError({"habitacion": "La habitación seleccionada no pertenece al geriátrico."})
            if self.estado == self.Estado.ACTIVO:
                ocupantes = Residente.objects.filter(
                    geriatrico_id=self.geriatrico_id,
                    estado=self.Estado.ACTIVO,
                    habitacion=self.habitacion,
                )
                if self.pk:
                    ocupantes = ocupantes.exclude(pk=self.pk)
                if ocupantes.exists():
                    raise ValidationError({"habitacion": "La habitación seleccionada ya está ocupada."})
        if self.estado != self.Estado.ACTIVO or not self.geriatrico_id:
            return
        residentes_activos = Residente.objects.filter(
            geriatrico_id=self.geriatrico_id,
            estado=self.Estado.ACTIVO,
        )
        if self.pk:
            residentes_activos = residentes_activos.exclude(pk=self.pk)
        if residentes_activos.count() >= self.geriatrico.capacidad_total:
            raise ValidationError({"geriatrico": "No se puede dar de alta un residente activo: el geriátrico alcanzó su capacidad."})

class Pago(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "Pendiente", "Pendiente"
        PARCIAL = "Parcial", "Parcial"
        PAGADO = "Pagado", "Pagado"
        VENCIDO = "Vencido", "Vencido"

    class MedioPago(models.TextChoices):
        EFECTIVO = "Efectivo", "Efectivo"
        TRANSFERENCIA = "Transferencia", "Transferencia"
        DEBITO_AUTOMATICO = "Débito automático", "Débito automático"
        CHEQUE = "Cheque", "Cheque"

    residente = models.ForeignKey(Residente, on_delete=models.PROTECT, related_name="pagos")
    periodo = models.CharField(max_length=7, validators=[RegexValidator(r"^\d{4}-(0[1-9]|1[0-2])$", "El período debe tener el formato AAAA-MM.")])
    concepto = models.CharField(max_length=150)
    monto = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    fecha_vencimiento = models.DateField()
    fecha_pago = models.DateField(blank=True, null=True)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE, editable=False)
    medio_pago = models.CharField(max_length=30, choices=MedioPago.choices, blank=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ["-periodo", "residente__apellido", "residente__nombre"]
        verbose_name = "pago"
        verbose_name_plural = "pagos"
        constraints = [models.UniqueConstraint(fields=["residente", "periodo"], name="pago_unico_por_residente_y_periodo")]

    def __str__(self):
        return f"{self.residente} · {self.periodo} · {self.concepto}"

    @property
    def total_abonado(self):
        if not self.pk:
            return Decimal("0.00")
        return self.abonos.aggregate(total=Sum("monto"))["total"] or Decimal("0.00")

    @property
    def saldo_pendiente(self):
        return max(self.monto - self.total_abonado, Decimal("0.00"))

    def calcular_estado(self):
        if self.total_abonado >= self.monto:
            return self.Estado.PAGADO
        if self.saldo_pendiente > 0 and self.fecha_vencimiento < date.today():
            return self.Estado.VENCIDO
        if self.total_abonado > 0:
            return self.Estado.PARCIAL
        return self.Estado.PENDIENTE

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        if self.fecha_pago and not self.abonos.exists():
            PagoParcial.objects.create(
                pago=self, monto=self.monto, fecha_pago=self.fecha_pago,
                medio_pago=self.medio_pago, observaciones=self.observaciones,
            )
        self.recalcular_estado()

    def clean(self):
        super().clean()
        if self.fecha_pago and self.fecha_pago > date.today():
            raise ValidationError({"fecha_pago": "La fecha de pago no puede ser posterior al día de hoy."})
        if self.pk and self.monto < self.total_abonado:
            raise ValidationError({"monto": "El monto no puede ser menor al total ya abonado."})

    def recalcular_estado(self):
        self.estado = self.calcular_estado()
        if self.pk:
            Pago.objects.filter(pk=self.pk).update(estado=self.estado)

    @classmethod
    def actualizar_vencidos(cls):
        for pago in cls.objects.exclude(estado=cls.Estado.PAGADO):
            pago.recalcular_estado()


class PagoParcial(models.Model):
    pago = models.ForeignKey(Pago, on_delete=models.CASCADE, related_name="abonos")
    monto = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    fecha_pago = models.DateField(default=date.today)
    medio_pago = models.CharField(max_length=30, choices=Pago.MedioPago.choices, blank=True)
    observaciones = models.TextField(blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="abonos_registrados")

    class Meta:
        ordering = ["fecha_pago", "pk"]
        verbose_name = "abono"
        verbose_name_plural = "abonos"

    def clean(self):
        super().clean()
        if self.fecha_pago and self.fecha_pago > date.today():
            raise ValidationError({"fecha_pago": "La fecha de abono no puede ser posterior al día de hoy."})
        if self.pago_id:
            anteriores = PagoParcial.objects.filter(pago_id=self.pago_id)
            if self.pk:
                anteriores = anteriores.exclude(pk=self.pk)
            abonado = anteriores.aggregate(total=Sum("monto"))["total"] or Decimal("0.00")
            if abonado + self.monto > self.pago.monto:
                raise ValidationError({"monto": "El importe no puede superar el saldo pendiente."})

    def save(self, *args, **kwargs):
        # El abono, el estado de la cuota y el ingreso de Caja forman una sola
        # operación financiera, incluso cuando se registra desde el Admin.
        with transaction.atomic():
            if self.pago_id:
                self.pago = Pago.objects.select_for_update().get(pk=self.pago_id)
            self.full_clean()
            super().save(*args, **kwargs)
            self.pago.recalcular_estado()
            CajaMovimiento.crear_ingreso_desde_abono(self)

    def __str__(self):
        return f"{self.pago} · {self.monto}"


class CategoriaCaja(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "categoría de caja"
        verbose_name_plural = "categorías de caja"

    def __str__(self):
        return self.nombre


class CajaMovimiento(models.Model):
    class Tipo(models.TextChoices):
        INGRESO = "Ingreso", "Ingreso"
        EGRESO = "Egreso", "Egreso"

    fecha = models.DateField(default=date.today)
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    geriatrico = models.ForeignKey(Geriatrico, on_delete=models.PROTECT, related_name="movimientos_caja", null=True, blank=True)
    residente = models.ForeignKey(Residente, on_delete=models.PROTECT, blank=True, null=True, related_name="movimientos_caja")
    pago = models.ForeignKey(Pago, on_delete=models.PROTECT, blank=True, null=True, related_name="movimientos_caja")
    abono = models.OneToOneField(PagoParcial, on_delete=models.PROTECT, blank=True, null=True, related_name="movimiento_caja")
    categoria = models.ForeignKey(CategoriaCaja, on_delete=models.PROTECT, blank=True, null=True, related_name="movimientos")
    descripcion = models.CharField(max_length=255, blank=True)
    proveedor_beneficiario = models.CharField(max_length=150, blank=True)
    importe = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    medio_pago = models.CharField(max_length=30, choices=Pago.MedioPago.choices, blank=True)
    observaciones = models.TextField(blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="movimientos_caja")

    class Meta:
        ordering = ["-fecha", "-pk"]
        verbose_name = "movimiento de caja"
        verbose_name_plural = "movimientos de caja"

    @property
    def nombre_geriatrico(self):
        return self.geriatrico.nombre if self.geriatrico else "Todos los geriátricos"

    def clean(self):
        super().clean()
        if self.fecha and self.fecha > date.today():
            raise ValidationError({"fecha": "La fecha del egreso no puede ser posterior al día de hoy."})
        if self.tipo == self.Tipo.EGRESO:
            if not self.categoria_id:
                raise ValidationError({"categoria": "Seleccioná una categoría para el egreso."})
            saldo = self.saldo_actual(excluir_pk=self.pk)
            if self.importe > saldo:
                raise ValidationError({"importe": "El egreso no puede superar el saldo disponible."})

    def save(self, *args, **kwargs):
        fecha = self._meta.get_field("fecha").to_python(self.fecha) if self.fecha else None
        if fecha and fecha > date.today():
            raise ValidationError({"fecha": "La fecha del egreso no puede ser posterior al día de hoy."})
        super().save(*args, **kwargs)

    @classmethod
    def saldo_actual(cls, excluir_pk=None):
        movimientos = cls.objects.all()
        if excluir_pk:
            movimientos = movimientos.exclude(pk=excluir_pk)
        ingresos = movimientos.filter(tipo=cls.Tipo.INGRESO).aggregate(total=Sum("importe"))["total"] or Decimal("0.00")
        egresos = movimientos.filter(tipo=cls.Tipo.EGRESO).aggregate(total=Sum("importe"))["total"] or Decimal("0.00")
        return ingresos - egresos

    @classmethod
    def crear_ingreso_desde_abono(cls, abono):
        return cls.objects.get_or_create(
            abono=abono,
            defaults={
                "fecha": abono.fecha_pago,
                "tipo": cls.Tipo.INGRESO,
                "geriatrico": abono.pago.residente.geriatrico,
                "residente": abono.pago.residente,
                "pago": abono.pago,
                "descripcion": f"Abono de {abono.pago.residente}",
                "importe": abono.monto,
                "medio_pago": abono.medio_pago,
                "observaciones": abono.observaciones,
                "usuario": abono.usuario,
            },
        )

    @classmethod
    def resumen_fecha(cls, fecha):
        movimientos = cls.objects.filter(fecha=fecha)
        ingresos = movimientos.filter(tipo=cls.Tipo.INGRESO).aggregate(total=Sum("importe"))["total"] or Decimal("0.00")
        egresos = movimientos.filter(tipo=cls.Tipo.EGRESO).aggregate(total=Sum("importe"))["total"] or Decimal("0.00")
        saldo_inicial = cls.objects.filter(fecha__lt=fecha, tipo=cls.Tipo.INGRESO).aggregate(total=Sum("importe"))["total"] or Decimal("0.00")
        saldo_inicial -= cls.objects.filter(fecha__lt=fecha, tipo=cls.Tipo.EGRESO).aggregate(total=Sum("importe"))["total"] or Decimal("0.00")
        return {"saldo_inicial": saldo_inicial, "ingresos": ingresos, "egresos": egresos, "saldo_final": saldo_inicial + ingresos - egresos, "cantidad_cobros": movimientos.filter(tipo=cls.Tipo.INGRESO).count(), "cantidad_egresos": movimientos.filter(tipo=cls.Tipo.EGRESO).count()}

    @classmethod
    def resumen_mes(cls, fecha, geriatrico=None):
        inicio = fecha.replace(day=1)
        movimientos = cls.objects.filter(fecha__gte=inicio, fecha__lte=fecha)
        if geriatrico:
            movimientos = movimientos.filter(geriatrico=geriatrico)
        ingresos = movimientos.filter(tipo=cls.Tipo.INGRESO).aggregate(total=Sum("importe"))["total"] or Decimal("0.00")
        egresos = movimientos.filter(tipo=cls.Tipo.EGRESO).aggregate(total=Sum("importe"))["total"] or Decimal("0.00")
        saldo_inicial = cls.saldo_actual_hasta(inicio, geriatrico=geriatrico)
        return {"saldo_inicial": saldo_inicial, "ingresos": ingresos, "egresos": egresos, "resultado": ingresos - egresos, "saldo_final": saldo_inicial + ingresos - egresos, "cantidad_cobros": movimientos.filter(tipo=cls.Tipo.INGRESO).count(), "cantidad_egresos": movimientos.filter(tipo=cls.Tipo.EGRESO).count()}

    @classmethod
    def saldo_actual_hasta(cls, fecha, geriatrico=None):
        movimientos = cls.objects.filter(fecha__lt=fecha)
        if geriatrico:
            movimientos = movimientos.filter(geriatrico=geriatrico)
        ingresos = movimientos.filter(tipo=cls.Tipo.INGRESO).aggregate(total=Sum("importe"))["total"] or Decimal("0.00")
        egresos = movimientos.filter(tipo=cls.Tipo.EGRESO).aggregate(total=Sum("importe"))["total"] or Decimal("0.00")
        return ingresos - egresos


class GastoRecurrente(models.Model):
    """Definición vigente de un gasto que se puede pagar una vez por período."""

    concepto = models.CharField(max_length=180)
    importe_estimado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    dia_vencimiento = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(31)]
    )
    geriatrico = models.ForeignKey(
        Geriatrico,
        on_delete=models.PROTECT,
        related_name="gastos_recurrentes",
        null=True,
        blank=True,
    )
    categoria = models.ForeignKey(
        CategoriaCaja,
        on_delete=models.PROTECT,
        related_name="gastos_recurrentes",
    )
    activo = models.BooleanField(default=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ["concepto"]
        verbose_name = "gasto recurrente"
        verbose_name_plural = "gastos recurrentes"

    @property
    def nombre_geriatrico(self):
        return self.geriatrico.nombre if self.geriatrico else "Todos los geriátricos"

    def __str__(self):
        return self.concepto


class GastoRecurrenteMensual(models.Model):
    """Instantánea del gasto efectivamente pagado en un período determinado."""

    gasto_recurrente = models.ForeignKey(
        GastoRecurrente,
        on_delete=models.PROTECT,
        related_name="historial_mensual",
    )
    periodo = models.CharField(max_length=7)
    concepto = models.CharField(max_length=180)
    importe_estimado = models.DecimalField(max_digits=12, decimal_places=2)
    importe_real = models.DecimalField(max_digits=12, decimal_places=2)
    dia_vencimiento = models.PositiveSmallIntegerField()
    geriatrico = models.ForeignKey(
        Geriatrico,
        on_delete=models.PROTECT,
        related_name="gastos_recurrentes_mensuales",
        null=True,
        blank=True,
    )
    categoria = models.ForeignKey(CategoriaCaja, on_delete=models.PROTECT)
    observaciones = models.TextField(blank=True)
    fecha_pago = models.DateField()
    movimiento_caja = models.OneToOneField(
        CajaMovimiento,
        on_delete=models.PROTECT,
        related_name="gasto_recurrente_mensual",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-periodo", "concepto"]
        verbose_name = "pago mensual de gasto recurrente"
        verbose_name_plural = "pagos mensuales de gastos recurrentes"
        constraints = [
            models.UniqueConstraint(
                fields=["gasto_recurrente", "periodo"],
                name="gasto_recurrente_unico_por_periodo",
            ),
        ]

    @property
    def nombre_geriatrico(self):
        return self.geriatrico.nombre if self.geriatrico else "Todos los geriátricos"

    def __str__(self):
        return f"{self.concepto} · {self.periodo}"


class CajaCierre(models.Model):
    fecha = models.DateField()
    geriatrico = models.ForeignKey(Geriatrico, on_delete=models.PROTECT, related_name="cierres_caja", null=True, blank=True)
    saldo_inicial = models.DecimalField(max_digits=12, decimal_places=2)
    ingresos = models.DecimalField(max_digits=12, decimal_places=2)
    egresos = models.DecimalField(max_digits=12, decimal_places=2)
    resultado = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    saldo_final = models.DecimalField(max_digits=12, decimal_places=2)
    cantidad_cobros = models.PositiveIntegerField()
    cantidad_egresos = models.PositiveIntegerField()
    cerrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    cerrado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "cierre de caja"
        verbose_name_plural = "cierres de caja"
        constraints = [
            models.UniqueConstraint(fields=["fecha", "geriatrico"], name="cierre_unico_por_geriatrico_y_mes"),
        ]

    @property
    def nombre_geriatrico(self):
        return self.geriatrico.nombre if self.geriatrico else "Todos los geriátricos"


class ConfiguracionInstitucional(models.Model):
    nombre_institucion = models.CharField(max_length=150, default="Dulce Atardecer")
    direccion = models.CharField(max_length=255, blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    cuit = models.CharField(max_length=20, blank=True)
    logo = models.FileField(upload_to="logos/", blank=True, null=True)
    dia_vencimiento_defecto = models.PositiveSmallIntegerField(default=10)
    concepto_cuota_defecto = models.CharField(max_length=150, default="Cuota mensual")
    moneda = models.CharField(max_length=10, default="ARS")
    observaciones = models.TextField(blank=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "configuración institucional"
        verbose_name_plural = "configuración institucional"

    def __str__(self):
        return self.nombre_institucion


class ObraSocial(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "obra social / prepaga"
        verbose_name_plural = "obras sociales / prepagas"

    def __str__(self):
        return self.nombre


class MedioPagoConfiguracion(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "medio de pago"
        verbose_name_plural = "medios de pago"

    def __str__(self):
        return self.nombre


class PorcentajeActualizacion(models.Model):
    porcentaje = models.DecimalField(max_digits=6, decimal_places=2, unique=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["porcentaje"]
        verbose_name = "porcentaje de actualización"
        verbose_name_plural = "porcentajes de actualización"

    def __str__(self):
        return f"{self.porcentaje}%"


class HistorialEnvioEmail(models.Model):
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    destinatario = models.EmailField()
    documento = models.CharField(max_length=100)
    resultado = models.CharField(max_length=20)
    error = models.TextField(blank=True)


class Personal(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = "Activo", "Activo"
        LICENCIA = "Licencia", "Licencia"
        VACACIONES = "Vacaciones", "Vacaciones"
        BAJA = "Baja", "Baja"

    class Cargo(models.TextChoices):
        ENFERMERO = "Enfermero/a", "Enfermero/a"
        CUIDADOR = "Cuidador/a", "Cuidador/a"
        MUCAMA = "Mucama", "Mucama"
        COCINERO = "Cocinero/a", "Cocinero/a"
        ADMINISTRATIVO = "Administrativo/a", "Administrativo/a"
        OTRO = "Otro", "Otro"

    nombre_completo = models.CharField(max_length=150)
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="perfil_personal")
    dni = models.CharField(max_length=20, unique=True, validators=[RegexValidator(r"^\d+$", "El DNI solo puede contener números.")])
    cargo = models.CharField(max_length=30, choices=Cargo.choices)
    turno_habitual = models.CharField(max_length=10, choices=[("Mañana", "Mañana"), ("Tarde", "Tarde"), ("Noche", "Noche")])
    telefono = models.CharField(max_length=30, blank=True, validators=[RegexValidator(r"^\d+$", "El teléfono solo puede contener números.")])
    cuil = models.CharField(max_length=30, blank=True)
    inicio_contrato = models.DateField()
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ACTIVO)
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ["nombre_completo"]
        verbose_name = "personal"
        verbose_name_plural = "personal"

    def __str__(self): return self.nombre_completo


class PerfilUsuario(models.Model):
    """Datos de presentación opcionales, independientes de la ficha laboral."""

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil")
    foto = models.ImageField(upload_to="perfiles/", blank=True, null=True)

    class Meta:
        verbose_name = "perfil de usuario"
        verbose_name_plural = "perfiles de usuario"

    def __str__(self):
        return f"Perfil de {self.usuario}"


class GrillaTurnos(models.Model):
    mes = models.PositiveSmallIntegerField()
    anio = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["mes", "anio"], name="grilla_unica_por_mes")]


class AsignacionTurno(models.Model):
    class Codigo(models.TextChoices):
        M = "M", "Mañana (7-15h)"
        T = "T", "Tarde (15-23h)"
        N = "N", "Noche (23-7h)"
        F = "F", "Franco"
        L = "L", "Licencia"
        V = "V", "Vacaciones"

    grilla = models.ForeignKey(GrillaTurnos, on_delete=models.CASCADE, related_name="asignaciones")
    personal = models.ForeignKey(Personal, on_delete=models.CASCADE, related_name="turnos")
    dia = models.PositiveSmallIntegerField()
    codigo = models.CharField(max_length=1, choices=Codigo.choices, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["grilla", "personal", "dia"], name="turno_unico_por_dia")]


class Tarea(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "Pendiente", "Pendiente"
        EN_PROCESO = "En proceso", "En proceso"
        COMPLETADA = "Completada", "Completada"

    class Turno(models.TextChoices):
        MANANA = "M", "Mañana"
        TARDE = "T", "Tarde"
        NOCHE = "N", "Noche"

    titulo = models.CharField(max_length=180)
    descripcion = models.TextField(blank=True)
    asignada_a = models.ForeignKey(Personal, on_delete=models.PROTECT, related_name="tareas")
    fecha = models.DateField()
    turno = models.CharField(max_length=1, choices=Turno.choices)
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.PENDIENTE)
    observacion_completado = models.TextField(blank=True)
    completada_en = models.DateTimeField(blank=True, null=True)
    completada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="tareas_completadas")
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fecha", "turno", "titulo"]
        verbose_name = "tarea"
        verbose_name_plural = "tareas"

    @property
    def vencida(self):
        return self.estado != self.Estado.COMPLETADA and self.fecha < date.today()

    def completar(self, usuario, observacion=""):
        self.estado = self.Estado.COMPLETADA
        self.observacion_completado = observacion
        self.completada_en = timezone.now()
        self.completada_por = usuario
        self.save(update_fields=("estado", "observacion_completado", "completada_en", "completada_por"))

    def __str__(self):
        return self.titulo


class NormaPolitica(models.Model):
    titulo = models.CharField(max_length=180)
    contenido = models.TextField()
    documento = models.FileField(upload_to="normas/", blank=True, null=True)
    publicada_en = models.DateTimeField(auto_now_add=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["-publicada_en"]
        verbose_name = "norma o política"
        verbose_name_plural = "normas y políticas"

    def __str__(self):
        return self.titulo


class LecturaNormaPolitica(models.Model):
    norma = models.ForeignKey(NormaPolitica, on_delete=models.CASCADE, related_name="lecturas")
    personal = models.ForeignKey(Personal, on_delete=models.CASCADE, related_name="lecturas_normas")
    leido_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("norma", "personal"), name="lectura_norma_unica_por_personal")]
        verbose_name = "lectura de norma"
        verbose_name_plural = "lecturas de normas"


def vencimiento_invitacion():
    return timezone.now() + timedelta(hours=48)


class InvitacionPersonal(models.Model):
    personal = models.OneToOneField(Personal, on_delete=models.CASCADE, related_name="invitacion")
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    creada_en = models.DateTimeField(auto_now_add=True)
    vence_en = models.DateTimeField(default=vencimiento_invitacion)
    utilizada_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "invitación de personal"
        verbose_name_plural = "invitaciones de personal"

    @property
    def vigente(self):
        return not self.utilizada_en and self.vence_en > timezone.now()

    def clean(self):
        if self.personal_id and self.personal.usuario_id:
            raise ValidationError("No se puede invitar a una empleada que ya tiene una cuenta activa.")

    def regenerar(self):
        self.token = uuid.uuid4()
        self.vence_en = vencimiento_invitacion()
        self.utilizada_en = None
        self.save(update_fields=("token", "vence_en", "utilizada_en"))

    def __str__(self):
        return f"Invitación de {self.personal}"
