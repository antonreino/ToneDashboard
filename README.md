# ToneDashboard

Panel de control personal para **Mac mini, automatización Emby, descargas, Telegram, estadísticas, ofertas y Orbit Zero**. Web responsive que sirve de backend a [ToneDashboardApps](https://github.com/antonreino/ToneDashboardApps) para macOS/iOS/iPadOS.

Repositorio: [antonreino/ToneDashboard](https://github.com/antonreino/ToneDashboard). Apps nativas: [antonreino/ToneDashboardApps](https://github.com/antonreino/ToneDashboardApps).

> **Instalaciones existentes:** la carpeta `emby-organizer`, el ejecutable `emby_organizer.py` y los identificadores `com.tone.emby-*` se conservan por compatibilidad con los servicios y el historial. **No renombres la carpeta activa sin actualizar las rutas de los LaunchAgents.**

## Funciones actuales

| Sección | Funciones |
| --- | --- |
| Inicio | Servicios, CPU/GPU/RAM/temperatura y red del Mac mini; métricas y almacenamiento de Emby |
| Descargas | Cola persistente de descargas HTTP/HTTPS con conexiones verificadas, progreso, velocidad, ETA, carga de `.torrent` y notificaciones Telegram |
| Actividad y estadísticas | Historial SQLite, 24 horas/7 días/30 días, movimientos a Emby por biblioteca |
| Chollos | Bot hermano `ps5-price-bot`: precios PS5 y Switch, alertas y registros |
| Orbit Zero | Catálogo y progreso de Orbit desde el Mac mini mediante proxy autenticado de mismo origen |
| Logs | Consulta de procesos Organizer, Telegram y alertas |

El organizador de ToneDashboard clasifica Series/Anime/Películas, consulta opcionalmente TMDb, envía por SFTP al servidor Emby, vigila la estabilidad de los archivos y registra los resultados.

## Arquitectura

```text
Mac mini (ToneDashboard, puerto 8765)
 ├── Dashboard web / API con HTTP Basic
 ├── Cola, organizador Emby, Telegram, SQLite
 ├── Chollos (lectura SQLite/log del proyecto hermano)
 └── /orbit-bridge/zero/ → Orbit Zero local 127.0.0.1:34179

ToneDashboardApps (macOS / iOS / iPadOS)
 ├── SwiftUI nativo → API HTTPS del dashboard
 └── pestaña Orbit (WKWebView) → mismo /orbit-bridge/zero/
```

El catálogo antiguo **Overdrive**, su indexador, sus archivos auxiliares, los enlaces de JDownloader y el antiguo actualizador programado ya no forman parte de este proyecto. Orbit mantiene su propio catálogo y descargas. No se integran ventanas remotas ni VNC: si un proveedor exige verificar en una ventana del Mac, debes completar ese paso físicamente en el Mac.

## Requisitos

- macOS con Python 3 y las dependencias de `requirements.txt`.
- Orbit Zero instalado en `/Applications/Orbit Zero.app` si se necesita la sección Orbit.
- Mac mini y PS5 enlazados mediante Orbit Zero si se van a transferir archivos.
- Dashboard con **`DASHBOARD_USER` y `DASHBOARD_PASSWORD`** establecidos (obligatorio para Orbit).
- Para el botón protegido de arranque, `ORBIT_CONTROL_PASSWORD` de **12 caracteres o más**, diferente de la contraseña del dashboard.

Configuración mínima (ejemplos, nunca publicar valores reales):

```dotenv
DASHBOARD_BIND=127.0.0.1
DASHBOARD_USER=usuario_seguro
DASHBOARD_PASSWORD=clave_larga_unica
ORBIT_CONTROL_PASSWORD=otra_clave_larga_unica
INBOX_DIR=/Users/usuario/Documents/Torrent
TORRENT_DROP_DIR=/Users/usuario/Downloads
GAME_DOWNLOAD_DIR=/Volumes/Datos/Descargas
PRICE_BOT_DIR=/Volumes/Datos/Proyectos/Scripts/ps5-price-bot
```

Utiliza `.env.example` para el resto (Emby/SFTP/TMDb/Telegram). `.env` no debe subirse nunca a GitHub. El estado histórico se almacena en SQLite y queda fuera del repositorio.

## Obtener ToneDashboard

Para una copia nueva del código:

```bash
git clone https://github.com/antonreino/ToneDashboard.git
cd ToneDashboard
```

Si ya tienes un clon instalado en `emby-organizer`, actualiza su remoto y conserva esa carpeta:

```bash
git remote set-url origin https://github.com/antonreino/ToneDashboard.git
git pull --ff-only
```

Ejecuta estos dos últimos comandos dentro del clon existente. La app nativa se obtiene del repositorio independiente **ToneDashboardApps**.

## Instalación / actualización sobre el Mac existente

Para actualizar desde una copia nueva del proyecto, ejecuta el actualizador desde esa copia indicando la instalación existente:

```bash
python3 /ruta/a/la/copia-nueva/scripts/update_macos.py /Volumes/Datos/Proyectos/Scripts/emby-organizer
```

El origen y el destino deben ser carpetas distintas. El actualizador valida todos los archivos Python antes de sustituir código, prepara una copia en `.update-backups/` y restaura los archivos sustituidos si falla la aplicación. Conserva `.env`, bases de datos y descargas. Reinicia los servicios después de copiar; informa si algún reinicio falla. No ejecutes este script al editar directamente el clon activo.

Para instalar desde cero puedes utilizar `./scripts/install-macos-services.sh`. En instalaciones existentes **no lo ejecutes solo para cambiar el nombre**, pues recrea LaunchAgents. Las etiquetas `com.tone.emby-log-viewer`, `com.tone.emby-organizer`, etc., se conservan por compatibilidad.

Tras actualizar:

```bash
cd /Volumes/Datos/Proyectos/Scripts/emby-organizer
~/.venvs/emby-organizer/bin/python -m unittest discover -s tests -q
launchctl kickstart -k gui/$(id -u)/com.tone.emby-log-viewer
```

Abre `http://127.0.0.1:8765` en el Mac mini. La pestaña **Orbit Zero** requiere que Orbit Zero esté abierto. `Iniciar Orbit` exige autenticación en el dashboard y una segunda contraseña; el código del ordenador se consulta por separado con «Ver código» y otra contraseña.

## Limpieza opcional de las tablas SQLite del catálogo viejo

Una vez que hayas comprobado Orbit y el historial, puedes retirar **solo** las tablas conocidas del catálogo anterior. Es un segundo paso explícito, no forma parte de la instalación automática:

```bash
cd /Volumes/Datos/Proyectos/Scripts/emby-organizer
~/.venvs/emby-organizer/bin/python limpiar_datos_catalogo.py
~/.venvs/emby-organizer/bin/python limpiar_datos_catalogo.py --apply --confirm ELIMINAR
```

Antes de borrar, genera una **copia SQLite consistente con verificación de integridad** en `.patch-backups/`. Conserva `history`, todas las tablas de Emby/Telegram y los datos de Orbit. Los datos de los antiguos catálogos sí desaparecerán de la base activa (seguirán en la copia local).

## API usada por la app nativa

- `GET /api/dashboard` — panel, métricas, historial y servicios.
- `GET /api/deals` — ofertas y alertas de precios.
- `GET /api/logs` — logs.
- `POST /api/download` — añade una URL a la cola del bot.
- `POST /api/torrent` — carga un archivo torrent.
- `GET /api/orbit/status` — estado del servicio Orbit.
- `POST /api/orbit/start` — arranque protegido de Orbit (contraseña adicional y validación de origen).
- `/orbit-bridge/zero/` — proxy autenticado del navegador Orbit, incluidos recursos gráficos y conexiones en tiempo real.

Se recomienda HTTPS con autenticación y VPN privada desde fuera de casa. **No abras los puertos 34179, 34177 ni VNC al exterior**. El proxy de Orbit es sólo para una instalación de confianza y no debe exponerse sin protección. El servidor no extrae contraseñas de Orbit; el lector opcional solo consulta el código visible del ordenador mediante Accesibilidad.

## Pruebas y calidad

```bash
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -v
python3 -m compileall -q .
bash -n scripts/install-macos-services.sh
```

`README.md`, `.env.example`, `MACOS_MIGRATION.md`, `launchd/` y scripts son parte del código. Los archivos `.env`, SQLite, logs, descargas, copias de seguridad y cachés no se distribuyen.

## Repositorios y rutas de instalación

Los repositorios oficiales son [ToneDashboard](https://github.com/antonreino/ToneDashboard) y [ToneDashboardApps](https://github.com/antonreino/ToneDashboardApps). Los remotos locales apuntan a estos nombres. El backend instalado conserva la carpeta `emby-organizer` y sus identificadores de servicio para mantener las rutas de los LaunchAgents. **El instalador no renombra el directorio activo automáticamente**.

## Licencia

Véase `LICENSE`. Orbit Zero pertenece a sus desarrolladores y se instala por separado: [saawant12/orbit-store-ps5](https://github.com/saawant12/orbit-store-ps5).

## Endurecimiento de seguridad

Las descargas directas solo aceptan destinos públicos HTTP/HTTPS en puertos 80 o 443, sin credenciales incrustadas. Cada salto de redirección vuelve a comprobar DNS y utiliza una IP validada para la conexión; TLS conserva la validación del certificado y del nombre original. Se rechazan redes privadas, loopback, link-local, multicast, respuestas DNS mixtas y redirecciones de HTTPS a HTTP. La descarga y la consulta de cabeceras comparten estos controles; los errores de validación no recurren a `curl`. Se conserva la reanudación y la prevención de suspensión del Mac.

Las acciones POST y las mutaciones de Orbit comprueban `Origin` contra `Host`. Los clientes nativos sin `Origin` deben enviar `X-Dashboard-Action: write`. Las conexiones WebSocket de Orbit exigen un origen coincidente. El proxy inverso debe conservar el Host público. Actualiza la app junto con el servidor: los clientes antiguos sin la cabecera deberán actualizarse para descargar o subir torrents.

El dashboard consulta cada 12 segundos y solo carga ofertas en Chollos y logs en Inicio. Orbit sigue siendo una aplicación de confianza que comparte origen con el dashboard; estos controles no aíslan un script comprometido servido por Orbit. Mantén el acceso privado y Orbit actualizado.

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
En las apps requiere ToneDashboardApps 1.2 (3) o posterior.

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

En **Ofertas**, el formulario EAN permite añadir productos de 8 o 13 cifras con control válido. Cada producto dispone de una tarjeta y ofertas ordenadas por precio ascendente, igual que PS5 y Switch. Se muestra el precio del artículo; gastos de envío aparte. El registro se comparte con `ps5-price-bot` mediante su SQLite, conservando historial y destinatarios. Requiere actualizar también ese repositorio: el bot incorpora las altas automáticamente sin reinicio individual.

PcComponentes y MediaMarkt se han validado con búsquedas y fichas reales. Chollometro se consulta por sus fuentes públicas existentes y exige coincidencia EAN para productos añadidos. Amazon (sin precios) e Idealo (403) continúan desactivados; no se presentan como fuentes operativas.

Validación local de esta actualización: 91 pruebas Python correctas, API HTTP con autenticación y control de origen, orden numérico de ofertas y comprobación JavaScript. Servicio reiniciado y API real comprobada, con SQLite íntegro y respaldo previo. No se enviaron mensajes de prueba a Telegram.
