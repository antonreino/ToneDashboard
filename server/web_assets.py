"""La única interfaz de Tone Dashboard para navegador y contenedores Apple."""
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent.parent / 'web'
VERSION = (WEB_DIR.parent / 'VERSION').read_text().strip()
# Transport first; feature modules attach to the existing shared page.
SCRIPT_FILES = ('api.js', 'dashboard.js', 'operations.js', 'anime-calendar.js', 'scheduled-tasks.js', 'tonetti.js')


def dashboard_html():
    html = (WEB_DIR / 'index.html').read_text()
    styles = (WEB_DIR / 'dashboard.css').read_text()
    scripts = '\n'.join((WEB_DIR / name).read_text() for name in SCRIPT_FILES)
    replacements = {
        '<!-- DASHBOARD_STYLE -->': f'<style>{styles}</style>',
        '<!-- DASHBOARD_SCRIPT -->': f'<script>{scripts}</script>',
        '{{VERSION}}': VERSION,
    }
    for marker, value in replacements.items():
        html = html.replace(marker, value)
    return html
