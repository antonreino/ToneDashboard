"""La única interfaz de Tone Dashboard para navegador y contenedores Apple."""
from pathlib import Path
WEB_DIR = Path(__file__).resolve().parent.parent / 'web'
VERSION = (WEB_DIR.parent / 'VERSION').read_text().strip()
def dashboard_html():
    html = (WEB_DIR / 'index.html').read_text()
    return html.replace('<!-- DASHBOARD_STYLE -->', '<style>' + (WEB_DIR / 'dashboard.css').read_text() + '</style>').replace('<!-- DASHBOARD_SCRIPT -->', '<script>' + (WEB_DIR / 'dashboard.js').read_text() + '\n' + (WEB_DIR / 'operations.js').read_text() + '</script>').replace('{{VERSION}}', VERSION)
