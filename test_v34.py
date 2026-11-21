import math,unittest
from bot import Bot
from test_bot import H,scenario,enemy,weapon,SCHEMA

class V34Tests(unittest.TestCase):
    def setUp(self):
        self.b=Bot(H); self.o=scenario(); self.m=self.o['self'];self.p=self.m['pos'];self.m['hp']=self.m['max_hp'];self.m['energy']=100.;self.m['weapons']=[weapon('gun'),None]
        self.b.map.ray=lambda *a:True;self.b.map.top=lambda *a:self.p[2];self.b.map.ground=lambda *a:self.p[2];self.b.map.surface=lambda *a:(self.p[2],self.p[2],50.);self.b.map.clearance=lambda *a:50.
    def test_roof_requires_reachable_energy(self):
        self.b.map.top=lambda *a:30.;self.m['energy']=10.;q=[self.p[0]+16,self.p[1],30.]
        self.assertGreater(self.b.climb_cost(self.p,q,self.m),40)
        self.assertFalse(self.b.loot_reachable(self.p,q,self.m,False))
        self.m['energy']=90.; self.assertTrue(self.b.loot_reachable(self.p,q,self.m,False))
        self.m['energy']=10.;q[0]+=60;self.assertTrue(self.b.loot_reachable(self.p,q,self.m,False));self.assertFalse(self.b.loot_reachable(self.p,q,self.m,True))
    def test_inaccessible_roof_cannot_displace_ground_cube(self):
        self.m['energy']=10; x,y,z=self.p
        self.b.map.top=lambda x1,y1:30. if x1>x+8 else z
        self.o['cubes']=[{'id':5001,'pos':[x+12,y,30.]},{'id':5002,'pos':[x-22,y,z]}]
        a=self.b.act(self.o);self.assertEqual(self.b.last_mode,'loot');self.assertLess(a['move'][0],-.5);self.assertFalse(SCHEMA.errors(a,'Action'))
    def test_weapon_downtime(self):
        g=weapon('gun');g['ammo']=0;self.assertEqual(self.b.weapon_wait(g,100,10,True),g['stats']['reload']);g['reload']=1.1;self.assertAlmostEqual(self.b.weapon_wait(g,100,10,True),1.1)
        l=weapon('laser');self.assertTrue(math.isinf(self.b.weapon_wait(l,100,10,False)));l['charge']=.6;self.assertAlmostEqual(self.b.weapon_wait(l,100,10,True),l['stats']['charge']-.6)
        arc=weapon('lightning');self.assertTrue(math.isinf(self.b.weapon_wait(arc,12,10,True)));self.assertEqual(self.b.weapon_wait(arc,90,10,True),0)
    def test_fallback_respects_lightning_blockers(self):
        w=weapon('lightning');e=enemy(self.o,2,40,0);blocker=enemy(self.o,3,12,0)
        self.b.intercept=lambda *a:(0.,0.,True,True,40.,.1,.1)
        self.assertFalse(self.b.firing_solutions(self.p,self.m,e,[w,None],True,[e,blocker])[0][2])
        self.assertTrue(self.b.firing_solutions(self.p,self.m,e,[w,None],True,[e])[0][2])
    def test_charged_laser_aim_kept_when_gun_aim_incompatible(self):
        self.m['weapons']=[weapon('gun'),weapon('laser')];self.m['weapons'][1]['charge']=.75
        self.o['mechs']=[enemy(self.o,2,40,0,25)];self.b.intercept=lambda p,m,t,w:(0.,0.,True,True,40.,.04,.04) if w['kind']=='gun' else (.17,0.,True,True,40.,.04,.04)
        a=self.b.act(self.o);self.assertAlmostEqual(a['aim'][0],.17);self.assertFalse(a['fire'][1]);self.assertFalse(a['fire'][0])
    def test_reloading_escape_detects_shorted_laser(self):
        self.m['weapons']=[weapon('gun'),weapon('laser')];self.m['weapons'][0]['reload']=2.;self.m['weapons'][0]['ammo']=0;self.m['hp']=self.m['max_hp']*.8
        self.o['mechs']=[enemy(self.o,2,50,0,1100)];self.o['events']=[{'type':'effect','effect':'short','by':2}]
        self.b.intercept=lambda *a:(0.,0.,True,True,50.,.1,.1)
        # Simulate a sheltered point to the west, while keeping the current line open.
        self.b.map.ray=lambda a,b:not (a[0]<self.p[0]-5 and b[0]>self.p[0]+40)
        a=self.b.act(self.o);self.assertFalse(any(a['fire']));self.assertLess(a['move'][0],-.3)
    def test_healing_cube_approach_does_not_start_laser_charge(self):
        self.m['hp']=self.m['max_hp']*.74; self.m['weapons']=[weapon('gun'),weapon('laser')];self.b.last_attack=self.o['t']-.5
        self.o['cubes']=[{'id':5000,'pos':[self.p[0]+30,self.p[1],self.p[2]]}]
        self.o['crates']=[{'id':1001,'hp':300,'pos':[self.p[0]+60,self.p[1],self.p[2]]}]
        self.b.intercept=lambda *a:(0.,0.,True,True,60.,.1,.1)
        a=self.b.act(self.o);self.assertEqual(self.b.last_mode,'loot');self.assertFalse(a['fire'][1]);self.assertTrue(a['fire'][0]);self.assertGreater(a['move'][0],.5)

    def test_underarmed_long_range_laser_triggers_early_escape(self):
        self.m['hp']=self.m['max_hp']*.77
        e=enemy(self.o,2,150,0,1400);e['weapons']=['gun','laser'];e['aim']=[math.pi,0.]
        self.o['mechs']=[e];self.o['events']=[{'type':'damaged','amount':315,'weapon':'laser','bearing':0.,'by':2}]
        self.b.duel_value=lambda *a:-.30
        a=self.b.act(self.o);self.assertTrue(self.b.recovering);self.assertEqual(self.b.last_mode,'escape');self.assertLess(a['move'][0],-.3)
    def test_long_range_policy_does_not_flee_unrelated_enemy(self):
        self.m['hp']=self.m['max_hp']*.77
        e=enemy(self.o,2,150,0,1400);e['weapons']=['gun','laser'];e['aim']=[math.pi,0.]
        self.o['mechs']=[e];self.o['events']=[{'type':'damaged','amount':45,'weapon':'gun','bearing':0.,'by':3}]
        self.b.duel_value=lambda *a:-.30
        self.b.act(self.o);self.assertFalse(self.b.recovering)

if __name__=='__main__':unittest.main()
