import unittest
from test_bot import H,scenario,weapon,enemy,SCHEMA
from bot import Bot

class V22Tests(unittest.TestCase):
    def setup_bot(self):
        b=Bot(H,'adaptive'); o=scenario();m=o['self'];m['hp']=m['max_hp'];m['energy']=100.;m['weapons']=[weapon('gun'),None]; p=m['pos'];b.map.ray=lambda *q:True;b.map.surface=lambda *q:(p[2],p[2],50.);b.map.top=lambda *q:p[2];return b,o,m,p
    def test_duel_estimate_rewards_damage_and_hp(self):
        b,o,m,p=self.setup_bot(); e=enemy(o,2,30,0,800)
        a=b.duel_advantage(m,e,30);m['weapons'][1]=weapon('lightning');self.assertGreater(b.duel_advantage(m,e,30),a*2)
        self.assertLess(b.sustained_damage([m['weapons'][1]],70),.001)
        m['hp']*=.25;self.assertLess(b.duel_advantage(m,e,30),a)
    def test_standoff_from_enemy_arc(self):
        b,o,m,p=self.setup_bot();e=enemy(o,2,35,0,1000);e['weapons']=['gun','lightning'];self.assertGreater(b.combat_distance(38,m,e,35,1),H['config']['weapons']['lightning']['range'])
    def test_upgrade_armor_when_under_pressure(self):
        b,o,m,p=self.setup_bot();m['hp']=m['max_hp']*.69;o['mechs']=[enemy(o,2,40,0,1000)];o['events']=[{'type':'damaged','by':2,'bearing':0.,'weapon':'gun','amount':45}];o['offer']={'choices':[{'id':'nanites'},{'id':'armor'},{'id':'gun_mag'}]};a=b.act(o);self.assertEqual(a['pick'],1);self.assertFalse(SCHEMA.errors(a,'Action'))
    def test_early_patrol_sprint(self):
        b,o,m,p=self.setup_bot();m['grounded']=True;m['energy']=80.;m['cubes']=0;b.goal_memory=(p[0]+85,p[1]);b.map.bounds={'minX':-500,'maxX':500,'minY':-350,'maxY':350};o['zone'].update(center=p[:2],radius=400,next_center=p[:2],next_radius=250,shrink_start=60,shrink_end=110);a=b.act(o);self.assertEqual(b.last_mode,'patrol');self.assertTrue(a['boost'])
if __name__=='__main__':unittest.main()
