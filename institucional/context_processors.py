from datetime import date
from django.db.models import Count, Q
from django.utils import timezone

from .models import Comunicado, Geriatrico, InvitacionPersonal, LecturaComunicado, LecturaNormaPolitica, NormaPolitica, Pago, Personal, Residente, Tarea


def notificaciones(request):
    """Avisos derivados de datos existentes, sin persistir ni duplicar estados."""
    if not request.user.is_authenticated:
        return {"notificaciones": [], "notificaciones_total": 0}

    avisos = []
    if request.user.is_staff:
        vencidos = Pago.objects.filter(estado=Pago.Estado.VENCIDO).count()
        pendientes = Tarea.objects.exclude(estado=Tarea.Estado.COMPLETADA).count()
        tareas_vencidas = Tarea.objects.exclude(estado=Tarea.Estado.COMPLETADA, fecha__lt=date.today()).count()
        invitaciones = InvitacionPersonal.objects.filter(utilizada_en__isnull=True, vence_en__gte=timezone.now()).count()
        if vencidos:
            avisos.append({"texto": f"{vencidos} pago(s) vencido(s)", "tipo": "danger", "url": "/pagos/?estado=Vencido"})
        if pendientes:
            avisos.append({"texto": f"{pendientes} tarea(s) pendientes", "tipo": "warning", "url": "/tareas/"})
        if tareas_vencidas:
            avisos.append({"texto": f"{tareas_vencidas} tarea(s) vencidas", "tipo": "danger", "url": "/tareas/"})
        if invitaciones:
            avisos.append({"texto": f"{invitaciones} invitación(es) pendientes", "tipo": "info", "url": "/personal/"})
        geriatrico_qs = Geriatrico.objects.filter(capacidad_total__gt=0).annotate(
            ocupadas=Count("residentes", filter=Q(residentes__estado=Residente.Estado.ACTIVO))
        )
        for geriatrico in geriatrico_qs:
            ocupadas = geriatrico.ocupadas
            if ocupadas / geriatrico.capacidad_total > .9:
                avisos.append({"texto": f"{geriatrico.nombre}: ocupación superior al 90%", "tipo": "warning", "url": "/"})
    else:
        try:
            personal = request.user.perfil_personal
        except Personal.DoesNotExist:
            personal = None
        if personal:
            pendientes = Tarea.objects.filter(asignada_a=personal).exclude(estado=Tarea.Estado.COMPLETADA).count()
            vencidas = Tarea.objects.filter(asignada_a=personal, fecha__lt=date.today()).exclude(estado=Tarea.Estado.COMPLETADA).count()
            leidas = LecturaNormaPolitica.objects.filter(personal=personal).values_list("norma_id", flat=True)
            normas = NormaPolitica.objects.filter(activa=True).exclude(pk__in=leidas).count()
            comunicaciones_leidas = LecturaComunicado.objects.filter(personal=personal).values_list("comunicado_id", flat=True)
            comunicados = Comunicado.objects.filter(activo=True).filter(
                Q(geriatrico__isnull=True) | Q(geriatrico=personal.geriatrico)
            ).exclude(pk__in=comunicaciones_leidas).count()
            if pendientes:
                avisos.append({"texto": f"Tenés {pendientes} tarea(s) pendientes", "tipo": "warning", "url": "/tareas/"})
            if vencidas:
                avisos.append({"texto": f"Tenés {vencidas} tarea(s) vencidas", "tipo": "danger", "url": "/tareas/"})
            if normas:
                avisos.append({"texto": f"Hay {normas} norma(s) nueva(s) sin leer", "tipo": "info", "url": "/normas/"})
            if comunicados:
                avisos.append({"texto": f"Hay {comunicados} comunicado(s) nuevo(s) sin leer", "tipo": "info", "url": "/comunicados/"})
    return {"notificaciones": avisos, "notificaciones_total": len(avisos)}
