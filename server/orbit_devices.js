/* Shared by browsers and both native WKWebViews. No secrets in web storage. */
(() => {
  'use strict';
  const panel = document.createElement('details');
  panel.className = 'tone-orbit-device-panel';
  panel.innerHTML = '<summary>Conexión automática</summary><p>Recuerda este dispositivo durante 30 días y vuelve a vincularlo si Orbit se reinicia. El lector del Mac debe poder consultar el código.</p><form><label>Contraseña de vinculación <input type="password" minlength="12" required autocomplete="off"></label><button type="submit">Recordar este dispositivo</button></form><button type="button" data-forget>Olvidar este dispositivo</button><p role="status"></p>';
  document.body.append(panel);
  const password = panel.querySelector('input');
  const status = panel.querySelector('[role=status]');
  const buttons = panel.querySelectorAll('button');
  fetch(location.origin + '/api/orbit/device', {credentials: 'same-origin', cache: 'no-store'})
    .then(response => response.ok ? response.json() : null)
    .then(data => { if (data) status.textContent = data.remembered ? 'Este dispositivo ya está autorizado.' : 'Este dispositivo todavía no está autorizado.'; })
    .catch(() => {});
  let busy = false;
  let generation = 0;
  async function action(remember) {
    if (busy) return;
    busy = true; buttons.forEach(b => b.disabled = true);
    const current = ++generation;
    const secret = password.value; password.value = '';
    status.textContent = 'Conectando…';
    try {
      // Absolute dashboard routes must bypass Orbit's fetch rewriting shim.
      const response = await fetch(location.origin + '/api/orbit/' + (remember ? 'remember' : 'forget'), {
        method: 'POST', credentials: 'same-origin', cache: 'no-store',
        headers: {'Content-Type': 'application/json', 'X-Dashboard-Action': 'write',
          'X-Orbit-Action': 'remember-device', ...(remember ? {'X-Orbit-Pair-Password': secret} : {})}, body: '{}'
      });
      const data = await response.json();
      if (current !== generation) return;
      if (!response.ok) throw new Error(data.error || 'No se pudo guardar la autorización.');
      status.textContent = remember ? 'Dispositivo autorizado durante 30 días.' : 'Autorización eliminada.';
      location.reload();
    } catch (error) {
      if (current === generation) status.textContent = error.message || 'No se pudo conectar.';
    } finally { busy = false; buttons.forEach(b => b.disabled = false); }
  }
  panel.querySelector('form').addEventListener('submit', event => { event.preventDefault(); action(true); });
  panel.querySelector('[data-forget]').addEventListener('click', () => action(false));
  document.addEventListener('visibilitychange', () => { if (document.hidden) { password.value = ''; status.textContent = ''; generation++; } });
  panel.addEventListener('toggle', () => { if (!panel.open) password.value = ''; });
})();
