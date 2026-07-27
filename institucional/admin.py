from django.contrib import admin
from django import forms
from .models import ConfiguracionInstitucional, Geriatrico, Residente


@admin.register(Geriatrico)
class GeriatricoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "capacidad_total", "camas_ocupadas", "camas_disponibles", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre", "codigo", "direccion")


@admin.register(Residente)
class ResidenteAdmin(admin.ModelAdmin):
    class ResidenteAdminForm(forms.ModelForm):
        class Meta:
            model = Residente
            fields = "__all__"

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields["email_contacto"].widget.attrs["placeholder"] = "ejemplo@correo.com"
            self.fields["telefono"].widget.attrs["placeholder"] = "3415123456"

    form = ResidenteAdminForm
    list_display = ("apellido", "nombre", "dni", "geriatrico", "estado")
    list_filter = ("geriatrico", "estado")
    search_fields = ("nombre", "apellido", "dni")

    class Media:
        js = ("institucional/js/residente_admin.js",)


@admin.register(ConfiguracionInstitucional)
class ConfiguracionInstitucionalAdmin(admin.ModelAdmin):
    list_display = ("nombre_institucion", "actualizado_en")
