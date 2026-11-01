# Tonetti 0.1.1: IA local con memoria

Actualización 28/10/2026: Tonetti 0.1.8 incorpora consultas acotadas de solo lectura en el chat. Puede consultar en vivo la RAM, el inventario LXC y la raíz del host o de un contenedor de Proxmox mediante comandos fijos, y leer archivos fuente permitidos de proyectos concretos. Para logs de TV sin conexión configurada y para peticiones textuales de ejecutar tareas, deja explícito que no ha realizado la acción. El mantenimiento sigue usando el panel de planes confirmados; un piloto de copias delegadas verificó tres bases. La escritura de código generada por el modelo continúa supervisada porque falló un ejercicio de parser. No hay shell ni SSH libre para el modelo.

Tonetti 0.1.9 añade un piloto de delegación para la tarea programada de PS5 por petición expresa de Tone. La IA solo puede proponer el ID fijo; el plan de un solo uso y el ejecutor controlado de Dashboard conservan las restricciones de PS5. Lanzar no equivale a completar: el resultado se toma del informe final y las comprobaciones, no de la respuesta del modelo.

La primera ejecución del 28/10 fue parcial: revisó 12 fuentes y preparó actualizaciones, pero no instaló porque el gestor de la consola no respondía. Su proceso CodexCLI obtuvo un error de ruta local de macOS. `ToneMaintenanceRunner`, ya autorizado para Red local, se ha ampliado al ID fijo de PS5; su prueba puntual alcanzó la IP y recibió conexión rechazada, que indica que el gestor no está escuchando en ese momento. Se requiere una nueva revisión cuando la consola y su cadena estén accesibles; no se reintentó automáticamente.

