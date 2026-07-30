# Manual de Usuario

Sistema de Gestión Dulce Atardecer · Versión 1.0

---

## Antes de comenzar

Ingresá por /login/ con tu usuario y contraseña. Usá una cuenta Administrador para las tareas que requieren Administración Django. No compartas credenciales ni backups.

## Dashboard

Sirve para leer el estado institucional. Elegí geriátrico, mes y año y presioná Aplicar filtros. Revisá ocupación, pagos, caja, personal, gráficos, deuda, últimos movimientos y cumplimiento de tareas.

Recomendación: revisar pagos vencidos y residentes con deuda antes de registrar nuevos movimientos.

## Residentes

Abrí Residentes y usá Nuevo residente. Completá DNI de ocho números, geriátrico, fecha de ingreso, contacto familiar, estado y datos de cobertura. La habitación debe estar disponible dentro de la capacidad del geriátrico.

La ficha muestra cuenta corriente, total facturado, abonado y deuda. Desde allí se puede iniciar el envío del estado de cuenta. La edición detallada se realiza desde Administración.

## Pagos, cuotas y abonos

En Pagos se filtra por residente/DNI, geriátrico, estado y período. Registrar pago crea una cuota individual. Generar cuotas del mes crea una cuota por residente activo con monto mensual y evita duplicados por residente/período.

Para cobrar, abrí Ver pago, completá monto, fecha, medio y observaciones en Registrar abono. El sistema permite pagos parciales, impide superar el saldo y recalcula Pendiente, Parcial, Pagado o Vencido.

Advertencia: la fecha de vencimiento de cuotas no puede ser anterior al día actual.

## Caja

Los ingresos no se cargan manualmente: se generan al registrar cada abono. Para un egreso usá Registrar egreso, seleccioná geriátrico, categoría, proveedor o beneficiario, importe y medio de pago. El importe no puede superar el saldo disponible.

Cerrar caja crea o actualiza el resumen del día con saldo inicial, ingresos, egresos, saldo final y cantidades. Usá filtros por fecha, geriátrico, categoría, proveedor y medio de pago.

## Personal, invitaciones y turnos

Personal lista empleados, estado laboral y estado de acceso. Una cuenta staff puede crear empleado/a y generar, copiar o regenerar invitaciones. El enlace vence a las 48 horas y se usa una sola vez.

Turnos ofrece la grilla mensual editable M, T, N, F, L y V. Elegí mes/año, cargá códigos por empleada y guardá los cambios. M=07:00-15:00, T=15:00-23:00 y N=23:00-07:00.

## Tareas y normas

Las tareas y normas se administran desde Administración Django. El panel de tareas resume pendientes, completadas, vencidas y cumplimiento. Las empleadas solo ven sus propias tareas y pueden completar con observación.

## Reportes, exportaciones y emails

Residentes, Pagos, Caja, Personal y Turnos ofrecen exportación PDF y Excel. Los enlaces conservan filtros. Pagos permite descargar comprobante PDF y abrir una confirmación antes de enviarlo por email. Residentes permite enviar el estado de cuenta.

Verificá destinatario, asunto y mensaje antes de Enviar. El resultado queda en el historial de envíos de Configuración.

## Configuración, usuarios y cierre

Configuración permite actualizar institución, logo, vencimiento/concepto de cuota, moneda y catálogos visibles. SMTP se define solo en variables de entorno. Backups requieren cuenta staff.

Para usuarios y grupos usá Django Admin. Asigná Administrador, Secretaría o Consulta según el nivel requerido. Cerrá sesión desde el pie del menú al finalizar.

---

Sistema desarrollado por

**Datanova IT Solutions**

www.datanovait.com
