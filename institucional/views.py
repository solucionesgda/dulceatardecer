from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Count, Q, Sum
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView
from .forms import GeriatricoForm
from .models import Geriatrico, Residente


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
