# Despliegue en PythonAnywhere

1. Crear un virtualenv con la versión de Python disponible y ejecutar `pip install -r requirements.txt`.
2. Definir `SECRET_KEY` (larga y aleatoria), `DEBUG=False`, `ALLOWED_HOSTS=tuusuario.pythonanywhere.com`, `SECURE_SSL_REDIRECT=True`, `SECURE_HSTS_SECONDS=31536000` y las variables `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_TLS`, `SMTP_USE_SSL`, `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME`. No versionar `.env`. `SECRET_KEY` es obligatoria: la aplicación no inicia si falta. SMTP no se almacena en la base de datos.
3. Ejecutar `python manage.py migrate`, `python manage.py cargar_datos_iniciales` y `python manage.py createsuperuser`.
4. En la pestaña **Web**, configurar el virtualenv y editar el archivo WSGI para añadir el directorio del proyecto al `sys.path`, definir las variables anteriores (o cargarlas desde el entorno) y usar `config.wsgi.application`.
5. Ejecutar `python manage.py collectstatic --noinput`; en **Static files**, mapear la URL `/static/` al directorio absoluto `.../Pythonanywhere/staticfiles`.
6. Recargar la aplicación web desde la pestaña **Web**.

El valor de `ALLOWED_HOSTS` puede contener varios dominios separados por comas.
