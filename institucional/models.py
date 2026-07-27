from django.core.exceptions import ValidationError
from django.db import models


class Geriatrico(models.Model):
    nombre = models.CharField(max_length=150)
    codigo = models.CharField(max_length=30, unique=True)
    direccion = models.CharField(max_length=255)
    capacidad_camas = models.PositiveIntegerField()
    capacidad_total = models.PositiveIntegerField()
    camas_ocupadas = models.PositiveIntegerField(default=0)
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
            models.CheckConstraint(
                condition=models.Q(camas_ocupadas__lte=models.F("capacidad_total")),
                name="ocupacion_no_supera_capacidad",
            ),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"

    @property
    def camas_disponibles(self):
        return self.capacidad_total - self.camas_ocupadas

    def clean(self):
        super().clean()
        if self.capacidad_total is not None and self.capacidad_total <= 0:
            raise ValidationError({"capacidad_total": "La capacidad total debe ser mayor que 0."})
        if (
            self.capacidad_total is not None
            and self.camas_ocupadas is not None
            and self.camas_ocupadas > self.capacidad_total
        ):
            raise ValidationError({"camas_ocupadas": "Las camas ocupadas no pueden superar la capacidad total."})


class ConfiguracionInstitucional(models.Model):
    nombre_institucion = models.CharField(max_length=150, default="Dulce Atardecer")
    observaciones = models.TextField(blank=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "configuración institucional"
        verbose_name_plural = "configuración institucional"

    def __str__(self):
        return self.nombre_institucion
