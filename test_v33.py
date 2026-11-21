import math,unittest
from bot import Bot,delta,distance
from test_bot import H,scenario,enemy,weapon,SCHEMA

class V33Tests(unittest.TestCase):
    def setUp(self):
        self.b=Bot(H);self.o=scenario();self.m=self.o['self'];self.p=self.m['pos'];self.m['hp']=self.m['max_hp'];self.m['energy']=100.;self.m['grounded']=True
        self.m['cubes']=0;self.m['weapons']=[weapon('gun'),None]
        self.b.map.ray=lambda *a:True;self.b.map.top=lambda *a:self.p[2];self.b.map.ground=lambda *a:self.p[2];self.b.map.surface=lambda *a:(self.p[2],self.p[2],50.);self.b.map.clearance=lambda *a:50.
    def test_lightning_blocker_and_chain(self):
        e=enemy(self.o,2,40,0);w=weapon('lightning');b=enemy(self.o,3,12,0)
        self.assertIsNone(self.b.lightning_lane(self.p,self.m,e,w,[e,b],0.,True))
        b['pos']=[self.p[0]+31,self.p[1],self.p[2]]
        self.assertEqual(self.b.lightning_lane(self.p,self.m,e,w,[e,b],0.,True),0.)
    def test_lightning_aim_offsets_around_blocker(self):
        e=enemy(self.o,2,40,0);w=weapon('lightning');b=enemy(self.o,3,15,3.5)
        yaw=self.b.lightning_lane(self.p,self.m,e,w,[e,b],0.,True)
        self.assertIsNotNone(yaw);self.assertLess(yaw,0);self.assertLess(abs(yaw),math.radians(15))
        self.assertIsNone(self.b.lightning_lane(self.p,self.m,e,w,[e,b],0.))
    def test_unsafe_arc_does_not_fire(self):
        self.m['weapons']=[weapon('gun'),weapon('lightning')];e=enemy(self.o,2,40,0,100);self.o['mechs']=[e];self.o['crates']=[{'id':1000,'hp':300,'pos':[self.p[0]+10,self.p[1],self.p[2]]}]
        self.b.intercept=lambda *a:(0.,0.,True,True,40.,.1,.1)
        a=self.b.act(self.o);self.assertFalse(a['fire'][1]);self.assertTrue(a['fire'][0]);self.assertFalse(SCHEMA.errors(a,'Action'))
    def test_drop_holder_prevents_impossible_capture(self):
        d={'id':20000,'pos':[self.p[0]+45,self.p[1],self.p[2]],'radius':8,'lands_in':0,'holder':(self.m['id']+1)%16,'capture_s':4,'progress':3.5}
        self.assertTrue(self.b.occupied_drop(self.p,self.m,d,[]));d['holder']=self.m['id'];self.assertFalse(self.b.occupied_drop(self.p,self.m,d,[]));d['holder']=None;self.assertFalse(self.b.occupied_drop(self.p,self.m,d,[]))
    def test_zone_anchor_walkable(self):
        z=dict(self.o['zone'],center=[40.,-70.],radius=100,next_center=[40.,-70.],next_radius=60);g=tuple(self.p[:2]);self.b.map.surface=lambda x,y:(20,0,0) if distance((x,y),g)<10 else (0,0,40)
        v=self.b.zone_anchor(self.p,g,self.m,z);self.assertGreaterEqual(distance(v,g),10);self.assertLess(distance(v,z['next_center']),52)
        z['next_radius']=10;self.assertEqual(self.b.zone_anchor(self.p,g,self.m,z),g)
    def test_crate_memory_and_expiration(self):
        c={'id':1000,'hp':90,'pos':[self.p[0]+40,self.p[1],self.p[2]]};self.o['crates']=[c];self.assertEqual(self.b.remember_crates(self.o),[]);self.o['crates']=[];self.o['t']+=2
        self.assertEqual(self.b.remember_crates(self.o),[c]);a=self.b.act(self.o);self.assertEqual(self.b.last_mode,'farm');self.assertGreater(a['move'][0],.4);self.assertFalse(any(a['fire']))
        self.o['t']+=14;self.assertEqual(self.b.remember_crates(self.o),[])
    def test_early_patrol_boost_hysteresis(self):
        self.b.goal_memory=(self.p[0]+100,self.p[1]);self.b.explore_at=self.o['t'];self.m['energy']=80
        a=self.b.act(self.o);self.assertEqual(self.b.last_mode,'patrol');self.assertTrue(a['boost']);self.o['t']+=.1;self.o['tick']+=2;self.m['energy']=60
        self.assertTrue(self.b.act(self.o)['boost']);self.o['t']+=.1;self.o['tick']+=2;self.m['energy']=42;self.assertFalse(self.b.act(self.o)['boost'])
    def test_short_gun_burst_finishes_crate_without_laser_charge(self):
        self.m['weapons']=[weapon('gun'),weapon('laser')];self.o['crates']=[{'id':1000,'hp':90,'pos':[self.p[0]+20,self.p[1],self.p[2]]}]
        self.b.intercept=lambda *a:(0.,0.,True,True,20.,.1,.1)
        a=self.b.act(self.o);self.assertTrue(a['fire'][0]);self.assertFalse(a['fire'][1])
    def test_outmatched_policy_keeps_active_defense(self):
        self.m['hp']=self.m['max_hp']*.72;e=enemy(self.o,2,80,0,1800);e.update(aim=[0.,0.],weapons=['gun','laser'],cubes=10,vel=[0.,0.,0.]);self.b.duel_value=lambda *a:-.35
        self.assertTrue(self.b.outmatched_disengage(self.p,self.m,e,[e],self.o['t']));e['aim']=[math.pi,0];self.assertFalse(self.b.outmatched_disengage(self.p,self.m,e,[e],self.o['t']));e['aim']=[0.,0.];self.b.last_damage=self.o['t']-2;self.assertFalse(self.b.outmatched_disengage(self.p,self.m,e,[e],self.o['t']))

if __name__=='__main__':unittest.main()
