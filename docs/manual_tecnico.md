# Manual técnico

El proyecto usa Django, SQLite, Bootstrap 5, ReportLab y openpyxl. La aplicación principal es `institucional`.

- Configuración: `config/settings.py`.
- Rutas: `institucional/urls.py`.
- Modelos y reglas: `institucional/models.py`.
- El middleware `AccesoEmpleadaMiddleware` restringe las cuentas vinculadas a Personal.
- Las notificaciones se calculan desde datos existentes en `institucional/context_processors.py`.

Ejecutá `py -3.11 manage.py check` y `py -3.11 manage.py test` antes de desplegar. Las credenciales se configuran por variables de entorno o en la configuración SMTP, nunca en el código.
