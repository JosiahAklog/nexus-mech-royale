import math, unittest
from bot import Bot, Map
from test_bot import H, scenario, enemy, weapon

class V30Tests(unittest.TestCase):
    def setUp(self): self.b=Bot(H)
    def test_acceleration_hazard_when_instantaneous_model_misses(self):
        # An airborne mech has velocity toward the shot. The command cannot
        # reverse it instantly; a current-velocity sample must detect danger.
        risks=Map.risk_python([(-1.,0.)],[([8.,0.,4.5],[-2.,0.,0.],'gun')],(0.,0.,0.),11.7,11.7,0.,12.,9.,2.5,22.,7.)
        self.assertGreater(risks[0],12.)
    def test_short_event_blocks_laser_but_not_gun(self):
        o=scenario();m=o['self'];m['hp']=m['max_hp'];m['weapons']=[weapon('gun'),weapon('laser')];o['mechs']=[enemy(o,2,50,0,600)];o['events']=[{'type':'effect','effect':'short','by':2}]
        self.b.map.ray=lambda *a:True;self.b.intercept=lambda *a:(0.,0.,True,True,50.,.04,.04)
        a=self.b.act(o);self.assertTrue(a['fire'][0]);self.assertFalse(a['fire'][1]);self.assertGreater(self.b.laser_short_until,o['t'])
        o['events']=[];o['t']+=2.1;o['tick']+=42
        a=self.b.act(o);self.assertTrue(a['fire'][1])
    def test_threat_rear_and_cookoff(self):
        o=scenario();m=o['self'];e=enemy(o,2,60,0,1400);e.update(weapons=['laser'],charging=True)
        m['aim']=[0.,0.];m['weapons']=[weapon('gun'),None];front=self.b.imminent_threats(m['pos'],m,[e],30)[0][1]
        m['aim']=[math.pi,0.];rear=self.b.imminent_threats(m['pos'],m,[e],30)[0][1];self.assertAlmostEqual(rear,front*1.5)
        m['weapons'][1]=weapon('mortar');cook=self.b.imminent_threats(m['pos'],m,[e],30)[0][1];self.assertAlmostEqual(cook,rear*1.6)
    def test_travel_does_not_start_laser_at_crate(self):
        o=scenario();m=o['self'];p=m['pos'];m['hp']=m['max_hp'];m['weapons']=[weapon('gun'),weapon('laser')];o['crates']=[{'id':1001,'pos':[p[0]+30,p[1],p[2]],'hp':300}]
        o['drops']=[{'id':20000,'pos':[p[0]+45,p[1],p[2]],'radius':8,'lands_in':0,'capture_s':4,'progress':0,'holder':None}]
        self.b.map.ray=lambda *args:True;self.b.map.surface=lambda *args:(p[2],p[2],50.);self.b.map.top=lambda *args:p[2];self.b.intercept=lambda *args:(0.,0.,True,True,30.,.04,.04)
        a=self.b.act(o);self.assertEqual(self.b.last_mode,'drop');self.assertFalse(a['fire'][1]);self.assertTrue(a['fire'][0])
    def test_upgraded_regen_earlier_repair(self):
        o=scenario();m=o['self'];m['hp']=m['max_hp']*.70;m['stats']['regen_delay']=2.;self.b.last_damage=o['t']-1.5;self.b.last_attack=o['t']-1.5
        self.b.act(o);self.assertTrue(self.b.recovering)

if __name__=='__main__':unittest.main()
