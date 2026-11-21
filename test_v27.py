import unittest, math
from test_bot import H, scenario, enemy
from bot import Bot
class OpportunityTests(unittest.TestCase):
    def test_third_party(self):
        b=Bot(H);o=scenario();m=o['self'];m['hp']=m['max_hp'];p=m['pos'];a=enemy(o,1,25,0,100);r=enemy(o,2,25,25);r['aim']=[-math.pi/2,0];self.assertGreater(b.opportunity_bonus(p,m,a,[a,r],o),0)
        b.last_attacker=1;b.last_damage=o['t'];self.assertEqual(b.opportunity_bonus(p,m,a,[a,r],o),0)
    def test_low_health(self):
        b=Bot(H);o=scenario();m=o['self'];m['hp']=100;a=enemy(o);self.assertEqual(b.opportunity_bonus(m['pos'],m,a,[a],o),0)
