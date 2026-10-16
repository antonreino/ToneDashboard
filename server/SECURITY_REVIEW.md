# Revisión de seguridad — 15 de octubre de 2026

Base revisada: `5fcd82c` de `antonreino/emby-organizer` y `836b0c9` de `antonreino/EmbyDashboardNative`. Los nombres de producto son ToneDashboard y ToneDashboardApps. En el momento de la revisión, los remotos con los nombres nuevos todavía no existían. El 16 de octubre de 2026 el propietario completó el cambio de nombre: los repositorios actuales son [ToneDashboard](https://github.com/antonreino/ToneDashboard) y [ToneDashboardApps](https://github.com/antonreino/ToneDashboard/tree/main/apple).

## Correcciones

- Descargas: la API, la entrada Telegram, la consulta de cabeceras y la descarga efectiva validan destinos públicos. Cada redirección valida nuevamente DNS. La conexión se fija a una dirección ya validada y TLS comprueba el hostname original. No se usan proxies del entorno ni un fallback sin validar. Se bloquean puertos ajenos a 80/443, credenciales en URL, redes internas y redirecciones HTTPS→HTTP. Los trabajos recuperados de SQLite pasan por la misma validación al descargarse.
- Reanudación: se verifica Content-Range, se reinicia el archivo si el servidor ignora Range y se detectan respuestas incompletas. Se mantiene caffeinate durante la descarga en macOS. El proceso de descarga pasa de curl a streaming HTTP de Python.
- API: las acciones requieren Origin coincidente o la cabecera del cliente nativo sin Origin; Fetch Metadata de otro sitio se rechaza. Los WebSocket de Orbit requieren Origin coincidente. Las credenciales Basic y la contraseña adicional no se reenvían a Orbit. Las comparaciones de credenciales admiten UTF-8.
- Proxy: la descompresión gzip tiene límite antes de crear un contenido completo en memoria. El destino del proxy sigue siendo fijo en localhost.
- App: las peticiones solo adjuntan credenciales a la autoridad HTTPS configurada. Las redirecciones fuera del origen y todas las redirecciones POST se bloquean. Las sesiones de API y WebKit son efímeras. Orbit recarga al cambiar ajustes y no repite indefinidamente un challenge fallido.
- Web: los enlaces de ofertas solo permiten HTTP/HTTPS. Las consultas se espacian a 12 segundos, se evita solaparlas y solo se consultan los datos de la vista activa.
- App: consultas cada 20 segundos mientras está activa; ofertas y logs solo en sus pestañas. La cancelación termina el bucle de actualización.
- Actualizador: validación previa, preparación de archivos, copia de los originales y restauración ante errores durante la sustitución. No cambia .env ni datos persistentes. El README ya no remite al instalador ausente.

## Comprobación

34 pruebas Python: controles de destinos, DNS mixto, redirección privada, IP fijada, TLS, reanudación, peticiones adversarias a los handlers, fallo de autenticación, restauración de actualización y regresiones existentes de Orbit/limpieza.

Pruebas Swift de autoridad HTTPS y callbacks de redirección. Compilaciones sin firma de macOS e iOS Simulator con Xcode 27.0. Las pruebas Swift se incorporan al workflow de la app y la validación de los módulos nuevos al workflow Python.

Inspección de SFTP y comandos: se conserva RejectPolicy y known_hosts; el comando de disco escapa la ruta. SQLite utiliza parámetros para las entradas revisadas. Los archivos .env reales, bases de datos y claves no aparecen entre los archivos versionados comprobados. No se ha certificado el historial Git completo ni las dependencias transitivas.

## Límites y activación

Orbit comparte origen con la API: un script comprometido de Orbit conserva capacidad para emitir solicitudes del mismo origen. La contraseña adicional protege el arranque, pero los controles CSRF no constituyen aislamiento entre aplicaciones del mismo origen. Se mantiene el uso privado/VPN documentado.

Las dependencias Python siguen sin versiones fijadas; esta revisión no determina vulnerabilidades de todas sus versiones. Los tests de red usan dobles y servidores locales; no se han descargado juegos reales ni probado dispositivos físicos.

Actualizar la app y reiniciar los procesos Python es necesario para activar todos los cambios. Los clientes antiguos sin `X-Dashboard-Action: write` tendrán que actualizarse. El actualizador puede restaurar fallos de aplicación detectados, pero no ofrece una transacción única frente a un corte de corriente ni revierte errores de launchctl.
