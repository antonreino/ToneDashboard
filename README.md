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
