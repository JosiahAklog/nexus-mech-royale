import math, unittest
from bot import Bot
from test_bot import H, scenario, enemy, weapon, SCHEMA

class V29Tests(unittest.TestCase):
    def setUp(self):
        self.b=Bot(H,'adaptive')
    def test_aimed_charging_enemy_increases_risk(self):
        o=scenario();m=o['self'];e=enemy(o,2,60,0,1400);e['weapons']=['laser'];e['charging']=True
        self.assertGreater(self.b.imminent_threats(m['pos'],m,[e],30)[0][1],100)
        e['charging']=False;self.assertEqual(self.b.imminent_threats(m['pos'],m,[e],30),[])
        e['charging']=True;e['aim']=[0,0];self.assertEqual(self.b.imminent_threats(m['pos'],m,[e],30),[])
    def test_preemptive_escape_two_aimed_lasers(self):
        o=scenario();m=o['self'];m['hp']=m['max_hp']*.72;m['weapons']=[weapon('gun'),None]
        a=enemy(o,2,50,0,1400);b=enemy(o,3,55,5,1400)
        for e in [a,b]:e['weapons']=['laser'];e['charging']=True;e['aim']=[math.atan2(m['pos'][1]-e['pos'][1],m['pos'][0]-e['pos'][0]),0]
        o['mechs']=[a,b];self.b.map.ray=lambda *args:True
        result=self.b.act(o);self.assertTrue(self.b.recovering);self.assertFalse(SCHEMA.errors(result,'Action'))
    def test_route_bonus_requires_safe_clear_second_leg(self):
        o=scenario();m=o['self'];p=m['pos'];z=o['zone'];a={'id':5100,'pos':[p[0]+20,p[1],p[2]]};b={'id':5101,'pos':[p[0]+35,p[1],p[2]]}
        self.b.map.ray=lambda *args:True
        self.assertGreater(self.b.route_loot_bonus(a,[a,b],m,z,30,p),0)
        self.b.map.ray=lambda *args:False
        self.assertEqual(self.b.route_loot_bonus(a,[a,b],m,z,30,p),0)
    def test_multi_threat_reserve_and_lethal_exception(self):
        o=scenario();m=o['self'];self.assertGreater(self.b.energy_reserve(m,30,2,False,False,0),self.b.policy['reserve'])
        self.assertEqual(self.b.energy_reserve(m,90,0,False,False,0),self.b.policy['reserve'])
        m['hp']=m['max_hp'];m['energy']=12;m['weapons']=[weapon('gun'),weapon('lightning')]
        o['mechs']=[enemy(o,2,30,0,800),enemy(o,3,35,0,1000)]
        self.b.map.ray=lambda *args:True;self.b.intercept=lambda *args:(0.,0.,True,True,30.,.04,.04)
        result=self.b.act(o);self.assertTrue(result['fire'][0]);self.assertFalse(result['fire'][1])
    def test_rear_threat_armor_reduces_estimate(self):
        o=scenario();m=o['self'];e=enemy(o,2,60,0,1400);a=self.b.imminent_threats(m['pos'],m,[e],30)[0][1]
        m['stats']['armor']=.2;b=self.b.imminent_threats(m['pos'],m,[e],30)[0][1];self.assertAlmostEqual(b,a*.8)

if __name__=='__main__':unittest.main()
