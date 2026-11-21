"""NEXUS: standalone mechfight/1 bot; only public map and observations are used."""
import array, heapq, json, math, pathlib, sys, time, ctypes
import mechfight as mf
from math import hypot, atan2, sin, cos, sqrt, pi

PROFILE='balanced'
def clip(v,a,b): return max(a,min(b,v))
def norm(x,y):
    d=hypot(x,y)
    return (x/d,y/d) if d>1e-8 else (0.,0.)
def delta(a,b): return (a-b+pi)%(2*pi)-pi
def distance(a,b): return hypot(a[0]-b[0],a[1]-b[1])
def bearing(a,b): return atan2(b[1]-a[1],b[0]-a[0])
DIR=[(cos(i*pi/8),sin(i*pi/8)) for i in range(16)]

class Map:
    def __init__(self):
        root=pathlib.Path(__file__).parent
        m=json.loads((root/'mapinfo.json').read_text()); self.x=m['x'];self.y=m['y'];self.nx=m['nx'];self.ny=m['ny'];self.step=m['step']; self.bounds=m['bounds']; self.n=self.nx*self.ny
        self.data=array.array('h'); self.data.frombytes((root/'map.bin').read_bytes())
        if sys.byteorder!='little': self.data.byteswap()
        self.gs=4; self.w=(self.nx-1)//self.gs+1; self.h=(self.ny-1)//self.gs+1; self.cell=self.gs*self.step
        self.nav=[]; self.clear=[]; self.inv_step=1.0/self.step
        for j in range(self.h):
            for i in range(self.w):
                x=min(self.nx-1,i*self.gs); y=min(self.ny-1,j*self.gs); k=y*self.nx+x
                c=self.data[2*self.n+k]*.01; self.clear.append(c); self.nav.append(c>=4.1 and 0<i<self.w-1 and 0<j<self.h-1)
        # Static adjacency is shared by all route searches in a match.
        w,h=self.w,self.h; nav=self.nav; clear=self.clear
        self.edges=[()]*(w*h)
        offsets=((1,0,1),(-1,0,1),(0,1,1),(0,-1,1),(1,1,1.414),(1,-1,1.414),(-1,1,1.414),(-1,-1,1.414))
        for n,valid in enumerate(nav):
            if not valid:continue
            i,j=n%w,n//w; edges=[]
            for dx,dy,step in offsets:
                if not (0<=i+dx<w and 0<=j+dy<h):continue
                k=n+dx+dy*w
                if not nav[k] or (dx and dy and (not nav[n+dx] or not nav[n+dy*w])):continue
                edges.append((k,step,max(0.,8-clear[k])*.10))
            self.edges[n]=tuple(edges)
        # No native dependency is required: use the exact Python algorithms if unavailable.
        self.native=None
        try:
            lib=ctypes.CDLL(str(root/'fastmap.so'))
            i32=ctypes.c_int32; i16=ctypes.c_int16; dbl=ctypes.c_double
            lib.fast_ray.argtypes=[ctypes.POINTER(i16),ctypes.c_int,ctypes.c_int]+[dbl]*9
            lib.fast_ray.restype=ctypes.c_int
            lib.fast_route.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.POINTER(i32),ctypes.POINTER(dbl),ctypes.c_int,ctypes.c_int,ctypes.POINTER(i32)]
            lib.fast_route.restype=ctypes.c_int
            lib.projectile_risk.argtypes=[ctypes.POINTER(dbl),ctypes.c_int,ctypes.POINTER(dbl),ctypes.c_int]+[dbl]*11+[ctypes.POINTER(dbl)]
            lib.projectile_risk.restype=None
            self.risk_candidates=(dbl*36)(); self.risk_shots=(dbl*(32*7))(); self.risk_out=(dbl*18)()
            self.raw=(i16*len(self.data)).from_buffer(self.data)
            self.adj=(i32*(len(nav)*8))(*([-1]*(len(nav)*8)))
            self.costs=(dbl*(len(nav)*16))()
            self.out=(i32*20000)()
            for i,edges in enumerate(self.edges):
                for j,(k,step,penalty) in enumerate(edges):
                    pos=i*8+j;self.adj[pos]=k;self.costs[pos*2]=step;self.costs[pos*2+1]=penalty
            self.native=lib
        except (OSError,AttributeError,ValueError):pass
    def projectile_risks(self,candidates,projectiles,p,me,gravity,splash):
        st=me['stats']; speed=st['walk_speed']; vx0,vy0=me['vel'][:2]; accel=st['ground_accel'] if me['grounded'] else st['air_accel']; height=st['height']; radius=st['radius']
        if not projectiles:return [0.]*len(candidates)
        if self.native is not None and len(candidates)<=18 and len(projectiles)<=32:
            for i,(dx,dy) in enumerate(candidates):self.risk_candidates[2*i]=dx;self.risk_candidates[2*i+1]=dy
            for i,(q,v,k) in enumerate(projectiles):self.risk_shots[7*i:7*i+7]=(*q,*v,float(k=='mortar'))
            self.native.projectile_risk(self.risk_candidates,len(candidates),self.risk_shots,len(projectiles),*p,speed,vx0,vy0,accel,height,radius,gravity,splash,self.risk_out)
            return self.risk_out[:len(candidates)]
        return self.risk_python(candidates,projectiles,p,speed,vx0,vy0,accel,height,radius,gravity,splash)
    @staticmethod
    def risk_python(candidates,projectiles,p,speed,vx0,vy0,accel,height,radius,gravity,splash):
        out=[]
        for dx,dy in candidates:
            vx,vy=dx*speed,dy*speed; ax,ay=vx-vx0,vy-vy0; turn=min(.8,hypot(ax,ay)/accel) if accel>0 else .8; risk=0.
            for q,v,k in projectiles:
                rx,ry=q[0]-p[0],q[1]-p[1]; rvx,rvy=v[0]-vx,v[1]-vy; den=rvx*rvx+rvy*rvy
                tt=clip(-(rx*rvx+ry*rvy)/den,0,.8) if den>1 else 0.
                if tt<.015:continue
                lag=(tt*(1-.5*tt/turn) if tt<turn else .5*turn) if turn>1e-8 else 0.
                vertical=q[2]+v[2]*tt-(p[2]+height*.5)-(.5*gravity*tt*tt if k=='mortar' else 0.)
                if abs(vertical)>height*.65+3:continue
                r=radius+(splash if k=='mortar' else 1.4)+3; x=rx+rvx*tt+ax*lag; y=ry+rvy*tt+ay*lag; miss2=x*x+y*y
                if miss2<r*r:risk+=(r-sqrt(miss2))*4
            out.append(risk)
        return out
    def idx(self,x,y):
        i=int((x-self.x)*self.inv_step+.5);j=int((y-self.y)*self.inv_step+.5)
        return j*self.nx+i if 0<=i<self.nx and 0<=j<self.ny else -1
    def top(self,x,y):
        k=self.idx(x,y); return self.data[self.n+k]*.01 if k>=0 else 1000.
    def ground(self,x,y):
        k=self.idx(x,y); return self.data[k]*.01 if k>=0 else 1000.
    def clearance(self,x,y):
        k=self.idx(x,y); return self.data[2*self.n+k]*.01 if k>=0 else 0.
    def ray(self,a,b):
        if self.native is not None:
            return bool(self.native.fast_ray(self.raw,self.nx,self.ny,self.x,self.y,self.inv_step,*a,*b))
        return self.ray_python(a,b)
    def ray_python(self,a,b):
        # Same sample positions as V2; inline raster lookup in this hot loop.
        ax,ay,az=a; dx=b[0]-ax;dy=b[1]-ay;dz=b[2]-az
        n=max(2,int(hypot(dx,dy)/3)+1)
        mx,my,inv,nx,ny,offset,data=self.x,self.y,self.inv_step,self.nx,self.ny,self.n,self.data
        for i in range(1,n):
            f=i/n
            ix=int((ax+dx*f-mx)*inv+.5);iy=int((ay+dy*f-my)*inv+.5)
            if not (0<=ix<nx and 0<=iy<ny):
                if 1000.>az+dz*f+.25:return False
            elif data[offset+iy*nx+ix]*.01>az+dz*f+.25:return False
        return True
    def surface(self,x,y):
        k=self.idx(x,y)
        if k<0:return 1000.,1000.,0.
        data=self.data;n=self.n
        return data[n+k]*.01,data[k]*.01,data[2*n+k]*.01
    def node(self,p):
        i=clip(round((p[0]-self.x)/self.cell),0,self.w-1); j=clip(round((p[1]-self.y)/self.cell),0,self.h-1); return j*self.w+i
    def point(self,node):return (self.x+(node%self.w)*self.cell,self.y+(node//self.w)*self.cell)
    def nearest(self,p):
        n=self.node(p); x=n%self.w;y=n//self.w
        if self.nav[n]:return n
        best=None; bd=1e9
        for r in range(1,7):
            for j in range(max(0,y-r),min(self.h,y+r+1)):
                for i in range(max(0,x-r),min(self.w,x+r+1)):
                    k=j*self.w+i
                    if self.nav[k]:
                        d=distance(self.point(k),p)
                        if d<bd:best=k;bd=d
            if best is not None:return best
        return None
    def route(self,a,b):
        start=self.nearest(a); goal=self.nearest(b)
        if start is None or goal is None or start==goal:return []
        if self.native is not None:
            length=self.native.fast_route(self.w,len(self.nav),self.adj,self.costs,start,goal,self.out)
            if length>=0:return [self.point(self.out[i]) for i in range(length)]
        return self.route_python(start,goal)
    def route_python(self,start,goal):
        gx=goal%self.w;gy=goal//self.w; w=self.w; edges=self.edges
        def h(k):return hypot(k%w-gx,k//w-gy)
        q=[(h(start),0.,start)]; cost={start:0.}; parent={}; best=start; bh=h(start); count=0; deadline=time.perf_counter()+.009
        while q and count<1800:
            _,g,n=heapq.heappop(q)
            if g!=cost[n]:continue
            count+=1
            if count%64==0 and time.perf_counter()>deadline:break
            hh=h(n)
            if hh<bh:best=n;bh=hh
            if n==goal:best=n;break
            for k,step,penalty in edges[n]:
                ng=g+step+penalty
                if ng<cost.get(k,1e9):cost[k]=ng;parent[k]=n;heapq.heappush(q,(ng+1.12*h(k),ng,k))
        out=[]
        while best!=start and best in parent:out.append(self.point(best));best=parent[best]
        return out[::-1]

class Bot:
    name='NEXUS-v5'
    def __init__(self,hello):
        self.cfg=hello['config']; self.map=Map(); self.slot=hello['slot']; self.last_damage=-100.; self.last_bearing=None; self.last_attack=-100.; self.last_pos=None; self.stuck=0.; self.path=[]; self.route_goal=None; self.route_time=-100.; self.target_id=None; self.last_t=-1.; self.goal_memory=None; self.loot_seen={}; self.last_move=(0.,0.); self.history={}; self.altitude_goal=None; self.boosting=False; self.recovering=False; self.recovery_since=-100.; self.jet_until=-100.; self.last_target=None; self.sight_scan=0.; self.last_hp=None
    def target_height(self,t):
        if t.get('kind')=='mech':return self.cfg['mech']['height']*(1+self.cfg['cubes']['size_per_cube']*t.get('cubes',0))*.52
        if t.get('kind')=='npc':return self.cfg['npc']['height']*.55
        return self.cfg['crates']['height']*.55
    def safe(self,p,zone,margin=8):return distance(p,zone['center']) < max(0,zone['radius']-margin)
    def intercept(self,p,me,t,w):
        k=w['kind']; st=w['stats']; ts=me['stats']; pos=t['pos']; v=t.get('vel',(0,0,0)); ht=self.target_height(t); muzzle=ts['height']+.5 if k=='mortar' else ts['muzzle_height']; origin=(p[0],p[1],p[2]+muzzle)
        delay=.045; speed=st.get('speed',1e8); gravity=st.get('gravity',0.) if k=='mortar' else 0.
        flight=max(0.,(distance(p,pos)-ts['radius']-.5)/speed)
        for _ in range(6 if gravity else 3):
            fut=flight+delay; tx=pos[0]+v[0]*fut;ty=pos[1]+v[1]*fut;tz=pos[2]+ht+v[2]*min(fut,.3)
            if gravity:tz+=.5*gravity*flight*flight
            dx=tx-origin[0];dy=ty-origin[1];dz=tz-origin[2]; dist=sqrt(dx*dx+dy*dy+dz*dz); flight=clip((dist-ts['radius']-.5)/speed,0.,5.)
        yaw=atan2(dy,dx);pitch=atan2(dz,hypot(dx,dy)); r=st.get('range',speed*speed/max(gravity,1.))
        good=dist<=r*.98 and ts['min_pitch']<=pitch<=ts['max_pitch']
        if k=='mortar':
            good=good and distance(p,pos)>14 and flight<3.5
            # Check the predicted arc at several points, not a straight ray.
            end=flight; travel=ts['radius']+.5
            if good:
                for frac in (.12,.25,.4,.55,.7,.85):
                    t1=end*frac; q=travel+speed*t1; xx=origin[0]+cos(yaw)*cos(pitch)*q; yy=origin[1]+sin(yaw)*cos(pitch)*q; zz=origin[2]+sin(pitch)*q-.5*gravity*t1*t1
                    if self.map.top(xx,yy)>zz+.25:good=False;break
        elif k=='lightning':
            good=good and distance(p,pos)<=st['range']*.96 and self.map.ray(origin,(tx,ty,tz))
        else:good=good and self.map.ray(origin,(tx,ty,tz))
        # Aim error in metres rather than a fixed angle. A small turn during the next sim tick is allowed.
        rad=(self.cfg['mech']['radius']*(1+self.cfg['cubes']['size_per_cube']*t.get('cubes',0)) if t.get('kind')=='mech' else self.cfg['npc']['radius'] if t.get('kind')=='npc' else self.cfg['crates']['radius'])
        tol=clip(atan2(rad*.72,max(1.,dist)),.009,.32); ptol=clip(atan2(ht*.72,max(1.,dist)),.009,.35)
        yerr=abs(delta(yaw,me['aim'][0])); perr=abs(pitch-me['aim'][1]); rate=ts['turn_rate']*.045; prate=ts['pitch_rate']*.045
        aligned=(yerr<=tol+rate and perr<=ptol+prate) if k!='lightning' else yerr<math.radians(st['cone_deg']*.42)+rate
        return yaw,pitch,good,aligned,dist,tol,ptol
    def choose_target(self,p,me,obs,enemies,npcs,loot):
        eye=(p[0],p[1],p[2]+me['stats']['muzzle_height']); cand=[]; nearby_enemy=any(distance(p,e['pos'])<40 for e in enemies)
        for t in enemies+npcs+obs.get('crates',[]):
            d=distance(p,t['pos']); kind=t.get('kind','crate'); hp=t.get('hp',1000); h=self.target_height(t)
            if d>220:continue
            line=self.map.ray(eye,(t['pos'][0],t['pos'][1],t['pos'][2]+h))
            if not line and (kind!='mech' or d>75):continue
            if kind=='mech': score=108-d*.65+(1-hp/max(1,t.get('max_hp',1400)))*58-(0 if line else 105)-min(16,t.get('cubes',0)*1.6)
            elif kind=='npc': score=78-d*.85+(1-hp/max(1,t.get('max_hp',350)))*27
            else:score=74-d*.80+(1-hp/300)*23
            if t['id']==self.target_id:score+=8
            if kind=='mech' and line and d<70:score+=12
            if kind=='mech' and line and t.get('charging'):score+=10 if d<45 and any(w and w['kind']=='lightning' for w in me['weapons']) else 0
            if kind!='mech' and loot:score-=15
            if kind!='mech' and me['hp']<me['max_hp']*.6:score-=65
            if kind!='mech' and me['cubes']<6 and d<45:score+=20
            if kind!='mech' and nearby_enemy:score-=75
            if kind=='mech' and me['hp']<me['max_hp']*.36:score-=25
            cand.append((score,t,line))
        if not cand:return None,False
        _,t,line=max(cand,key=lambda it:it[0]);return t,line
    def act(self,obs):
        p=obs['self']['pos']; me=obs['self']; t=obs['t']; z=obs['zone']; stats=me['stats']; hp=me['hp']/max(1,me['max_hp']); energy=me['energy']; weapons=me['weapons']; kinds=[w['kind'] if w else None for w in weapons]; dt=clip(t-self.last_t,0,.3); self.last_t=t
        if self.last_pos is not None:
            if distance(p,self.last_pos)<.22 and hypot(*self.last_move)>.5 and me['grounded']:self.stuck+=dt
            else:self.stuck=max(0.,self.stuck-dt*.75)
        self.last_pos=p[:]
        for e in obs['events']:
            if e['type']=='damaged' and e.get('weapon')!='zone':self.last_damage=t;self.last_bearing=e.get('bearing')
            if e['type']=='hit':self.last_attack=t
        if self.last_hp is not None and me['hp']<self.last_hp-.5 and not me['in_zone']:self.last_damage=t
        self.last_hp=me['hp']
        enemies=sorted((e for e in obs['mechs'] if e['kind']=='mech'),key=lambda e:distance(p,e['pos'])); npcs=[e for e in obs['mechs'] if e['kind']=='npc']; close=[e for e in enemies if distance(p,e['pos'])<125]; near=close[0] if close else None; nd=distance(p,near['pos']) if near else 999.; danger=len([e for e in close if distance(p,e['pos'])<85]); recovering=hp<.56 and (danger>=1 or t-self.last_damage<5) and (nd>18 or danger>=2); recovering=recovering or (hp<.32 and danger>=1)
        # Hysteresis: after disengaging, stay out of combat until repair has actually worked.
        if hp<.59 and (danger>=1 or t-self.last_damage<6) or hp<.42:
            if not self.recovering:self.recovery_since=t
            self.recovering=True
        if hp>.90 or (z['radius']<30 and hp>.35):self.recovering=False
        recovering=self.recovering and z['radius']>14
        threatened_now=nd<30 or t-self.last_damage<1.4
        zone_margin=z['radius']-distance(p,z['center']); emergency_zone=zone_margin<12 or not me['in_zone']
        # Distinguish a dangerous visible/remembered mech from one behind a building.
        eye=(p[0],p[1],p[2]+stats['eye_height'])
        exposed=[e for e in close if self.map.ray(eye,(e['pos'][0],e['pos'][1],e['pos'][2]+self.target_height(e)))]
        result={'tick':obs['tick'],'fire':[False,False]}
        if obs.get('offer'):
            ranks={'nanites':100,'armor':94,'plating':88,'servos':86,'gun_mag':82,'laser_damage':83,'mortar_reload':79,'gun_damage':78,'gun_rate':75,'laser_charge':77,'reactor':74,'jets':70,'capacitor':66,'lightning_efficiency':65,'lightning_range':69,'gyros':48,'gun_velocity':50,'mortar_velocity':46,'mortar_splash':59,'sensors':35,'laser_pierce':25,'lightning_chain':30}
            result['pick']=max(range(len(obs['offer']['choices'])),key=lambda i:ranks.get(obs['offer']['choices'][i]['id'],0))
        # Prioritize an appropriate second weapon; keep the gun for consistent DPS.
        pref={'gun':0,'lightning':3,'mortar':2,'laser':4}
        if PROFILE=='mortar':pref['mortar']=5
        loot=[]
        for x in obs['pickups']:
            k=x['kind']; d=distance(p,x['pos']); dz=abs(p[2]-x['pos'][2]); old=kinds[1]; want=k not in kinds and k!='gun' and (old is None or pref.get(k,0)>pref.get(old,0)) and not (old=='laser' and weapons[1].get('charge',0)>0)
            if want and d<=self.cfg['loot']['pickup_radius'] and dz<=4:
                result['take']=x['id'];
                if old is not None:result['drop']=1
                break
            if want and d<100 and dz<27 and self.safe(x['pos'],z):loot.append((d+dz*2-(18 if old is None else 0),x))
        for x in obs['cubes']:
            d=distance(p,x['pos']);dz=abs(p[2]-x['pos'][2]);
            if d<120 and dz<26 and self.safe(x['pos'],z):loot.append((d+dz*2-40,x))
        loot.sort(key=lambda q:q[0]); lootgoal=loot[0][1] if loot else None
        target, line=self.choose_target(p,me,obs,enemies,npcs,lootgoal); self.target_id=target['id'] if target else None
        if recovering and (not threatened_now or target is None or target.get('kind')!='mech'):
            target=None;line=False
        # Avoid wasting a shot on a target tracked through solid cover.
        if target and not line and 'mortar' not in kinds and distance(p,target['pos'])>30:target=None
        # Aim and select weapons using live stats. Laser is charged only when a real target is available.
        aim=list(me['aim']); active=None; solutions={}
        if target:
            for i,w in enumerate(weapons):
                if w:solutions[i]=self.intercept(p,me,target,w)
            good=[i for i,s in solutions.items() if s[2]]
            if good:
                def priority(i):
                    w=weapons[i]; k=w['kind']; s=solutions[i]; ready=w['cooldown']<=.11; val=0
                    if k=='gun':val=30 if ready and not w.get('reload',0) and w.get('ammo',1)>0 else 8
                    elif k=='laser':val=(70 if w.get('charge',0)>0 else 53) if ready and not recovering else 4
                    elif k=='mortar':val=64 if ready else 3
                    elif k=='lightning':val=48 if ready and energy>=w['stats'].get('energy',3)+12 else 1
                    return val
                active=max(good,key=priority); aim=list(solutions[active][:2]);
                for i,s in solutions.items():
                    w=weapons[i]; k=w['kind']; st=w['stats']; charge=w.get('charge',0); same=abs(delta(s[0],aim[0]))<s[5]+.018 and abs(s[1]-aim[1])<s[6]+.018
                    if k=='laser':
                        if charge>0:
                            result['fire'][i]=bool(not recovering and s[2] and (charge<st['charge']-.06 or not (s[3] and same)) and charge<st['charge']+.6 and not (recovering and danger>=2))
                        else:result['fire'][i]=bool(s[2] and same and w['cooldown']<=.08 and not recovering)
                    elif s[2] and same and s[3] and (not recovering or target.get('kind')=='mech' and nd<38):
                        result['fire'][i]=bool(k!='lightning' or energy>=st.get('energy',3)+10)
            else:aim=[bearing(p,target['pos']),0.]
        if recovering and (nd>32 or not exposed):result['fire']=[False,False]
        if emergency_zone:
            for i,w in enumerate(weapons):
                if w and w['kind']=='laser':result['fire'][i]=False
        if weapons[0] and weapons[0]['kind']=='gun' and weapons[0].get('ammo',12)<weapons[0]['stats']['mag']*.72 and (not target or recovering or not line):result['reload']=True
        # Goal selection. Stay in a healthy part of the zone without blindly rushing its center.
        curd=distance(p,z['center']); nextd=distance(p,z['next_center']); next_r=z['next_radius']; current_margin=z['radius']-curd; next_margin=next_r-nextd
        travel_time=max(0.,nextd-max(0,next_r-18))/max(1.,stats['walk_speed']*.72)
        urgency=(current_margin<18 or t+travel_time+10>z['shrink_end'] and next_margin<10 or next_r<30 and next_margin<6)
        goal=None; mode='patrol'; hold=False; altitude=None
        # Uncontested drops are powerful healing and upgrade opportunities.
        drops=[]
        for d in obs['drops']:
            dd=distance(p,d['pos']); threatened=any(distance(e['pos'],d['pos'])<32 for e in close)
            if d.get('lands_in',0)<=max(0,dd/stats['walk_speed'])+3 and self.safe(d['pos'],z,4) and not threatened and dd<180:
                drops.append((dd-(1-hp)*100,d))
        if drops and (hp<.93 or me['cubes']<12) and not urgency:
            d=min(drops,key=lambda q:q[0])[1];goal=d['pos'];mode='drop';hold=distance(p,goal)<d['radius']*.58 and abs(p[2]-goal[2])<7
        if goal is None and urgency:
            ux,uy=norm(p[0]-z['next_center'][0],p[1]-z['next_center'][1]); r=max(0,next_r-min(42,max(12,next_r*.35)));goal=(z['next_center'][0]+ux*r,z['next_center'][1]+uy*r);mode='zone'
        if goal is None and recovering:
            # If hidden and safe, stop spending energy and let HP restore rather than wandering into combat.
            if not exposed and nd>36 and t-self.last_damage>1.1 and current_margin>32:
                goal=p;mode='repair';hold=True
            elif near:ex,ey=norm(p[0]-near['pos'][0],p[1]-near['pos'][1])
            elif self.last_bearing is not None:ex,ey=-cos(self.last_bearing),-sin(self.last_bearing)
            else:ex,ey=norm(z['next_center'][0]-p[0],z['next_center'][1]-p[1])
            if goal is None:goal=(p[0]+ex*70,p[1]+ey*70);mode='escape'
        if goal is None and lootgoal and (nd>35 or lootgoal['id']>=5000 and lootgoal['id']<8000):
            goal=lootgoal['pos'];mode='loot';altitude=goal[2]
        if goal is None and target:
            d=distance(p,target['pos']);kind=target.get('kind','crate')
            if kind=='mech':
                ideal=33 if 'lightning' in kinds and 'laser' not in kinds else 78 if 'mortar' in kinds else 75 if 'laser' in kinds else 47
                if danger>=2:ideal+=25
                if hp<.72:ideal+=10
                # Close isolated weak targets; strafe rather than run straight at them.
                if target.get('hp',1400)<300 and danger<=1 and hp>.70:ideal=min(ideal,36)
                ex,ey=norm(target['pos'][0]-p[0],target['pos'][1]-p[1]); sign=1 if (int(t/2.7)+self.slot)%2 else -1; radial=clip((d-ideal)/16,-1,1) if line else 1
                sx,sy=norm(ex*radial-ey*sign*.7,ey*radial+ex*sign*.7);goal=(p[0]+sx*35,p[1]+sy*35);mode='fight'
            else:
                ideal=16 if kind=='npc' else 13; ex,ey=norm(target['pos'][0]-p[0],target['pos'][1]-p[1]);goal=(target['pos'][0]-ex*ideal,target['pos'][1]-ey*ideal);mode='farm';hold=d<ideal+3 and line and nd>75;altitude=target['pos'][2]
        if goal is None:
            if self.goal_memory is None or distance(p,self.goal_memory)<15 or not self.safe(self.goal_memory,z,18):
                angle=.8+self.slot*2.399+int(t/14)*1.7; r=min(max(0,next_r*.55),95); self.goal_memory=(z['next_center'][0]+cos(angle)*r,z['next_center'][1]+sin(angle)*r)
            goal=self.goal_memory;mode='patrol'
        # Boundary correction on any non-zone goal.
        gx,gy=goal[:2]; center=z['center']; ux,uy=norm(gx-center[0],gy-center[1]); gd=distance(goal,center); rr=max(0,z['radius']-12)
        if gd>rr:gx=center[0]+ux*rr;gy=center[1]+uy*rr
        b=self.map.bounds;gx=clip(gx,b['minX']+8,b['maxX']-8);gy=clip(gy,b['minY']+8,b['maxY']-8);goal=(gx,gy)
        if mode=='zone' and distance(p,goal)<(0.7 if z['radius']<6 else 2.0):hold=True
        # Ground route when needed; local steering handles combat, roofs, and moving threats.
        direct=norm(gx-p[0],gy-p[1]); route_needed=mode in ('zone','loot','drop','patrol','farm','escape') and not hold and distance(p,goal)>13 and (altitude is None or altitude<p[2]+5)
        if route_needed and self.map.ray((p[0],p[1],p[2]+1.1),(gx,gy,self.map.ground(gx,gy)+1.1)) and distance(p,goal)<75:route_needed=False
        if route_needed:
            if self.route_goal is None or distance(goal,self.route_goal)>20 or t-self.route_time>2.0 or not self.path or self.stuck>.6 and t-self.route_time>.5:
                self.route_goal=goal;self.route_time=t;self.path=self.map.route(p,goal)
            while self.path and distance(p,self.path[0])<9:self.path.pop(0)
            if self.path:direct=norm(self.path[0][0]-p[0],self.path[0][1]-p[1])
        else:self.path=[];self.route_goal=None
        # Pick local steering direction. Estimate impact danger from incoming projectiles.
        projectiles=[]
        for obj in obs['projectiles']:
            q=obj['pos'];v=obj['vel']; dd=distance(p,q)
            if dd<100 and (obj['kind']=='mortar' or (q[0]-p[0])*v[0]+(q[1]-p[1])*v[1]<dd*stats['boost_speed']):projectiles.append((dd,q,v,obj['kind']))
        projectiles=[(q,v,k) for _,q,v,k in sorted(projectiles,key=lambda item:item[0])[:32]]
        candidates=[direct]+DIR
        if hold:candidates=[(0.,0.)]+candidates
        best=None;bestscore=-1e12
        risks=self.map.projectile_risks(candidates,projectiles,p,me,self.cfg['weapons']['mortar']['gravity'],self.cfg['weapons']['mortar']['splash_radius'])
        for (dx,dy),risk in zip(candidates,risks):
            score=0 if hold else 14*(dx*direct[0]+dy*direct[1]); score+=2*(dx*self.last_move[0]+dy*self.last_move[1]);
            if hold:score-=hypot(dx,dy)*(20 if mode=='repair' else 12)
            # terrain/wall checks at multiple distances; allow moving along roof edges.
            for dd,pen in (((3,65),(7,34),(13,15)) if hypot(dx,dy)>.01 else ()):
                xx=p[0]+dx*dd;yy=p[1]+dy*dd; top,ground,clearance=self.map.surface(xx,yy)
                if top>p[2]+stats['step_up']+.55:score-=pen
                elif clearance<stats['radius']+1 and p[2]<ground+3:score-=pen*.35
            xx=p[0]+dx*12; yy=p[1]+dy*12; future=(xx,yy,p[2]); zm=z['radius']-distance(future,z['center']);
            if zm<12:score-=max(0,12-zm)*(2.5 if urgency else 1.6)
            if near:
                for e in close[:5]:
                    old=distance(p,e['pos']); new=distance(future,e['pos']);
                    if recovering and not hold:score+=(new-old)*(.95 if old<70 else .28)
                    elif old<20:score+=(new-old)*.85
                    if recovering and not hold and old<100 and not self.map.ray((xx,yy,p[2]+stats['eye_height']),(e['pos'][0],e['pos'][1],e['pos'][2]+self.target_height(e))):score+=6
            score-=risk
            if score>bestscore:bestscore=score;best=(dx,dy)
        move=best or direct; jump=False;boost=False
        if mode in ('zone','loot','drop') and not hold and distance(p,goal)<8 and self.stuck<.5:
            # Slow down approaching a pickup/capture point rather than overshooting.
            factor=clip(distance(p,goal)/7,.08,1.);move=(move[0]*factor,move[1]*factor)
        if self.stuck>.55 and not hold and energy>30:
            self.jet_until=t+1.8
            # Vertical escape if the selected route is obstructed and walking has failed.
            if me['grounded']:jump=True
            else:boost=True
            if self.stuck>2.4:self.stuck=.3;self.path=[]
        if t<self.jet_until and not me['grounded'] and energy>15 and not hold:boost=True
        if altitude is not None and altitude>p[2]+3 and distance(p,goal)<28 and energy>25 and not hold:
            jump=me['grounded'];boost=not me['grounded']
        if not me['grounded'] and stats['height']>0 and energy>19 and self.map.top(p[0]+move[0]*9,p[1]+move[1]*9)>p[2]+1.5:boost=True
        if me['grounded'] and not hold and hypot(*move)>.25 and self.map.top(p[0]+move[0]*4,p[1]+move[1]*4)<p[2]+stats['step_up']+.55:
            if mode in ('escape','zone') and (energy>48 or self.boosting and energy>22):boost=True
            elif mode=='loot' and distance(p,goal)>20 and energy>78:boost=True
            elif mode=='fight' and danger and nd<27 and energy>52:boost=True
            elif mode=='patrol' and energy>90 and distance(p,goal)>70:boost=True
        self.boosting=boost
        if not target:
            if recovering and exposed:aim=[bearing(p,exposed[0]['pos']),0.]
            elif recovering and self.last_bearing is not None and t-self.last_damage<6:aim=[self.last_bearing,0.]
            elif near:aim=[bearing(p,near['pos']),0.]
            elif t-self.last_damage<3 and self.last_bearing is not None:aim=[self.last_bearing,0.]
            elif not recovering and any(s.get('dist')=='near' and s.get('kind') in ('gun','laser_charge','lightning','mortar','boost') for s in obs.get('sounds',[])):
                sound=min((s for s in obs['sounds'] if s.get('dist')=='near' and s.get('kind') in ('gun','laser_charge','lightning','mortar','boost')),key=lambda s:s.get('age',0)); aim=[sound['bearing'],0.]
            else:
                yaw=atan2(move[1],move[0]) if hypot(*move)>.1 else me['aim'][0];aim=[yaw+.55*sin(t*1.1+self.slot),-.05]
        if target and recovering and near and target.get('kind')!='mech':aim=[bearing(p,near['pos']),0.]
        result.update(move=list(move),boost=bool(boost),jump=bool(jump),aim=[float(delta(aim[0],0)),float(clip(aim[1],stats['min_pitch'],stats['max_pitch']))]);self.last_move=move
        return result

if __name__=='__main__':mf.run(Bot)
