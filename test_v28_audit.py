import math, unittest
from bot import Bot
from test_bot import H, scenario, enemy, weapon

class AuditTests(unittest.TestCase):
    def setUp(self): self.b=Bot(H)
    def test_rear_armor_is_more_dangerous(self):
        o=scenario(); m=o['self']; m['weapons']=[weapon('gun'),None]; m['hp']=m['max_hp']; e=enemy(o,2,30,0,1400)
        # A target in front of us is less dangerous than the same target at our back.
        m['aim']=[0.,0.]; front=self.b.duel_value(m,e,30)
        m['aim']=[math.pi,0.]; rear=self.b.duel_value(m,e,30)
        self.assertLess(rear,front)
    def test_enemy_rear_exposure(self):
        o=scenario(); m=o['self']; m['weapons']=[weapon('gun'),None]; m['hp']=m['max_hp']; e=enemy(o,2,30,0,1400)
        e['aim']=[math.pi,0.]; front=self.b.duel_value(m,e,30)
        e['aim']=[0.,0.]; rear=self.b.duel_value(m,e,30)
        self.assertGreater(rear,front)
    def test_drop_landing_and_capture_sequential(self):
        o=scenario(); m=o['self']; p=m['pos']; m['stats']['walk_speed']=10
        z=dict(center=p[:2],next_center=p[:2],radius=100,next_radius=20,shrink_start=30,shrink_end=40)
        q=(p[0]+40,p[1],p[2])
        # Travel takes five seconds, landing takes seven, capture four more.
        self.assertTrue(self.b.objective_viable(p,q,m,z,30,0,0))
        self.assertFalse(self.b.objective_viable(p,q,m,z,30,4,7))
    def test_landing_overlaps_travel(self):
        o=scenario(); m=o['self']; p=m['pos']; m['stats']['walk_speed']=10
        z=dict(center=p[:2],next_center=p[:2],radius=100,next_radius=20,shrink_start=30,shrink_end=45)
        q=(p[0]+40,p[1],p[2])
        self.assertEqual(self.b.objective_viable(p,q,m,z,30,4,3),self.b.objective_viable(p,q,m,z,30,4,0))
