import math,unittest
from bot import Bot
from test_bot import H,scenario,enemy,weapon,SCHEMA

class V32Tests(unittest.TestCase):
    def setUp(self): self.b=Bot(H)
    def flat(self,o):
        z=o['self']['pos'][2];self.b.map.surface=lambda *a:(z,z,50.);self.b.map.top=lambda *a:z;self.b.map.ground=lambda *a:z;self.b.map.clearance=lambda *a:50.;self.b.map.ray=lambda *a:True
    def underarmed(self):
        o=scenario();m=o['self'];m['hp']=m['max_hp'];m['weapons']=[weapon('gun'),None];m['cubes']=0;m['energy']=95.;m['grounded']=True
        e=enemy(o,2,65,0,1400);e.update(aim=[0.,0.],weapons=['gun','laser'],cubes=3);o['mechs']=[e];self.flat(o);return o,e
    def test_underarmed_disengages_even_without_visible_loot(self):
        o,e=self.underarmed();m=o['self'];self.assertTrue(self.b.underarmed_disengage(m['pos'],m,e,[e],o['t']))
        a=self.b.act(o);self.assertFalse(any(a['fire']));self.assertEqual(self.b.last_mode,'escape');self.assertLess(a['move'][0],-.4);self.assertFalse(SCHEMA.errors(a,'Action'))
    def test_disengagement_does_not_override_active_defense(self):
        o,e=self.underarmed();m=o['self'];e['aim']=[math.pi,0.];self.assertFalse(self.b.underarmed_disengage(m['pos'],m,e,[e],o['t']))
        e['aim']=[0.,0.];self.b.last_damage=o['t']-1;self.assertFalse(self.b.underarmed_disengage(m['pos'],m,e,[e],o['t']))
        self.b.last_damage=-100;e['hp']=120;self.assertFalse(self.b.underarmed_disengage(m['pos'],m,e,[e],o['t']))
    def test_disengage_rejects_unreachable_and_unsafe_locations(self):
        o,e=self.underarmed();m=o['self'];p=m['pos'];q=self.b.safe_disengage_goal(p,m,o['zone'],[e],o['t'],[]);self.assertIsNotNone(q);self.assertLess(q[0],p[0]);self.b.map.clearance=lambda *a:0.;self.b.map.surface=lambda *a:(p[2],p[2],0.)
        self.assertIsNone(self.b.safe_disengage_goal(p,m,o['zone'],[e],o['t'],[]))
    def test_loot_interception_risk(self):
        o,e=self.underarmed();m=o['self'];p=m['pos'];e['vel']=[-12.,0.,0.];q={'id':5001,'pos':[p[0]+30,p[1],p[2]]};safe={'id':5002,'pos':[p[0]-30,p[1],p[2]]}
        self.assertGreater(self.b.resource_exposure(p,q,[e],m),10.);self.assertEqual(self.b.resource_exposure(p,safe,[e],m),0.)
        self.b.map.ray=lambda *a:False;self.assertEqual(self.b.resource_exposure(p,q,[e],m),0.)
    def test_gun_leads_later_shot(self):
        o=scenario();m=o['self'];self.flat(o);e=enemy(o,2,60,0,1100);e['vel']=[0.,12.,0.];w=weapon('gun');a=self.b.intercept(m['pos'],m,e,w);w['cooldown']=.09;b=self.b.intercept(m['pos'],m,e,w);self.assertGreater(b[0],a[0])
    def test_finish_crate_while_approaching_loot(self):
        o=scenario();m=o['self'];self.flat(o);m['hp']=m['max_hp'];m['cubes']=0;m['weapons']=[weapon('gun'),None];p=m['pos'];o['crates']=[{'id':1001,'hp':70,'pos':[p[0]+14,p[1],p[2]]}]
        a=self.b.act(o);self.assertEqual(self.b.last_mode,'farm');self.assertGreater(a['move'][0],.5)

    def test_second_weapon_priority_over_isolated_cube(self):
        o=scenario();m=o['self'];self.flat(o);m['hp']=m['max_hp'];m['cubes']=0;m['weapons']=[weapon('gun'),None];p=m['pos'];o['cubes']=[{'id':5001,'pos':[p[0]-13,p[1],p[2]]}];o['pickups']=[{'id':8001,'kind':'laser','pos':[p[0]+19,p[1],p[2]]}]
        a=self.b.act(o);self.assertEqual(self.b.last_mode,'loot');self.assertGreater(a['move'][0],.5)
    def test_recovery_ignores_unrelated_unaware_enemy(self):
        o=scenario();m=o['self'];p=m['pos'];e=enemy(o,2,65,0,1400);e['aim']=[0.,0.];self.b.last_damage=o['t']-1;self.b.last_attacker=3
        self.assertFalse(self.b.retreat_pressure([e],p,m,o['t']))
        self.b.last_attacker=2;self.assertTrue(self.b.retreat_pressure([e],p,m,o['t']))

if __name__=='__main__':unittest.main()
