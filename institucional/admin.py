from django.contrib import admin
from .models import ConfiguracionInstitucional, Geriatrico


@admin.register(Geriatrico)
class GeriatricoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "capacidad_camas", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre", "codigo", "direccion")


@admin.register(ConfiguracionInstitucional)
class ConfiguracionInstitucionalAdmin(admin.ModelAdmin):
    list_display = ("nombre_institucion", "actualizado_en")
