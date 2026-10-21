# Instantánea de Tone Dashboard · 21 de octubre de 2026

Esta fotografía corresponde al estado inicial anterior a la revisión visual solicitada ese día. Se ha leído el código, la configuración de planificación, los metadatos de las bases y los servicios locales. Los resultados de pruebas de una nueva versión deben acompañar a su entrega: no se dan por realizados en esta instantánea. No se han leído archivos `.env`, claves, cookies ni enlaces de suscripción.

## Proyecto y arquitectura

- Repositorio único: `antonreino/ToneDashboard`, rama `main`, commit inicial `2f6136f`. Versión publicada al comenzar: **1.1.9**. La siguiente publicación corresponde a **1.2.0**, según `AGENTS.md`.
- `web/` es la interfaz funcional común. Un cambio publicado en el servidor llega al navegador y a las apps al recargar; el contenedor Apple solo requiere recompilación para cambios nativos.
- `server/` mantiene API, seguridad, Organizer, colas, métricas, actividad, diagnóstico, aMule, Orbit y calendario. El listener es el existente, puerto 8765.
- `workers/price_tracker/` contiene seguimiento PS5/Switch/EAN, fuentes públicas, preferencias y Telegram. Las bases y destinatarios existentes se conservan.
- `apple/` es el contenedor SwiftUI/WKWebView de macOS/iOS: llavero, conexión, origen, cookies, archivos y diálogos. No duplica las pantallas del producto.
- `infra-maintenance/` y `audits/`, fuera del repositorio principal, contienen herramientas e informes privados de infraestructura y PS5. Jarvis sigue siendo un proyecto independiente.
- El árbol inicial tenía una modificación previa en `web/index.html` y la carpeta local `audits/`; se deben preservar durante esta intervención.

## Qué funciona y qué información conserva

Inicio resume servicios; Descargas contiene colas e historial y búsqueda aMule; Chollos agrupa productos/ofertas, actividad y alertas; Orbit incluye vinculación protegida y despertar desde reposo; Más reúne calendario, equipos, estadísticas, revisiones, diagnóstico y Logs. La API aplica autenticación y controles de origen a mutaciones. Descargas comprueba destinos y redirecciones; SFTP comprueba host, estabilidad y publicación temporal antes de borrar el origen.

El calendario prioriza Japón (fecha civil JST) y conserva por separado doblajes castellanos. Los animes retirados manualmente siguen fuera de avisos. Archivado significa esperar y vigilar próximas temporadas; no equivale a historia finalizada. Las portadas se guardan localmente y el alta busca su cartel antes de publicar una tarjeta.

Lecturas locales realizadas para esta instantánea, sin extraer el contenido privado:

| Almacén | Tamaño / conteo observado |
|---|---|
| Estado SQLite | 16,3 MB; 70 entradas de historial, 17 descargas registradas, 36 eventos de archivos y 2 revisiones conservadas |
| Tracker SQLite | 188 KB; 31 ofertas, 67 notificaciones publicadas, 2 destinatarios, 2 familias y ningún EAN añadido |
| Calendario | 37 registros: 35 seguidos y 2 bajas; 3 en emisión, 32 esperando, 35 portadas locales y 5 eventos conservados |
| Copias SQLite | 28 archivos, 230,3 MB, en el mismo Mac |

Las cantidades son una lectura puntual y cambiarán con la actividad normal. Una fila registrada no prueba que una transferencia siga activa; tampoco una revisión conservada prueba que esté pendiente. No se ha ejecutado borrado ni migración de estos datos.

Los datos operativos permanecen en `~/.local/share/emby_organizer`, el tracker en `workers/price_tracker/data/prices.sqlite3` y las preferencias nativas en sus almacenes de Apple. La clave Remote Play, SSH de mantenimiento, configuración privada, ledger de avisos y suscripción de calendario quedan fuera de Git. Las copias actuales protegen frente a errores lógicos, pero no frente a perder ese disco.

## Tareas programadas

Se han leído los cuatro `automation.toml` instalados, sin publicar sus prompts completos. Todos figuran activos. Horarios de **Europe/Madrid**, con cambio estacional automático:

