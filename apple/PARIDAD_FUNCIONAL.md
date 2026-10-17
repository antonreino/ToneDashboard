# Una única interfaz ·1.0.0

Web, macOS e iOS cargan la misma raíz del dashboard: Inicio, descargas, Orbit, actividad, ofertas, estadísticas y logs. `ContentView.swift` contiene el contenedor, ajustes y adaptaciones del sistema; `DashboardSession.swift` conserva conexión/almacén por cuenta. El llavero no se expone a JavaScript.

Regresiones funcionales: `server/tests`, `workers/price_tracker/tests` y pruebas JS. `apple/tests/ContainerTests.swift` cubre origen y preferencias; el test WebKit comprueba cookies. Los diálogos, archivos y ciclo de vida se comprueban también en dispositivos.

La búsqueda y la cola de aMule se implementan en la interfaz común y en el servidor: no necesitan un navegador externo ni cambios de credenciales del contenedor Apple.
