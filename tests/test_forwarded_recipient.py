import json
import unittest
from unittest.mock import Mock
from ps5bot.app import command_reply

class ForwardedRecipientTests(unittest.TestCase):
    def test_authorized_forward_records_id_without_content_or_authorizing(self):
        store = Mock()
        message = {'chat': {'id': 123}, 'text': 'contenido privado', 'date': 42,
                   'forward_origin': {'type': 'user', 'sender_user': {'id': 456, 'first_name': 'Amigo'}}}
        self.assertIsNone(command_reply(message, 'bot', ('123',), store, {'sources': []}))
        key, raw = store.set_meta.call_args.args
        self.assertEqual(key, 'forwarded_chat_candidate')
        self.assertEqual(json.loads(raw)['id'], '456')
        self.assertNotIn('contenido privado', raw)
        store.queue.assert_not_called()

    def test_unauthorized_chat_cannot_nominate_recipient(self):
        store = Mock()
        message = {'chat': {'id': 999}, 'forward_origin': {'type': 'user', 'sender_user': {'id': 456}}}
        command_reply(message, 'bot', ('123',), store, {'sources': []})
        store.set_meta.assert_not_called()

    def test_hidden_forward_does_not_invent_identifier(self):
        store = Mock()
        message = {'chat': {'id': 123}, 'forward_origin': {'type': 'hidden_user', 'sender_user_name': 'Amigo'}}
        command_reply(message, 'bot', ('123',), store, {'sources': []})
        self.assertEqual(json.loads(store.set_meta.call_args.args[1]), {'error': 'hidden_user'})

    def test_legacy_forward_is_supported(self):
        store = Mock()
        command_reply({'chat': {'id': 123}, 'forward_from': {'id': 456}}, 'bot', ('123',), store, {'sources': []})
        self.assertEqual(json.loads(store.set_meta.call_args.args[1])['id'], '456')
