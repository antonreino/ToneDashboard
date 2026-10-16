# Migración a Tone Dashboard 1.0.0

Consulta [la guía principal](../README.md). Los componentes forman un único repositorio; los instaladores parciales antiguos no se utilizan.

Antes de mover una instalación, detén las transferencias, respalda repositorios, archivos privados y bases SQLite con su API de backup. Comprueba integridad y todas las tablas, incluidos historial, destinatarios, productos y cola de notificaciones. `scripts/migration.py` verifica copias sin borrar el origen.

La raíz contiene `.venv`; `server/.env` y `workers/price_tracker/.env` conservan credenciales y destinatarios propios. El tracker mantiene `workers/price_tracker/data/prices.sqlite3`; Organizer y Orbit mantienen `~/.local/share/emby_organizer`. No limpies tablas históricas durante una migración.

Actualiza los cinco LaunchAgents existentes con el instalador de la raíz y comprueba rutas, procesos, API, SFTP, métricas y apps antes de retirar instalaciones antiguas. Los bundle IDs, llavero y almacenamiento WebKit se conservan; no desinstales las apps para actualizarlas.
