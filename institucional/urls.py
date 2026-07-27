from django.contrib.auth import views as auth_views
from django.urls import path
from .views import GeriatricoCreateView, GeriatricoDeleteView, GeriatricoListView, GeriatricoUpdateView, InicioView

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", InicioView.as_view(), name="inicio"),
    path("geriátricos/", GeriatricoListView.as_view(), name="geriatrico_list"),
    path("geriátricos/nuevo/", GeriatricoCreateView.as_view(), name="geriatrico_create"),
    path("geriátricos/<int:pk>/editar/", GeriatricoUpdateView.as_view(), name="geriatrico_update"),
    path("geriátricos/<int:pk>/eliminar/", GeriatricoDeleteView.as_view(), name="geriatrico_delete"),
]
