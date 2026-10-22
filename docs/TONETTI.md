# Tonetti 0.0.1: IA local con memoria

Implementación independiente en el proyecto privado [antonreino/tonetti](https://github.com/antonreino/tonetti), antes carpeta Jarvis. La versión del asistente es0.0.1; no reinicia la versión pública del Dashboard. El adapter `server/tonetti.py` usa un ZIP versionado del paquete y comprueba su SHA256. Se genera con `../tonetti/scripts/bundle_dashboard.py`, sin datos privados ni una segunda implementación manual. Dashboard y su CI funcionan sin acceso al checkout privado.

La interfaz única `web/tonetti.js` sirve a web,Mac e iPhone. No requiere reinstalar contenedores Apple. Conversación protegida por auth y origen existentes, salida renderizada como texto, API modelo solo127.0.0.1. No hay SSH,shell,Telegram,navegador ni escritura de proyectos disponible para el modelo: genera propuestas, no ejecuta ni aplica parches.

## Identidad y contexto

Nombre de la IA:Tonetti. Interlocutor:Tone. Perfil privado con preferencias, trabajo técnico habitual, proyectos, infraestructura e incidencias históricas. No se inventa profesión o empresa. Inventario fechado deProxmox/LXC/VM,Dashboard,PS5 yprocedimientos; documentos versionados localmente, no presentados como telemetría.

`data/tonetti/infrastructure.md`, `tone-profile.md` y `runbooks.md` y `projects.json` son privados y excluidos deGit. El catálogo de tareas se lee en la consulta pertinente mediante `scheduled_tasks.snapshot()`, sin exponer prompts. El listado y los horarios se renderizan desde datos actuales para evitar que el modelo invente estados o fechas.

## Memoria persistente

`data/tonetti/chat.sqlite3` conserva mensajes anteriores sin borrarlos al cambiar la ventana del modelo. Tablas aditivas para búsquedaFTS5 y referencias. Se indexan declaraciones deTone; las respuestas de la IA no se convierten en hechos confirmados. Se priorizan correcciones recientes de una misma entidad, manteniendo el original. Las credenciales reconocibles se excluyen del índice; no introducir secretos en el chat.

Directorio0700,base0600. La UI muestra últimas80 entradas; la base conserva el resto. El contexto del modelo usa hasta12 mensajes recientes/6000caracteres más evidencia recuperada y catálogo pertinente; ventana12288tokens. Almacenar todo no significa introducir todo simultáneamente ni garantiza recuerdo perfecto ante cualquier pregunta. Puede equivocarse. Un reinicio marca respuesta interrumpida sin reenviarla automáticamente.

El índice de código se crea desde árboles explícitos:server,web,docs yworkers/price_tracker. Excluye.env,datos,tests,logs,audits,symlinks yotrosdirectoriosprivados. Fuentes deDashboard se revisan de nuevo ante preguntas sobre código/scripts/parches. `../tonetti/scripts/index_dashboard.py` realiza una actualización completa controlada. Los documentos se separan por sección para no mezclar incidentes.

## Operación y verificación

Ollama estable0.40.8,servicio sh.brew.ollama,cloud desactivado,un modelo/una inferencia simultáneos,descarga tras2min sinuso. Modelo definitivo:Qwen3.5:9b-q4_K_M,solo local. Mediciones de la comparación en `../audits/tonetti-training-20261023/RESULTADO.md`. Conservar variables de privacidad enLaunchAgents siHomebrewregeneraelplist.

Pruebas: batería delDashboard,backendauth/origen,adaptaciónresponsive,pruebas delpaqueteTonetti ymensajessintéticosconmásde2100entradas. Evaluacionesdeincidentes guardan respuestas completas y fallos:coincidenciasdepalabrasno equivalenacorreccióntécnica. No es fine-tuning ni promesa de resolución autónoma.

Se conserva la base en su rutaoriginal; no se migra al renombrar elproyecto. Copia previa verificada antes de modificar esquema en audits/tonetti-training-20261023/chat-before.sqlite3. La memoriaSQLite ya está incluida en la tarea existenteCopiasverificadas,conintegridad yretención14. SoncopiaslocalesdelMac,norespaldoexternoindependiente. Conservartambiéndocumentosprivadosenlas copiasdelpropietario; nunca subirlosalrepo.
