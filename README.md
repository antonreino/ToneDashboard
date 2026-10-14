# ToneDashboard

Panel de control personal para **Mac mini, automatización Emby, descargas, Telegram, estadísticas, ofertas y Orbit Zero**. Web responsive que sirve de backend a [ToneDashboardApps](../ToneDashboardApps/README.md) para macOS/iOS/iPadOS.

> Cambio de marca de `emby-organizer`: los ejecutables de Emby y los identificadores de los LaunchAgents se mantienen a propósito para conservar el servicio y el historial. **No cambies la ruta del repositorio en el Mac sin reinstalar los LaunchAgents.** El nombre `ToneDashboard` corresponde al proyecto, a la interfaz y al nuevo repositorio deseado, no a una migración destructiva de las rutas actuales.

## Funciones actuales

| Sección | Funciones |
| --- | --- |
| Inicio | Servicios, CPU/GPU/RAM/temperatura y red del Mac mini; métricas y almacenamiento de Emby |
| Descargas | Cola persistente de descargas HTTP/HTTPS con conexiones verificadas, progreso, velocidad, ETA, carga de `.torrent` y notificaciones Telegram |
| Actividad y estadísticas | Historial SQLite, 24 horas/7 días/30 días, movimientos a Emby por biblioteca |
| Chollos | Bot hermano `ps5-price-bot`: precios PS5 y Switch, alertas y registros |
| Orbit Zero | Catálogo y progreso de Orbit desde el Mac mini mediante proxy autenticado de mismo origen |
| Logs | Consulta de procesos Organizer, Telegram y alertas |

Emby Organizer **sigue** clasificando Series/Anime/Películas, consultando opcionalmente TMDb, enviando por SFTP al LXC Emby, vigilando estabilidad de archivos y registrando resultados. No se han eliminado estas funcionalidades.

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

Abre `http://127.0.0.1:8765` en el Mac mini. La pestaña **Orbit Zero** requiere que Orbit Zero esté abierto. `Iniciar Orbit` exige autenticación en el dashboard y una segunda contraseña; no recupera ni expone los códigos de emparejamiento de Orbit.

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

Se recomienda HTTPS con autenticación y VPN privada desde fuera de casa. **No abras los puertos 34179, 34177 ni VNC al exterior**. El proxy de Orbit es sólo para una instalación de confianza y no debe exponerse sin protección. El servidor no extrae contraseñas ni códigos de Orbit.

## Pruebas y calidad

```bash
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -v
python3 -m compileall -q .
bash -n scripts/install-macos-services.sh
```

`README.md`, `.env.example`, `MACOS_MIGRATION.md`, `launchd/` y scripts son parte del código. Los archivos `.env`, SQLite, logs, descargas, copias de seguridad y cachés no se distribuyen.

## Publicación y cambio de nombre de GitHub

El ZIP contiene la nueva estructura **ToneDashboard**. Renombrar el repositorio remoto en GitHub y actualizar el `git remote` local se hace aparte, después de comprobar el despliegue. Hasta entonces, los enlaces a `antonreino/emby-organizer` que no se hayan cambiado siguen funcionando. **El instalador no renombra el repositorio ni el directorio activo automáticamente**.

## Licencia

Véase `LICENSE`. Orbit Zero pertenece a sus desarrolladores y se instala por separado: [saawant12/orbit-store-ps5](https://github.com/saawant12/orbit-store-ps5).

## Endurecimiento de seguridad

Las descargas directas solo aceptan destinos públicos HTTP/HTTPS en puertos 80 o 443, sin credenciales incrustadas. Cada salto de redirección vuelve a comprobar DNS y utiliza una IP validada para la conexión; TLS conserva la validación del certificado y del nombre original. Se rechazan redes privadas, loopback, link-local, multicast, respuestas DNS mixtas y redirecciones de HTTPS a HTTP. La descarga y la consulta de cabeceras comparten estos controles; los errores de validación no recurren a `curl`. Se conserva la reanudación y la prevención de suspensión del Mac.

Las acciones POST y las mutaciones de Orbit comprueban `Origin` contra `Host`. Los clientes nativos sin `Origin` deben enviar `X-Dashboard-Action: write`. Las conexiones WebSocket de Orbit exigen un origen coincidente. El proxy inverso debe conservar el Host público. Actualiza la app junto con el servidor: los clientes antiguos sin la cabecera deberán actualizarse para descargar o subir torrents.

El dashboard consulta cada 12 segundos y solo carga ofertas en Chollos y logs en Inicio. Orbit sigue siendo una aplicación de confianza que comparte origen con el dashboard; estos controles no aíslan un script comprometido servido por Orbit. Mantén el acceso privado y Orbit actualizado.
