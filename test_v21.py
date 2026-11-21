import unittest
from test_bot import H,scenario,weapon,enemy,SCHEMA
from bot import Bot
class V21Tests(unittest.TestCase):
    def test_cover_preserves_target_lane(self):
        b=Bot(H,'adaptive');o=scenario();m=o['self'];p=m['pos'];a=enemy(o,2,40,0);c=enemy(o,3,0,40)
        b.map.ground=lambda *q:p[2]
        # At negative y the target stays visible and secondary is blocked.
        b.map.ray=lambda start,end: end[0]==a['pos'][0] or start[1]>=p[1]
        self.assertGreater(b.fight_cover_value(p,(p[0],p[1]-12,p[2]),m,a,[a,c]),b.fight_cover_value(p,(p[0],p[1]+12,p[2]),m,a,[a,c]))
    def test_ready_lethal_gun_over_uncharged_laser(self):
        b=Bot(H,'adaptive');o=scenario();m=o['self'];p=m['pos'];m['hp']=m['max_hp'];m['weapons']=[weapon('gun'),weapon('laser')];o['mechs']=[enemy(o,2,40,0,20)]
        b.map.ray=lambda *q:True;b.intercept=lambda *q:(0.,0.,True,True,40.,.1,.1)
        a=b.act(o);self.assertTrue(a['fire'][0]);self.assertFalse(a['fire'][1]);self.assertFalse(SCHEMA.errors(a,'Action'))
    def test_late_patrol_goal_replaced(self):
        b=Bot(H,'adaptive');o=scenario();m=o['self'];m['hp']=m['max_hp'];p=m['pos'];o['zone'].update(center=[p[0],p[1]],radius=300,next_center=[p[0],p[1]],next_radius=100,shrink_end=o['t']+9,shrink_start=o['t']-1)
        b.goal_memory=(p[0]+180,p[1]);b.act(o);self.assertLessEqual(__import__('math').dist(b.goal_memory,p[:2]),100)
if __name__=='__main__':unittest.main()
