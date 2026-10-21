// One same-origin JSON transport for shared web and native features.
window.ToneAPI = Object.freeze({
  async json(path, body, {timeoutMs = 20000} = {}) {
    if (typeof path !== 'string' || !path.startsWith('/api/') || path.includes('\\')) {
      throw new Error('Dirección de consulta no válida');
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), Math.max(1000, Math.min(timeoutMs, 60000)));
    try {
      const response = await fetch(path, {
        cache: 'no-store',
        signal: controller.signal,
        ...(body !== undefined ? {
          method: 'POST',
          headers: {'Content-Type': 'application/json', 'X-Dashboard-Action': 'write'},
          body: JSON.stringify(body)
        } : {})
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'No se pudo completar la consulta');
      return data;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error(body === undefined
        ? 'La consulta está tardando demasiado. Inténtalo de nuevo.'
        : 'La operación sigue sin confirmación. Actualiza el estado antes de repetirla.');
      throw error;
    } finally {
      clearTimeout(timer);
    }
  }
});
