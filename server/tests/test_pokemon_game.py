import io
import json
import unittest
from pathlib import Path

import pokemon_game


class FakeResponse(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *_): self.close()


class FixedChooser:
    def sample(self, population, count):
        self.population, self.count = population, count
        return [1, 4, 7, 25]
    def choice(self, values): return values[2]


class PokemonGameTests(unittest.TestCase):
    def test_round_uses_four_unique_first_generation_options(self):
        def opener(request, timeout):
            pokemon_id = int(request.full_url.rstrip('/').split('/')[-1])
            payload = {'name': f'pokemon-{pokemon_id}', 'sprites': {'other': {'official-artwork': {'front_default': f'https://img.test/{pokemon_id}.png'}}}}
            self.assertEqual(timeout, 8)
            return FakeResponse(json.dumps(payload).encode())
        result = pokemon_game.new_round(opener=opener, chooser=FixedChooser())
        self.assertEqual([item['id'] for item in result['options']], [1, 4, 7, 25])
        self.assertEqual(result['correct_id'], 7)
        self.assertEqual(result['pokemon'], {'id': 7, 'image': 'https://img.test/7.png'})

    def test_incomplete_provider_response_is_rejected(self):
        opener = lambda *_args, **_kwargs: FakeResponse(b'{"name":"missing-image","sprites":{}}')
        with self.assertRaisesRegex(ValueError, 'incompleta'):
            pokemon_game._fetch_pokemon(1, opener)


class PokemonWebContractTests(unittest.TestCase):
    def test_shared_interface_contains_playable_view(self):
        root = Path(__file__).resolve().parents[2]
        html = (root / 'web/index.html').read_text()
        script = (root / 'web/pokemon.js').read_text()
        self.assertIn('id="view-pokemon"', html)
        self.assertIn("ToneAPI.json('/api/pokemon/round')", script)
        self.assertIn("root.classList.contains('active')", script)


if __name__ == '__main__':
    unittest.main()
