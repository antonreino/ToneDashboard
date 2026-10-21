# Tone Dashboard · servidor

Componente Python del [proyecto unificado](../README.md). La instalación, actualización y pruebas completas se ejecutan desde la raíz de ToneDashboard. No se actualiza ni se instala por separado.

- Interfaz única en `../web/`, también utilizada por las apps de `../apple/`.
- Organizer clasifica vídeos, envía por SFTP y registra el historial.
- API y proxy autenticados, descargas/torrents, métricas Mac/Emby, logs y Orbit.
- Ofertas compartidas con `../workers/price_tracker/`, dentro del mismo proyecto.
- Configuración privada en `server/.env`; consulta `.env.example`. `PRICE_BOT_DIR` es opcional: su valor por defecto apunta al worker del repositorio.
- Se conservan los identificadores `com.tone.*`, el puerto 8765 y los datos de `~/.local/share/emby_organizer`.

Para diagnóstico desde la raíz:

```bash
bash server/scripts/status-macos.sh
bash scripts/check.sh
```

El servicio Linux `emby-watch-refresh.service` permanece independiente del Mac. Orbit Zero se instala por separado; el lector de Accesibilidad conserva su instalación y permisos.

## Endurecimiento de seguridad

Las descargas directas solo aceptan destinos públicos HTTP/HTTPS en puertos 80 o 443, sin credenciales incrustadas. Cada salto de redirección vuelve a comprobar DNS y utiliza una IP validada para la conexión; TLS conserva la validación del certificado y del nombre original. Se rechazan redes privadas, loopback, link-local, multicast, respuestas DNS mixtas y redirecciones de HTTPS a HTTP. La descarga y la consulta de cabeceras comparten estos controles; los errores de validación no recurren a `curl`. Se conserva la reanudación y la prevención de suspensión del Mac.

Las acciones POST y las mutaciones de Orbit comprueban `Origin` contra `Host`. Los clientes nativos sin `Origin` deben enviar `X-Dashboard-Action: write`. Las conexiones WebSocket de Orbit exigen un origen coincidente. El proxy inverso debe conservar el Host público. Actualiza la app junto con el servidor: los clientes antiguos sin la cabecera deberán actualizarse para descargar o subir torrents.

El dashboard consulta cada 12 segundos y solo carga ofertas en Chollos y logs en su sección propia. Orbit sigue siendo una aplicación de confianza que comparte origen con el dashboard; estos controles no aíslan un script comprometido servido por Orbit. Mantén el acceso privado y Orbit actualizado.

## Mostrar el código de Orbit desde web y apps

1. Establece `ORBIT_PAIR_CODE_PASSWORD` en el `.env` local (mínimo 12 caracteres y diferente de las otras contraseñas).
2. Instala el lector: `bash scripts/install-orbit-code-reader.sh`. Autoriza **ToneOrbitCodeReader** en Ajustes del Sistema → Privacidad y seguridad → Accesibilidad.
3. Reinicia el servicio `com.tone.emby-log-viewer` y actualiza las apps. En Orbit pulsa **Ver código**, introduce la contraseña y consulta el código vigente. Se oculta a los 60 segundos, al cerrar el diálogo o al pasar a segundo plano.

El lector local puede abrir la pestaña Consola y el desplegable Cómo funciona de Orbit. No modifica el paquete de Orbit, no utiliza sus cookies ni lee el llavero. Solo funciona con la interfaz en español o inglés y con Orbit instalado en `/Applications/Orbit Zero.app`. Si Orbit no muestra el código (por ejemplo, PS5 desconectada en esta versión), se devuelve un error explícito; nunca un código guardado de un arranque anterior.

`POST /api/orbit/pair-code` exige el login del dashboard, protección de origen, `X-Orbit-Action: reveal-code` y `X-Orbit-Pair-Password`. No devuelve el código en `/api/orbit/status`, no lo persiste ni lo registra. Cinco contraseñas incorrectas bloquean la consulta durante un minuto por dirección de conexión; detrás del proxy ese límite puede compartirse. La contraseña nunca se envía a Orbit y cada consulta vuelve a leer el código vigente.

