# Tone Dashboard · 1.0.0

Un único proyecto para web, macOS/iOS, Organizer, descargas, Telegram, ofertas y Orbit.

## Estructura

- `web/`: **una sola interfaz**, adaptable a navegador, Mac, iPhone e iPad. Pantallas, formularios, precios, diálogos y conexión Orbit compartidos.
- `server/`: API autenticada, proxy Orbit, métricas, historial, Organizer y automatización de descargas.
- `workers/price_tracker/`: PS5/Switch/EAN y bot Telegram; la API utiliza este mismo paquete dentro del repositorio.
- `apple/`: contenedor SwiftUI/WebKit para macOS/iOS. Solo ajustes, llavero, aislamiento por origen/cuenta, selección de archivos y diálogos nativos. No replica pantallas ni modelos de ofertas.
- `VERSION`: versión común. La compilación Apple crece independientemente para permitir actualizaciones.

Los historiales Git originales están integrados mediante subtrees sin squash. Los datos y secretos quedan fuera de Git.

## Instalar o actualizar

Python3.12 o posterior. En macOS:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp server/.env.example server/.env
cp workers/price_tracker/.env.example workers/price_tracker/.env
# Configurar ambos archivos privados: los bots pueden tener credenciales distintas.
bash scripts/install-macos-services.sh
```

Para una instalación migrada: `git pull --ff-only`, instalar `requirements.txt` en `.venv` y ejecutar el instalador de servicios. Conserva los archivos privados, SQLite, colas, historial y destinatarios. Evita actualizar a mitad de una transferencia.

El dashboard mantiene el puerto8765 y las rutas API. El tracker utiliza `workers/price_tracker/data/prices.sqlite3`. Organizer, descargas, autorizaciones Orbit e historial mantienen `~/.local/share/emby_organizer`; los identificadores LaunchAgent `com.tone.*` se conservan. No se añaden servicios permanentes.

## Apps Apple

Abrir `apple/ToneDashboardApps.xcodeproj`: versión1.0.0, compilación8. Los identificadores de bundle y llavero anteriores se conservan para actualizar sin perder credenciales, preferencias ni cookies. La cuenta anterior mantiene su almacén WebKit; otras cuentas tienen almacenes persistentes separados. No se borra el almacén de Orbit.

Las apps cargan `/` del dashboard HTTPS. Las mejoras de interfaz se reciben al recargar; cambios del contenedor requieren nueva compilación. Autenticación y navegación quedan limitadas al origen configurado. No se entregan contraseñas a JavaScript ni hay un puente de ejecución de comandos.

## Pruebas

```bash
bash scripts/check.sh
swiftc apple/ToneDashboardApps/APIClient.swift apple/ToneDashboardApps/DashboardSession.swift apple/ToneDashboardApps/KeychainStore.swift apple/tests/ContainerTests.swift -o /tmp/container-tests
/tmp/container-tests
```

CI ejecuta regresiones de servidor/tracker, pruebas de la interfaz común, seguridad del contenedor, persistencia de cookies y compilaciones macOS/iOS. La migración se valida además contra servicios y datos reales; los informes privados no se publican.

## Funciones conservadas

Organizer y SFTP, refresco Emby, métricas, cola de descargas/torrents, logs, estadísticas e historial; ofertas PS5/Switch/EAN con eliminación/restauración y Telegram; Orbit integrado, código protegido y autorización persistente.

Amazon e Idealo mantienen sus limitaciones previas; la migración no elimina sus bloqueos. Jarvis permanece como proyecto independiente.

## aMule integrado

La pestaña aMule permite buscar por Kad, el servidor conectado o todos los servidores, filtrar por tipo y añadir resultados directamente a la cola del aMule que ya corre en el Mac. Web, macOS e iOS comparten esta misma interfaz. Las búsquedas pertenecen a una sola instancia de aMule: una nueva búsqueda sustituye la anterior también en otros dispositivos. La cola sigue funcionando al cerrar Dashboard.

El servidor se conecta por EC 0x0204 exclusivamente a `127.0.0.1:4712`; no añade otro motor ni un servicio permanente. Configurar `[ExternalConnect]` de aMule con `AcceptExternalConnections=1`, `ECAddress=127.0.0.1`, `ECPort=4712` y una credencial interna. En `server/.env`, `AMULE_ENABLED=true` y `AMULE_EC_PASSWORD_HASH` y `ECPassword` de aMule deben contener exactamente el mismo hash MD5 de la contraseña elegida (no volver a hashear ese valor). No exponer ese puerto a Internet ni incluir el hash en Git. aMule puede requerir un reinicio ordenado para aplicar estos ajustes.

No se ejecutan comandos de consola recibidos del cliente. Las operaciones usan el protocolo EC con autenticación, límites de tamaño y tiempo; el navegador recibe nombres, tamaños, fuentes y progreso, nunca la credencial interna. Descargar valida la generación de búsqueda y el hash exacto, evita duplicados y comprueba que el archivo aparece en la cola. Las mutaciones mantienen la autenticación y protección de origen del Dashboard.

Se muestran como máximo 500 resultados, ordenados por fuentes. Un archivo con cero fuentes puede quedar esperando indefinidamente. Organizer procesa los archivos terminados de la carpeta de entrada existente; los parciales de aMule deben permanecer en otra carpeta. En la instalación actual, aMule y Organizer ya comparten `~/Documents/Torrent`. Esta integración no modifica renombres, bibliotecas o historial existentes.

## Navegación compartida y presentación adaptable

En pantallas de hasta 600 px, la interfaz utiliza cinco accesos inferiores: Inicio, Descargas, Chollos, Orbit y Más. Inicio resume servicios y actividad; Descargas reúne la cola de aMule y las descargas del panel, con historial separado. El buscador aMule mantiene sus filtros plegables. Más agrupa equipos, estadísticas, historial, preferencias de lectura y Logs como última opción. Los ajustes de conexión permanecen en el contenedor nativo.

Las tarjetas muestran primero nombre, estado y progreso; los detalles se despliegan y conservan su apertura durante las actualizaciones. Chollos destaca la oferta más barata por producto y permite abrir las demás. La web y macOS utilizan las mismas cinco secciones con una barra lateral a partir de 601 px. Inicio presenta el resumen; las herramientas se encuentran en Más, con Logs al final. En escritorio las tablas muestran sus columnas y Chollos todas sus ofertas ordenadas. Los formularios y las colas son únicos para todos los tamaños: cambiar el ancho conserva valores, sección activa y estado, sin duplicar identificadores, credenciales ni lógica del servidor. El historial de descargas se puede consultar con el filtro Historial.
