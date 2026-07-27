from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models


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

    def __str__(self):
        return f"{self.residente} · {self.periodo} · {self.concepto}"

    def calcular_estado(self):
        if self.fecha_pago:
            return self.Estado.PAGADO
        if self.fecha_vencimiento < date.today():
            return self.Estado.VENCIDO
        return self.Estado.PENDIENTE

    def save(self, *args, **kwargs):
        self.estado = self.calcular_estado()
        super().save(*args, **kwargs)

    @classmethod
    def actualizar_vencidos(cls):
        cls.objects.filter(
            fecha_pago__isnull=True,
            fecha_vencimiento__lt=date.today(),
        ).exclude(estado=cls.Estado.VENCIDO).update(estado=cls.Estado.VENCIDO)


class ConfiguracionInstitucional(models.Model):
    nombre_institucion = models.CharField(max_length=150, default="Dulce Atardecer")
    observaciones = models.TextField(blank=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "configuración institucional"
        verbose_name_plural = "configuración institucional"

    def __str__(self):
        return self.nombre_institucion