El servicio inicia el lector como aplicación independiente mediante LaunchServices para que macOS aplique el permiso de Accesibilidad del lector, no el del proceso Python. La respuesta usa una FIFO de modo 0600 dentro de un directorio privado 0700; el código no se escribe en un archivo regular. Si al actualizar el lector el permiso aparece activado pero macOS lo deniega, elimina su entrada de Accesibilidad y vuelve a añadir la aplicación instalada para autorizar su firma actual.

## Clasificación y estabilidad de vídeos

El organizador obtiene primero el título del nombre del vídeo. Usa las carpetas superiores como alternativa cuando el archivo solo contiene un identificador de episodio, omitiendo `Season 2` / `Temporada 2` y sin usar la raíz `Torrent` como título. Limpia etiquetas como `4K`, `UHD`, `HDR` y `H.265`; conserva los números del título. Reconoce temporada 0, episodios concatenados `S01E01E02` y rangos `S01E01-S01E03`, `S01E01-E03` y `S01E01-03`. Rechaza rangos entre temporadas y episodios repetidos o invertidos. `Cap.103` se interpreta como temporada 1, episodio 3, salvo que haya una señal explícita de anime.

Cada archivo debe permanecer sin cambios durante 180 segundos **observados por el proceso**, aunque tenga una fecha antigua. Un reinicio comienza de nuevo esa observación. `--scan-once` hace dos pasadas separadas por 180 segundos; los archivos modificados entre ambas esperan a otra ejecución. Solo puede ejecutarse una instancia, también para `--dry-run`. La simulación conserva los vídeos, pero sigue consultando bibliotecas y registrando el historial.

Antes de publicar una subida se comprueba que el origen no cambió. Los temporales SFTP son únicos y terminan en `.uploading`; un fallo conserva el origen. No se sobrescribe un destino ya existente: el origen se conserva en `NoClasificado`. Esta carpeta, `.staging`, sus descendientes y los enlaces simbólicos se excluyen del procesamiento. Un fallo de archivo no detiene el resto del escaneo. Las carpetas antiguas creadas por clasificaciones erróneas requieren revisión manual: no se fusionan automáticamente.

TMDb solo acepta una coincidencia inequívoca de título, comprueba el año indicado y renueva su caché cada 24 horas. Una respuesta ambigua no se decide por popularidad; se usan las reglas locales o cuarentena.

### Refresco en el servidor Emby

`scripts/emby-watch-refresh.sh` se instala **en el servidor Linux de Emby**, con Bash, `inotifywait` y `curl`. Conserva las variables `EMBY_WATCH_DIR`, `EMBY_URL`, `EMBY_API_KEY`, `COOLDOWN` (180 s) y `MIN_REFRESH_INTERVAL` (300 s); añade `RETRY_INTERVAL` (30 s). Un único planificador espera el silencio de eventos y conserva cualquier refresco pendiente hasta cumplir el intervalo mínimo. Solo actualiza por vídeos publicados/eliminados o directorios movidos/eliminados, no por crear carpetas o escribir `.uploading`. Los fallos se reintentan sin necesitar otro archivo.

Tras actualizar este script en el clon, hay que copiarlo al servidor como `/usr/local/bin/emby-watch-refresh.sh` y reiniciar `emby-watch-refresh.service` allí. Un `git pull` o reinicio del organizador en el Mac no actualiza esa copia remota. Los tests ejecutan el script con `inotifywait` y `curl` simulados, sin acceder a Emby ni a Telegram.

### Conexión automática de Orbit (web, iOS y macOS)

En la pestaña Orbit abre **Conexión automática**, introduce la contraseña de
`ORBIT_PAIR_CODE_PASSWORD` y pulsa **Recordar este dispositivo**. La autorización
caduca a los 30 días. Se conserva en una cookie `Secure`, `HttpOnly` y
`SameSite=Strict`; utiliza la URL HTTPS del dashboard, también en la red local.
Las apps de esta arquitectura comparten la versión 1.2.0 y la interfaz web.

