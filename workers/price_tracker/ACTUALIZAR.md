# Actualizar el tracker

Forma parte de Tone Dashboard 1.0.0. Sigue [la actualización del proyecto completo](../../README.md); no se distribuye como repositorio independiente.

Conserva `.env`, `config.json`, `data/prices.sqlite3`, `logs/` y todos los destinatarios. Antes de actualizar, respalda SQLite mediante su API de backup. No borres datos para resolver una actualización ni ejecutes dos procesos del bot simultáneamente.

Para diagnóstico sin Telegram ni cambios de historial, desde esta carpeta:

```bash
../../.venv/bin/python -m ps5bot.app --check --diagnose
```

Amazon e Idealo conservan sus limitaciones de lectura anteriores; consulta `VALIDACION.md` y `README.md`.
