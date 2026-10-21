# Tone Dashboard · entrega 1.2.0

Rediseño compartido de web, macOS e iPhone sobre la arquitectura existente. Tema crema, superficies marfil, acciones verde bosque y estados legibles. No se cambia de framework ni se duplica la interfaz.

## Qué cambia

- Navegación directa a Anime, Tareas y Logs en escritorio; accesos a calendario y tareas desde Inicio también en móvil. Más agrupa biblioteca, automatización/sistema y preferencias.
- CSS consolidado en un sistema visual común. Formularios, segmentos, tablas móviles, tarjetas, botones, márgenes y rejillas adaptados; títulos y fechas de anime comparten filas sin recortar información.
- Tareas programadas descubre las cuatro automatizaciones actuales y muestra dos trabajos internos: copias verificadas y recuperación de aMule. Cada ficha explica su función, horario, requisitos y últimos resultados documentados. Las tareas nuevas aparecen al refrescar; los metadatos y el historial siguen una convención declarativa segura.
- Los horarios corresponden a Europe/Madrid. Activa significa programada, no ejecutada con éxito. Las fuentes inaccesibles y las actualizaciones aplazadas aparecen como parciales; la tarea semanal anime conserva «Sin registros» si no hay evidencia propia. No se atribuye a ella el historial del monitor de episodios.
- La sección es de solo lectura. No permite ejecutar, detener o modificar automatizaciones. El endpoint exige autenticación y oculta instrucciones completas, credenciales, rutas privadas y enlaces de informes.
- Contenedores Apple con fondos y barras claros a juego, mismos identificadores de app y almacenes persistentes. La versión pública es 1.2.0, sin número interno visible.

## Clean code aplicado

Calendario separado de operaciones generales y catálogo de tareas en su módulo. Transporte JSON común con plazo acotado y encabezados de escritura existentes; el alta de anime dispone de 60 segundos y los POST sin respuesta no se presentan como rechazados con certeza. Ensamblado de recursos legible y con orden explícito. Caché de métricas con una sola consulta simultánea por clave y sin bloquear claves independientes; errores no cacheados y conexiones del catálogo cerradas al terminar.

La instantánea conserva las prioridades siguientes: separar handlers del servidor y clasificación de Organizer, reforzar configuración tipada y documentación, copias cifradas externas con ensayo de restauración, y mayor historial estructurado de tareas. No se ha borrado el catálogo legado ni ninguna tabla bajo la etiqueta de limpieza de código.

## Validación realizada

- 229 pruebas Python del servidor y 74 del tracker: correctas.
- JavaScript: sintaxis, navegación, formularios únicos, conservación de estado, aMule, ofertas, Orbit, operaciones y transporte común: correcto.
- Navegador real con datos ficticios: todas las vistas, anchos 320–2560 px, tarjetas alineadas, ausencia de desbordes, errores de conexión, contenido escapado, avisos y registros que mantienen su apertura. Sin excepciones JavaScript.
- Pruebas Swift de autenticación/origen y persistencia de cookies: correctas. Compilaciones macOS, simulador iOS e iPhone firmado: correctas.
- Instalación Mac e iPhone 1.2.0; iPhone arrancado con devicectl. Dashboard actualizado y APIs reales de versión, tareas, inicio y calendario HTTP 200; tareas sin autenticación HTTP 401.
- Comparación de claves primarias de ambas SQLite con la instantánea: ningún registro previo perdido; integridad `ok`. Calendario conserva los 37 registros, estados, altas y bajas manuales; API muestra 35 series seguidas.
- Instantánea local recuperable: archivo del código inicial, modificación local previa, copias SQLite verificadas, calendario e instalación Mac anterior. Los datos y secretos no se incluyen en Git.

Los escenarios simulados no certifican todos los dispositivos ni las fuentes externas. El controlador visual de Codex agotó el tiempo al intentar leer la ventana nativa del Mac; la revisión visual física queda sujeta a la confirmación del propietario. Las capturas del navegador son fixtures de prueba, no su información personal.
