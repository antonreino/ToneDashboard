// Read-only overview. This feature never runs, pauses or edits a task.
window.ToneScheduledTasks = (() => {
  const labels = {
    success: 'Correcto', ok: 'Correcto', error: 'Error', failed: 'Error',
    partial: 'Parcial', unchanged: 'Sin cambios', no_changes: 'Sin cambios',
    paused: 'Pausada', unknown: 'Sin registros', pending: 'Pendiente',
    running: 'En ejecución', active: 'Activa', idle: 'En espera'
  };
  let busy = false;
  let lastRead = 0;
  function statusBadge(value) {
    const status = Object.hasOwn(labels, value) ? value : 'unknown';
    return `<span class="task-status is-${status}">${labels[status]}</span>`;
  }
  function date(value) {
    if (!value) return 'Sin registro de ejecución';
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? 'Fecha no disponible' : parsed.toLocaleString('es-ES', {timeZone: 'Europe/Madrid', dateStyle: 'medium', timeStyle: 'short'});
  }
  function card(task) {
    const logs = task.logs || [];
    const lastRun = typeof task.last_run === 'object' ? task.last_run?.at : task.last_run;
    return `<article class="scheduled-card" data-task-id="${esc(task.id)}">
      <header><div><span class="eyebrow">${esc(task.executor)}</span><h3>${esc(task.name)}</h3></div><span class="scheduled-result"><small>Último resultado</small>${statusBadge(task.enabled ? task.status : 'paused')}</span></header>
      <p class="scheduled-description">${esc(task.description)}</p>
      <dl class="scheduled-meta"><div><dt>Frecuencia</dt><dd>${esc(task.schedule)}</dd></div><div><dt>Último registro</dt><dd>${esc(date(lastRun))}</dd></div></dl>
      <details class="scheduled-details"><summary>Qué necesita esta tarea</summary><p>${esc(Array.isArray(task.requirements) ? task.requirements.join(' · ') : task.requirements || 'Consulta supervisada, sin acciones desde esta pantalla.')}</p></details>
      <details class="scheduled-details"><summary>Registro de actividad <span>${logs.length ? `${logs.length} recientes` : 'Sin registros'}</span></summary>
        ${logs.length ? `<ol class="scheduled-logs">${logs.map(log => `<li><div><time>${esc(date(log.at))}</time>${statusBadge(log.status)}</div><p>${esc(log.message)}</p></li>`).join('')}</ol>` : '<p>No hay un resultado registrado todavía. La tarea puede estar programada aunque no tenga historial disponible.</p>'}
      </details>
      <div class="scheduled-follow-up">${task.follow_up ? `<strong>Seguimiento · ${esc(date(task.follow_up.at))}</strong><p>${esc(task.follow_up.message)}</p>` : ''}</div>
    </article>`;
  }
  async function refresh(force = false) {
    if (!document.getElementById('view-tareas').classList.contains('active') || busy) return;
    if (!force && Date.now() - lastRead < 20000) return;
    const status = document.getElementById('scheduledStatus');
    const button = document.getElementById('scheduledRefresh');
    busy = true;
    button.disabled = true;
    status.textContent = 'Consultando tareas y registros…';
    try {
      const data = await window.ToneAPI.json('/api/scheduled-tasks');
      // Keep expanded logs open when a background refresh updates the snapshot.
      const open = new Set([...document.querySelectorAll('.scheduled-card details[open]')].map(el => `${el.closest('[data-task-id]').dataset.taskId}:${[...el.parentElement.querySelectorAll('details')].indexOf(el)}`));
      const warnings = document.getElementById('scheduledWarnings');
      warnings.hidden = !(data.warnings || []).length;
      warnings.textContent = (data.warnings || []).join(' ');
      const summary = data.summary;
      document.getElementById('scheduledSummary').innerHTML = [['total','Tareas'],['active','Activas'],['paused','Pausadas'],['attention','Por revisar']].map(([key,label]) => `<div class="scheduled-metric"><span>${label}</span><strong>${Number(summary[key]) || 0}</strong></div>`).join('');
      document.getElementById('scheduledTasks').innerHTML = data.tasks.map(card).join('') || '<div class="empty">Todavía no hay tareas programadas.</div>';
      document.querySelectorAll('.scheduled-card').forEach(el => [...el.querySelectorAll('details')].forEach((details,index) => { details.open = open.has(`${el.dataset.taskId}:${index}`); }));
      status.textContent = `Última lectura: ${date(data.checked_at)} · Los resultados proceden de registros guardados.`;
      lastRead = Date.now();
    } catch (error) {
      status.textContent = 'No se pudo actualizar. Se conserva la última lectura. ' + error.message;
    } finally {
      busy = false;
      button.disabled = false;
    }
  }
  document.getElementById('scheduledRefresh').addEventListener('click', () => refresh(true));
  return Object.freeze({refresh});
})();
