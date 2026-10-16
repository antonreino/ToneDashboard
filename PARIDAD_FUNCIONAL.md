# Paridad con ToneDashboard web — versión 1.1 (2)

Revisión del 16 de octubre de 2026 sobre `emby-organizer/scripts/log-viewer.py` y los dos targets SwiftUI. El botón de código de Orbit ya existía en el código fuente anterior; esta revisión refuerza su ciclo de vida y accesibilidad, y completa las diferencias de datos y errores. Tener el repositorio actualizado no actualiza por sí solo las aplicaciones instaladas.

| Función web | iOS/iPadOS y macOS 1.1 |
| --- | --- |
| Servicios y métricas del Mac | CPU, GPU, RAM, presión de memoria, swap, temperaturas CPU/GPU, red y discos |
| Servidor Emby | CPU, RAM, carga, almacenamiento, fecha del dato, estado obsoleto y errores |
| Resumen 24 horas | Eventos, correctos, errores, bytes descargados y movidos |
| Descargas | URL directa, torrent, progreso, bytes, velocidad activa, ETA, intentos y errores; bloqueo de envíos dobles |
| Estadísticas | Totales históricos, fechas, periodos con cantidades y desglose por biblioteca |
| Historial | Tipo, estado, título, categoría, fecha y detalle |
| Ofertas | Familias PS5/Switch, precio, vendedor, envío, disponibilidad, tipo, última lectura y enlaces HTTP(S) |
| Bot de ofertas | Historial completo recibido, eventos de fuentes y registro |
| Logs | Selección 100/300/1000 líneas y servicios adicionales que devuelva la API |
| Orbit | Catálogo/cola mediante el mismo proxy WebKit, comprobar, recargar e inicio protegido |
| Código Orbit | Petición protegida con contraseña separada; sin persistencia ni portapapeles; plazo del servidor limitado a 60 s |
| Actualización | Consultas cada 12 s en primer plano; ofertas y logs solo en su pestaña; errores visibles |

## Seguridad y ciclo de vida

El código se borra al cerrar, cambiar de pestaña, cambiar URL/credenciales o abandonar el primer plano. La caducidad cierra el diálogo. Una respuesta tardía de una petición cancelada no puede volver a mostrarlo. La contraseña adicional se limpia del campo antes de la consulta. Los mensajes de JSON inválido no reproducen el cuerpo de respuesta, que podría contener un código. Las respuestas del servidor anterior se descartan si cambian las credenciales; se limpian los datos visibles al editar la conexión.

Se mantienen HTTPS obligatorio, validación del certificado del sistema, credenciales limitadas al origen y rechazo de redirecciones de acciones POST. No cambia la configuración del servidor ni se automatiza la lectura real del código durante los tests.

## Verificación

- `tests/APISecurityTests.swift`: orígenes y política de redirecciones.
- `tests/FunctionalParityTests.swift`: transporte simulado, cabeceras de contraseñas separadas, errores 401/429/503, JSON inválido sin filtración, caducidad, cancelación tardía, reintentos, acciones simuladas de arranque/descarga/torrent, ofertas, logs, estado Orbit y cambio de cuenta.
- `tests/ServerContractTests.swift`: decodificación de las cuatro respuestas de lectura, tanto contra el servidor local real como con fixtures anonimizados para CI. No se publican respuestas privadas.
- Compilación Xcode de macOS e iOS Simulator sin firma de distribución.

Los tests no descargan archivos, no envían torrents, no arrancan Orbit ni obtienen un código real. La firma y la instalación en un iPhone físico, y la vinculación real a la PS5, requieren pruebas posteriores en ese dispositivo. Las comprobaciones de interfaz en simulador no sustituyen esas pruebas.

- 1.3 (4): alta EAN mediante `POST /api/deals/products`, listado `products` y ofertas con campo `ean` en `/api/deals`. Formulario, tarjeta por producto y orden ascendente de precios en web, iOS y macOS. Errores de validación del servidor visibles; sin productos duplicados.

- 1.3.1 (5): eliminación confirmada mediante `POST /api/deals/products/remove` en web, iOS y macOS. Conservación del historial y cancelación de avisos EAN pendientes en el tracker; Telegram compartido para todos los EAN.
