import math,unittest
from bot import Bot
from test_bot import H,scenario,enemy,weapon,SCHEMA

class V31Tests(unittest.TestCase):
    def setUp(self):self.b=Bot(H)
    def flat(self,o):
        z=o['self']['pos'][2];self.b.map.surface=lambda *a:(z,z,50.);self.b.map.top=lambda *a:z;self.b.map.ground=lambda *a:z;self.b.map.clearance=lambda *a:50.;self.b.map.ray=lambda *a:True
    def test_optional_duel_does_not_start_unnecessary_fight(self):
        o=scenario();m=o['self'];m['hp']=m['max_hp'];m['cubes']=0;m['weapons']=[weapon('gun'),None];e=enemy(o,2,70,0,1400);e['aim']=[0.,0.];p=m['pos'];loot={'id':5001,'pos':[p[0]-30,p[1],p[2]]};o['mechs']=[e];o['cubes']=[loot];self.flat(o)
        self.assertTrue(self.b.avoid_optional_duel(p,m,e,[e],loot,o['t']))
        a=self.b.act(o);self.assertFalse(any(a['fire']));self.assertEqual(self.b.last_mode,'loot');self.assertLess(a['move'][0],0);self.assertFalse(SCHEMA.errors(a,'Action'))
    def test_optional_duel_protect_active_defense(self):
        o=scenario();m=o['self'];m['hp']=m['max_hp'];m['cubes']=0;p=m['pos'];e=enemy(o,2,70,0,1400);e['aim']=[0.,0.];loot={'id':5001,'pos':[p[0]-30,p[1],p[2]]};self.b.last_damage=o['t']-1
        self.assertFalse(self.b.avoid_optional_duel(p,m,e,[e],loot,o['t']))
        self.b.last_damage=-100;e['aim']=[math.pi,0.];self.assertFalse(self.b.avoid_optional_duel(p,m,e,[e],loot,o['t']))
        e['aim']=[0.,0.];e['hp']=150;self.assertFalse(self.b.avoid_optional_duel(p,m,e,[e],loot,o['t']))
    def test_cover_search_requires_reachable_cover(self):
        o=scenario();m=o['self'];p=m['pos'];e=enemy(o,2,50,0,1400);self.flat(o)
        self.assertIsNone(self.b.escape_cover_goal(p,m,o['zone'],[e],(-1.,0.),o['t']))
        self.b.map.ray=lambda a,b:not(a[0]<p[0]-12 and a[2]>p[2]+5 and b[0]>p[0]+30)
        q=self.b.escape_cover_goal(p,m,o['zone'],[e],(-1.,0.),o['t']);self.assertIsNotNone(q);self.assertLess(q[0],p[0]-12)
        self.b.map.clearance=lambda *a:0.
        self.assertIsNone(self.b.escape_cover_goal(p,m,o['zone'],[e],(-1.,0.),o['t']))
    def test_loot_braking_does_not_override_dodge(self):
        o=scenario();m=o['self'];p=m['pos'];m['hp']=m['max_hp'];m['weapons']=[weapon('gun'),None];o['cubes']=[{'id':5001,'pos':[p[0]+4,p[1],p[2]]}];self.flat(o)
        a=self.b.act(o);self.assertLess(math.hypot(*a['move']),.8)
        self.b.map.projectile_risks=lambda candidates,*args:[40. if dx>.5 else 0. for dx,dy in candidates]
        o['projectiles']=[{'id':99,'kind':'gun','pos':[p[0]+25,p[1],p[2]+4],'vel':[-250.,0.,0.]}];o['tick']+=2;o['t']+=.1
        a=self.b.act(o);self.assertGreater(math.hypot(*a['move']),.95);self.assertLess(a['move'][0],.51)

if __name__=='__main__':unittest.main()
