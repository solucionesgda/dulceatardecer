# Guía de backup y restauración

## Generar

Un administrador abre **Configuración > Copias de seguridad** y presiona **Generar y descargar backup**. El ZIP contiene `db.sqlite3`, la carpeta `media/` si existe y estas instrucciones. Los respaldos locales se guardan fuera del control de versiones en `backups/`.

## Restaurar manualmente

1. Detener o poner en mantenimiento la aplicación.
2. Conservar una copia del `db.sqlite3` y `media/` actuales.
3. Extraer el ZIP en una carpeta temporal.
4. Reemplazar `db.sqlite3` por el archivo del ZIP.
5. Copiar el contenido de `media/` del ZIP sobre la carpeta `media/` de la instalación.
6. Verificar permisos de lectura/escritura y reiniciar la aplicación.

No existe restauración desde la web: evita reemplazar la base accidentalmente.
