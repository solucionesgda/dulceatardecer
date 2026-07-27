from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView
from .forms import AjusteMontoForm, GenerarCuotasForm, GeriatricoForm, PagoForm, PagoParcialForm
from .models import Geriatrico, Pago, PagoParcial, Residente


class InicioView(LoginRequiredMixin, TemplateView):
    template_name = "institucional/inicio.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        geriatrico_qs = Geriatrico.objects.annotate(
            residentes_activos=Count(
                "residentes",
                filter=Q(residentes__estado=Residente.Estado.ACTIVO),
            )
        )
        geriatrico_estadisticas = []
        for geriatrico in geriatrico_qs:
            disponibles = geriatrico.capacidad_total - geriatrico.residentes_activos
            geriatrico_estadisticas.append({
                "geriatrico": geriatrico,
                "ocupadas": geriatrico.residentes_activos,
                "disponibles": disponibles,
                "ocupacion": (geriatrico.residentes_activos / geriatrico.capacidad_total * 100),
            })
        capacidad_total = geriatrico_qs.aggregate(total=Sum("capacidad_total"))["total"] or 0
        residentes_activos = Residente.objects.filter(estado=Residente.Estado.ACTIVO).count()
        context.update({
            "residentes_activos": residentes_activos,
            "camas_ocupadas": residentes_activos,
            "camas_disponibles": capacidad_total - residentes_activos,
            "capacidad_total": capacidad_total,
            "geriatrico_estadisticas": geriatrico_estadisticas,
        })
        return context


class GeriatricoListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Geriatrico
    template_name = "institucional/geriatrico_list.html"
    permission_required = "institucional.view_geriatrico"


class GeriatricoCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Geriatrico
    form_class = GeriatricoForm
    template_name = "institucional/geriatrico_form.html"
    permission_required = "institucional.add_geriatrico"
    success_url = reverse_lazy("geriatrico_list")


class GeriatricoUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Geriatrico
    form_class = GeriatricoForm
    template_name = "institucional/geriatrico_form.html"
    permission_required = "institucional.change_geriatrico"
    success_url = reverse_lazy("geriatrico_list")


class GeriatricoDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Geriatrico
    template_name = "institucional/geriatrico_confirm_delete.html"
    permission_required = "institucional.delete_geriatrico"
    success_url = reverse_lazy("geriatrico_list")


class ResidenteListView(LoginRequiredMixin, ListView):
    model = Residente
    template_name = "institucional/residente_list.html"

    def get_queryset(self):
        queryset = Residente.objects.select_related("geriatrico")
        busqueda = self.request.GET.get("q", "").strip()
        geriatrico = self.request.GET.get("geriatrico", "")
        estado = self.request.GET.get("estado", "")
        if busqueda:
            queryset = queryset.filter(
                Q(nombre__icontains=busqueda)
                | Q(apellido__icontains=busqueda)
                | Q(dni__icontains=busqueda)
            )
        if geriatrico:
            queryset = queryset.filter(geriatrico_id=geriatrico)
        if estado:
            queryset = queryset.filter(estado=estado)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "geriatrico_opciones": Geriatrico.objects.all(),
            "estado_opciones": Residente.Estado.choices,
            "filtros": self.request.GET,
        })
        return context


class ResidenteDetailView(LoginRequiredMixin, DetailView):
    model = Residente
    template_name = "institucional/residente_detail.html"
    queryset = Residente.objects.select_related("geriatrico")


class PagoListView(LoginRequiredMixin, ListView):
    model = Pago
    template_name = "institucional/pago_list.html"

    def get_queryset(self):
        Pago.actualizar_vencidos()
        queryset = Pago.objects.select_related("residente__geriatrico")
        busqueda = self.request.GET.get("q", "").strip()
        geriatrico = self.request.GET.get("geriatrico", "")
        estado = self.request.GET.get("estado", "")
        periodo = self.request.GET.get("periodo", "").strip()
        if busqueda:
            queryset = queryset.filter(
                Q(residente__nombre__icontains=busqueda)
                | Q(residente__apellido__icontains=busqueda)
                | Q(residente__dni__icontains=busqueda)
            )
        if geriatrico:
            queryset = queryset.filter(residente__geriatrico_id=geriatrico)
        if estado:
            queryset = queryset.filter(estado=estado)
        if periodo:
            queryset = queryset.filter(periodo=periodo)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "geriatrico_opciones": Geriatrico.objects.all(),
            "estado_opciones": Pago.Estado.choices,
            "periodo_opciones": Pago.objects.order_by("-periodo").values_list("periodo", flat=True).distinct(),
            "filtros": self.request.GET,
        })
        return context


