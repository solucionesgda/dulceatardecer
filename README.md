# Gestión del geriátrico

Base Django para la administración institucional. Incluye autenticación, roles, geriátricos y configuración institucional; no incluye residentes, personal, turnos, pagos, caja, dashboards, reportes, importadores ni correos.

## Desarrollo

Crear y activar un entorno virtual, instalar dependencias y configurar las variables de entorno según `.env.example`.

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py cargar_datos_iniciales
python manage.py createsuperuser
python manage.py runserver
```

Asignar cada usuario a uno de los grupos desde `/admin/`: Administrador (gestión total), Secretaría (alta/edición y consulta) o Consulta (sólo lectura).

## Verificación

```bash
python manage.py check
python manage.py test
```
