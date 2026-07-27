from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView
from .forms import GeriatricoForm
from .models import Geriatrico


class InicioView(LoginRequiredMixin, TemplateView):
    template_name = "institucional/inicio.html"


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
