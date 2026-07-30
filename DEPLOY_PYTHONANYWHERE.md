# Despliegue en PythonAnywhere

1. Crear un virtualenv con la versión de Python disponible y ejecutar `pip install -r requirements.txt`.
2. Definir `SECRET_KEY` (larga y aleatoria), `DEBUG=False`, `ALLOWED_HOSTS=tuusuario.pythonanywhere.com`, `SECURE_SSL_REDIRECT=True` y `SECURE_HSTS_SECONDS=31536000` como variables de entorno. No versionar `.env`. `SECRET_KEY` es obligatoria: la aplicación no inicia si falta.
3. Ejecutar `python manage.py migrate`, `python manage.py cargar_datos_iniciales` y `python manage.py createsuperuser`.
4. En la pestaña **Web**, configurar el virtualenv y editar el archivo WSGI para añadir el directorio del proyecto al `sys.path`, definir las variables anteriores (o cargarlas desde el entorno) y usar `config.wsgi.application`.
5. Ejecutar `python manage.py collectstatic --noinput`; en **Static files**, mapear la URL `/static/` al directorio absoluto `.../Pythonanywhere/staticfiles`.
6. Recargar la aplicación web desde la pestaña **Web**.

El valor de `ALLOWED_HOSTS` puede contener varios dominios separados por comas.
