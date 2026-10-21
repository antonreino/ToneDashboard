# Tareas programadas

La sección común web, macOS e iOS muestra el catálogo de automatizaciones de Codex y las tareas periódicas del propio Dashboard. El catálogo explica los resultados históricos. «Recargar informes» solo consulta los registros. «Ejecutar ahora» inicia una de las seis tareas autorizadas tras confirmación; no permite editar órdenes, horarios ni instrucciones desde el cliente.

## Qué se muestra

| Tarea | Horario (Europe/Madrid) | Función |
| --- | --- | --- |
| Anime: Japón y avisos | Cada 3 horas | Portadas, próximas emisiones japonesas y doblajes castellanos; Telegram solo tras verificar la publicación. |
| Anime: próximas temporadas | Lunes, 08:00 | Investigación de continuaciones y películas; conserva los animes archivados y las bajas manuales. |
| Mantener payloads de PS5 | Diario, 10:00 | Versiones oficiales, compatibilidad, recuperación e informe Telegram. Puede despertar una consola emparejada; no ejecuta el jailbreak ni reinicia la consola. |
| Mantenimiento semanal Proxmox y Emby | Lunes, 04:00 | Actualizaciones compatibles, copias y validaciones; aplaza reinicios con actividad y notifica siempre. |
| Copias verificadas | Cada 24 horas de actividad del Dashboard | Copias consistentes de las bases, comprobación de integridad y retención. |
| Disponibilidad de aMule | Cada 30 segundos | Comprueba el proceso; si está ausente y la recuperación está habilitada, solicita abrirlo. Espera al menos 2 minutos entre intentos. |

Los horarios Codex requieren que el Mac y Codex estén disponibles. No se promete ejecución puntual con el equipo apagado. El estado de programación (activa/pausada) se distingue del resultado de la última revisión (correcto/parcial/error/sin registros). Un registro documenta un resultado pasado; no demuestra que una ejecución esté en curso ni que un servicio siga activo.

Las limitaciones de una fuente externa o una instalación aplazada se muestran como resultado parcial. **Sin registros** no significa error y nunca se inventa una ejecución. Las dos tareas anime tienen historiales independientes: una revisión de episodios no acredita una investigación semanal.

## Contrato del backend

`server/scheduled_tasks.py` expone `snapshot()`. La ruta de integración es `GET /api/scheduled-tasks`, bajo la autenticación habitual. No acepta parámetros de archivos, órdenes, consultas SQL ni identificadores de red. El servidor puede proporcionar `database=state_db.DB_PATH` para utilizar su base configurada; ese argumento nunca procede del cliente.

```json
{
  "checked_at": "2026-10-21T12:00:00+00:00",
  "timezone": "Europe/Madrid",
  "summary": {"total": 6, "active": 6, "paused": 0, "attention": 0},
  "tasks": [{
    "id": "example-task",
    "name": "Comprobación de ejemplo",
    "description": "Comprueba el estado del servicio.",
    "executor": "Codex",
    "enabled": true,
    "schedule": "Cada día a las 10:00",
    "status": "ok",
    "status_label": "Correcto",
    "last_run": "2026-10-21T10:00:00+00:00",
    "history_available": true,
    "logs": [{"at": "2026-10-21T10:00:00+00:00", "status": "ok", "message": "Comprobación completada."}],
    "requirements": ["Mac y Codex disponibles"],
    "source": "Automatización Codex y auditorías registradas"
  }],
  "warnings": [],
  "limitations": []
}
```

El JSON no publica rutas privadas, instrucciones completas, credenciales, nombres de bases ni identificadores de Telegram. `attention` cuenta tareas activas con resultado parcial o error; no es una alarma de indisponibilidad actual.

## Incorporación de tareas futuras y sus registros

El descubrimiento de `~/.codex/automations/*/automation.toml` se realiza al consultar el catálogo: una automatización nueva aparece sin mantener una segunda lista ni reiniciar el servicio. Se leen solo campos públicos seleccionados; el prompt nunca se transforma en descripción, órdenes o rutas de informes.

Para aportar una explicación y un historial seguros a una tarea nueva, el operador registra archivos declarativos bajo el directorio de auditoría existente del proyecto Scripts:

```text
audits/scheduled-tasks/<id>/metadata.json
audits/scheduled-tasks/<id>/2026-10-21T100000Z.json
```

`<id>` debe coincidir con el ID de la automatización y su carpeta Codex; solo se aceptan letras minúsculas ASCII, números, guion y guion bajo (máximo 96 caracteres). Los archivos forman parte del registro local de confianza del operador; no hay API para escribirlos.

Metadatos opcionales:

```json
{"description":"Comprueba y actualiza el servicio autorizado.","requirements":["Servidor accesible","Mac y Codex disponibles"]}
```

Resultado de cada ejecución (fecha con zona horaria y nombre ordenable por fecha):

