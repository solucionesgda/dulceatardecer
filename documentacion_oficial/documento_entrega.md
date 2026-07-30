# Documento de Entrega

Sistema de Gestión Dulce Atardecer · Versión 1.0

---

## Presentación

Dulce Atardecer cuenta con una aplicación web privada para centralizar la operación institucional, el seguimiento de residentes, la gestión administrativa y la coordinación diaria del personal.

El sistema utiliza datos reales de la base institucional y está preparado para ejecutarse en PythonAnywhere con archivos estáticos administrados por WhiteNoise.

## Objetivo y alcance

El objetivo es reducir registros dispersos y brindar trazabilidad sobre ocupación, residentes, pagos, caja, tareas y turnos. La versión entregada no incorpora módulos de farmacia, historia clínica, liquidación de sueldos, recibos fiscales ni restauración automática de backups.

## Módulos entregados

Dashboard: indicadores, gráficos, filtros por geriátrico/mes/año, pagos, caja, ocupación y tareas.

Residentes: alta web, ficha, capacidad y habitaciones, obra social, número de afiliado, cuenta corriente y estado de cuenta por email.

Pagos y Caja: cuotas, ajustes, abonos parciales, comprobantes, ingresos automáticos, egresos, cierre y categorías.

Personal, turnos, tareas, normas, notificaciones, perfil, configuración, reportes y PWA.

## Arquitectura y tecnologías

Django 5, Python 3.11, SQLite, Bootstrap 5, WhiteNoise, ReportLab, openpyxl y Chart.js. La aplicación institucional concentra modelos, formularios, vistas y reglas. Los PDFs se generan con ReportLab; los XLSX con openpyxl.

## Roles y seguridad

Administrador: gestión integral dentro de la aplicación y Django Admin para tareas administrativas avanzadas. Secretaría: operación diaria sin Configuración ni Administración. Consulta: lectura, exportación y sin acciones de gestión. Empleada: acceso exclusivo a sus tareas, normas, perfil, notificaciones y mis turnos.

Las credenciales de SMTP se cargan exclusivamente como variables de entorno. SECRET_KEY, DEBUG y ALLOWED_HOSTS también se administran por entorno.

## Entrega, hosting y soporte

La entrega incluye código fuente, migraciones, documentación técnica, manuales, archivos estáticos y PWA. La instalación prevista es PythonAnywhere. Ejecutar migraciones, cargar datos iniciales, crear superusuario, recolectar estáticos y recargar la aplicación.

Los accesos iniciales deben ser entregados por la persona administradora; este documento no incluye contraseñas. Datanova IT Solutions brinda soporte y actualizaciones bajo el acuerdo comercial vigente.

## Copias y actualizaciones

Administración puede descargar un ZIP desde Configuración con db.sqlite3, media si existe e instrucciones. La restauración es manual para evitar reemplazos accidentales. Antes de actualizar, generar un backup y ejecutar check, test y migrate en el entorno de destino.

---

Sistema desarrollado por

**Datanova IT Solutions**

www.datanovait.com
