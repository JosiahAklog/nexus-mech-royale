import unittest, math
from bot import Bot
from test_bot import H, scenario, enemy, weapon, SCHEMA

class EconomyTests(unittest.TestCase):
    def setUp(self):
        self.b=Bot(H);self.o=scenario();self.m=self.o['self'];self.p=self.m['pos'];self.m.update(hp=self.m['max_hp'],energy=100.,grounded=True,cubes=0,weapons=[weapon('gun'),None]);self.o['zone'].update(center=self.p[:2],next_center=self.p[:2],radius=300.,next_radius=260.,shrink_start=100.,shrink_end=140.)
        self.b.map.ray=lambda *a:True;self.b.map.surface=lambda *a:(self.p[2],self.p[2],50.);self.b.map.top=lambda *a:self.p[2];self.b.map.ground=lambda *a:self.p[2];self.b.map.clearance=lambda *a:50.
    def step(self):
        a=self.b.act(self.o);self.assertFalse(SCHEMA.errors(a,'Action'));return a
    def pickup(self,dx,dy=0,dz=0):return {'id':8001,'kind':'laser','pos':[self.p[0]+dx,self.p[1]+dy,self.p[2]+dz]}
    def cube(self,dx,dy=0):return {'id':5001,'pos':[self.p[0]+dx,self.p[1]+dy,self.p[2]]}
    def test_second_weapon_over_single_cube(self):
        self.o['pickups']=[self.pickup(40)];self.o['cubes']=[self.cube(-15)];a=self.step();self.assertEqual(self.b.last_mode,'loot');self.assertGreater(a['move'][0],.6)
    def test_no_bonus_for_contested_or_rooftop(self):
        self.assertGreater(self.b.acquisition_bonus(self.p,self.m,self.pickup(40),[]),0)
        self.assertEqual(self.b.acquisition_bonus(self.p,self.m,self.pickup(40),[enemy(self.o,2,37,0)]),0)
        self.assertEqual(self.b.acquisition_bonus(self.p,self.m,self.pickup(40,dz=20),[]),0)
    def test_boost_hysteresis_stops_at_reserve(self):
        self.b.goal_memory=(self.p[0]+60,self.p[1]);self.b.explore_at=self.o['t'];self.m['energy']=80.
        self.assertTrue(self.step()['boost']);self.m['energy']=50.;self.o['t']+=.1;self.o['tick']+=2;self.assertTrue(self.step()['boost']);self.m['energy']=35.;self.o['t']+=.1;self.o['tick']+=2;self.assertFalse(self.step()['boost'])
    def test_direct_attacker_not_ignored(self):
        self.o['mechs']=[enemy(self.o,3,68,0,1400)];self.o['crates']=[{'id':1001,'pos':[self.p[0]+12,self.p[1],self.p[2]],'hp':100}];self.o['events']=[{'type':'damaged','by':3,'weapon':'gun','amount':45.,'bearing':0.}]
        self.b.intercept=lambda *a:(0.,0.,True,True,68.,.05,.05);a=self.step();self.assertTrue(a['fire'][0]);self.assertEqual(self.b.target_id,3)
    def test_laser_crate_damage_threshold(self):
        self.m['weapons']=[weapon('gun'),weapon('laser')];self.m['weapons'][1]['charge']=.69;self.o['crates']=[{'id':1001,'pos':[self.p[0]+25,self.p[1],self.p[2]],'hp':300}];self.b.intercept=lambda *a:(0.,0.,True,True,25.,.05,.05)
        self.assertTrue(self.step()['fire'][1]);self.m['weapons'][1]['charge']=.75;self.o['t']+=.1;self.o['tick']+=2;self.assertFalse(self.step()['fire'][1])
    def test_pickup_dodge_not_braked(self):
        self.o['cubes']=[self.cube(4)];p=self.p;self.o['projectiles']=[{'id':901,'kind':'gun','pos':[p[0]+10,p[1],p[2]+4],'vel':[-200.,0.,0.]}];self.b.map.projectile_risks=lambda candidates,*a,**kw:[100. if abs(dx)>.5 else 0. for dx,dy in candidates]
        a=self.step();self.assertGreater(math.hypot(*a['move']),.95);self.assertGreater(abs(a['move'][1]),.7)

if __name__=='__main__':unittest.main()
