from django.http import HttpResponseForbidden
from django.shortcuts import redirect


class AccesoEmpleadaMiddleware:
    """Aplica la política de acceso en backend para personal y grupos."""

    prefijos_permitidos = ("/tareas/", "/normas/", "/mi-perfil/", "/mis-turnos/", "/notificaciones/", "/logout/", "/static/", "/media/")
    prefijos_administracion = ("/configuracion/", "/admin/")
    rutas_post_permitidas_consulta = ("/logout/", "/mi-perfil/")
    rutas_solo_gestion = (
        "/residentes/nuevo/", "/pagos/registrar/", "/pagos/generar-cuotas/",
        "/pagos/ajustar-montos/", "/caja/egresos/nuevo/", "/caja/gastos-recurrentes/", "/caja/categorias/",
        "/caja/cerrar/", "/personal/nuevo/", "/personal/adelantos/nuevo/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = request.user
        # El grupo funcional Administrador opera dentro de la aplicación. No
        # equivale a un administrador técnico de Django, aunque por datos
        # históricos alguno de esos usuarios tenga is_staff activado.
        if (
            usuario.is_authenticated
            and request.path.startswith("/admin/")
            and not usuario.is_superuser
            and usuario.groups.filter(name="Administrador").exists()
        ):
            return HttpResponseForbidden("Esta cuenta no tiene acceso al administrador de Django.")
        if usuario.is_authenticated and not usuario.is_staff:
            try:
                usuario.perfil_personal
            except Exception:
                grupos = set(usuario.groups.values_list("name", flat=True))
                if "Administrador" in grupos:
                    return self.get_response(request)
                if "Secretaría" in grupos:
                    if request.path.startswith(self.prefijos_administracion):
                        return HttpResponseForbidden("Esta cuenta no tiene acceso a Configuración ni Administración.")
                    return self.get_response(request)
                if "Consulta" in grupos:
                    if request.path.startswith(self.prefijos_administracion):
                        return HttpResponseForbidden("Esta cuenta es de solo consulta.")
                    if request.path.startswith(self.rutas_solo_gestion) or request.path.endswith("/editar/"):
                        return HttpResponseForbidden("Esta cuenta es de solo consulta.")
                    if request.method not in {"GET", "HEAD", "OPTIONS"} and not request.path.startswith(self.rutas_post_permitidas_consulta):
                        return HttpResponseForbidden("Esta cuenta es de solo consulta.")
                    return self.get_response(request)
                return HttpResponseForbidden("La cuenta no tiene un rol de acceso asignado.")
            else:
                if request.path == "/":
                    return redirect("tarea_list")
                if not request.path.startswith(self.prefijos_permitidos):
                    return HttpResponseForbidden("Esta cuenta solo tiene acceso a Tareas, Normas y su perfil.")
        return self.get_response(request)
