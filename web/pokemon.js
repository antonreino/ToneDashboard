(() => {
  const root = document.getElementById('view-pokemon');
  if (!root) return;
  const image = document.getElementById('pokemonImage');
  const loading = document.getElementById('pokemonLoading');
  const options = document.getElementById('pokemonOptions');
  const result = document.getElementById('pokemonResult');
  const next = document.getElementById('pokemonNext');
  let round = null;
  let answered = false;

  const setLoading = active => {
    loading.hidden = !active;
    if (active) loading.textContent = 'Preparando una ronda…';
    image.hidden = active;
    next.disabled = active;
  };
  const answer = id => {
    if (!round || answered) return;
    answered = true;
    image.classList.add('revealed');
    const correct = round.options.find(option => option.id === round.correct_id);
    options.querySelectorAll('button').forEach(button => {
      const optionId = Number(button.dataset.id);
      button.disabled = true;
      if (optionId === round.correct_id) button.classList.add('correct');
      else if (optionId === id) button.classList.add('wrong');
    });
    result.textContent = id === round.correct_id ? `¡Correcto! Es ${correct.name}.` : `Era ${correct.name}. ¡Prueba otra ronda!`;
  };
  const render = data => {
    round = data;
    answered = false;
    result.textContent = '';
    image.classList.remove('revealed');
    image.src = data.pokemon.image;
    options.replaceChildren(...data.options.map((option, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.dataset.id = String(option.id);
      button.textContent = `${index + 1}. ${option.name}`;
      button.addEventListener('click', () => answer(option.id));
      return button;
    }));
    setLoading(false);
  };
  const loadRound = async () => {
    round = null;
    answered = false;
    result.textContent = '';
    options.replaceChildren();
    setLoading(true);
    try { render(await window.ToneAPI.json('/api/pokemon/round')); }
    catch (error) {
      loading.hidden = false;
      loading.textContent = error.message || 'No se pudo preparar la ronda.';
      next.disabled = false;
    }
  };
  next.addEventListener('click', loadRound);
  document.addEventListener('keydown', event => {
    if (!root.classList.contains('active') || answered || event.metaKey || event.ctrlKey || event.altKey) return;
    const index = Number(event.key) - 1;
    if (index >= 0 && index < 4 && round) answer(round.options[index].id);
  });
  document.querySelectorAll('[data-phone-go="pokemon"]').forEach(button => button.addEventListener('click', () => { if (!round) loadRound(); }));
})();