```json
{"at":"2026-10-21T10:00:00Z","status":"partial","message":"Dos actualizaciones verificadas. Una instalación aplazada por actividad."}
```

Estados admitidos: `ok`, `partial`, `error`, `unknown`. Nunca incluir secretos, sesiones, enlaces de recuperación o registros crudos. Cada tarea puede añadir resultados con esta convención a su flujo existente, sin crear servicios. El catálogo conserva hasta ocho eventos recientes y limita cada mensaje visible a 2400 caracteres; los informes originales siguen íntegros en el almacenamiento local. Para las tareas internas también se admite esta convención con los IDs `dashboard-backups` y `dashboard-amule-recovery`; mientras no haya historial propio se muestra únicamente el último estado de servicio disponible.

Los adaptadores actuales consultan únicamente informes conocidos de anime, PS5 y mantenimiento semanal. No buscan recursivamente cualquier archivo del ordenador ni atribuyen al calendario semanal el historial de episodios. Una tarea futura sin metadatos muestra una descripción neutral; sin informe muestra «Sin registros».

## Límites y seguridad

- Solo archivos regulares, sin enlaces simbólicos ni escapes del directorio permitido.
- Archivos de hasta 128 KiB; máximo 100 automatizaciones y 200 candidatos por fuente, ocho resultados visibles por tarea.
- TOML/JSON inválidos, archivos demasiado grandes y fechas sin zona horaria no generan una ejecución ficticia.
- La lectura de SQLite utiliza conexión de solo lectura y consulta únicamente `backup_status` y `amule_recovery`; no inicializa tablas ni carga el entorno de secretos.
- Redacción adicional de contraseñas, tokens, credenciales, URLs, rutas, direcciones privadas, correos e identificadores largos antes de publicar texto de informes.
- El frontend debe insertar las cadenas como texto, nunca como HTML, y conservar la autenticación del endpoint.

Validación: `PYTHONPATH=server .venv/bin/python -m unittest discover -s server/tests -p 'test_scheduled_tasks.py' -v`. Las pruebas cubren descubrimiento futuro, horarios, separación de historiales, formato inválido, archivos grandes, enlaces simbólicos, redacción, registros acotados y ausencia de escrituras de base.


## Seguimiento posterior a una ejecución

`metadata.json` admite `follow_up: {"at":"2026-10-21T13:00:47Z","message":"La incidencia documentada fue resuelta posteriormente; se conserva el resultado original."}`. La interfaz lo muestra separado del último resultado. Nunca altera la fecha, estado o log de aquella ejecución. El texto también se acota y sanea; no constituye una nueva comprobación del servicio.


## Resultado claro y ejecución manual

Cada tarjeta muestra un resumen visible, motivo, estado de consola cuando consta, siguiente paso y seguimiento posterior. «Parcial» describe la última ejecución guardada: no demuestra que el servicio esté caído. El seguimiento no borra incidencias históricas.

POST `/api/scheduled-tasks/run` acepta exclusivamente `{id}` (hasta 256 bytes), con autenticación y protección de origen existentes. IDs permitidos: las cuatro automatizaciones mantenidas y las comprobaciones de copias y aMule. Las futuras automatizaciones aparecen en el catálogo, pero no reciben capacidad de ejecución automáticamente.

El ejecutor carga las instrucciones de la configuración local de confianza, nunca del navegador. Codex recibe el prompt por stdin y devuelve un JSON validado; el cliente no recibe prompts, rutas, órdenes, credenciales ni salida cruda. Las copias y aMule usan las funciones existentes. Se conserva el horario periódico: una ejecución manual no lo cambia. El lanzamiento de Codex requiere el perfil limitado autorizado; no se usa acceso completo ni omisión de aprobaciones.

Solo una tarea manual puede ejecutarse a la vez, con bloqueo de proceso y fichero heredado por Codex. Un segundo clic devuelve conflicto; hay una pausa mínima entre lanzamientos. Estado manual y resultado histórico aparecen separados. El proceso depende del Mac encendido, de la sesión de Codex y de sus límites de uso. Un exit code cero sin informe válido no se considera mantenimiento completado. Tras una interrupción se pide comprobar el informe antes de repetir. El bloqueo manual no sustituye las comprobaciones de actividad de la consola ni constituye exclusión automática de las ejecuciones periódicas de Codex.

Los resultados manuales se guardan como informes fechados en el catálogo existente; no se añade un servicio permanente. La prueba de navegador simula la ejecución, sin realizar mantenimiento real.

Validación de la ejecución manual: copias verificadas probadas contra el servicio real (HTTP 202 y resultado correcto). Perfil limitado autorizado por el propietario; prueba real del ejecutor Codex completada con JSON correcto, sin usar herramientas ni realizar mantenimiento. Las cuatro revisiones Codex están habilitadas. Esta prueba acredita el lanzamiento y la respuesta del ejecutor, no una nueva actualización de PS5 o Proxmox.
