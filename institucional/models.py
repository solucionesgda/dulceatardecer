from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Sum
from django.conf import settings


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
    contacto_familiar = models.CharField(max_length=150, validators=[RegexValidator(r"^\d+$", "Ingrese únicamente números.")])
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

    def clean(self):
        super().clean()
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
        super().save(*args, **kwargs)
        if self.fecha_pago and not self.abonos.exists():
            PagoParcial.objects.create(
                pago=self, monto=self.monto, fecha_pago=self.fecha_pago,
                medio_pago=self.medio_pago, observaciones=self.observaciones,
            )
        self.recalcular_estado()

    def clean(self):
        super().clean()
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
        if self.pago_id:
            anteriores = PagoParcial.objects.filter(pago_id=self.pago_id)
            if self.pk:
                anteriores = anteriores.exclude(pk=self.pk)
            abonado = anteriores.aggregate(total=Sum("monto"))["total"] or Decimal("0.00")
            if abonado + self.monto > self.pago.monto:
                raise ValidationError({"monto": "El importe no puede superar el saldo pendiente."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        self.pago.recalcular_estado()
        CajaMovimiento.crear_ingreso_desde_abono(self)

    def __str__(self):
        return f"{self.pago} · {self.monto}"


class CajaMovimiento(models.Model):
    class Tipo(models.TextChoices):
        INGRESO = "Ingreso", "Ingreso"
        EGRESO = "Egreso", "Egreso"

    fecha = models.DateField(default=date.today)
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    geriatrico = models.ForeignKey(Geriatrico, on_delete=models.PROTECT, related_name="movimientos_caja")
    residente = models.ForeignKey(Residente, on_delete=models.PROTECT, blank=True, null=True, related_name="movimientos_caja")
    pago = models.ForeignKey(Pago, on_delete=models.PROTECT, blank=True, null=True, related_name="movimientos_caja")
    abono = models.OneToOneField(PagoParcial, on_delete=models.PROTECT, blank=True, null=True, related_name="movimiento_caja")
    categoria = models.CharField(max_length=100, blank=True)
    descripcion = models.CharField(max_length=255, blank=True)
    importe = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    medio_pago = models.CharField(max_length=30, choices=Pago.MedioPago.choices, blank=True)
    observaciones = models.TextField(blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="movimientos_caja")

    class Meta:
        ordering = ["-fecha", "-pk"]
        verbose_name = "movimiento de caja"
        verbose_name_plural = "movimientos de caja"

    def clean(self):
        super().clean()
        if self.tipo == self.Tipo.EGRESO:
            saldo = self.saldo_actual(excluir_pk=self.pk)
            if self.importe > saldo:
                raise ValidationError({"importe": "El egreso no puede superar el saldo disponible."})

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
                "categoria": "Cuota residente",
                "descripcion": f"Abono de {abono.pago.residente}",
                "importe": abono.monto,
                "medio_pago": abono.medio_pago,
                "observaciones": abono.observaciones,
                "usuario": abono.usuario,
            },
        )


class ConfiguracionInstitucional(models.Model):
    nombre_institucion = models.CharField(max_length=150, default="Dulce Atardecer")
    observaciones = models.TextField(blank=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "configuración institucional"
        verbose_name_plural = "configuración institucional"

    def __str__(self):
        return self.nombre_institucion
