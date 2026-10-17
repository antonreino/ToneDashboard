import json
from pathlib import Path
import tempfile
import unittest
from ps5bot.store import Store
from ps5bot import preferences
from ps5bot.models import Offer
from unittest.mock import Mock

class PreferencesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=Store(Path(self.tmp.name)/'prices.sqlite3',('1','2'));self.addCleanup(self.store.db.close)
        self.offer=Mock(price=8000,availability='in_stock')
        self.old={'price':10000,'payload':json.dumps({'availability':'in_stock'})}
    def allowed(self,chat='1',now=100):return preferences.eligible(self.store.db,'ps5',chat,self.offer,self.old,now)
    def test_default_preserves_notifications_for_both_recipients(self):
        self.assertTrue(self.allowed());self.assertTrue(self.allowed('2'))
    def test_target_drop_individual_override(self):
        preferences.save(self.store.db,{'product':'ps5','target_cents':7000})
        self.assertFalse(self.allowed())
        preferences.save(self.store.db,{'product':'ps5','chat':'1','target_cents':9000,'min_drop':15})
        self.assertTrue(self.allowed());self.assertFalse(self.allowed('2'))
        self.offer.price=9500;self.assertFalse(self.allowed())
    def test_mute_and_restock(self):
        preferences.save(self.store.db,{'product':'ps5','mute_hours':1});self.assertFalse(self.allowed(now=__import__('time').time()))
        preferences.save(self.store.db,{'product':'ps5','restock':False});self.old['payload']=json.dumps({'availability':'out_of_stock'});self.assertFalse(self.allowed())
    def test_invalid_recipient_product_nan_and_boolean_values(self):
        for body in [{'product':'ps5','chat':'unknown'},{'product':'ean:bad'},{'product':'ps5','target_cents':True},{'product':'ps5','min_drop':float('nan')},{'product':'ps5','restock':'false'}]:
            with self.assertRaises(ValueError):preferences.save(self.store.db,body)
    def test_save_never_sends_or_replays_existing_offers(self):
        preferences.save(self.store.db,{'product':'ps5','target_cents':10000})
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM outbox').fetchone()[0],0)
        self.assertEqual(set(preferences.list_preferences(self.store.db)['recipients']),{'1','2'})
