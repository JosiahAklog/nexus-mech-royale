"""Deterministic feature and stress tests. No match simulator is supplied by the kit."""
import copy,gzip,json,math,pathlib,random,sys,time,unittest
from bot import Bot,Map,delta
from check.check import Schema
ROOT=pathlib.Path(__file__).parent
with gzip.open(ROOT/'check/stream.jsonl.gz','rt') as f: M=[json.loads(x) for x in f]
H=M[0]; O=next(x for x in M if x.get('type')=='obs'); C=H['config']; SCHEMA=Schema(str(ROOT/'mechfight.schema.json'))
def scenario():
    o=copy.deepcopy(O); o['self']['pos']=[40.,-70.,0.];o['self']['vel']=[0.,0.,0.]; o['self']['aim']=[0.,0.];o['t']=30.;o['tick']=600
    for k in ['mechs','crates','cubes','pickups','projectiles','events','sounds','drops','beams']:o[k]=[]
    return o
def weapon(kind):
    w={'kind':kind,'cooldown':0.,'stats':copy.deepcopy(C['weapons'][kind])}
    if kind=='gun':w.update(ammo=12,reload=0.)
    if kind=='laser':w['charge']=0.
    return w
def enemy(o,i=1,dx=25,dy=0,hp=600):
    x,y,z=o['self']['pos'];return {'kind':'mech','id':i,'pos':[x+dx,y+dy,z],'vel':[2.,1.,0.],'hp':hp,'max_hp':1400,'cubes':1,'aim':[math.pi,0.],'weapons':['gun'],'charging':False}
