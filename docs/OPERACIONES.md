# Tone Dashboard 1.1 · operación y recuperación

La interfaz y las operaciones siguen compartidas por web, iOS y macOS. No se añaden servicios LaunchAgent. La versión pública es 1.1.0, sin sufijo de compilación.

## Datos y actualización

Se mantienen las tablas y los historiales originales. Las tablas de órdenes, revisiones, reglas y actividad se crean de forma aditiva. El historial reciente tiene paginación por identificador y los trabajos activos se consultan independientemente del límite del historial.

El actualizador legado `server/scripts/update_macos.py` ya impedía actualizaciones parciales dentro del monorepositorio; conserva esa protección. Actualizar desde la raíz, instalar `requirements.txt` y ejecutar `bash scripts/install-macos-services.sh`, con las transferencias terminadas. Los archivos `.env` no se sustituyen.

## Descargas

- Los controles de URL se guardan en SQLite y los ejecuta el bot existente. Un HTTP 202 indica una orden pendiente, no una transferencia detenida. La interfaz muestra la última orden y el estado confirmado.
- Pausar y cancelar conservan los parciales. Reanudar y reintentar verifican el estado actual, los destinos públicos, los redireccionamientos y la identidad remota. Los parciales antiguos sin validador se vuelven a descargar desde cero; no se unen bytes sin conocer su identidad.
- Los servidores sin ETag fuerte ni Last-Modified requieren empezar desde cero tras una interrupción. Un servidor que ignore Range también provoca reinicio del contenido.
- Se conserva un margen de 256 MiB de disco libre. Se comprueba el tamaño conocido antes de escribir y el espacio durante el streaming.
- Los controles aMule usan EC sobre loopback. «Detener» utiliza STOP, no DELETE: no elimina los parciales. Se valida el hash contra la cola actual y se vuelve a leer tras la respuesta del motor. La confirmación de la orden no significa que se haya completado la descarga.
- La cancelación de una lectura de red puede tardar hasta el timeout de la conexión.

## Revisar archivos

Más → Revisar archivos muestra la cuarentena existente y los archivos que Organizer no ha podido clasificar. La decisión incluye título, categoría y, para series/anime, temporada y episodio. Se comprueba que el archivo no haya cambiado, sigue dentro de cuarentena y no sea un enlace simbólico. Se conservan estabilidad, comprobación de destino y subida temporal. Un destino existente no se reemplaza.

Las reglas recordadas son fragmentos literales del nombre, sin expresiones regulares ni comandos. Conservan título/categoría/año; nunca reutilizan el episodio de un archivo anterior. La extracción de temporada y episodio sigue haciéndose por archivo. Las reglas se pueden eliminar en esta sección.

El historial de actividad permite abrir el recorrido de un archivo y conserva la relación al pasar a cuarentena. «Enviado a biblioteca Emby» confirma la transferencia al destino: no certifica que el servidor haya terminado de indexarlo. No se reconstruye retrospectivamente una etapa de la que no existía registro.

## Alertas

Cada seguimiento tiene un botón Alertas. Se configura precio máximo, bajada mínima, reposición y silencio. Una regla general se aplica a todos los destinatarios; una regla individual la sustituye para ese destinatario. Los filtros se combinan. Las preferencias por defecto conservan el comportamiento previo. No se envían ofertas antiguas al guardar. Silenciar retira avisos pendientes del producto/destinatario, conservando el historial publicado.

## Diagnóstico y copias

Más → Diagnóstico distingue procesos en ejecución de lecturas disponibles; consulta EC de aMule, disponibilidad de Orbit, antigüedad de lecturas Emby y resultado de las copias. No pretende certificar la entrega de un mensaje de Telegram sin enviarlo. La exportación no incluye contraseñas, tokens, cookies, enlaces privados, rutas locales ni logs completos. Las apps ofrecen guardar/compartir el JSON generado por el origen del Dashboard.

El proceso existente del Dashboard crea una copia diaria de cada SQLite mediante la API online de backup, incluyendo datos confirmados del WAL. Comprueba integridad y conserva las 14 últimas copias de cada base en `~/.local/share/emby_organizer/backups/`. Las carpetas se crean privadas y los archivos con modo 0600. Las copias permanecen en el mismo Mac: protegen frente a errores de datos, no frente a la pérdida de ese disco.

