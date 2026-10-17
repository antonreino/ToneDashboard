# Tone Dashboard · contenedores Apple 1.1.0

Parte del único repositorio [ToneDashboard](https://github.com/antonreino/ToneDashboard). Ambos targets cargan la interfaz común `web/` mediante HTTPS. Se mantienen bundle IDs, preferencias `baseURL`/`username`, llavero y almacén WebKit de la cuenta existente. Cuentas diferentes tienen almacenes separados, sin borrar los anteriores.

La UI funcional se prueba en servidor y JavaScript; aquí se prueban origen, autenticación, cookies y migración de ajustes. Abrir `ToneDashboardApps.xcodeproj`. Versión pública 1.1.0. El contador interno de Apple no se muestra al usuario.