class Tests(unittest.TestCase):
    def setUp(self):self.b=Bot(H)
    def validate(self,o):
        a=self.b.act(o); self.assertEqual(a['tick'],o['tick']); self.assertFalse(SCHEMA.errors(a,'Action')); self.assertLessEqual(math.hypot(*a['move']),1.000001);return a
    def test_upgrade(self):
        o=scenario();o['offer']={'choices':[{'id':'sensors'},{'id':'nanites'},{'id':'armor'}]};self.assertEqual(self.validate(o)['pick'],1)
    def test_pickup(self):
        o=scenario();x,y,z=o['self']['pos'];o['pickups']=[{'id':8001,'kind':'laser','pos':[x+1,y,z]}];self.assertEqual(self.validate(o)['take'],8001)
    def test_laser_swap_busy(self):
        o=scenario();o['self']['weapons'][1]=weapon('laser');o['self']['weapons'][1]['charge']=.3;o['pickups']=[{'id':8001,'kind':'mortar','pos':o['self']['pos']}];self.assertNotIn('take',self.validate(o))
    def test_aim_lead(self):
        o=scenario(); t=enemy(o); t['vel']=[0,11,0]; sol=self.b.intercept(o['self']['pos'],o['self'],t,weapon('gun'));self.assertGreater(sol[0],0.)
    def test_zone(self):
        o=scenario();o['zone'].update(center=[0.,0.],next_center=[0.,0.],radius=40.,next_radius=25.,shrink_start=20.,shrink_end=35.);a=self.validate(o);p=o['self']['pos'];self.assertGreater(-p[0]*a['move'][0]-p[1]*a['move'][1],0)
    def test_recovery_hysteresis(self):
        o=scenario();o['self']['hp']=o['self']['max_hp']*.35
        q=self.b.map.point(self.b.map.nearest(o['self']['pos']));o['self']['pos']=[*q,self.b.map.ground(*q)];o['self']['in_zone']=True
        a=self.validate(o);self.assertTrue(self.b.recovering);self.assertEqual(a['fire'],[False,False]);self.assertLess(math.hypot(*a['move']),.01)
        o['self']['hp']=o['self']['max_hp']*.75;o['t']+=1;o['tick']+=20
        a=self.validate(o);self.assertTrue(self.b.recovering);self.assertEqual(a['fire'],[False,False])
        o['self']['hp']=o['self']['max_hp']*.97;o['t']+=1;o['tick']+=20
        self.validate(o);self.assertFalse(self.b.recovering)
    def test_recorded_actions_without_wrapper_fallback(self):
        b=Bot(H)
        count=0
        for o in M:
            if o.get('type')!='obs':continue
            a=b.act(o);self.assertEqual(a['tick'],o['tick']);self.assertFalse(SCHEMA.errors(a,'Action'));self.assertTrue(all(math.isfinite(v) for v in a['move']+a['aim']));count+=1
        self.assertEqual(count,300)
    def test_crowded_observation(self):
        o=scenario();o['self']['weapons'][1]=weapon('mortar');p=o['self']['pos'];o['self']['hp']=400
        o['mechs']=[enemy(o,i,50*math.cos(i),50*math.sin(i)) for i in range(15)]
        o['projectiles']=[{'id':i+500,'kind':'gun','pos':[p[0]+40*math.cos(i),p[1]+40*math.sin(i),p[2]+5],'vel':[-200*math.cos(i),-200*math.sin(i),0]} for i in range(64)]
        self.validate(o)
    def test_native_map_equivalence(self):
        m=self.b.map
        if m.native is None:self.skipTest('optional Linux native helper not loaded')
        rng=random.Random(77); nodes=[i for i,v in enumerate(m.nav) if v]
        for _ in range(150):
            a,b=rng.sample(nodes,2); p=(*m.point(a),rng.uniform(0,40));q=(*m.point(b),rng.uniform(0,40))
            self.assertEqual(m.ray(p,q),m.ray_python(p,q))
            path=m.route(p,q);last=a
            for point in path:
                k=m.node(point);self.assertIn(k,[e[0] for e in m.edges[last]]);last=k
    def test_recovery_releases_laser(self):
        o=scenario();o['self']['hp']=300;o['self']['weapons'][1]=weapon('laser');o['self']['weapons'][1]['charge']=.35
        o['mechs']=[enemy(o,2,25,0)];self.b.recovering=True
        a=self.validate(o);self.assertFalse(a['fire'][1])
    def test_projectile_native_equivalence(self):
        m=self.b.map
        if m.native is None:self.skipTest('native helper unavailable')
        rng=random.Random(97);o=scenario();me=o['self'];p=me['pos'];st=me['stats'];dirs=[(math.cos(i*math.pi/8),math.sin(i*math.pi/8)) for i in range(16)] + [(0.,0.)]
        for _ in range(200):
            me['vel']=[rng.uniform(-15,15),rng.uniform(-15,15),0.];me['grounded']=rng.choice([True,False]);accel=st['ground_accel'] if me['grounded'] else st['air_accel']
            shots=[([p[0]+rng.uniform(-40,40),p[1]+rng.uniform(-40,40),p[2]+rng.uniform(0,15)],[rng.uniform(-200,200),rng.uniform(-200,200),rng.uniform(-10,10)],rng.choice(['gun','mortar'])) for _ in range(32)]
            native=m.projectile_risks(dirs,shots,p,me,22.,7.)
            py=m.risk_python(dirs,shots,p,st['walk_speed'],*me['vel'][:2],accel,st['height'],st['radius'],22.,7.)
            for a,b in zip(native,py):self.assertAlmostEqual(a,b,places=8)
    def test_no_laser_charge_outside_zone(self):
        o=scenario();o['self']['in_zone']=False;o['self']['weapons'][1]=weapon('laser');o['self']['weapons'][1]['charge']=.4;o['mechs']=[enemy(o)]
        self.assertFalse(self.validate(o)['fire'][1])
    def test_final_zone_braking(self):
        o=scenario(); p=o['self']['pos']; o['zone'].update(center=[p[0]+2,p[1]],next_center=[p[0]+2,p[1]],radius=5.,next_radius=0.,shrink_start=20.,shrink_end=35.); o['self']['vel']=[6.,0.,0.]
        o['self']['energy']=100.; a=self.validate(o);self.assertFalse(a['boost']);self.assertGreater(a['move'][0],0.);self.assertLess(a['move'][0],.5)
        o['self']['pos'][0]+=2;o['self']['vel']=[0.,0.,0.];o['t']+=.1;o['tick']+=2;a=self.validate(o);self.assertLess(math.hypot(*a['move']),.01)
    def test_finish_supply_capture(self):
        o=scenario(); q=self.b.map.point(self.b.map.nearest(o['self']['pos']));o['self']['pos']=[*q,self.b.map.ground(*q)];o['self']['hp']=1000
        p=o['self']['pos'];o['drops']=[{'id':20000,'pos':p[:],'radius':8,'lands_in':0,'capture_s':4,'progress':3.6,'holder':o['self']['id']}];o['mechs']=[enemy(o,2,25,0)]
        self.assertLess(math.hypot(*self.validate(o)['move']),.01)
    def test_loot_memory(self):
        o=scenario(); p=o['self']['pos']; o['pickups']=[{'id':8001,'kind':'laser','pos':[p[0]+40,p[1],p[2]]}];o['cubes']=[{'id':5001,'pos':[p[0]+25,p[1],p[2]]}]
        a,b=self.b.remembered_loot(o);self.assertEqual(len(a),1);self.assertEqual(len(b),1)
        o['pickups']=[];o['cubes']=[];o['t']+=1;a,b=self.b.remembered_loot(o);self.assertEqual(len(a),1);self.assertEqual(len(b),1)
        o['self']['pos'][0]+=25;a,b=self.b.remembered_loot(o);self.assertEqual(len(b),0)
        o['t']+=46;a,b=self.b.remembered_loot(o);self.assertEqual(len(a),0)
    def test_pick_nearest(self):
        o=scenario();p=o['self']['pos'];o['pickups']=[{'id':8000,'kind':'laser','pos':[p[0]+3,p[1],p[2]]},{'id':8001,'kind':'laser','pos':[p[0]+1,p[1],p[2]]}]
        self.assertEqual(self.validate(o)['take'],8001)
    def test_no_blind_gun_target(self):
        o=scenario();me=o['self'];p=me['pos'];me['weapons']=[weapon('gun'),None];e=enemy(o,2,20,0);self.b.map.ray=lambda a,b:False
        self.assertIsNone(self.b.choose_target(p,me,o,[e],[],None)[0])
    def test_reload_not_while_firing(self):
        o=scenario();me=o['self'];me['hp']=500;me['weapons']=[weapon('gun'),None];me['weapons'][0]['ammo']=4;o['mechs']=[enemy(o,2,20,0)];self.b.map.ray=lambda a,b:True
        self.b.intercept=lambda *args:(0.,0.,True,True,20.,.1,.1)
        a=self.validate(o);self.assertTrue(a['fire'][0]);self.assertFalse(a.get('reload',False))
    def test_return_fire_when_recovery_blocked(self):
        o=scenario();me=o['self'];me['hp']=500;me['weapons']=[weapon('gun'),None];o['mechs']=[enemy(o,2,65,0)];o['events']=[{'type':'damaged','weapon':'gun','by':2,'amount':45,'bearing':0.}]
        self.b.map.ray=lambda a,b:True
        self.b.intercept=lambda *args:(0.,0.,True,True,65.,.1,.1)
        a=self.validate(o);self.assertTrue(self.b.recovering);self.assertTrue(a['fire'][0]);self.assertLess(a['move'][0],0.)
        o['t']+=3.;o['tick']+=60;o['events']=[];self.b.map.ray=lambda a,b:False
        a=self.validate(o);self.assertFalse(any(a['fire']))
    def test_lightning_and_gun_compatible_aim(self):
        o=scenario();me=o['self'];me['hp']=me['max_hp'];me['energy']=100;me['weapons']=[weapon('gun'),weapon('lightning')];o['mechs']=[enemy(o,2,35,0)];self.b.map.ray=lambda a,b:True
        self.b.intercept=lambda p,m,t,w:(.12,.16,True,True,35.,.03,.04) if w['kind']=='gun' else (0.,-.05,True,True,35.,.03,.04)
        a=self.validate(o);self.assertEqual(a['fire'],[True,True]);self.assertAlmostEqual(a['aim'][0],.12)
    def test_safe_cube_during_recovery(self):
        o=scenario();me=o['self'];me['hp']=400;me['cubes']=1;q=self.b.map.point(self.b.map.nearest(me['pos']));me['pos']=[*q,self.b.map.ground(*q)];me['in_zone']=True
        p=me['pos'];self.b.map.surface=lambda x,y:(p[2],p[2],20.);self.b.map.top=lambda x,y:p[2];o['cubes']=[{'id':5001,'pos':[p[0]+9,p[1],p[2]]}]
        a=self.validate(o);self.assertTrue(self.b.recovering);self.assertGreater(a['move'][0],.4);self.assertFalse(any(a['fire']))
    def test_stress(self):
        rng=random.Random(44); samples=[]
        for i in range(360):
            o=scenario();o['t']=i*.1;o['tick']=i*2; me=o['self'];me['pos']=[rng.uniform(-450,480),rng.uniform(-280,320),0.];me['pos'][2]=self.b.map.ground(*me['pos'][:2]);me['hp']=rng.randint(100,1400);me['energy']=rng.uniform(0,100);me['aim']=[rng.uniform(-math.pi,math.pi),rng.uniform(-.7,1.3)];me['weapons'][1]=weapon(['laser','mortar','lightning'][i%3]);
            if i%3==0:me['weapons'][1]['charge']=rng.choice([0.,.3,.8])
            if i%6: o['mechs']=[enemy(o,j+1,rng.uniform(-100,100),rng.uniform(-100,100)) for j in range(i%10)]
            p=me['pos'];o['projectiles']=[{'id':j+900,'pos':[p[0]+rng.uniform(-75,75),p[1]+rng.uniform(-75,75),p[2]+4],'vel':[rng.uniform(-200,200),rng.uniform(-200,200),0.],'kind':'gun'} for j in range(i%16)]
            start=time.perf_counter();self.validate(o);samples.append((time.perf_counter()-start)*1000)
        print(f'360 synthetic cases: max {max(samples):.2f} ms, p99 {sorted(samples)[356]:.2f} ms')
if __name__=='__main__':unittest.main()
