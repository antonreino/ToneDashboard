# Tone Dashboard · servidor

Componente Python del [proyecto unificado](../README.md). La instalación, actualización y pruebas completas se ejecutan desde la raíz de ToneDashboard. No se actualiza ni se instala por separado.

- Interfaz única en `../web/`, también utilizada por las apps de `../apple/`.
- Organizer clasifica vídeos, envía por SFTP y registra el historial.
- API autenticada, descargas/torrents, métricas Mac/Emby y logs.
- Ofertas compartidas con `../workers/price_tracker/`, dentro del mismo proyecto.
- Configuración privada en `server/.env`; consulta `.env.example`. `PRICE_BOT_DIR` es opcional: su valor por defecto apunta al worker del repositorio.
- Se conservan los identificadores `com.tone.*`, el puerto 8765 y los datos de `~/.local/share/emby_organizer`.

Para diagnóstico desde la raíz:

```bash
bash server/scripts/status-macos.sh
bash scripts/check.sh
```

El servicio Linux `emby-watch-refresh.service` permanece independiente del Mac.

## Endurecimiento de seguridad

Las descargas directas solo aceptan destinos públicos HTTP/HTTPS en puertos 80 o 443, sin credenciales incrustadas. Cada salto de redirección vuelve a comprobar DNS y utiliza una IP validada para la conexión; TLS conserva la validación del certificado y del nombre original. Se rechazan redes privadas, loopback, link-local, multicast, respuestas DNS mixtas y redirecciones de HTTPS a HTTP. La descarga y la consulta de cabeceras comparten estos controles; los errores de validación no recurren a `curl`. Se conserva la reanudación y la prevención de suspensión del Mac.

Las acciones POST comprueban `Origin` contra `Host`. Los clientes nativos sin `Origin` deben enviar `X-Dashboard-Action: write`. El proxy inverso debe conservar el Host público. Actualiza la app junto con el servidor: los clientes antiguos sin la cabecera deberán actualizarse para descargar o subir torrents.

El dashboard consulta cada 12 segundos y solo carga ofertas en Chollos y logs en su sección propia. Mantén el acceso privado.

## Clasificación y estabilidad de vídeos

El organizador obtiene primero el título del nombre del vídeo. Usa las carpetas superiores como alternativa cuando el archivo solo contiene un identificador de episodio, omitiendo `Season 2` / `Temporada 2` y sin usar la raíz `Torrent` como título. Limpia etiquetas como `4K`, `UHD`, `HDR` y `H.265`; conserva los números del título. Reconoce temporada 0, episodios concatenados `S01E01E02` y rangos `S01E01-S01E03`, `S01E01-E03` y `S01E01-03`. Rechaza rangos entre temporadas y episodios repetidos o invertidos. `Cap.103` se interpreta como temporada 1, episodio 3, salvo que haya una señal explícita de anime.

Cada archivo debe permanecer sin cambios durante 180 segundos **observados por el proceso**, aunque tenga una fecha antigua. Un reinicio comienza de nuevo esa observación. `--scan-once` hace dos pasadas separadas por 180 segundos; los archivos modificados entre ambas esperan a otra ejecución. Solo puede ejecutarse una instancia, también para `--dry-run`. La simulación conserva los vídeos, pero sigue consultando bibliotecas y registrando el historial.

Antes de publicar una subida se comprueba que el origen no cambió. Los temporales SFTP son únicos y terminan en `.uploading`; un fallo conserva el origen. No se sobrescribe un destino ya existente: el origen se conserva en `NoClasificado`. Esta carpeta, `.staging`, sus descendientes y los enlaces simbólicos se excluyen del procesamiento. Un fallo de archivo no detiene el resto del escaneo. Las carpetas antiguas creadas por clasificaciones erróneas requieren revisión manual: no se fusionan automáticamente.

TMDb solo acepta una coincidencia inequívoca de título, comprueba el año indicado y renueva su caché cada 24 horas. Una respuesta ambigua no se decide por popularidad; se usan las reglas locales o cuarentena.

### Refresco en el servidor Emby

`scripts/emby-watch-refresh.sh` se instala **en el servidor Linux de Emby**, con Bash, `inotifywait` y `curl`. Conserva las variables `EMBY_WATCH_DIR`, `EMBY_URL`, `EMBY_API_KEY`, `COOLDOWN` (180 s) y `MIN_REFRESH_INTERVAL` (300 s); añade `RETRY_INTERVAL` (30 s). Un único planificador espera el silencio de eventos y conserva cualquier refresco pendiente hasta cumplir el intervalo mínimo. Solo actualiza por vídeos publicados/eliminados o directorios movidos/eliminados, no por crear carpetas o escribir `.uploading`. Los fallos se reintentan sin necesitar otro archivo.

Tras actualizar este script en el clon, hay que copiarlo al servidor como `/usr/local/bin/emby-watch-refresh.sh` y reiniciar `emby-watch-refresh.service` allí. Un `git pull` o reinicio del organizador en el Mac no actualiza esa copia remota. Los tests ejecutan el script con `inotifywait` y `curl` simulados, sin acceder a Emby ni a Telegram.

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
