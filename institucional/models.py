from django.db import models


class Geriatrico(models.Model):
    nombre = models.CharField(max_length=150)
    codigo = models.CharField(max_length=30, unique=True)
    direccion = models.CharField(max_length=255)
    capacidad_camas = models.PositiveIntegerField()
    activo = models.BooleanField(default=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "geriátrico"
        verbose_name_plural = "geriátricos"

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"


class ConfiguracionInstitucional(models.Model):
    nombre_institucion = models.CharField(max_length=150, default="Dulce Atardecer")
    observaciones = models.TextField(blank=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "configuración institucional"
        verbose_name_plural = "configuración institucional"

    def __str__(self):
        return self.nombre_institucion
