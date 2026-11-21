"""Policy separation and protocol regression tests, not a match simulator."""
import copy, math, unittest, random
from test_bot import H,M,SCHEMA,scenario,weapon,enemy
from bot import Bot, POLICIES

class ProfileTests(unittest.TestCase):
    def test_distinct_policies(self):
        o=scenario();m=o['self'];m['hp']=m['max_hp']*.65;m['energy']=100.;m['weapons']=[weapon('gun'),None];o['mechs']=[enemy(o,2,50,0,1100)]
        a=Bot(H,'aggressive');s=Bot(H,'survivor');a.act(o);s.act(o)
        self.assertFalse(a.recovering);self.assertTrue(s.recovering)
    def test_empty_gun_requests_reload(self):
        for key in POLICIES:
            b=Bot(H,key);o=scenario();m=o['self'];m['hp']=m['max_hp'];m['weapons']=[weapon('gun'),None];m['weapons'][0]['ammo']=0;o['mechs']=[enemy(o,2,25,0,500)]
            b.map.ray=lambda a,b:True;b.intercept=lambda *args:(0.,0.,True,True,25.,.04,.04)
            a=b.act(o);self.assertFalse(a['fire'][0]);self.assertTrue(a['reload'])
    def test_fallback_to_hittable_target(self):
        b=Bot(H,'adaptive');o=scenario();m=o['self'];m['hp']=m['max_hp'];m['weapons']=[weapon('gun'),None]
        a=enemy(o,2,25,0,100);c=enemy(o,3,35,0,700);o['mechs']=[a,c]
        b.map.ray=lambda *args:True
        b.intercept=lambda p,m,t,w:(0.,0.,t['id']==3,True,35.,.1,.1)
        result=b.act(o);self.assertEqual(b.target_id,3);self.assertTrue(result['fire'][0])
    def test_no_idle_air_jet_under_roof(self):
        b=Bot(H,'adaptive');o=scenario();m=o['self'];m['grounded']=False;m['hp']=m['max_hp']*.35;m['energy']=100.;m['in_zone']=True
        b.map.top=lambda *args:50.;b.map.surface=lambda *args:(50.,0.,100.)
        result=b.act(o);self.assertEqual(b.last_mode,'repair');self.assertFalse(result['boost'])
    def test_close_target_pitch_reachable(self):
        b=Bot(H,'adaptive');o=scenario();m=o['self'];e=enemy(o,2,3.,0.,800);e['vel']=[0.,0.,0.]
        b.map.ray=lambda *args:True;b.map.top=lambda *args:-100.
        sol=b.intercept(m['pos'],m,e,weapon('gun'));self.assertTrue(sol[2]);self.assertGreaterEqual(sol[1],m['stats']['min_pitch'])
    def test_farm_drone_on_move(self):
        b=Bot(H,'adaptive');o=scenario();m=o['self'];m['hp']=m['max_hp'];m['weapons']=[weapon('gun'),None]
        p=m['pos'];o['mechs']=[{'id':104,'kind':'npc','pos':[p[0]+28,p[1],p[2]],'hp':350,'max_hp':350,'vel':[0.,0.,0.],'aim':[math.pi,0.]}]
        b.map.ray=lambda *args:True;b.map.surface=lambda *args:(p[2],p[2],50.);b.map.top=lambda *args:p[2]
        a=b.act(o);self.assertEqual(b.last_mode,'farm');self.assertGreater(abs(a['move'][1]),.5)
    def test_close_crowd_maintains_mobility(self):
        b=Bot(H,'adaptive');o=scenario();m=o['self'];m['hp']=m['max_hp']*.77;m['weapons']=[weapon('gun'),weapon('laser')];o['mechs']=[enemy(o,2,30,0,1000),enemy(o,4,35,10,1200)]
        b.map.ray=lambda *args:True;b.intercept=lambda *args:(0.,0.,True,True,30.,.07,.07)
        a=b.act(o);self.assertTrue(a['fire'][0]);self.assertFalse(a['fire'][1])
    def test_reload_gun_in_second_slot(self):
        b=Bot(H,'adaptive');o=scenario();m=o['self'];m['hp']=m['max_hp'];m['weapons']=[weapon('laser'),weapon('gun')];m['weapons'][1]['ammo']=2
        a=b.act(o);self.assertTrue(a.get('reload'))
    def test_all_profiles_replay_and_stress(self):
        rng=random.Random(884)
        for key in POLICIES:
            b=Bot(H,key);count=0
            for o in M:
                if o.get('type')!='obs':continue
                a=b.act(o);self.assertEqual(a['tick'],o['tick']);self.assertFalse(SCHEMA.errors(a,'Action'));count+=1
            self.assertEqual(count,300)
            b=Bot(H,key)
            for i in range(160):
                o=scenario();o['t']=30+i*.1;o['tick']=600+2*i;m=o['self'];m['hp']=rng.uniform(1,m['max_hp']);m['energy']=rng.uniform(0,100);m['weapons']=[weapon('gun'),weapon(('laser','mortar','lightning')[i%3])];m['pos']=[rng.uniform(-450,480),rng.uniform(-280,320),0];m['pos'][2]=b.map.ground(*m['pos'][:2]);m['weapons'][0]['ammo']=i%13
                o['mechs']=[enemy(o,2+j,rng.uniform(-100,100),rng.uniform(-100,100),rng.uniform(1,1400)) for j in range(i%6)]
                a=b.act(o);self.assertFalse(SCHEMA.errors(a,'Action'));self.assertTrue(all(math.isfinite(x) for x in a['move']+a['aim']))

if __name__=='__main__':unittest.main()