| Tarea | Frecuencia | Función y límites | Registro / avisos |
|---|---|---|---|
| Anime: Japón y avisos | Cada 3 horas | Refresca las series seguidas y portadas; contrasta próximos episodios japoneses y audio castellano. Solo marca disponible después de verificar publicación real. Respeta bajas e historial. | `audits/anime-calendar`; Telegram al propietario solo para estrenos nuevos confirmados, con deduplicación. |
| Anime: próximas temporadas | Lunes, 08:00 | Investigación de continuaciones de las series archivadas, incluidas películas y doblajes pendientes. No inventa días ni da una historia por finalizada al acabar temporada. | Informes de calendario; comparte datos con el aviso cada 3 horas. No es una segunda lista de suscripciones. |
| Mantener payloads de PS5 | Diario, 10:00 | Revisa versiones oficiales y prepara archivos compatibles con firmware 13.40. Puede despertar una vez desde reposo confirmado. Conserva la cadena YouTube y DNS; no reinicia ni ejecuta jailbreak. Instala solo con actividad segura y lectura posterior verificable. | `audits/ps5-payload-updates/checks`; informe diario a Telegram incluso sin cambios, sin consola o con error. |
| Mantenimiento semanal Proxmox y Emby | Lunes, 04:00 | Revisa host, VM/contenedores y aplicaciones; copias, simulación de cambios y validación. Aplaza servicios ocupados. No reinicia automáticamente el host ni realiza migraciones mayores. | Informes privados Proxmox/Emby y Telegram siempre, con cambios, errores y pendientes. |

Estas cuatro tareas son automatizaciones de Codex: necesitan el Mac encendido y Codex disponible. No son daemons permanentes añadidos a macOS. Una planificación activa no prueba que la última ejecución haya acabado correctamente: los informes fechados son su evidencia.

Existen además trabajos internos que no deben confundirse con esas cuatro automatizaciones:

- Dashboard ejecuta el mantenimiento de aMule cada 30 segundos y copias SQLite cada 24 horas desde su bucle existente (`server/operations.py`). No mata instancias aMule abiertas.
- Organizer vigila archivos continuamente y espera estabilidad antes de procesar.
- El bot de descargas conserva su cola; el tracker consulta fuentes según sus intervalos y límites por dominio; el vigilante de logs avisa errores.
- En el servidor Linux de Emby, el watcher de biblioteca es una unidad independiente del Mac; un cambio local de su script no actualiza automáticamente esa copia remota.

## Servicios observados

Los cinco LaunchAgents configurados están cargados con PID y último código 0: Dashboard, Organizer, bot Telegram de descargas, alertas de logs y tracker. Todos usan el entorno Python común del monorepositorio y `KeepAlive`. La muestra puntual de CPU fue 0,0–0,2 % para esos cinco procesos; aMule 0,3 % y qBittorrent 0,0 %. Son valores instantáneos, no una medición de carga sostenida ni prueba funcional de conexiones externas. No se ha detenido, reiniciado ni instalado ningún servicio para obtener esta lectura.

La última revisión de infraestructura documentada el 19/10 conserva NPM reparado y las adaptaciones de proxy; **este documento no ha vuelto a conectarse a Proxmox para certificar su estado actual**. Ese informe registra CT Emby aún sobre Ubuntu 20.04 y almacenamiento thin pool al 87,14 %: son pendientes de planificación y capacidad, no cambios a aplicar durante un rediseño.

## Pruebas y controles existentes

- `scripts/check.sh`: regresiones Python servidor/tracker, validación sintáctica JavaScript y contratos de navegación/interfaz/seguridad.
- CI: trabajos separados de servidor, navegador y Apple; auditoría de dependencias fijadas, Playwright y compilación macOS/iOS sin firma.
- `scripts/browser-check.mjs` usa servidor ficticio: no accede a `.env`, aMule, Telegram ni biblioteca del usuario; guarda capturas.
- Apple tiene pruebas de origen/autenticación/llavero y persistencia de cookies. La prueba simulada no reemplaza revisión física de safe areas, lector de archivos o permisos del sistema.
- Las copias usan la API online de SQLite y comprobación de integridad. La restauración rechaza sobrescribir un destino ya existente.

