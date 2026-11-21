import math,unittest
from bot import Bot,delta
from test_bot import H,scenario,enemy,weapon,SCHEMA

class V35Tests(unittest.TestCase):
    def setUp(self):
        self.b=Bot(H);self.o=scenario();self.m=self.o['self'];self.p=self.m['pos'];self.m['hp']=self.m['max_hp']*.77
        self.m['energy']=100.;self.m['weapons']=[weapon('gun'),None]
        self.b.map.ray=lambda *args:True; self.b.map.top=lambda *args:self.p[2];self.b.map.ground=lambda *args:self.p[2];self.b.map.surface=lambda *args:(self.p[2],self.p[2],50.);self.b.map.clearance=lambda *args:50.
    def attacker(self):
        e=enemy(self.o,2,150,0,1400);e['weapons']=['gun','laser'];e['aim']=[math.pi,0.];return e
    def test_keep_evading_recent_long_range_attacker(self):
        e=self.attacker();self.o['mechs']=[e];self.b.recovering=True;self.b.attacker_seen[2]=self.o['t']-7;self.b.last_damage=self.o['t']-7
        a=self.b.act(self.o);self.assertEqual(self.b.last_mode,'escape');self.assertLess(a['move'][0],-.25);self.assertAlmostEqual(a['aim'][0],0.);self.assertFalse(SCHEMA.errors(a,'Action'))
    def test_repair_when_actual_cover(self):
        self.o['mechs']=[self.attacker()];self.b.recovering=True;self.b.attacker_seen[2]=self.o['t']-7;self.b.last_damage=self.o['t']-7;self.b.map.ray=lambda *args:False
        a=self.b.act(self.o);self.assertEqual(self.b.last_mode,'repair');self.assertLess(math.hypot(*a['move']),.01)
    def test_visible_aimed_charging_beam_interrupts_repair(self):
        e=self.attacker();e['charging']=True;self.o['mechs']=[e];self.b.recovering=True;self.b.last_damage=self.o['t']-10
        self.b.act(self.o);self.assertEqual(self.b.last_mode,'escape')
    def test_unrelated_distant_enemy_does_not_interrupt_repair(self):
        self.o['mechs']=[self.attacker()];self.b.recovering=True;self.b.last_damage=self.o['t']-7
        self.b.act(self.o);self.assertEqual(self.b.last_mode,'repair')
    def test_zone_damage_does_not_erase_attacker(self):
        self.o['mechs']=[self.attacker()];self.b.duel_value=lambda *a:-.3;self.o['events']=[{'type':'damaged','amount':315,'weapon':'laser','bearing':0.,'by':2},{'type':'damaged','amount':2,'weapon':'zone','bearing':None,'by':None}]
        self.b.act(self.o);self.assertTrue(self.b.recovering);self.assertIn(2,self.b.attacker_seen)
    def test_attacker_memory_expires(self):
        self.b.attacker_seen[2]=self.o['t']-13;self.b.act(self.o);self.assertNotIn(2,self.b.attacker_seen)
if __name__=='__main__':unittest.main()
