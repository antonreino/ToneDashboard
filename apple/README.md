# Tone Dashboard · contenedores Apple 1.2.0

Parte del único repositorio [ToneDashboard](https://github.com/antonreino/ToneDashboard). Ambos targets cargan la interfaz común `web/` mediante HTTPS. Se mantienen bundle IDs, preferencias `baseURL`/`username`, llavero y almacén WebKit de la cuenta existente. Cuentas diferentes tienen almacenes separados, sin borrar los anteriores.

La UI funcional se prueba en servidor y JavaScript; aquí se prueban origen, autenticación, cookies y migración de ajustes. Abrir `ToneDashboardApps.xcodeproj`. Versión pública 1.2.0. El contador interno de Apple no se muestra al usuario.


## Paquete de macOS

Distribuir la configuración **Release** en un paquete nuevo, conservando `ENABLE_DEBUG_DYLIB=NO` en el target macOS. No superponer una compilación Release encima de una app Debug: pueden quedar archivos antiguos. Firmar el paquete final y ejecutar `bash apple/verify-macos-app.sh /ruta/ToneDashboardApps.app`; comprobar también un arranque real antes de instalar. Una firma válida por sí sola no demuestra que dyld pueda cargar todas las bibliotecas.

Corrección de empaquetado 21/10/2026: la primera instalación 1.2.0 usaba una biblioteca Debug que macOS rechazaba por identidad de firma. Se sustituyó por Release sin esa dependencia; versión pública 1.2.0 conservada porque no cambió la interfaz ni sus datos. No se desactivó validación de bibliotecas ni ninguna protección de macOS.
