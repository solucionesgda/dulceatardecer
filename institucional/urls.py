from django.contrib.auth import views as auth_views
from django.urls import path
from .views import AjusteMontoView, CajaListView, EgresoCajaCreateView, GenerarCuotasView, GeriatricoCreateView, GeriatricoDeleteView, GeriatricoListView, GeriatricoUpdateView, InicioView, PagoCreateView, PagoDetailView, PagoListView, PagoUpdateView, ResidenteDetailView, ResidenteListView

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", InicioView.as_view(), name="inicio"),
    path("residentes/", ResidenteListView.as_view(), name="residente_list"),
    path("residentes/<int:pk>/", ResidenteDetailView.as_view(), name="residente_detail"),
    path("pagos/", PagoListView.as_view(), name="pago_list"),
    path("pagos/registrar/", PagoCreateView.as_view(), name="pago_create"),
    path("pagos/generar-cuotas/", GenerarCuotasView.as_view(), name="generar_cuotas"),
    path("pagos/ajustar-montos/", AjusteMontoView.as_view(), name="ajuste_montos"),
    path("pagos/<int:pk>/", PagoDetailView.as_view(), name="pago_detail"),
    path("pagos/<int:pk>/editar/", PagoUpdateView.as_view(), name="pago_update"),
    path("caja/", CajaListView.as_view(), name="caja_list"),
    path("caja/egresos/nuevo/", EgresoCajaCreateView.as_view(), name="egreso_create"),
    path("geriátricos/", GeriatricoListView.as_view(), name="geriatrico_list"),
    path("geriátricos/nuevo/", GeriatricoCreateView.as_view(), name="geriatrico_create"),
    path("geriátricos/<int:pk>/editar/", GeriatricoUpdateView.as_view(), name="geriatrico_update"),
    path("geriátricos/<int:pk>/eliminar/", GeriatricoDeleteView.as_view(), name="geriatrico_delete"),
]
