# ToneDashboardApps

Aplicación nativa en **SwiftUI** para **macOS, iPhone y iPad**, que acompaña a [ToneDashboard](../ToneDashboard/README.md). Reemplaza el nombre anterior `EmbyDashboardNative` / `Emby Dashboard`.

## Funciones

| Pestaña | Funciones |
| --- | --- |
| Inicio | Métricas del Mac mini y del servidor Emby, servicios y almacenamiento |
| Descargas | Lista/progreso, encolar URL directa y subir `.torrent` |
| Orbit | Catálogo de Orbit Zero integrado en WebKit; carátulas, filtros, cola y progreso |
| Actividad | Historial y estadísticas disponibles en la API |
| Ofertas | PS5 y Switch, información de alertas del bot de precios |
| Logs | Registros de Organizer, Telegram y servicios |
| Ajustes | URL HTTPS de ToneDashboard, usuario y contraseña protegida en Keychain |

La pestaña **Orbit** no instala Orbit Zero ni almacena sus enlaces: usa el proxy `https://TU-DASHBOARD/orbit-bridge/zero/`. El navegador nativo reutiliza las credenciales Basic del dashboard **sólo para el host y puerto HTTPS configurados**. El inicio de Orbit está disponible mediante el endpoint protegido y pide una contraseña adicional de 12+ caracteres que **no se guarda**. Las ventanas de verificación que Orbit abre en el escritorio del Mac no se controlan desde el iPhone; completa ese paso en casa.

La propia aplicación de Orbit sigue gestionando los códigos de vinculación; ToneDashboardApps no los lee ni los almacena.

## Requisitos

- Xcode (compilación para ambas plataformas), iOS/iPadOS 17+ y macOS 14+.
- El servidor ToneDashboard actualizado, accesible por **HTTPS con certificado válido**. No se aceptan certificados falsos.
- `DASHBOARD_USER`, `DASHBOARD_PASSWORD` y, para iniciar Orbit, `ORBIT_CONTROL_PASSWORD` configurados en el Mac mini.
- VPN privada para acceder desde el iPhone fuera de la LAN. No publiques los puertos internos de Orbit.

## Abrir el proyecto

En el Mac con Xcode:

```bash
cd ToneDashboardApps
open ToneDashboardApps.xcodeproj
```

Esquemas: **ToneDashboardApps iOS** y **ToneDashboardApps macOS**. Si cambias ficheros con XcodeGen: `brew install xcodegen` y `./generate-xcodeproj.sh` (regenera el `.xcodeproj`).

En **Ajustes**, introduce la URL del dashboard `https://...`, usuario y contraseña. La URL debe ser HTTPS y se conserva en `UserDefaults`, mientras que la contraseña va a **Keychain**. El host de Orbit siempre será el mismo del dashboard, nunca una IP local solicitada al iPhone. Para un acceso remoto fiable utiliza una VPN privada y certificado correcto.

## Actualizar desde la app anterior

Se conserva el identificador de paquete previo (`ovh.tonecas.embydashboard.ios` y `.macos`) **intencionadamente** para permitir actualizar la instalación existente y conservar ajustes y Keychain. El nombre visual y los esquemas de Xcode ahora son **ToneDashboardApps**. No cambies el identificador de paquete sin planear la migración de credenciales.

La carpeta raíz y el `.xcodeproj` pasan a llamarse `ToneDashboardApps`; abre el nuevo proyecto en lugar del anterior. Conserva una copia del proyecto antiguo hasta compilar y probar Mac + simulador iPhone en tu Xcode.

## Seguridad y límites

- Login Basic sobre TLS; sin almacenamiento de contraseña de inicio de Orbit.
- WebKit sólo navega a páginas HTTPS bajo la autoridad configurada para el dashboard. No se abren páginas de proveedores dentro de otras ventanas del sistema.
- Sin VNC, sin lectura del llavero de Orbit, sin exposición de códigos de emparejamiento.
- El código fuente y los ZIP no contienen contraseñas ni `.env` reales.
- Las vistas nativas y Orbit se ejecutan en el mismo dispositivo, pero Orbit Zero debe seguir abierto en el Mac mini para proporcionar su catálogo/cola.

## Validación

```bash
xcodebuild -project ToneDashboardApps.xcodeproj -scheme 'ToneDashboardApps macOS' \
  -destination 'platform=macOS' CODE_SIGNING_ALLOWED=NO build
xcodebuild -project ToneDashboardApps.xcodeproj -scheme 'ToneDashboardApps iOS' \
  -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' \
  CODE_SIGNING_ALLOWED=NO build
```

La sintaxis Swift se puede validar fuera de macOS, pero para verificar realmente WebKit, permisos, empaquetado, firma e instalación hay que compilar con Xcode en un Mac. No se incluyen builds firmadas ni archivos de distribución de App Store.