No se afirma en esta instantánea que se hayan vuelto a ejecutar todas las pruebas, ni que exista un backup externo o una recuperación integral ensayada.

## Clean code: prioridades concretas

1. **Separar responsabilidades sin cambiar arquitectura.** `server/scripts/log-viewer.py` concentra rutas GET (117 líneas al inicio) y POST (204); `server/emby_organizer.py` contiene clasificación de 111 líneas y el bot una descarga de 109. Extraer handlers y servicios por dominio preservando rutas, controles de autenticación, estados y pruebas existentes; no hace falta migrar de framework para ello.
2. **Código legible y transporte común en interfaz.** `web/operations.js` tenía 18,8 KB en 140 líneas con líneas de hasta 1.153 caracteres; `dashboard.js`, 40,8 KB/583 líneas. Extraer calendario y transporte HTTP común, mantener un único tratamiento de timeout/error/encabezados y formatear las funciones. El número de líneas por sí solo no mide calidad; aquí la compactación y mezcla de dominios sí dificultan revisar cambios.
3. **Evitar bloqueos entre métricas independientes.** `server/runtime_support.py`, `SnapshotCache.get`, ejecutaba el cargador dentro de un único lock global. Una lectura lenta podía retrasar otras claves. Utilizar coordinación de solicitudes simultáneas por clave y liberar el lock durante la E/S, con pruebas de concurrencia, caducidad y fallo.
4. **Un sistema visual coherente.** Variables para paleta crema, tipografía, espacios, tamaños y estados; componentes de tarjeta, cabecera, formulario, toolbar, vacío/error y acciones. Rejillas adaptables y pruebas con textos largos, ausencia de datos y ancho móvil. Conservar todos los datos aunque los detalles se plieguen.
5. **Registro seguro y único de tareas.** Inventario desde fuentes reales, estado de ejecución diferenciado de planificación, fecha del informe y log acotado/sanitizado. Nunca presentar un informe ausente como ejecución correcta ni entregar prompts, rutas de claves o tokens al navegador.
6. **Documentación actual.** `server/README.md` aún menciona versiones anteriores y selectores Kad, y `docs/OPERACIONES.md` arranca con 1.1.0. Mantener referencias históricas identificadas como tales y actualizar las instrucciones del producto actual.
7. **Datos retirados con criterio.** La base conserva tablas de un catálogo PS5 ya retirado (incluida una tabla de 35.501 URLs archivadas). Existe `server/limpiar_datos_catalogo.py` con simulación y copia previa. Es una operación de limpieza separada: no eliminar historial automáticamente bajo la etiqueta clean code.
8. **Configuración y errores.** Introducir progresivamente tipos/configuración validada y errores de dominio. Revisar capturas amplias de excepciones en límites de proceso; conservar mensajes públicos discretos y contexto seguro interno. No convertir todos los fallos de red en reintentos indiscriminados.

## Qué incorporaría después

- Copia cifrada fuera del Mac y prueba periódica de restauración sobre una carpeta temporal, con estado visible.
- Acceso directo a herramientas frecuentes y buscador de navegación, sin duplicar pantallas ni información.
- Historial estructurado de automatizaciones (inicio, fin, resultado, resumen, fuente), para depender menos de nombres de archivos privados y detectar ejecuciones sin terminar.
- Alertas de capacidad del almacenamiento Proxmox y plan de migración soportada para el CT Emby; hacer ambas tareas fuera de la entrega visual.
- Cuando exista un segundo dominio HTTPS, completar pruebas reales del aislamiento Orbit ya preparado y desactivado por decisión del propietario.
- Pruebas de accesibilidad: foco de teclado, lector de pantalla, texto grande, contraste y movimiento reducido; además de comparaciones visuales en Safari/WKWebView.

La entrega visual debe publicar por separado los cambios, pruebas ejecutadas y limitaciones pendientes de instalación o comprobación física. Esta instantánea conserva el punto de partida para poder comparar.
