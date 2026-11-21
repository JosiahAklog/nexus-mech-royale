import unittest
from test_bot import H,scenario,weapon,enemy,SCHEMA
from bot import Bot
class V20Tests(unittest.TestCase):
    def setup_bot(self):
        b=Bot(H,'adaptive');o=scenario();m=o['self'];m['hp']=m['max_hp'];m['weapons']=[weapon('gun'),None];p=m['pos'];m['energy']=100
        b.map.ray=lambda *args: True;b.map.top=lambda *args:p[2];b.map.surface=lambda *args:(p[2],p[2],50.)
        b.intercept=lambda *args:(0.,0.,True,True,50.,.1,.1)
        return b,o,m,p
    def test_active_attacker_over_crate(self):
        b,o,m,p=self.setup_bot(); o['mechs']=[enemy(o,2,65,0,1400)];o['crates']=[{'id':1001,'pos':[p[0]+15,p[1],p[2]],'hp':100}]; o['events']=[{'type':'damaged','by':2,'bearing':0.,'weapon':'gun','amount':45}]
        a=b.act(o);self.assertEqual(b.target_id,2);self.assertTrue(a['fire'][0])
    def test_finish_enemy_before_distant_cube(self):
        b,o,m,p=self.setup_bot();o['mechs']=[enemy(o,2,50,0,100)];o['cubes']=[{'id':5001,'pos':[p[0]-21,p[1],p[2]]}]
        a=b.act(o);self.assertEqual(b.last_mode,'fight');self.assertTrue(a['fire'][0]);self.assertFalse(SCHEMA.errors(a,'Action'))
    def test_near_cube_still_allowed(self):
        b,o,m,p=self.setup_bot();o['mechs']=[enemy(o,2,50,0,100)];o['cubes']=[{'id':5001,'pos':[p[0]-5,p[1],p[2]]}]
        b.act(o);self.assertEqual(b.last_mode,'loot')
    def test_long_distance_projectile_planning(self):
        b,o,m,p=self.setup_bot();o['projectiles']=[{'id':90,'kind':'gun','pos':[p[0]+140,p[1],p[2]+5],'vel':[-252,0,0]}];counts=[]
        def risk(candidates,projectiles,*args):
            counts.append(len(projectiles));return [0.]*len(candidates)
        b.map.projectile_risks=risk;b.act(o);self.assertGreater(max(counts),0)
if __name__=='__main__':unittest.main()