Si Orbit pierde su sesión o se reinicia, el puente consulta el código vigente
mediante ToneOrbitCodeReader y realiza la vinculación normal de Orbit. El lector
necesita permiso de Accesibilidad y debe poder encontrar el código en la ventana
del Mac: conecta la consola y deja abierta **Consola → Cómo funciona**. Si la
lectura falla, sigue disponible **Ver código** y la vinculación manual. Los
intentos automáticos se limitan a uno por minuto y dispositivo; después
de corregir la conexión espera un minuto y pulsa **Recargar/Reconectar**.

**Olvidar este dispositivo** revoca su autorización en el servidor y elimina sus
cookies de vinculación. Cambiar cualquiera de las contraseñas del dashboard o
`ORBIT_PAIR_CODE_PASSWORD` e iniciar de nuevo el servicio invalida las
autorizaciones existentes. El servidor guarda únicamente hashes de las
autorizaciones en `~/.local/share/emby_organizer/orbit-devices.sqlite3` (permisos
0600); no guarda el código ni la contraseña de vinculación. Las sesiones de Orbit
se mantienen en memoria y se pueden reconstruir después de reiniciar el servicio.
La consola necesita tener iniciado su receptor de Orbit para utilizar sus funciones.

### Seguimiento de productos por EAN

En **Chollos**, el formulario EAN permite añadir productos de 8 o 13 cifras con control válido. Cada producto dispone de una tarjeta y ofertas ordenadas por precio ascendente, igual que PS5 y Switch. Se muestra el precio del artículo; gastos de envío aparte. El registro se comparte con el worker `workers/price_tracker` mediante su SQLite, conservando historial y destinatarios. El worker forma parte del mismo repositorio e incorpora las altas sin reinicio individual.

PcComponentes y MediaMarkt se han validado con búsquedas y fichas reales. Chollometro se consulta por sus fuentes públicas existentes y exige coincidencia EAN para productos añadidos. Amazon (sin precios) e Idealo (403) continúan desactivados; no se presentan como fuentes operativas.

Validación local de esta actualización: 91 pruebas Python correctas, API HTTP con autenticación y control de origen, orden numérico de ofertas y comprobación JavaScript. Servicio reiniciado y API real comprobada, con SQLite íntegro y respaldo previo. No se enviaron mensajes de prueba a Telegram.

Cada tarjeta EAN incluye **Eliminar**, con confirmación. Deja de seguir ese producto y cancela sus avisos pendientes sin borrar el historial. Los productos nuevos notifican por el bot Telegram y a los destinatarios existentes.

**PS5 y Switch también son eliminables** desde su tarjeta, igual que los EAN. Al retirarlas se detienen sus consultas y avisos, no solo se ocultan. Las familias retiradas muestran **Volver a seguir**. El historial se conserva y los EAN continúan usando sus tiendas, aunque se retire PS5 o Switch. El mismo control existe en web, iOS y macOS, con la versión pública común.

### Recuperación de conexiones SSH/SFTP

El Organizer comprueba también si el canal SFTP está cerrado, mantiene viva la sesión SSH y aplica tiempos de espera a las lecturas. Biblioteca, espacio y CPU/RAM recuperan una conexión interrumpida con un único reintento, igual que las operaciones de subida. Se mantiene la verificación estricta de `known_hosts`; un fallo de autenticación o de clave del servidor no se trata como una interrupción recuperable. Los errores incluyen su tipo incluso cuando la excepción no tiene mensaje, sin exponer credenciales.


### Interfaz y tareas programadas · 1.2.0

El sistema visual crema es común a las tres plataformas. Inicio ofrece accesos directos; Más agrupa biblioteca, sistema y preferencias. La sección Tareas programadas usa `GET /api/scheduled-tasks` autenticado y de solo lectura. Descubre nuevas automatizaciones y consulta resultados acotados/sanitizados sin ejecutar procesos ni publicar prompts. Véanse [Tareas programadas](../docs/TAREAS-PROGRAMADAS.md) e [instantánea del proyecto](../docs/ESTADO-PROYECTO-2026-10-21.md). Las cifras de validación de apartados anteriores son históricas de sus entregas.