class PagoCreateView(LoginRequiredMixin, CreateView):
    model = Pago
    form_class = PagoForm
    template_name = "institucional/pago_form.html"

    def get_initial(self):
        initial = super().get_initial()
        residente = self.request.GET.get("residente")
        if residente:
            initial["residente"] = residente
        return initial

    def get_success_url(self):
        return reverse("pago_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["montos_residentes"] = {
            str(residente.pk): str(residente.monto_mensual or "")
            for residente in Residente.objects.only("pk", "monto_mensual")
        }
        return context


class PagoUpdateView(LoginRequiredMixin, UpdateView):
    model = Pago
    form_class = PagoForm
    template_name = "institucional/pago_form.html"

    def get_success_url(self):
        return reverse("pago_detail", kwargs={"pk": self.object.pk})


class PagoDetailView(LoginRequiredMixin, DetailView):
    model = Pago
    template_name = "institucional/pago_detail.html"
    queryset = Pago.objects.select_related("residente__geriatrico").prefetch_related("abonos")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["abono_form"] = kwargs.get("abono_form", PagoParcialForm())
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = PagoParcialForm(request.POST)
        if form.is_valid():
            abono = form.save(commit=False)
            abono.pago = self.object
            try:
                abono.save()
            except ValidationError as error:
                form.add_error("monto", error.message_dict.get("monto", ["No se pudo registrar el abono."])[0])
            else:
                messages.success(request, "Abono registrado correctamente.")
                return redirect("pago_detail", pk=self.object.pk)
        return self.render_to_response(self.get_context_data(abono_form=form))


class GenerarCuotasView(LoginRequiredMixin, TemplateView):
    template_name = "institucional/generar_cuotas.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = kwargs.get("form", GenerarCuotasForm())
        return context

    def post(self, request, *args, **kwargs):
        form = GenerarCuotasForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        residentes = Residente.objects.filter(estado=Residente.Estado.ACTIVO)
        if form.cleaned_data["geriatrico"]:
            residentes = residentes.filter(geriatrico=form.cleaned_data["geriatrico"])
        creados = existentes = sin_monto = 0
        for residente in residentes:
            if not residente.monto_mensual:
                sin_monto += 1
                continue
            try:
                _, creado = Pago.objects.get_or_create(
                    residente=residente,
                    periodo=form.cleaned_data["periodo"],
                    defaults={"concepto": "Cuota mensual", "monto": residente.monto_mensual, "fecha_vencimiento": form.cleaned_data["fecha_vencimiento"]},
                )
                if creado:
                    creados += 1
                else:
                    existentes += 1
            except IntegrityError:
                existentes += 1
        messages.success(request, f"Cuotas creadas: {creados}. Ya existentes: {existentes}. Sin monto configurado: {sin_monto}.")
        return redirect("pago_list")


class AjusteMontoView(LoginRequiredMixin, TemplateView):
    template_name = "institucional/ajuste_montos.html"

    def residentes_filtrados(self, data):
        residentes = Residente.objects.filter(estado=Residente.Estado.ACTIVO, monto_mensual__isnull=False)
        if data.get("geriatrico"):
            residentes = residentes.filter(geriatrico=data["geriatrico"])
        if data.get("obra_social"):
            residentes = residentes.filter(obra_social=data["obra_social"])
        return residentes

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"form": kwargs.get("form", AjusteMontoForm()), "vista_previa": kwargs.get("vista_previa", [])})
        return context

    def post(self, request, *args, **kwargs):
        form = AjusteMontoForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        residentes = self.residentes_filtrados(form.cleaned_data)
        factor = Decimal("1") + form.cleaned_data["porcentaje"] / Decimal("100")
        vista_previa = [(residente, (residente.monto_mensual * factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) for residente in residentes]
        if request.POST.get("accion") == "confirmar":
            for residente, nuevo_monto in vista_previa:
                residente.monto_mensual = nuevo_monto
                residente.save(update_fields=["monto_mensual"])
            messages.success(request, f"Se actualizaron {len(vista_previa)} montos mensuales.")
            return redirect("pago_list")
        return self.render_to_response(self.get_context_data(form=form, vista_previa=vista_previa))
