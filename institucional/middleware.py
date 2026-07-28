from django.http import HttpResponseForbidden
from django.shortcuts import redirect


class AccesoEmpleadaMiddleware:
    """Limita las cuentas de Personal a su espacio operativo."""

    prefijos_permitidos = ("/tareas/", "/normas/", "/mi-perfil/", "/mis-turnos/", "/notificaciones/", "/logout/", "/static/", "/media/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = request.user
        if usuario.is_authenticated and not usuario.is_staff:
            try:
                usuario.perfil_personal
            except Exception:
                pass
            else:
                if request.path == "/":
                    return redirect("tarea_list")
                if not request.path.startswith(self.prefijos_permitidos):
                    return HttpResponseForbidden("Esta cuenta solo tiene acceso a Tareas, Normas y su perfil.")
        return self.get_response(request)
