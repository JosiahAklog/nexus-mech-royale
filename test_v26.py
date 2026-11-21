import unittest
from test_bot import H, scenario, enemy, weapon
from bot import Bot
class DuelTests(unittest.TestCase):
    def test_weaker_target(self):
        b=Bot(H); o=scenario(); m=o['self']; m['weapons']=[weapon('gun'),None]
        self.assertGreater(b.duel_value(m,enemy(o,hp=150),25),b.duel_value(m,enemy(o,hp=1400),25))
    def test_empty_magazine(self):
        b=Bot(H); o=scenario(); m=o['self']; m['weapons']=[weapon('gun'),None]; e=enemy(o)
        full=b.duel_value(m,e,25); m['weapons'][0]['ammo']=0
        self.assertLess(b.duel_value(m,e,25),full)
    def test_lightning_range(self):
        b=Bot(H); o=scenario(); m=o['self']; m['weapons']=[weapon('lightning'),None]; e=enemy(o)
        self.assertGreater(b.duel_value(m,e,25),b.duel_value(m,e,80))