Restauración segura a una ruta **nueva**:

```sh
.venv/bin/python scripts/restore-backup.py /ruta/copia.sqlite3 /ruta/recuperada.sqlite3
```

La herramienta rechaza sobrescribir un archivo existente y comprueba integridad. Detener los servicios afectados antes de sustituir una base activa; conservar su copia anterior junto con sus archivos WAL/SHM. No copiar una base activa con `cp` ni sustituirla mientras se escribe.

## Aislamiento opcional de Orbit

**Preparado y desactivado por decisión del propietario.** La conexión actual se conserva. No activar hasta disponer de un segundo dominio HTTPS, preferiblemente del mismo dominio principal para compatibilidad de cookies, que llegue al listener existente del Dashboard.

Configurar `DASHBOARD_PUBLIC_ORIGIN=https://dashboard.ejemplo` y `ORBIT_ISOLATED_ORIGIN=https://orbit.ejemplo` en `.env`. El proxy frontal debe conservar Host y servir ambos HTTPS. El host aislado solo admite el proxy Orbit con una sesión específica; las APIs del Dashboard se rechazan incluso si recibe sus credenciales Basic. El Dashboard emite tickets de un solo uso, de 60 segundos, para establecer esa sesión. Los tickets no contienen la contraseña y no deben conservarse en registros del proxy frontal. La cookie es Secure, HttpOnly y limitada al host. Las sesiones expiran a las 12 horas y al reiniciar el proceso; se recuperan desde el Dashboard.

Antes de activar: probar ruta HTTPS, carga, cookies, WebSocket y reconexión en Safari y ambas apps con el dominio real. El lector y la autorización automática existentes siguen en el origen principal; las operaciones sensibles no se exponen en el host aislado. La funcionalidad no se considera validada en infraestructura real hasta completar esas pruebas. Dejar ambas variables vacías mantiene el funcionamiento anterior.

## Verificación

`bash scripts/check.sh` usa una base temporal para las pruebas del servidor. Incluye seguridad, protocolo aMule, revisión, recuperación de descargas, copias y preferencias. Los tests de Swift verifican el aislamiento por autoridad HTTPS y la migración del llavero sin copiar una credencial heredada a otro servidor.

CI ejecuta también `npm ci`, instala Chromium y realiza recorridos de navegador contra `scripts/ui-fixture.py`, un servidor ficticio que nunca accede a `.env`, aMule, Telegram ni los archivos del usuario y rechaza escrituras. Guarda capturas de diferentes tamaños como artefactos de CI. La prueba visual no sustituye las comprobaciones de dispositivos físicos.


## PS5 desde reposo · 1.1.1

«Ver código» y «Recordar dispositivo» comprueban la PS5 solo después de validar contraseña y origen. Si responde standby, se envía un único despertar Remote Play y se espera a Orbit antes de leer el código. El flujo es común para web, macOS e iOS; las apps instaladas lo reciben al recargar el Dashboard. No se ejecuta el jailbreak. La consola apagada o sin respuesta no se considera en reposo. Límite entre señales: 90 segundos por proceso y espera acotada.

El servidor usa `server/ps5_wake.py`; la tarea diaria usa el mismo módulo mediante su entrada de mantenimiento. El emparejamiento permanece fuera del repositorio en `~/.config/tone-maintenance/ps5-wake.json`, propio del usuario y permisos 600, con host fijo de la consola y su registration_key. Nunca enviar esta clave al navegador, Telegram o Git.

Validación: pruebas de estados, credencial ausente, permisos, protocolo, contraseña incorrecta sin despertar, espera limitada, ausencia de Orbit y limitación de intentos. Despertar físico validado en esta instalación; la disponibilidad de jailbreak y Orbit tras reposo debe verificarse por separado.

En macOS ejecutar `bash server/scripts/install-ps5-wake-helper.sh` y permitir Red local para TonePS5Wake cuando lo solicite. El Dashboard abre este asistente puntual mediante LaunchServices para respetar la identidad de privacidad del sistema. El asistente se cierra al terminar. Su código y el instalador se incluyen en el repositorio; la clave y la aplicación instalada son locales al Mac. Tras reemplazar el ejecutable, macOS puede pedir de nuevo el permiso.
