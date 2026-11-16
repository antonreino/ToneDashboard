# Tone Dashboard · 1.2.2

Panel privado unificado para web, macOS e iOS. Reúne Tonetti, descargas, Organizer, ofertas, calendario, automatizaciones y diagnóstico en una sola interfaz adaptable.

## Estructura

- `web/`: **una sola interfaz**, adaptable a navegador, Mac, iPhone e iPad. Pantallas, formularios, precios y diálogos compartidos.
- `server/`: API autenticada, métricas, historial, Organizer y automatización de descargas.
- `workers/price_tracker/`: PS5/Switch/EAN y bot Telegram; la API utiliza este mismo paquete dentro del repositorio.
- `apple/`: contenedor SwiftUI/WebKit para macOS/iOS. Solo ajustes, llavero, aislamiento por origen/cuenta, selección de archivos y diálogos nativos. No replica pantallas ni modelos de ofertas.
- `VERSION`: versión común. El contador interno de Apple se conserva para permitir actualizaciones y no se muestra al usuario.

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

El dashboard mantiene el puerto8765 y las rutas API. El tracker utiliza `workers/price_tracker/data/prices.sqlite3`. Organizer, descargas e historial mantienen `~/.local/share/emby_organizer`; los identificadores LaunchAgent `com.tone.*` se conservan. No se añaden servicios permanentes.

## Apps Apple

Abrir `apple/ToneDashboardApps.xcodeproj`: versión 1.2.2. Los identificadores de bundle y llavero anteriores se conservan para actualizar sin perder credenciales, preferencias ni cookies. La cuenta anterior mantiene su almacén WebKit; otras cuentas tienen almacenes persistentes separados.

Las apps cargan `/` del dashboard HTTPS. Las mejoras de interfaz se reciben al recargar; cambios del contenedor requieren nueva compilación. Autenticación y navegación quedan limitadas al origen configurado. No se entregan contraseñas a JavaScript ni hay un puente de ejecución de comandos.

## Pruebas

```bash
bash scripts/check.sh
swiftc apple/ToneDashboardApps/APIClient.swift apple/ToneDashboardApps/DashboardSession.swift apple/ToneDashboardApps/KeychainStore.swift apple/tests/ContainerTests.swift -o /tmp/container-tests
/tmp/container-tests
```

CI ejecuta regresiones de servidor y tracker, pruebas de la interfaz común, seguridad del contenedor, el modelo del widget de uso y compilaciones macOS/iOS. La migración se valida además contra servicios y datos reales; los informes privados no se publican.

## Funciones actuales

- **Tonetti:** conversaciones persistentes, historial paginado, Markdown seguro, recuperación de contexto y adjuntos privados de texto, PDF, DOCX e imágenes. Las acciones sensibles se preparan como planes confirmables y las tareas permitidas tienen identificadores y límites fijos.
- **Descargas:** enlaces HTTP/HTTPS validados, torrents, pausa, reanudación, cancelación, progreso, velocidad, tiempo estimado e historial. Los destinos, redirecciones y tamaños se comprueban en el servidor.
- **aMule:** búsqueda por Kad/servidor, filtros, incorporación por hash exacto y seguimiento de la cola mediante EC local autenticado.
- **Organizer y Emby:** clasificación y revisión de archivos, reglas recordadas, cuarentena, publicación SFTP segura, refresco de bibliotecas y métricas de almacenamiento y sistema.
- **Ofertas:** seguimiento de PS5, Switch y productos EAN, agrupación por producto, altas y bajas persistentes, alertas configurables e historial de avisos por Telegram.
- **Calendario de anime:** seguimiento de series, portadas, episodios y anuncios oficiales, fechas japonesas separadas del doblaje castellano y calendario privado suscribible.
- **Tareas programadas:** catálogo de automatizaciones Codex y trabajos internos, horarios, requisitos, resultados documentados y ejecución manual de los perfiles expresamente autorizados.
- **Diagnóstico y copias:** servicios, métricas, actividad, logs, exportación sin secretos y copias SQLite verificadas con retención limitada.
- **Apps Apple:** interfaz web común dentro de contenedores SwiftUI/WebKit, credenciales separadas por servidor en el llavero y descargas/compartición nativas.
- **Tone Usage:** panel macOS independiente que consulta los límites de Codex desde ChatGPT instalado en `/Applications`, `~/Applications` o `/Volumes/Datos/Apps`.

Amazon e Idealo mantienen sus limitaciones previas y no se presentan como fuentes operativas cuando la lectura está bloqueada.

## aMule integrado

La pestaña aMule permite buscar por Kad, el servidor conectado o todos los servidores, filtrar por tipo y añadir resultados directamente a la cola del aMule que ya corre en el Mac. Web, macOS e iOS comparten esta misma interfaz. Las búsquedas pertenecen a una sola instancia de aMule: una nueva búsqueda sustituye la anterior también en otros dispositivos. La cola sigue funcionando al cerrar Dashboard.

El servidor se conecta por EC 0x0204 exclusivamente a `127.0.0.1:4712`; no añade otro motor ni un servicio permanente. Configurar `[ExternalConnect]` de aMule con `AcceptExternalConnections=1`, `ECAddress=127.0.0.1`, `ECPort=4712` y una credencial interna. En `server/.env`, `AMULE_ENABLED=true` y `AMULE_EC_PASSWORD_HASH` y `ECPassword` de aMule deben contener exactamente el mismo hash MD5 de la contraseña elegida (no volver a hashear ese valor). No exponer ese puerto a Internet ni incluir el hash en Git. aMule puede requerir un reinicio ordenado para aplicar estos ajustes.