Implementación independiente en el proyecto privado [antonreino/tonetti](https://github.com/antonreino/tonetti), antes carpeta Jarvis. La versión del asistente es0.1.1; no reinicia la versión pública del Dashboard. El adapter `server/tonetti.py` usa un ZIP versionado del paquete y comprueba su SHA256. Se genera con `../tonetti/scripts/bundle_dashboard.py`, sin datos privados ni una segunda implementación manual. Dashboard y su CI funcionan sin acceso al checkout privado.

La interfaz única `web/tonetti.js` sirve a web,Mac e iPhone. No requiere reinstalar contenedores Apple. Conversación protegida por auth y origen existentes, salida renderizada como Markdown seguro, API modelo solo127.0.0.1. No hay SSH,shell,Telegram,navegador ni escritura de proyectos disponible para el modelo: genera propuestas, no ejecuta ni aplica parches.

## Identidad y contexto

Nombre de la IA:Tonetti. Interlocutor:Tone. Perfil privado con preferencias, trabajo técnico habitual, proyectos, infraestructura e incidencias históricas. No se inventa profesión o empresa. Inventario fechado deProxmox/LXC/VM,Dashboard,PS5 yprocedimientos; documentos versionados localmente, no presentados como telemetría.

`data/tonetti/infrastructure.md`, `tone-profile.md` y `runbooks.md` y `projects.json` son privados y excluidos deGit. El catálogo de tareas se lee en la consulta pertinente mediante `scheduled_tasks.snapshot()`, sin exponer prompts. El listado y los horarios se renderizan desde datos actuales para evitar que el modelo invente estados o fechas.

## Memoria persistente

`data/tonetti/chat.sqlite3` conserva mensajes anteriores sin borrarlos al cambiar la ventana del modelo. Tablas aditivas para búsquedaFTS5 y referencias. Se indexan declaraciones deTone; las respuestas de la IA no se convierten en hechos confirmados. Se priorizan correcciones recientes de una misma entidad, manteniendo el original. Las credenciales reconocibles se excluyen del índice; no introducir secretos en el chat.

Directorio0700,base0600. La UI muestra páginas de hasta 80 entradas por conversación y permite cargar las anteriores; la base conserva el resto. El contexto del modelo usa hasta12 mensajes recientes/6000caracteres más evidencia recuperada y catálogo pertinente; ventana12288tokens. Almacenar todo no significa introducir todo simultáneamente ni garantiza recuerdo perfecto ante cualquier pregunta. Puede equivocarse. Un reinicio marca respuesta interrumpida sin reenviarla automáticamente.

El índice de código se crea desde árboles explícitos:server,web,docs yworkers/price_tracker. Excluye backups históricos,.env,datos,tests,logs,audits,symlinks yotrosdirectoriosprivados. Fuentes deDashboard se revisan de nuevo ante preguntas sobre código/scripts/parches. `../tonetti/scripts/index_dashboard.py` realiza una actualización completa controlada. Los documentos se separan por sección para no mezclar incidentes.

## Operación y verificación

Ollama estable0.40.8,servicio sh.brew.ollama,cloud desactivado,un modelo/una inferencia simultáneos,descarga tras2min sinuso. Modelo activo:Gemma 4 12B,solo local; Qwen3.5:9b-q4_K_M se conserva para recuperación. Mediciones de la comparación en `../audits/tonetti-training-20261023/RESULTADO.md`. Conservar variables de privacidad enLaunchAgents siHomebrewregeneraelplist.

Pruebas: batería delDashboard,backendauth/origen,adaptaciónresponsive,pruebas delpaqueteTonetti ymensajessintéticosconmásde2100entradas. Evaluacionesdeincidentes guardan respuestas completas y fallos:coincidenciasdepalabrasno equivalenacorreccióntécnica. No es fine-tuning ni promesa de resolución autónoma.

Se conserva la base en su rutaoriginal; no se migra al renombrar elproyecto. Copia previa verificada antes de modificar esquema en audits/tonetti-training-20261023/chat-before.sqlite3. La memoriaSQLite ya está incluida en la tarea existenteCopiasverificadas,conintegridad yretención14. SoncopiaslocalesdelMac,norespaldoexternoindependiente. Conservartambiéndocumentosprivadosenlas copiasdelpropietario; nunca subirlosalrepo.

Tone Dashboard es la aplicación; Tonetti es la IA independiente; OpenClaw es su entorno de agente y Ollama es el motor local. Integrar el chat no fusiona proyectos, datos ni versiones.

Actualización 29/10/2026: el chat de Tone Dashboard delega sus turnos en el agente principal de OpenClaw mediante su Gateway local. Cada conversación conserva una sesión estable `agent:main:tone-dashboard-v4-fast-agent-<espacio>-<id>`. El agente dispone de lectura y edición del workspace, con un catálogo reducido; la ejecución continúa limitada por allowlist y las acciones sensibles requieren autorización. El historial, los adjuntos y la autenticación continúan en el Dashboard. El Dashboard no expone el token del Gateway ni convierte el texto del usuario en shell: invoca el CLI con argumentos separados y un archivo temporal privado. Integrar el chat no autoriza reinicios, firmware, borrados ni cambios destructivos.

El modelo activo único del chat y del agente es `qwen3.5:9b-q4_K_M`. El 4B, el 20B, el 7B de código, el modelo de embeddings y Gemma se retiraron el 01/11/2026 para evitar presión de memoria y duplicación de funciones en el Mac de 16 GB. La prueba operativa del 4B creó y releyó un archivo aislado; otra lectura real del workspace tardó 38,458 segundos. La prueba compleja «Adivina el Pokémon» no produjo una implementación válida y no se publicó. El supervisor ignora `__pycache__` y exige cambios fuente reales para evitar falsos candidatos. Esto acredita herramientas básicas, no autonomía general.

La configuración privada usa `qwen3.5:9b-q4_K_M`; `data/tonetti/runtime-model.json` registra el digest validado para las comprobaciones periódicas. Revisión diaria pequeña a las 06:30 Europe/Madrid, unitarias y dos casos; los lunes servidor completo. Sin nuevas herramientas administrativas para la IA.

## Conversaciones y adjuntos

El chat compartido permite crear, renombrar y retomar conversaciones. La migración conserva los identificadores y el texto anteriores en «Historial anterior». El historial reciente se limita al hilo abierto; la recuperación de declaraciones del usuario y documentos sigue disponible entre hilos. Guardar todo no significa introducirlo todo en cada respuesta: hay presupuestos de contexto y la recuperación puede omitir información relevante. Las respuestas del modelo no se convierten en hechos confirmados.

Los mensajes de Tonetti muestran Markdown seguro (énfasis, listas, citas, tablas y código copiable); no se interpreta HTML ni se cargan imágenes externas del modelo. Se pueden adjuntar hasta cuatro archivos por mensaje, con un máximo de dos imágenes y 8 MB por archivo, mediante botón, arrastre o pegado de imágenes. JPEG/PNG/WebP se normalizan a JPEG de hasta 1280 píxeles para el modelo visual local. PDF con texto, DOCX y texto UTF-8 se leen sin ejecutar su contenido; un PDF escaneado necesita OCR o fotos. La extracción se limita a 50 páginas/60.000 caracteres y el contexto de adjuntos a 20.000 caracteres por turno. Los originales permanecen privados y no se publican con el código.

El parser usa un proceso temporal, 20 segundos de tiempo máximo, límite de CPU y comprobación de memoria; solo un adjunto se procesa a la vez. El almacenamiento tiene un tope de 512 MB. Las rutas requieren autenticación; los originales se sirven como descargas con `nosniff`, nunca como HTML activo. Las apps solo aceptan esas descargas desde su origen HTTPS configurado. No hay ejecución de documentos ni nuevos permisos de administración de infraestructura.

Las copias verificadas diarias incluyen ahora una copia privada independiente de cada objeto de adjunto, validada por SHA256, en `backups/chat/attachments`. Los objetos son inmutables y se copian una sola vez, sin multiplicar fotos por cada copia diaria de SQLite. Para restaurar un historial con adjuntos se necesitan tanto su instantánea SQLite como este directorio. Las copias siguen siendo locales, no una protección ante pérdida del disco completo.

Revisión 25/10: el contexto selecciona las tareas nombradas, conserva JSON válido y el registro relevante; no confunde fecha de consulta con fecha del evento. Dos inferencias con reservas semánticas documentadas; no es entrenamiento de pesos ni garantía de exactitud.


## Planes confirmados de tareas · Dashboard 1.2.2

En Tonetti, abrir «Preparar una tarea de mantenimiento», elegir un ID del catálogo y preparar el plan. Se muestran requisitos, controles, límites y ejecutor. Preparar no ejecuta. «Confirmar y ejecutar esta tarea» es una acción explícita del propietario, protegida por la autenticación y el control de origen habituales. Los mensajes, los documentos y las respuestas del modelo no seleccionan comandos ni disparan acciones.

Los seis IDs actuales reutilizan `task_runner`, sus bloqueos y el perfil limitado ya autorizado. Las cuatro revisiones de Codex siguen dependiendo de Codex y su cuota; las copias y recuperación aMule son operaciones internas. No es todavía sustitución autónoma de Codex por el modelo local ni cambia los horarios.

Los planes privados se conservan en `data/tonetti-task-plans/plans.sqlite3` (0600), con procedimiento identificado por hash y vigencia de diez minutos. Pausas y cambios invalidan el lanzamiento. Cada plan se consume antes de despachar: un doble clic, reinicio o respuesta perdida no provoca reintento automático. Si se pierde el recibo, revisar Tareas programadas antes de crear otro. Los planes aceptados se correlacionan con la hora exacta del lanzamiento; si aparece otra ejecución, se indica que debe consultarse el historial. Los resultados completos siguen en los registros habituales; la pantalla no convierte parciales en éxitos. Cien planes sin usar como máximo, limpieza de preparados caducados tras un día; los consumidos se conservan como auditoría.

No hay timeout que mate una actualización a medias: la caducidad se aplica a la confirmación, no a una operación ya aceptada. La autonomía completa requiere más trabajo y validación por capacidad.


## Comprensión y seguimiento · Tonetti 0.1.1
El modelo y sus permisos se conservan. Las preguntas cortas con referencia al hilo recuperan contexto desde mensajes completados del usuario en esa conversación; un equipo nombrado explícitamente mantiene su propio alcance. No se usan respuestas de la IA como antecedente para escoger la tarea. Es una heurística acotada, no resolución universal de ambigüedades. El catálogo transmite ahora execution y bloqueo separados del último resultado guardado, y el listado textual explica las ejecuciones en curso. Se añaden diez regresiones de continuidad/estado y dos casos nuevos de evaluación local; una prueba adicional protege el proveedor sintético. Revisión semántica: un correcto y uno con reservas por atribuir verificación no acreditada. El error queda conservado y la mejora posterior de instrucciones sigue pendiente de validación de transferencia. No se han modificado controles visuales ni añadido herramientas; la integración anterior de planes se mantiene.


## Refinamiento progresivo ·0.1.1
Las migraciones genéricas y la palabraWAL no seleccionanSQLite por defecto; motores explícitos separan guías. Las comparaciones temporales reciben hasta tres registros fechados y uno no conciliado, conUTC y alcance del orden visibles; la ausencia de zona impide declarar un último global. Se preservan presupuestos de contexto y registros originales. El currículo diario pasa a29 casos, manteniendo dos inferencias por revisión y sin nuevas tareas. No se han añadido permisos ni herramientas a la IA. El examen progresivo ha detectado errores críticos y reservas, por lo que el uso sigue supervisado; no se acredita recuperación/código autónomos ni se promete perfección. Informes privados del25/10 conservan criterios y respuestas con revisiones por hash.

## Latencia y entrega progresiva (27/10/2026)

Tonetti 0.1.3 entrega fragmentos locales mientras genera. El mensaje sigue pendiente hasta recibir el cierre válido; un flujo cortado o agotado queda como error, nunca completo. La interfaz común consulta cada 750 ms mientras responde y muestra «Trabajando · N s» y «Trabajó durante N s». Es tiempo de respuesta, no prueba de acciones ejecutadas. Los registros anteriores sin métricas no reciben una duración inventada.

`response_metrics` en la base privada guarda preparación, primer texto, carga, evaluación del contexto, generación y duración final sin copiar prompts ni secretos. Modelo activo qwen2.5-coder:7b; fotos conservan Gemma local. Una sola inferencia y residencia de 10 minutos tras cada consulta, sin carga periódica forzada. No hay caché de respuestas o estados de infraestructura; las fuentes actuales se siguen consultando.

Auditoría local `../audits/tonetti-latency-20261027`: ejemplo sintético frío 35 s (26 s contexto, 5 s carga); cálido 14,3 s; consulta enfocada 7,3 s hasta texto / 12,1 s total. No son percentiles ni una comparación idéntica fría/caliente. Preguntas grandes o modelo descargado pueden tardar más.
