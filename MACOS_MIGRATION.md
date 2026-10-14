# ToneDashboard — Instalación y migración a macOS

El proyecto se llama ToneDashboard. Los nombres de los servicios de lanzamiento y la ruta de la instalación original se conservan por compatibilidad. Puedes usar el disco interno o un volumen externo; mover una instalación ya activa exige regenerar sus LaunchAgents.

## 1. Configurar

```bash
cp .env.example .env
```

Edita `.env`. En tu instalación actual puedes usar, por ejemplo:

```dotenv
INBOX_DIR=/Users/tuusuario/Documents/Torrent
TORRENT_DROP_DIR=/Users/tuusuario/Downloads
GAME_DOWNLOAD_DIR=/Volumes/Datos/Descargas
GAME_MAX_RETRIES=20
GAME_RETRY_DELAY=5
GAME_MAX_CONCURRENT=2
```

Añade también las credenciales reales de Telegram, TMDb y SFTP. `.env` está ignorado por Git.

## 2. Instalar servicios

Desde la raíz del proyecto:

```bash
chmod +x scripts/install-macos-services.sh scripts/status-macos.sh
./scripts/install-macos-services.sh
```

El instalador obtiene automáticamente `PROJECT_ROOT`, crea/reutiliza `~/.venvs/emby-organizer`, instala dependencias y genera los dos LaunchAgents con las rutas reales del equipo.

## 3. Telegram

```text
/ping
/help
/juego URL
/estado
```

- `.torrent` se guarda en `TORRENT_DROP_DIR`.
- `/juego` descarga en `GAME_DOWNLOAD_DIR`.
- Se detecta nombre/tamaño/reanudación cuando el servidor lo permite.
- `curl` negocia HTTP/2 o HTTP/1.1 automáticamente.
- Hay hasta `GAME_MAX_CONCURRENT` descargas simultáneas y cola para el resto.
- `/estado` muestra progreso y cola.

## 4. Comprobar

```bash
./scripts/status-macos.sh
```

Logs:

```bash
tail -f ~/Library/Logs/telegram-download-bot.out.log
tail -f ~/Library/Logs/telegram-download-bot.err.log
tail -f ~/Library/Logs/emby-organizer.out.log
tail -f ~/Library/Logs/emby-organizer.err.log
```

## Migración de nombre sin romper servicios

Si ya usas `/Volumes/Datos/Proyectos/Scripts/emby-organizer`, mantenlo mientras los LaunchAgents apunten allí. Ejecuta primero `ToneDashboard/instalar.py --dry-run`, luego `--apply`. Solo después de verificar funcionamiento plantea trasladar la carpeta y regenerar todos los plists con `scripts/install-macos-services.sh`. No cambies ni elimines el histórico SQLite. El nombre de aplicación, título y documentación ya es ToneDashboard.