No se ejecutan comandos de consola recibidos del cliente. Las operaciones usan el protocolo EC con autenticación, límites de tamaño y tiempo; el navegador recibe nombres, tamaños, fuentes y progreso, nunca la credencial interna. Descargar valida la generación de búsqueda y el hash exacto, evita duplicados y comprueba que el archivo aparece en la cola. Las mutaciones mantienen la autenticación y protección de origen del Dashboard.

Se muestran como máximo 500 resultados, ordenados por fuentes. Un archivo con cero fuentes puede quedar esperando indefinidamente. Organizer procesa los archivos terminados de la carpeta de entrada existente; los parciales de aMule deben permanecer en otra carpeta. En la instalación actual, aMule y Organizer ya comparten `~/Documents/Torrent`. Esta integración no modifica renombres, bibliotecas o historial existentes.

## Navegación compartida y presentación adaptable

En pantallas de hasta 600 px, la interfaz utiliza cuatro accesos inferiores: Inicio, Descargas, Chollos y Más. Inicio resume servicios y actividad; Descargas reúne la cola de aMule y las descargas del panel, con historial separado. El buscador aMule mantiene sus filtros plegables. Más agrupa equipos, estadísticas, historial, preferencias de lectura y Logs como última opción. Los ajustes de conexión permanecen en el contenedor nativo.

Las tarjetas muestran primero nombre, estado y progreso; los detalles se despliegan y conservan su apertura durante las actualizaciones. Chollos destaca la oferta más barata por producto y permite abrir las demás. Web y macOS utilizan la misma navegación compartida, con barra lateral a partir de 601 px. Inicio presenta el resumen; las herramientas se encuentran en Más, con Logs al final. En escritorio las tablas muestran sus columnas y Chollos todas sus ofertas ordenadas. Los formularios y las colas son únicos para todos los tamaños: cambiar el ancho conserva valores, sección activa y estado, sin duplicar identificadores, credenciales ni lógica del servidor. El historial de descargas se puede consultar con el filtro Historial.

## Novedades 1.1

Controles persistentes de descargas y aMule; revisión de cuarentena y reglas recordadas; alertas por producto/destinatario; historial paginado y recorrido de archivos; diagnóstico exportable y copias SQLite diarias verificadas. Se optimizan las consultas por sección, las métricas compartidas y la lectura de logs. El llavero pasa a separar credenciales por servidor, puerto y usuario, conservando la cuenta instalada.

Consulta [Operación y recuperación](docs/OPERACIONES.md) para conocer límites, restauración y pruebas.

## Numeración de versiones

La versión publicada es **1.2.2**; la siguiente será **1.2.3**, seguida de 1.2.4, …, 1.2.9 y 1.3.0. Cada versión publicada incrementa el último dígito; después de 9, ese dígito vuelve a 0 y se incrementa el componente central. La versión principal permanece en 1 hasta que el propietario autorice expresamente cambiarla. La versión pública es común a web, macOS e iOS y se presenta sin sufijos ni números entre paréntesis. El contador interno de Apple no forma parte del nombre público.

Con `AMULE_AUTOSTART=true`, el mantenimiento existente del Dashboard comprueba aMule cada 30 segundos y solicita abrir la aplicación instalada si no existe proceso ni control EC disponible. No mata ni reinicia instancias abiertas, limita reintentos a dos minutos y no añade agentes permanentes. La búsqueda compartida usa siempre «Todos los servidores» y muestra un único aviso ante el mismo fallo de conexión.

Organizer conserva el bloqueo ante carpetas ambiguas. `ORGANIZER_SERIES_FOLDER_OVERRIDES` permite fijar explícitamente una coincidencia existente por categoría y título normalizado, por ejemplo `{"series":{"suenosdelibertad":"Sueños de Libertad"}}`. Nunca permite apuntar fuera de las carpetas coincidentes ni fusiona o elimina contenido.

El calendario ordena siempre las series en emisión primero y las demás después, alfabéticamente dentro de cada grupo (sin distinguir mayúsculas o tildes, con ñ en su posición española). El orden se calcula al consultar y no modifica el historial.


## Interfaz y estado del proyecto

La versión 1.2.0 comparte un tema crema entre web, Mac e iPhone, con accesos directos a Anime y Tareas y herramientas agrupadas por función. Tareas programadas descubre las automatizaciones de Codex y muestra horarios, requisitos y resultados documentados, junto con las copias y recuperación de aMule del Dashboard. Permite lanzar tareas autorizadas y no publica instrucciones privadas.

- [Instantánea del proyecto y prioridades](docs/ESTADO-PROYECTO-2026-10-21.md)
- [Catálogo de tareas y registro de nuevas automatizaciones](docs/TAREAS-PROGRAMADAS.md)
- [Operación, datos y recuperación](docs/OPERACIONES.md)

## Novedades 1.2.2

Tonetti incorpora conversaciones, historial paginado, Markdown seguro y adjuntos privados. El calendario distingue anuncios oficiales de temporada y episodios emitidos. El widget Tone Usage localiza ChatGPT también en el disco de datos. La integración retirada ya no forma parte de la interfaz, del servidor, de las apps, de las pruebas ni de la documentación.
