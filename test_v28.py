import math, unittest
from bot import Bot
from test_bot import H, scenario, enemy, weapon

class TacticalTests(unittest.TestCase):
    def setUp(self): self.b=Bot(H)
    def test_future_zone_rejects_late_loot(self):
        o=scenario();m=o['self'];p=m['pos'];z=dict(center=p[:2],next_center=p[:2],radius=120,next_radius=30,shrink_start=30,shrink_end=35)
        self.assertFalse(self.b.objective_viable(p,(p[0]+90,p[1],p[2]),m,z,30))
        self.assertTrue(self.b.objective_viable(p,(p[0]+10,p[1],p[2]),m,z,30))
    def test_patrol_prefers_unvisited(self):
        o=scenario();m=o['self'];p=m['pos'];z=o['zone'];b=self.b
        b.map.surface=lambda x,y:(0.,0.,30.)
        b.map.ray=lambda *args:True
        first=b.explore_goal(p,m,z,30.)
        self.assertIsNotNone(first)
        b.visited[(int(first[0]//45),int(first[1]//45))]=30.
        self.assertNotEqual(first,b.explore_goal(p,m,z,30.))
    def test_dual_weapon_budget(self):
        o=scenario();m=o['self'];m['hp']=m['max_hp'];m['energy']=100.;e=enemy(o,2,35,0,1400)
        m['weapons']=[weapon('gun'),None];single=self.b.duel_value(m,e,35)
        m['weapons'][1]=weapon('lightning');dual=self.b.duel_value(m,e,35)
        self.assertGreater(dual,single)
        m['energy']=0.;self.assertAlmostEqual(self.b.duel_value(m,e,35),single)
    def test_burst_damage_promotes_retreat(self):
        o=scenario();m=o['self'];m['hp']=m['max_hp']*.69;m['weapons']=[weapon('gun'),None];o['mechs']=[enemy(o,2,60,0,1400)];o['events']=[{'type':'damaged','weapon':'mortar','by':2,'amount':350,'bearing':0.}]
        self.b.map.ray=lambda *args:True
        self.b.act(o);self.assertTrue(self.b.recovering)
    def test_escape_recharge_latch(self):
        o=scenario();m=o['self'];m['hp']=m['max_hp']*.35;m['energy']=20.;o['mechs']=[enemy(o,2,60,0,1400)];o['events']=[{'type':'damaged','weapon':'gun','by':2,'amount':45,'bearing':0.}]
        p=m['pos'];self.b.map.ray=lambda *args:True;self.b.map.surface=lambda *args:(p[2],p[2],30.);self.b.map.top=lambda *args:p[2]
        self.b.act(o);self.assertTrue(self.b.escape_recharge)
        o['t']+=.1;o['tick']+=2;o['events']=[];m['energy']=40.;a=self.b.act(o);self.assertFalse(a['boost'])
        o['t']+=.1;o['tick']+=2;m['energy']=60.;self.b.act(o);self.assertFalse(self.b.escape_recharge)
if __name__=='__main__':unittest.main()
