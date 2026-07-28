from django.contrib import admin
from django import forms
from django.http import JsonResponse
from django.urls import path, reverse
from .models import CajaCierre, CajaMovimiento, CategoriaCaja, ConfiguracionInstitucional, Geriatrico, HistorialEnvioEmail, Pago, PagoParcial, Residente


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
            geriatrico_id = self.data.get(self.add_prefix("geriatrico")) or getattr(self.instance, "geriatrico_id", None)
            self.fields["habitacion"] = forms.ChoiceField(
                required=False,
                choices=ResidenteAdmin.habitaciones_disponibles(geriatrico_id, self.instance.pk),
            )
            self.fields["habitacion"].widget.attrs["data-habitaciones-url"] = reverse(
                "admin:institucional_residente_habitaciones_disponibles", args=[0]
            )

    form = ResidenteAdminForm
    list_display = ("apellido", "nombre", "dni", "geriatrico", "estado")
    list_filter = ("geriatrico", "estado")
    search_fields = ("nombre", "apellido", "dni")

    @staticmethod
    def habitaciones_disponibles(geriatrico_id, residente_id=None):
        if not geriatrico_id:
            return [("", "Seleccioná primero un geriátrico")]
        try:
            geriatrico = Geriatrico.objects.get(pk=geriatrico_id)
        except (Geriatrico.DoesNotExist, ValueError):
            return [("", "Seleccioná primero un geriátrico")]
        ocupadas = Residente.objects.filter(
            geriatrico=geriatrico,
            estado=Residente.Estado.ACTIVO,
        ).exclude(habitacion="")
        if residente_id:
            ocupadas = ocupadas.exclude(pk=residente_id)
        habitaciones_ocupadas = set(ocupadas.values_list("habitacion", flat=True))
        return [("", "---------")] + [
            (str(numero), f"Habitación {numero}")
            for numero in range(1, geriatrico.capacidad_total + 1)
            if str(numero) not in habitaciones_ocupadas
        ]

    def get_urls(self):
        urls = super().get_urls()
        personalizados = [
            path(
                "habitaciones-disponibles/<int:geriatrico_id>/",
                self.admin_site.admin_view(self.habitaciones_disponibles_view),
                name="institucional_residente_habitaciones_disponibles",
            ),
        ]
        return personalizados + urls

    def habitaciones_disponibles_view(self, request, geriatrico_id):
        residente_id = request.GET.get("residente_id")
        return JsonResponse({"habitaciones": self.habitaciones_disponibles(geriatrico_id, residente_id)})

    class Media:
        js = ("institucional/js/residente_admin.js", "institucional/js/residente_habitaciones_admin.js")


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_filter = ("residente__geriatrico", "estado", "periodo")
    search_fields = ("residente__nombre", "residente__apellido", "residente__dni")
    readonly_fields = ("estado",)
    list_display = ("residente", "geriatrico", "periodo", "concepto", "monto", "total_abonado", "saldo_pendiente", "fecha_vencimiento", "estado")

    @admin.display(description="Geriátrico", ordering="residente__geriatrico__nombre")
    def geriatrico(self, pago):
        return pago.residente.geriatrico

    def get_queryset(self, request):
        Pago.actualizar_vencidos()
        return super().get_queryset(request).select_related("residente__geriatrico")


@admin.register(PagoParcial)
class PagoParcialAdmin(admin.ModelAdmin):
    list_display = ("pago", "monto", "fecha_pago", "medio_pago")
    search_fields = ("pago__residente__nombre", "pago__residente__apellido", "pago__residente__dni")

    def save_model(self, request, obj, form, change):
        if not obj.usuario_id:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)


@admin.register(CajaMovimiento)
class CajaMovimientoAdmin(admin.ModelAdmin):
    list_display = ("fecha", "tipo", "geriatrico", "residente", "importe", "medio_pago", "usuario")
    list_filter = ("tipo", "geriatrico", "fecha")
    search_fields = ("residente__nombre", "residente__apellido", "descripcion", "proveedor_beneficiario")
    readonly_fields = ("tipo", "residente", "pago", "abono", "usuario")


@admin.register(CategoriaCaja)
class CategoriaCajaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activa")
    list_filter = ("activa",)
    search_fields = ("nombre",)


@admin.register(CajaCierre)
class CajaCierreAdmin(admin.ModelAdmin):
    list_display = ("fecha", "saldo_inicial", "ingresos", "egresos", "saldo_final", "cantidad_cobros", "cantidad_egresos")
    readonly_fields = ("fecha", "saldo_inicial", "ingresos", "egresos", "saldo_final", "cantidad_cobros", "cantidad_egresos", "cerrado_por", "cerrado_en")


@admin.register(ConfiguracionInstitucional)
class ConfiguracionInstitucionalAdmin(admin.ModelAdmin):
    list_display = ("nombre_institucion", "actualizado_en")


@admin.register(HistorialEnvioEmail)
class HistorialEnvioEmailAdmin(admin.ModelAdmin):
    list_display = ("fecha", "usuario", "destinatario", "documento", "resultado", "error")
    list_filter = ("resultado", "documento", "fecha")
    search_fields = ("destinatario", "documento", "error")
    readonly_fields = ("fecha", "usuario", "destinatario", "documento", "resultado", "error")
