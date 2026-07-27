from django.contrib import admin
from .models import ConfiguracionInstitucional, Geriatrico, Residente


@admin.register(Geriatrico)
class GeriatricoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "capacidad_total", "camas_ocupadas", "camas_disponibles", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre", "codigo", "direccion")


@admin.register(Residente)
class ResidenteAdmin(admin.ModelAdmin):
    list_display = ("apellido", "nombre", "dni", "geriatrico", "estado")
    list_filter = ("geriatrico", "estado")
    search_fields = ("nombre", "apellido", "dni")


@admin.register(ConfiguracionInstitucional)
class ConfiguracionInstitucionalAdmin(admin.ModelAdmin):
    list_display = ("nombre_institucion", "actualizado_en")
