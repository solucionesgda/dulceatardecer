# Guía de instalación

1. Crear y activar un entorno virtual Python 3.11.
2. Instalar dependencias: `py -3.11 -m pip install -r requirements.txt`.
3. Definir `SECRET_KEY`, `DEBUG` y `ALLOWED_HOSTS`.
4. Ejecutar `py -3.11 manage.py migrate`.
5. Ejecutar `py -3.11 manage.py cargar_datos_iniciales`.
6. Crear el administrador con `py -3.11 manage.py createsuperuser`.
7. Ejecutar `py -3.11 manage.py collectstatic` para producción.

En PythonAnywhere, configurar el virtualenv, las variables de entorno y la ruta de archivos estáticos antes de recargar la aplicación web.
