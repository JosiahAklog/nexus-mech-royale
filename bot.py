"""NEXUS: standalone mechfight/1 bot; only public map and observations are used."""
import array, heapq, json, math, pathlib, sys, time, ctypes
import mechfight as mf
from math import hypot, atan2, sin, cos, sqrt, pi

PROFILE='adaptive'
# Independent policies for practice A/B testing. No seed or opponent information
# beyond the current legal observations is used.
POLICIES={
 'aggressive': dict(retreat=.45, heal=.84, quiet=.65, escape=1.0, farm=10, loot=12, reserve=3, cover=9, risk=1.05, strafe=1.1),
 'survivor': dict(retreat=.76, heal=.96, quiet=.87, escape=2.1, farm=14, loot=22, reserve=17, cover=19, risk=1.7, strafe=.9),
 'adaptive': dict(retreat=.60, heal=.91, quiet=.79, escape=1.55, farm=21, loot=18, reserve=7, cover=14, risk=1.35, strafe=1.0),
}

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
        if len(self.data)!=3*self.n: raise ValueError('Invalid map cache length')
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
    def projectile_risks(self,candidates,projectiles,p,me,gravity,splash,speed_override=None):
        st=me['stats']; speed=st['walk_speed'] if speed_override is None else speed_override; vx0,vy0=me['vel'][:2]; accel=st['ground_accel'] if me['grounded'] else st['air_accel']; height=st['height']; radius=st['radius']
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
    name='NEXUS-experiment'
    def __init__(self,hello,profile=None):
        self.profile=profile or PROFILE; self.policy=POLICIES[self.profile]; self.name='NEXUS-V28.1-'+self.profile; self.variant=getattr(type(self),'variant','baseline'); self.name='NEXUS-V37-'+self.variant if self.variant!='baseline' else self.name
        self.cfg=hello['config']; self.map=Map(); self.slot=hello['slot']; self.last_damage=-100.; self.last_bearing=None; self.last_attack=-100.; self.last_pos=None; self.stuck=0.; self.path=[]; self.route_goal=None; self.route_time=-100.; self.target_id=None; self.last_t=-1.; self.goal_memory=None; self.loot_seen={}; self.last_move=(0.,0.); self.history={}; self.altitude_goal=None; self.boosting=False; self.recovering=False; self.recovery_since=-100.; self.jet_until=-100.; self.last_target=None; self.sight_scan=0.; self.last_hp=None; self.motion={}; self.last_attacker=None; self.roof_goal=None; self.roof_until=-1.; self.last_mode=None; self.damage_recent=[]; self.visited={}; self.explore_at=-100.; self.escape_recharge=False
    def target_height(self,t):
        if t.get('kind')=='mech':return self.cfg['mech']['height']*(1+self.cfg['cubes']['size_per_cube']*t.get('cubes',0))*.52
        if t.get('kind')=='npc':return self.cfg['npc']['height']*.55
        return self.cfg['crates']['height']*.55
    def safe(self,p,zone,margin=8):return distance(p,zone['center']) < max(0,zone['radius']-margin)
    def loot_cost(self,p,obj,enemies,me):
        # Legs and torso are independent. Price travel time and contention, rather
        # than blindly chasing the Euclidean-nearest object behind a wall.
        q=obj['pos']; d=distance(p,q); dz=abs(p[2]-q[2]); st=me['stats']
        cost=d+1.8*dz
        if d>12 and dz<5 and not self.map.ray((p[0],p[1],p[2]+1.2),(q[0],q[1],q[2]+1.2)):
            cost+=min(30.,8.+.2*d)
        if q[2]>p[2]+5 and me['energy']<25:cost+=45.
        # Prefer pickups we can reach first; don't run into a stronger opponent
        # merely for a single cube. Near-at-hand resources remain attractive.
        if d>8:
            for e in enemies[:5]:
                ed=distance(q,e['pos'])
                if ed<25 and ed+7<d and abs(q[2]-e['pos'][2])<8:
                    cost+=max(0., min(35.,(d-ed)*.65))
        return cost
    def retreat_pressure(self,exposed,p,me,t):
        # Low health does not imply a safe repair window. A close, armed pursuer
        # can reset the regeneration clock; keep fighting until cover is reached.
        for e in exposed:
            d=distance(p,e['pos'])
            if d<35 or t-self.last_damage<2.5 or (d<65 and e.get('hp',1e9)<180):return True
            if d<80:
                vx,vy=e.get('vel',(0.,0.,0.))[:2]; dx,dy=norm(p[0]-e['pos'][0],p[1]-e['pos'][1])
                if vx*dx+vy*dy>3.5 and e.get('weapons') and abs(delta(bearing(e['pos'],p),e.get('aim',[0,0])[0]))<.65:return True
        return False
    def fight_cover_value(self,p,future,me,target,threats):
        # Prefer a firing lane to the selected target and solid cover from other
        # opponents. Evaluate at the predicted ground/roof height, not at a
        # fictional point below terrain. Bounded to three nearby threats.
        eye=me['stats']['eye_height']; z=max(future[2],self.map.ground(*future[:2])); start=(future[0],future[1],z+eye)
        value=0.
        if target is not None and target.get('kind')=='mech':
            tp=target['pos']; end=(tp[0],tp[1],tp[2]+self.target_height(target))
            if self.map.ray(start,end): value+=4.5
            elif target.get('hp',1400)<350: value-=5.
        for e in threats[:3]:
            if target is not None and e['id']==target['id']:continue
            if distance(p,e['pos'])>95:continue
            ep=e['pos']; end=(ep[0],ep[1],ep[2]+self.target_height(e))
            if not self.map.ray(start,end):value+=8.
            else:value-=3.
        return value
    def update_motion(self,obs):
        now=obs['t']
        for e in obs['mechs']:
            ident=e['id']; v=e.get('vel',(0.,0.,0.)); pos=e['pos']; old=self.motion.get(ident)
            ax=ay=0.
            if old and .045<now-old[0]<.4 and distance(pos,old[3])<12:
                dt=now-old[0]; ax=(v[0]-old[1][0])/dt; ay=(v[1]-old[1][1])/dt
                mag=hypot(ax,ay); scale=min(1.,30/max(1.,mag)); ax=ax*scale*.55+old[2][0]*.30; ay=ay*scale*.55+old[2][1]*.30
            self.motion[ident]=(now,tuple(v),(ax,ay),tuple(pos))
        for ident,entry in list(self.motion.items()):
            if now-entry[0]>6:self.motion.pop(ident,None)
    def predict_target(self,target,fut):
        pos=target['pos'];v=target.get('vel',(0.,0.,0.)); hist=self.motion.get(target['id']); ax,ay=hist[2] if hist else (0.,0.)
        # Extrapolate observed acceleration briefly, then taper to constant velocity.
        horizon=min(fut,.28); extra=horizon*(fut-.5*horizon); extra=min(extra,5/max(1.,hypot(ax,ay))); dx=v[0]*fut+ax*extra;dy=v[1]*fut+ay*extra
        # Clamp acceleration contribution; avoid leading through sharp reversals.
        mx=pos[0]+dx;my=pos[1]+dy
        if fut>.12 and self.map.top(mx,my)>pos[2]+max(2.,v[2]*min(fut,.3)+1.2):
            mx=pos[0]+v[0]*min(fut,.12);my=pos[1]+v[1]*min(fut,.12)
        # Vertical velocity matters on rooftop jumps; bound the horizon and
        # never predict a target below the terrain it will encounter.
        zt=min(fut,.6); mz=pos[2]+v[2]*zt
        if abs(v[2])>2:
            mz=max(self.map.ground(mx,my),mz-.5*self.cfg['mech']['gravity']*zt*zt if v[2]<0 else mz)
        return mx,my,mz
    def intercept(self,p,me,t,w):
        k=w['kind']; st=w['stats']; ts=me['stats']; pos=t['pos']; v=t.get('vel',(0,0,0)); ht=self.target_height(t); muzzle=ts['height']+.5 if k=='mortar' else ts['muzzle_height']; origin=(p[0],p[1],p[2]+muzzle)
        delay=.5/max(1.,self.cfg['match']['tick_hz']); speed=st.get('speed',1e8); gravity=st.get('gravity',0.) if k=='mortar' else 0.
        if self.variant=='combat' and k in ('gun','mortar') and w.get('cooldown',0.)<=.12:delay=max(delay,w.get('cooldown',0.))
        flight=max(0.,(distance(p,pos)-ts['radius']-.5)/speed)
        for _ in range(6 if gravity else 3):
            fut=flight+delay; tx,ty,tz=self.predict_target(t,fut);tz+=ht
            if gravity:tz+=.5*gravity*flight*flight
            elif k in ('gun','laser'):
                # Aim at a reachable portion of the cylinder rather than rejecting
                # a close target merely because its midpoint exceeds pitch limits.
                horizontal=hypot(tx-origin[0],ty-origin[1]); bottom=tz-ht; top=bottom+ht/({'mech':.52,'npc':.55}.get(t.get('kind'),.55))
                low=max(bottom+.12,origin[2]+horizontal*math.tan(ts['min_pitch']+.002))
                high=min(top-.12,origin[2]+horizontal*math.tan(ts['max_pitch']-.002))
                if low<=high:tz=clip(tz,low,high)
            dx=tx-origin[0];dy=ty-origin[1];dz=tz-origin[2]; dist=sqrt(dx*dx+dy*dy+dz*dz); flight=clip((dist-ts['radius']-.5)/speed,0.,5.)
        yaw=atan2(dy,dx);pitch=atan2(dz,hypot(dx,dy)); r=st.get('range',speed*speed/max(gravity,1.))
        good=dist<=r*.98 and ts['min_pitch']<=pitch<=ts['max_pitch']
        if k=='mortar':
            good=good and distance(p,pos)>max(14,ts['radius']+st['splash_radius']+5) and flight<3.5
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
    def remembered_loot(self,obs):
        # Pickups and cubes vanish from observations as the torso turns. Retain
        # short-lived sightings, and retire them once we reach their location.
        p=obs['self']['pos']; t=obs['t']; live={}
        for key in ('pickups','cubes'):
            for obj in obs[key]:live[obj['id']]=obj;self.loot_seen[obj['id']]=(t,obj)
        for ident,(seen,obj) in list(self.loot_seen.items()):
            if ident in live:continue
            d=distance(p,obj['pos']); dz=abs(p[2]-obj['pos'][2]); iscube=ident<8000
            gone=t-seen>(18 if iscube else 45) or (d<7 and dz<5)
            # A successful take/failed take due to a gone object is definitive.
            gone=gone or any(e.get('id')==ident and (e['type']=='took' or e['type']=='take_failed' and e.get('reason')=='gone') for e in obs['events'])
            if gone:del self.loot_seen[ident]
        return [obj for _,obj in self.loot_seen.values() if obj['id']>=8000],[obj for _,obj in self.loot_seen.values() if obj['id']<8000]
    def duel_value(self,me,target,d):
        # Expected damage over two seconds, including magazine, charge, and
        # available energy. Two weapons can fire together, but Share an aim.
        def budget(kind,st,ready=0.,ammo=None,energy=None,charge=0.):
            reach=st.get('range',st.get('speed',72)**2/max(1.,st.get('gravity',22)))
            if d>reach or ready>=2.:return 0.
            accuracy={'gun':.83 if d<45 else .65 if d<100 else .42,'mortar':.48 if d<85 else .28,'laser':.80,'lightning':.96}.get(kind,.5)
            if kind=='mortar' and d<15:accuracy*=.2
            if kind=='laser':
                ready+=max(0.,st['charge']-charge)
                if ready>=2.:return 0.
            cycle=st.get('cooldown',1.)+(st.get('charge',0.) if kind=='laser' else 0.)
            shots=1.+max(0.,(2.-ready)/max(.1,cycle)-.5)
            if ammo is not None:shots=min(shots,ammo)
            if kind=='lightning' and energy is not None:shots=min(shots,max(0.,energy-12)/max(.1,st['energy']))
            return st.get('damage',0.)*shots*accuracy
        own=[]
        for w in me['weapons']:
            if not w:continue
            k=w['kind']; ready=max(w.get('cooldown',0.),w.get('reload',0.))
            ammo=w.get('ammo') if k=='gun' else None
            if k=='gun' and w.get('reload',0)>0:ammo=w['stats']['mag']
            v=budget(k,w['stats'],ready,ammo,me['energy'],w.get('charge',0.))
            if k=='laser' and 'mortar' in target.get('weapons',[]):v*=1+w['stats'].get('cookoff',0.)
            own.append(v)
        incoming=[]
        for k in target.get('weapons',[]):
            if k not in self.cfg['weapons']:continue
            v=budget(k,self.cfg['weapons'][k])
            if k=='laser' and any(w and w['kind']=='mortar' for w in me['weapons']):v*=1+self.cfg['weapons'][k].get('cookoff',0.)
            incoming.append(v)
        def combined(values):
            v=sorted(values,reverse=True)
            return v[0]+.5*sum(v[1:]) if v else 0.
        scale=self.cfg['cubes'];cap=scale['stat_cap'];mult=scale['damage_per_cube']
        dealt=combined(own)*(1+mult*min(cap,me['cubes']))
        taken=combined(incoming)*(1+mult*min(cap,target.get('cubes',0)))*(1-me['stats'].get('armor',0.))
        # Apply the public rear-armor rules to the current observed poses.
        # This is a snapshot, not a guarantee the enemy will keep facing away.
        base=self.cfg['mech']; rear=base['rear_mult']; half_arc=math.radians(base['front_arc_deg']*.5)
        if abs(delta(bearing(target['pos'],me['pos']),target.get('aim',[0,0])[0]))>half_arc:dealt*=rear
        if abs(delta(bearing(me['pos'],target['pos']),me['aim'][0]))>math.radians(me['stats'].get('front_arc_deg',base['front_arc_deg'])*.5):taken*=me['stats'].get('rear_mult',rear)
        return clip(dealt/max(100.,target.get('hp',1400))-taken/max(100.,me['hp']),-1.,1.)

    def swept_risks(self,candidates,projectiles,p,me,speed):
        # Split the acceleration path into 0.1 s segments. Find the closest
        # horizontal approach on each segment, then check its vertical height.
        # No external simulation or future observations are used.
        if not projectiles:return [0.]*len(candidates)
        st=me['stats']; vx0,vy0=me['vel'][:2]; accel=st['ground_accel'] if me['grounded'] else st['air_accel']; gravity=self.cfg['weapons']['mortar']['gravity']; splash=self.cfg['weapons']['mortar']['splash_radius']; out=[]
        times=(0.,.1,.2,.3,.4,.5,.6,.7,.8)
        for dx,dy in candidates:
            vx,vy=dx*speed,dy*speed; ax,ay=vx-vx0,vy-vy0; turn=hypot(ax,ay)/max(.1,accel); path=[]
            for t in times:
                lag=(t*(1-.5*t/turn) if t<turn else .5*turn) if turn>1e-8 else 0.
                path.append((vx*t-ax*lag,vy*t-ay*lag))
            risk=0.
            for q,v,k in projectiles:
                rx,ry=q[0]-p[0],q[1]-p[1]; radius=st['radius']+(splash if k=='mortar' else 1.4)+3.; hit=0.
                for i,t in enumerate(times[:-1]):
                    x=rx+v[0]*t-path[i][0];y=ry+v[1]*t-path[i][1]
                    ux=v[0]*.1-(path[i+1][0]-path[i][0]);uy=v[1]*.1-(path[i+1][1]-path[i][1]); den=ux*ux+uy*uy
                    f=clip(-(x*ux+y*uy)/den,0.,1.) if den>1e-12 else 0.
                    d2=(x+ux*f)**2+(y+uy*f)**2
                    if d2>=radius*radius:continue
                    tt=t+.1*f; z=q[2]+v[2]*tt-(.5*gravity*tt*tt if k=='mortar' else 0.)-(p[2]+st['height']*.5)
                    if abs(z)>st['height']*.65+3:continue
                    hit=max(hit,(radius-sqrt(d2))*4.)
                risk+=hit
            out.append(risk)
        return out

    def objective_viable(self,p,q,me,zone,t,wait=0.,lands_in=0.):
        # Reject objectives that become unsafe before arrival and capture. The
        # next circle is guaranteed inside the current one by the protocol.
        if zone['radius']<25:return self.safe(q,zone,4)
        d=distance(p,q);speed=max(1.,me['stats']['walk_speed']*.8)
        arrival=t+max(d/speed,lands_in)+wait
        if arrival<=zone['shrink_start']:return True
        f=clip((arrival-max(t,zone['shrink_start']))/max(.1,zone['shrink_end']-max(t,zone['shrink_start'])),0.,1.)
        center=tuple(a+(b-a)*f for a,b in zip(zone['center'],zone['next_center']))
        radius=zone['radius']+(zone['next_radius']-zone['radius'])*f
        return distance(q,center)<max(0.,radius-5.)

    def drop_value(self,p,me,drop,enemies,zone,t):
        q=drop['pos']; st=me['stats']; distance_to=distance(p,q); hp=me['hp']/max(1.,me['max_hp']); lands=max(0.,drop.get('lands_in',0.)); hold=drop.get('holder')==me['id']
        capture=max(.1,drop.get('capture_s',4.)-(drop.get('progress',0.) if hold else 0.))
        travel=distance_to/max(1.,st['walk_speed']*.82)
        if distance_to>12 and not self.map.ray((p[0],p[1],p[2]+1.2),(q[0],q[1],q[2]+1.2)):travel*=1.3
        if not self.safe(q,zone,4) or not self.objective_viable(p,q,me,zone,t,capture,lands):return None
        if lands>travel+6:return None # avoid standing around long before the drop lands
        for e in enemies:
            ed=distance(e['pos'],q)
            if ed<drop['radius']+4 and e.get('hp',1400)>me['hp']*.55:return None
            if ed<40 and ed+10<distance_to and e.get('hp',1400)>me['hp']*.8:return None
        if drop.get('holder') not in (None,me['id']) and lands<=0 and capture< travel+drop.get('progress',0.):return None
        # Healing + three cubes + upgrade opportunity versus travel time.
        value=30*(1-hp)+17*(me['cubes']<self.cfg['cubes']['stat_cap'])+7*(1-me['energy']/100.)+9
        return value-max(travel,lands)-capture+ (15 if hold else 0.)

    def explore_goal(self,p,me,zone,t):
        # Online coverage map, no privileged spawn positions. Scout unvisited
        # walkable ground with a broad view, rather than orbiting old locations.
        best=None;bestscore=-1e9;heading=me['aim'][0]
        for i,(dx,dy) in enumerate(DIR):
            for length in (65.,125.):
                q=(p[0]+dx*length,p[1]+dy*length)
                if not self.safe(q,zone,24) or not self.objective_viable(p,q,me,zone,t):continue
                top,ground,clear=self.map.surface(*q)
                if clear<me['stats']['radius']+2 or top-ground>2:continue
                key=(int(q[0]//45),int(q[1]//45));seen=self.visited.get(key,-1000.)
                novelty=clip((t-seen)/90.,0.,1.)
                direct=self.map.ray((p[0],p[1],p[2]+1.2),(q[0],q[1],ground+1.2))
                score=30*novelty+min(12.,clear*.35)+(12 if direct else -5)-length*.065+4*(dx*cos(heading)+dy*sin(heading))
                if score>bestscore:bestscore=score;best=q
        return best

    def opportunity_bonus(self,p,me,target,enemies,obs):
        # Bounded third-party preference; never displace emergency attacker priority.
        d=distance(p,target['pos'])
        if d>85 or me['hp']<me['max_hp']*.65:return 0.
        if target['id']==self.last_attacker and obs['t']-self.last_damage<3:return 0.
        rivals=0
        for e in enemies[:8]:
            if e['id']==target['id'] or not e.get('weapons'):continue
            if distance(e['pos'],target['pos'])<75 and abs(delta(bearing(e['pos'],target['pos']),e.get('aim',[0,0])[0]))<.28 and abs(delta(bearing(e['pos'],p),e.get('aim',[0,0])[0]))>.45:rivals+=1
        weak=clip(1-target.get('hp',1400)/max(1,target.get('max_hp',1400)),0,1)
        return min(16.,rivals*8.*weak) if self.duel_value(me,target,d)>-.12 else 0.

    def combat_opportunity(self,me,target,d):
        # Score a short usable damage window using live weapons, not nominal DPS.
        angle=abs(delta(bearing(me['pos'],target['pos']),me['aim'][0])); turn=angle/max(.1,me['stats']['turn_rate'])
        health=max(1.,target.get('hp',1400)); values=[]
        rear=abs(delta(bearing(target['pos'],me['pos']),target.get('aim',[0.,0.])[0]))>math.radians(self.cfg['mech']['front_arc_deg']*.5)
        for w in me['weapons']:
            if not w:continue
            k=w['kind'];st=w['stats']; reach=st.get('range',st.get('speed',72)**2/max(1.,st.get('gravity',22)))
            if d>reach*.98 or k=='mortar' and d<15:continue
            wait=max(turn,w.get('cooldown',0.),w.get('reload',0.)); cycle=max(.1,st['cooldown']); accuracy=1.
            if k=='gun':
                accuracy=clip(1.-d/320,.25,.95)
                if w.get('ammo',0)<=0:wait=max(wait,st['reload'])
            elif k=='laser':wait+=max(0.,st['charge']-w.get('charge',0.));cycle+=st['charge'];accuracy=.83
            elif k=='mortar':accuracy=.45 if d<90 else .25
            if wait>=1.8:continue
            shots=1+int((1.8-wait)/cycle)
            if k=='gun':shots=min(shots,w.get('ammo',0) if w.get('reload',0)<=0 else st['mag'])
            if k=='lightning':shots=min(shots,max(0,int((me['energy']-7)/max(.1,st['energy']))))
            damage=st['damage']*shots*accuracy
            if k=='laser' and 'mortar' in target.get('weapons',[]):damage*=1+st.get('cookoff',0.)
            values.append(damage)
        values.sort(reverse=True); damage=(values[0]+.6*sum(values[1:])) if values else 0.
        damage*=1+self.cfg['cubes']['damage_per_cube']*min(me['cubes'],self.cfg['cubes']['stat_cap'])
        if rear:damage*=self.cfg['mech']['rear_mult']
        return clip(28*damage/health,0.,36.)-min(14.,turn*11)+ (8 if rear and damage>0 else 0.)

    def choose_target(self,p,me,obs,enemies,npcs,loot):
        eye=(p[0],p[1],p[2]+me['stats']['muzzle_height']); cand=[]; nearby_enemy=any(distance(p,e['pos'])<40 for e in enemies)
        reach=max((w['stats'].get('range',w['stats'].get('speed',72)**2/max(1.,w['stats'].get('gravity',22))) for w in me['weapons'] if w),default=0.)
        for t in enemies+npcs+obs.get('crates',[]):
            d=distance(p,t['pos']); kind=t.get('kind','crate'); hp=t.get('hp',1000); h=self.target_height(t)
            if d>reach*.99:continue
            line=self.map.ray(eye,(t['pos'][0],t['pos'][1],t['pos'][2]+h))
            if not line and (kind!='mech' or d>110 or not any(w and w['kind']=='mortar' for w in me['weapons'])):continue
            if kind=='mech': score=108-d*.65+(1-hp/max(1,t.get('max_hp',1400)))*58-(0 if line else 105)-min(16,t.get('cubes',0)*1.6)
            elif kind=='npc': score=78-d*.85+(1-hp/max(1,t.get('max_hp',350)))*27
            else:score=74-d*.80+(1-hp/300)*23
            if t['id']==self.target_id:
                score+=12
                if line and any(w and w['kind']=='laser' and w.get('charge',0)>.12 for w in me['weapons']):score+=36
            if kind=='mech' and line and d<45 and any(w and w['kind']=='lightning' for w in me['weapons']):score+=22
            if kind=='mech' and line and d<55 and hp<280:score+=22
            if kind=='mech':
                # Finish weakened foes; focus the active attacker when exposed.
                score+=max(0,360-hp)*.12
                if t['id']==self.last_attacker and obs['t']-self.last_damage<3:score+=24
                if line and abs(delta(bearing(p,t['pos']),me['aim'][0]))<.35:score+=8
                if 'mortar' in t.get('weapons',[]) and any(w and w['kind']=='laser' for w in me['weapons']):score+=12
                if 'laser' in t.get('weapons',[]) and d<45 and any(w and w['kind']=='lightning' for w in me['weapons']):score+=12
            if kind=='mech' and line and d<70:score+=12
            if self.profile=='adaptive' and kind=='mech' and line:
                recent=t['id']==self.last_attacker and obs['t']-self.last_damage<3.0
                aiming=bool(t.get('weapons')) and abs(delta(bearing(t['pos'],p),t.get('aim',[0.,0.])[0]))<.35
                if recent:score+=125
                elif d<90 and aiming:score+=38
            if kind=='mech' and hp>me['hp']*.9 and d>35 and me['cubes']<6:score-=35
            if kind=='mech' and line and t.get('charging'):score+=10 if d<45 and any(w and w['kind']=='lightning' for w in me['weapons']) else 0
            if kind!='mech' and loot:score-=15
            if kind!='mech' and me['hp']<me['max_hp']*.6:score-=65
            if kind!='mech' and me['cubes']<10 and d<90:score+=45 if kind=='crate' else 34
            if kind!='mech' and nearby_enemy:score-=75
            if kind=='crate' and me['cubes']<10 and not nearby_enemy:score+=28
            # A crate can fill an empty weapon slot. Favor it over drones only
            # while healthy and outside immediate enemy pressure.
            if kind == 'crate' and None in me['weapons'] and not nearby_enemy and line and d <= 65 and me['hp'] >= .75 * me['max_hp']:
                score += 36 * self.cfg['loot']['crate_weapon_chance']
            if kind=='mech' and hp<220 and line:score+=42
            if self.profile=='adaptive' and kind=='mech' and line and hp<160 and d<55:score+=18
            if kind=='mech' and not line:score-=45
            if kind=='mech' and line:
                if self.profile=='aggressive':score+=22 if d<95 else 4
                elif self.profile=='survivor' and d>45 and hp>me['hp']*.65:score-=24
                elif self.profile=='adaptive' and d<85 and hp<me['hp']*.7:score+=18
            elif kind!='mech' and not nearby_enemy and me['cubes']<self.cfg['cubes']['stat_cap']:
                score+=self.policy['farm']
            # Reduce aim cycling toward targets beyond the usable weapon envelope.
            if kind=='mech' and not any(w and d<=w['stats'].get('range',w['stats'].get('speed',72)**2/max(1,w['stats'].get('gravity',22)))*.98 for w in me['weapons']):continue
            if kind=='mech' and me['hp']<me['max_hp']*.36:score-=25
            if self.profile=='adaptive' and kind=='mech' and line:
                score+=12*self.duel_value(me,t,d)
                score+=self.opportunity_bonus(p,me,t,enemies,obs)
                if self.variant=='combat':score+=self.combat_opportunity(me,t,d)
            cand.append((score,t,line))
        self.target_candidates=sorted(cand,key=lambda it:it[0],reverse=True)
        if not self.target_candidates:return None,False
        _,t,line=self.target_candidates[0];return t,line
    def act(self,obs):
        p=obs['self']['pos']; me=obs['self']; t=obs['t']; z=obs['zone']; stats=me['stats']; hp=me['hp']/max(1,me['max_hp']); energy=me['energy']; weapons=me['weapons']; kinds=[w['kind'] if w else None for w in weapons]; dt=clip(t-self.last_t,0,.3); self.last_t=t
        if self.last_pos is not None:
            if distance(p,self.last_pos)<.22 and hypot(*self.last_move)>.5 and me['grounded']:self.stuck+=dt
            else:self.stuck=max(0.,self.stuck-dt*.75)
        self.last_pos=p[:]
        for e in obs['events']:
            if e['type']=='damaged' and e.get('weapon')!='zone':
                self.last_damage=t;self.last_bearing=e.get('bearing');self.last_attacker=e.get('by');self.damage_recent.append((t,e.get('amount',0.)))
            if e['type']=='damaged' and e.get('weapon')=='zone':self.last_damage=t;self.last_attacker=None
            if e['type']=='hit':self.last_attack=t
        if self.last_hp is not None and me['hp']<self.last_hp-.5 and not me['in_zone']:self.last_damage=t
        self.last_hp=me['hp']; self.update_motion(obs)
        self.damage_recent=[(when,amt) for when,amt in self.damage_recent if t-when<1.8]
        burst=sum(amt for _,amt in self.damage_recent)/max(1.,me['max_hp'])
        self.visited[(int(p[0]//45),int(p[1]//45))]=t
        enemies=sorted((e for e in obs['mechs'] if e['kind']=='mech'),key=lambda e:distance(p,e['pos'])); npcs=[e for e in obs['mechs'] if e['kind']=='npc']; close=[e for e in enemies if distance(p,e['pos'])<125]; near=close[0] if close else None; nd=distance(p,near['pos']) if near else 999.; danger=len([e for e in close if distance(p,e['pos'])<85]); recovering=hp<.56 and (danger>=1 or t-self.last_damage<5) and (nd>18 or danger>=2); recovering=recovering or (hp<.32 and danger>=1)
        # Hysteresis: after disengaging, stay out of combat until repair has actually worked.
        # Adapt retreat to pressure and the ability to finish a duel.
        policy=self.policy; retreat=policy['retreat']; recovery_goal=policy['heal']
        if self.profile=='adaptive':
            retreat=clip(retreat+(.10 if danger>=2 else 0.)-(.09 if near and near.get('hp',1400)<me['hp']*.45 and danger==1 else 0.),.46,.76)
        if self.profile=='adaptive' and burst>.20 and hp<.72 and danger>=1 and (danger>=2 or not near or near.get('hp',1400)>me['hp']*.65):retreat=max(retreat,.73)
        if hp<retreat and (danger>=1 or t-self.last_damage<6) or hp<min(.50,retreat):
            if not self.recovering:self.recovery_since=t
            self.recovering=True
        if (hp<policy['quiet'] and nd>95 and t-self.last_damage>2.5 and t-self.last_attack>2.5 and not any(distance(p,e['pos'])<70 for e in npcs)):
            self.recovering=True
        if hp>recovery_goal or (z['radius']<30 and hp>.35):self.recovering=False
        recovering=self.recovering and z['radius']>14
        zone_margin=z['radius']-distance(p,z['center']); emergency_zone=zone_margin<12 or not me['in_zone']
        # Distinguish a dangerous visible/remembered mech from one behind a building.
        eye=(p[0],p[1],p[2]+stats['eye_height'])
        exposed=[e for e in close if self.map.ray(eye,(e['pos'][0],e['pos'][1],e['pos'][2]+self.target_height(e)))]
        # Return fire while fleeing under active pressure until actual cover is available.
        pressure=self.retreat_pressure(exposed,p,me,t)
        # A drone can reset the regeneration clock, too. Do not wait
        # indefinitely under its fire when there is no higher-priority mech.
        # Limit this to visible, nearby drones to avoid interrupting safe repairs.
        drone_threats=[e for e in npcs if nd>70 and distance(p,e['pos'])< (65 if e['id']==self.last_attacker and t-self.last_damage<5 else 44) and self.map.ray(eye,(e['pos'][0],e['pos'][1],e['pos'][2]+self.target_height(e)))] if recovering else []
        drone= min(drone_threats,key=lambda e: (e.get('hp',350),distance(p,e['pos']))) if drone_threats else None
        threatened_now=pressure or nd<30
        result={'tick':obs['tick'],'fire':[False,False]}
        if obs.get('offer'):
            ranks={'nanites':100,'armor':94,'plating':88,'servos':86,'gun_mag':96,'laser_damage':87,'mortar_reload':79,'gun_damage':78,'gun_rate':75,'laser_charge':77,'reactor':80,'jets':78,'capacitor':66,'lightning_efficiency':85,'lightning_range':85,'gyros':48,'gun_velocity':50,'mortar_velocity':46,'mortar_splash':59,'sensors':35,'laser_pierce':25,'lightning_chain':30}
            if me['cubes']>=6:ranks['armor']=99
            if self.profile=='aggressive':ranks.update(gun_mag=110,gun_damage=95,gun_rate=97,lightning_range=102,lightning_efficiency=100)
            elif self.profile=='survivor':ranks.update(nanites=120,armor=110,plating=103,servos=99,reactor=92,jets=91)
            if 'lightning' in kinds and 'laser' not in kinds:ranks['lightning_range']=91;ranks['lightning_efficiency']=90
            if 'laser' in kinds:ranks['laser_charge']=88
            result['pick']=max(range(len(obs['offer']['choices'])),key=lambda i:ranks.get(obs['offer']['choices'][i]['id'],0))
        # Prioritize an appropriate second weapon; keep the gun for consistent DPS.
        pref={'gun':0,'lightning':3,'mortar':2,'laser':4}
        if self.profile=='aggressive':
            pref['lightning']=5;pref['laser']=4
        elif self.profile=='adaptive' and near and nd<55 and energy>55 and kinds[1] is None:
            pref['lightning']=5
        # Lightning gives immediate damage and counters nearby lasers; retain an
        # existing laser rather than repeatedly swapping under pressure.
        if kinds[1]=='mortar' and near and nd<40 and 'laser' in near.get('weapons',[]) and hp>.65:
            pref['lightning']=5
        if kinds[1] is None and near and nd<48 and energy>40:
            pref['lightning']=5
        if self.profile=='adaptive' and near and nd<45 and energy>50 and danger>=2 and kinds[1]!='laser':
            pref['lightning']=5
        loot=[]
        remembered_pickups,remembered_cubes=self.remembered_loot(obs)
        visible_pickups={x['id'] for x in obs['pickups']}
        for x in sorted(remembered_pickups,key=lambda x:(distance(p,x['pos'])-(2 if kinds[1] is None and pref.get(x['kind'],0)>=5 else 0),x['id'])):
            k=x['kind']; d=distance(p,x['pos']); dz=abs(p[2]-x['pos'][2]); old=kinds[1]; want=k not in kinds and k!='gun' and (old is None or pref.get(k,0)>pref.get(old,0)) and not (old=='laser' and weapons[1].get('charge',0)>0)
            if want and x['id'] in visible_pickups and d<=self.cfg['loot']['pickup_radius'] and dz<=4:
                result['take']=x['id'];
                if old is not None:result['drop']=1
                break
            if want and d<155 and dz<36 and self.safe(x['pos'],z) and self.objective_viable(p,x['pos'],me,z,t):loot.append((self.loot_cost(p,x,close,me)-(42+policy['loot'] if old is None else 10),x))
        for x in sorted(remembered_cubes,key=lambda c:distance(p,c['pos']))[:40]:
            d=distance(p,x['pos']);dz=abs(p[2]-x['pos'][2]);
            if d<170 and dz<36 and self.safe(x['pos'],z) and self.objective_viable(p,x['pos'],me,z,t):
                cap=self.cfg['cubes']['stat_cap']; thresholds=self.cfg['cubes']['upgrade_thresholds']; next_upgrade=min((n for n in thresholds if n>me['cubes']),default=100000)
                extra=0 if me['cubes']<cap else 12 if next_upgrade-me['cubes']<=2 else 35
                cluster=sum(1 for c in remembered_cubes[:160] if c['id']!=x['id'] and distance(c['pos'],x['pos'])<9 and abs(c['pos'][2]-x['pos'][2])<4)
                # Beyond the stat cap, a lone cube grows our hitbox. Travel for it
                # only when an upgrade is close, or the cube is already nearby.
                if me['cubes'] >= cap and next_upgrade - me['cubes'] > 2 and cluster == 0 and d > 12:
                    continue
                route_bonus=0.
                if self.profile=='adaptive' and me['cubes']<cap and nd>75 and d<100:
                    route_bonus=min(9.,cluster*3.) if self.map.ray((p[0],p[1],p[2]+1.2),(x['pos'][0],x['pos'][1],x['pos'][2]+1.2)) else 0.
                econ_bonus=0.
                if self.variant=='economy' and nd>55 and not recovering and me['cubes']<cap:
                    # Prefer a nearby multi-cube group, not a distant speculative route.
                    econ_bonus=min(24.,cluster*8.)+ (8. if d<14 else 0.)
                loot.append((self.loot_cost(p,x,close,me)-route_bonus-69-policy['loot']+extra-min(30,cluster*10)-(12 if self.profile=='adaptive' and me['cubes']<4 and nd>90 and d<95 and hp>.75 else 0)-econ_bonus,x))
        loot.sort(key=lambda q:q[0]); lootgoal=loot[0][1] if loot else None
        target, line=self.choose_target(p,me,obs,enemies,npcs,lootgoal)
        if recovering and pressure and (target is None or target.get('kind')!='mech'):
            target,line=self.choose_target(p,me,{**obs,'crates':[]},exposed,[],None)
            if target and target.get('kind')!='mech':target,line=None,False
        if recovering and (not threatened_now or target is None or target.get('kind')!='mech'):
            target=None;line=False
            if drone is not None and me['hp']>100 and not emergency_zone:
                target=drone;line=True
        drone_defense=bool(recovering and target is not None and target.get('kind')=='npc' and drone is not None)
        # Avoid wasting a shot on a target tracked through solid cover.
        if target and not line and 'mortar' not in kinds and distance(p,target['pos'])>30:target=None
        self.target_id=target['id'] if target else None
        # Aim and select weapons using live stats. Laser is charged only when a real target is available.
        aim=list(me['aim']); active=None; solutions={}
        if target:
            for i,w in enumerate(weapons):
                if w:solutions[i]=self.intercept(p,me,target,w)
            good=[i for i,s in solutions.items() if s[2]]
            # Bounded fallback: do not spend the entire engagement tracking a target
            # whose predicted position is unreachable by either weapon.
            if not good and not recovering:
                for _,candidate,cl in getattr(self,'target_candidates',())[1:4]:
                    if candidate['id']==target['id']:continue
                    trial={i:self.intercept(p,me,candidate,w) for i,w in enumerate(weapons) if w}
                    usable=[i for i,s in trial.items() if s[2]]
                    if usable:
                        target,line,solutions,good=candidate,cl,trial,usable
                        self.target_id=target['id'];break
            if good:
                def priority(i):
                    w=weapons[i]; k=w['kind']; s=solutions[i]; ready=w['cooldown']<=.11; val=0
                    if k=='gun':
                        val=30 if ready and not w.get('reload',0) and w.get('ammo',1)>0 else (4 if w.get('ammo',1)>0 and not w.get('reload',0) else 0)
                        # An uncharged laser halves movement. During a close
                        # multi-enemy fight, maintain gun pressure and mobility.
                        if val==30 and self.profile=='adaptive' and target.get('kind')=='mech' and danger>=2 and nd<42 and hp<.82 and any(q and q['kind']=='laser' and q.get('charge',0)<=0 for q in weapons):val=76
                        if val>=30 and self.profile=='adaptive' and s[3] and target.get('hp',1e9)<=w['stats']['damage']*(1+self.cfg['cubes']['damage_per_cube']*min(me['cubes'],self.cfg['cubes']['stat_cap']))*.85:val=100
                    elif k=='laser':val=(85 if w.get('charge',0)>0 else 56) if ready and (not recovering or pressure and self.profile!='survivor' and nd>28 and hp>.28) else 1
                    elif k=='mortar':val=(70 if target.get('kind')=='mech' and s[4]<95 else 45) if ready else 3
                    elif k=='lightning':val=(65 if self.profile=='aggressive' else 54) if ready and energy>=w['stats'].get('energy',3)+policy['reserve'] else 1
                    return val
                def combined_priority(i):
                    base=priority(i); a=solutions[i]
                    for j in good:
                        if j==i:continue
                        w=weapons[j]; q=solutions[j]; k=w['kind']; st=w['stats']
                        if w['cooldown']>.11 or not q[3] or (k=='gun' and (w.get('reload',0)>0 or w.get('ammo',1)<=0)):continue
                        compatible=(abs(delta(q[0],a[0]))<=math.radians(st['cone_deg']*.42) if k=='lightning' else abs(delta(q[0],a[0]))<q[5]+.018 and abs(q[1]-a[1])<q[6]+.018)
                        if compatible and (k!='lightning' or energy>=st.get('energy',3)+max(12,policy['reserve']+(8 if emergency_zone or recovering else 0))):
                            base+=priority(j)*.70
                    return base
                active=max(good,key=combined_priority)
                if weapons[active]['kind']=='lightning':
                    for gi in good:
                        if weapons[gi]['kind']=='gun' and priority(gi)>=30 and abs(delta(solutions[gi][0],solutions[active][0]))<math.radians(weapons[active]['stats']['cone_deg']*.36):active=gi;break
                aim=list(solutions[active][:2])
                for i,s in solutions.items():
                    w=weapons[i]; k=w['kind']; st=w['stats']; charge=w.get('charge',0); same=(abs(delta(s[0],aim[0]))<=math.radians(st['cone_deg']*.42) if k=='lightning' else abs(delta(s[0],aim[0]))<s[5]+.018 and abs(s[1]-aim[1])<s[6]+.018)
                    if k=='laser':
                        if charge>0:
                            fraction=st['min_frac']+(1-st['min_frac'])*min(1.,charge/max(.01,st['charge']))
                            damage=st['damage']*fraction*(1+self.cfg['cubes']['damage_per_cube']*min(me['cubes'],self.cfg['cubes']['stat_cap']))
                            if 'mortar' in target.get('weapons',[]):damage*=1+st.get('cookoff',0.)
                            lethal=charge>=st.get('min_charge',.15) and damage*.82>=target.get('hp',1e9)
                            result['fire'][i]=bool((not recovering or pressure and self.profile!='survivor' and nd>28 and hp>.28) and s[2] and ((charge<st['charge']-.06 and not lethal) or not (s[3] and same)) and charge<st['charge']+.6)
                        else:result['fire'][i]=bool(s[2] and same and w['cooldown']<=.08 and (not recovering or pressure and self.profile!='survivor' and nd>28 and hp>.28) and (active==i) and abs(delta(s[0],me['aim'][0]))<.65 and abs(s[1]-me['aim'][1])<.55)
                    elif s[2] and same and s[3] and (not recovering or target.get('kind')=='mech' and pressure or drone_defense):
                        result['fire'][i]=bool(k!='lightning' or energy>=st.get('energy',3)+policy['reserve']+(8 if self.profile=='adaptive' and (recovering or emergency_zone) and target.get('hp',1000)>st.get('damage',0) else 0))
                        if k == 'lightning' and not result['fire'][i] and w['cooldown'] == 0 and energy >= st['energy'] and target.get('charging') and not emergency_zone:
                            # Spend the reserve to short a visible laser aimed at us.
                            # A closer object could take the arc instead.
                            target_distance = distance(p, target['pos'])
                            if abs(delta(bearing(target['pos'], p), target['aim'][0])) < .25 and not any(
                                obj['id'] != target['id'] and distance(p, obj['pos']) <= target_distance
                                for obj in enemies + npcs + obs['crates']
                            ):
                                result['fire'][i] = True
            else:aim=[bearing(p,target['pos']),0.]
        if recovering and not pressure and not drone_defense:result['fire']=[False,False]
        if emergency_zone:
            for i,w in enumerate(weapons):
                if w and w['kind']=='laser':result['fire'][i]=False
        for i,w in enumerate(weapons):
            if w and w['kind']=='gun' and (w.get('ammo',1)<=0 or w.get('reload',0)>0):
                result['fire'][i]=False
                if w.get('ammo',1)<=0 and w.get('reload',0)<=0:result['reload']=True
        for i,w in enumerate(weapons):
            if w and w['kind']=='gun' and not result['fire'][i] and w.get('reload',0)<=0 and w.get('ammo',12)<w['stats']['mag']*.72 and (not target or (recovering and not pressure and not drone_defense) or not line or (active==1-i and weapons[1-i] and weapons[1-i]['kind']=='laser' and w.get('ammo',0)<=2)):result['reload']=True
        # Goal selection. Stay in a healthy part of the zone without blindly rushing its center.
        curd=distance(p,z['center']); nextd=distance(p,z['next_center']); next_r=z['next_radius']; current_margin=z['radius']-curd; next_margin=next_r-nextd
        travel_time=max(0.,nextd-max(0,next_r-18))/max(1.,stats['walk_speed']*.72)
        urgency=(current_margin<18 or t+travel_time+10>z['shrink_end'] and next_margin<10 or next_r<30 and next_margin<6)
        goal=None; mode='patrol'; hold=False; altitude=None; capture_radius=8.
        # Uncontested drops are powerful healing and upgrade opportunities.
        drops=[]
        for d in obs['drops']:
            dd=distance(p,d['pos']); threatened=any(distance(e['pos'],d['pos'])<32 for e in close)
            finishing=(d.get('holder')==me['id'] and d.get('lands_in',0)<=0 and dd<d['radius']*.85 and d.get('progress',0)>=max(0,d.get('capture_s',4)-.9) and hp>.25 and not any(distance(e['pos'],d['pos'])<d['radius']+3 for e in close))
            if d.get('lands_in',0)<=max(0,dd/stats['walk_speed'])+3 and self.safe(d['pos'],z,4) and (not threatened or finishing) and dd<240 and (finishing or self.objective_viable(p,d['pos'],me,z,t,d.get('capture_s',4),d.get('lands_in',0))):
                drops.append((dd-(1-hp)*120-(180 if finishing else 0)-(35 if d.get('holder')==me['id'] else 0),d))
        if self.variant=='economy' and not urgency and not recovering:
            viable=[(self.drop_value(p,me,d,enemies,z,t),d) for d in obs['drops']]
            viable=[(v,d) for v,d in viable if v is not None and v>8.]
            if viable:
                d=max(viable,key=lambda pair:pair[0])[1]
                # Treat an attractive drop as a high-value objective even before
                # landing, but never extend the baseline's capture ring.
                drops=[(-1000.,d)]+drops
        if drops and (hp<.98 or me['cubes']<15 or self.variant=='economy' and energy<55) and not urgency:
            d=min(drops,key=lambda q:q[0])[1];goal=d['pos'];mode='drop';altitude=goal[2];capture_radius=d['radius'];hold=distance(p,goal)<d['radius']*.58 and abs(p[2]-goal[2])<4
        if goal is None and urgency:
            if hp<.78 and target and target.get('kind')!='mech':result['fire']=[False,False]
            ux,uy=norm(p[0]-z['next_center'][0],p[1]-z['next_center'][1]); r=max(0,next_r-min(42,max(12,next_r*.35)));goal=(z['next_center'][0]+ux*r,z['next_center'][1]+uy*r);mode='zone'
        if goal is None and recovering:
            # If hidden and safe, stop spending energy and let HP restore rather than wandering into combat.
            if drone_defense and current_margin>25:
                # Keep the proven recovery policy, but avoid standing still under drone fire.
                ex,ey=norm(drone['pos'][0]-p[0],drone['pos'][1]-p[1])
                sign=1 if (int(t/3.8)+self.slot)%2 else -1
                radial=clip((distance(p,drone['pos'])-29)/14,-1.,1.)
                sx,sy=norm(ex*radial-ey*sign*.74,ey*radial+ex*sign*.74)
                goal=(p[0]+sx*20,p[1]+sy*20);mode='farm';hold=False
            elif not exposed and drone is None and nd>30 and t-self.last_damage>1.8 and current_margin>25:
                self.roof_goal=None
                nearby_cubes=[c for c in remembered_cubes if distance(p,c['pos'])<13 and abs(p[2]-c['pos'][2])<3 and self.safe(c['pos'],z,12)]
                if nearby_cubes and me['cubes']<self.cfg['cubes']['stat_cap']:
                    goal=min(nearby_cubes,key=lambda c:distance(p,c['pos']))['pos'];mode='loot';altitude=goal[2]
                else:goal=p;mode='repair';hold=True
            elif not exposed and self.last_bearing is not None and t-self.last_damage<2.0:ex,ey=-cos(self.last_bearing),-sin(self.last_bearing)
            elif near:ex,ey=norm(p[0]-near['pos'][0],p[1]-near['pos'][1])
            elif drone is not None:ex,ey=norm(p[0]-drone['pos'][0],p[1]-drone['pos'][1])
            elif self.last_bearing is not None:ex,ey=-cos(self.last_bearing),-sin(self.last_bearing)
            else:ex,ey=norm(z['next_center'][0]-p[0],z['next_center'][1]-p[1])
            if goal is None:
                goal=(p[0]+ex*70,p[1]+ey*70);mode='escape'
                # Low roofs can break ground pursuit. Only commit if there is enough energy and the roof is safe.
                if self.roof_goal and t<self.roof_until and energy>18 and self.safe(self.roof_goal,z,15) and p[2]<self.roof_goal[2]-1 and distance(p,self.roof_goal)<42:
                    goal=self.roof_goal;altitude=goal[2]
                elif energy>55 and nd<85 and stats['jet_accel']>stats['gravity'] and current_margin>32:
                    options=[]
                    for dx,dy in DIR[::2]:
                        for d in (12.,22.,32.):
                            x,y=p[0]+dx*d,p[1]+dy*d;top,ground,_=self.map.surface(x,y);rise=top-p[2]
                            if not 7<rise<min(32., (energy-22)/max(1.,stats['jet_drain'])*stats['max_rise_speed']*.8):continue
                            if top-ground<5 or not self.safe((x,y),z,20):continue
                            if any(abs(self.map.top(x+ox,y+oy)-top)>1.5 for ox,oy in ((3,0),(-3,0),(0,3),(0,-3))):continue
                            value=(dx*ex+dy*ey)*12+rise*.5-d*.22
                            if near and distance((x,y),near['pos'])<nd-5:continue
                            options.append((value,(x,y,top)))
                    if options:
                        roof=max(options,key=lambda item:item[0])[1];goal=roof;altitude=roof[2];mode='escape';self.roof_goal=roof;self.roof_until=t+4.0
        # Maintain a useful firing position during a winnable duel.
        combat_commit=bool(self.profile=='adaptive' and target and target.get('kind')=='mech' and line and
            ((distance(p,target['pos'])<65 and target.get('hp',1e9)<min(350,me['hp']*.55)) or
             (target['id']==self.last_attacker and t-self.last_damage<2.2 and distance(p,target['pos'])<95)))
        if goal is None and lootgoal and (not combat_commit or distance(p,lootgoal['pos'])<9) and (nd>25 or lootgoal['id']>=5000 and lootgoal['id']<8000) and (not exposed or distance(p,lootgoal['pos'])< (35 if me['cubes']<6 and hp>.65 else 25)):
            goal=lootgoal['pos'];mode='loot';altitude=goal[2]
        if goal is None and target:
            d=distance(p,target['pos']);kind=target.get('kind','crate')
            if kind=='mech':
                ideal=33 if 'lightning' in kinds and 'laser' not in kinds else 78 if 'mortar' in kinds else 75 if 'laser' in kinds else 47
                if self.profile=='adaptive' and 'lightning' in kinds and 'laser' not in kinds and 'mortar' not in kinds:
                    arc=next(w for w in weapons if w and w['kind']=='lightning')
                    ideal=clip(arc['stats']['range']*.72,24.,52.)
                if self.profile=='aggressive':ideal=max(20,ideal-14)
                elif self.profile=='survivor':ideal+=20
                elif me['cubes']>=5 and hp>.75 and danger<=1 and target.get('hp',1400)<me['hp']*.8:ideal=max(24,ideal-12)
                if danger>=2:ideal+=18
                if self.profile=='adaptive' and obs.get('alive',16)<=5 and danger>=2 and hp<.85:ideal+=8
                if 'lightning' in kinds and 'laser' in target.get('weapons',[]) and danger<=1 and hp>.62:ideal=32
                if 'laser' in kinds and 'mortar' in target.get('weapons',[]):ideal=85
                if self.variant=='combat' and danger<=1 and hp>.72 and line:
                    if target.get('hp',1400)<me['hp']*.65 or self.duel_value(me,target,d)>.20:
                        if 'laser' not in kinds and 'mortar' not in kinds:ideal=max(23.,ideal-10.)
                        elif 'laser' in kinds:ideal=max(55.,ideal-8.)
                if hp<.72:ideal+=10
                if self.profile=='adaptive' and line and danger<=1:
                    advantage=self.duel_value(me,target,d)
                    if advantage<-.15 and target.get('hp',1400)>350:ideal+=10
                    elif advantage>.35 and hp>.75:ideal=max(24,ideal-6)
                # Close isolated weak targets; strafe rather than run straight at them.
                if target.get('hp',1400)<300 and danger<=1 and hp>.70:ideal=min(ideal,36)
                ex,ey=norm(target['pos'][0]-p[0],target['pos'][1]-p[1]); sign=1 if (int(t/2.7)+self.slot)%2 else -1; radial=clip((d-ideal)/16,-1,1) if line else 1
                sx,sy=norm(ex*radial-ey*sign*.7*policy['strafe'],ey*radial+ex*sign*.7*policy['strafe']);goal=(p[0]+sx*35,p[1]+sy*35);mode='fight'
            else:
                ideal=29 if kind=='npc' else 13; ex,ey=norm(target['pos'][0]-p[0],target['pos'][1]-p[1]);goal=(target['pos'][0]-ex*ideal,target['pos'][1]-ey*ideal);mode='farm';hold=d<ideal+3 and line and nd>75;altitude=target['pos'][2]
                if kind=='npc' and line and d<ideal+9:
                    # A drone has slow projectiles. Farm while orbiting rather
                    # than standing in its aim; retain the firing distance.
                    sign=1 if (int(t/3.8)+self.slot)%2 else -1
                    radial=clip((d-ideal)/13,-1.,1.)
                    sx,sy=norm(ex*radial-ey*sign*.74,ey*radial+ex*sign*.74)
                    goal=(p[0]+sx*22,p[1]+sy*22);hold=False;altitude=None
        if goal is None:
            if self.profile=='adaptive' and me['cubes']<10 and nd>85 and not recovering and (self.goal_memory is None or distance(p,self.goal_memory)<18 or t-self.explore_at>10 or not self.safe(self.goal_memory,z,18)):
                self.goal_memory=self.explore_goal(p,me,z,t);self.explore_at=t
            if self.goal_memory is None or distance(p,self.goal_memory)<15 or not self.safe(self.goal_memory,z,18) or (t+12>z['shrink_end'] and distance(self.goal_memory,z['next_center'])>max(0,next_r-8)):
                angle=.8+self.slot*2.399+int(t/14)*1.7; r=min(max(0,next_r*.78),220); self.goal_memory=(z['next_center'][0]+cos(angle)*r,z['next_center'][1]+sin(angle)*r)
            goal=self.goal_memory;mode='patrol'
        if not recovering or mode!='escape':self.roof_goal=None
        # Boundary correction on any non-zone goal.
        gx,gy=goal[:2]; center=z['center']; ux,uy=norm(gx-center[0],gy-center[1]); gd=distance(goal,center); rr=max(0,z['radius']-12)
        if gd>rr:gx=center[0]+ux*rr;gy=center[1]+uy*rr
        b=self.map.bounds;gx=clip(gx,b['minX']+8,b['maxX']-8);gy=clip(gy,b['minY']+8,b['maxY']-8);goal=(gx,gy)
        if mode=='zone' and distance(p,goal)<(.2 if z['radius']<6 else 2.0):hold=True
        if z['radius']<18 and (distance(p,z['center'])>max(.3,z['radius']-3) or z['next_radius']<3):
            gx,gy=z['center'];goal=(gx,gy);mode='zone';hold=distance(p,goal)<.18 and hypot(*me['vel'][:2])<.35
        # Ground route when needed; local steering handles combat, roofs, and moving threats.
        direct=norm(gx-p[0],gy-p[1]); route_needed=mode in ('zone','loot','drop','patrol','farm','escape') and not hold and distance(p,goal)>13 and (altitude is None or altitude<p[2]+5)
        if route_needed and self.map.ray((p[0],p[1],p[2]+1.1),(gx,gy,self.map.ground(gx,gy)+1.1)) and distance(p,goal)<75:route_needed=False
        if route_needed:
            if self.route_goal is None or distance(goal,self.route_goal)>20 or t-self.route_time>2.0 or not self.path or self.stuck>.6 and t-self.route_time>.5:
                self.route_goal=goal;self.route_time=t;self.path=self.map.route(p,goal)
            # Don't discard a waypoint around a corner just because it is
            # nearby. Skip ahead only when the next segment is unobstructed.
            while self.path and distance(p,self.path[0])<3.5:self.path.pop(0)
            if len(self.path)>1:
                for i in range(min(3,len(self.path)-1),0,-1):
                    q=self.path[i]
                    if distance(p,q)<30 and self.map.ray((p[0],p[1],p[2]+.65),(q[0],q[1],self.map.ground(*q)+.65)) and self.map.clearance(*q)>=stats['radius']+.5:
                        del self.path[:i];break
            if self.path:direct=norm(self.path[0][0]-p[0],self.path[0][1]-p[1])
        else:self.path=[];self.route_goal=None
        # Pick local steering direction. Estimate impact danger from incoming projectiles.
        projectiles=[]
        for obj in obs['projectiles']:
            q=obj['pos'];v=obj['vel']; dd=distance(p,q)
            if dd<165 and (obj['kind']=='mortar' or (q[0]-p[0])*v[0]+(q[1]-p[1])*v[1]<dd*stats['boost_speed']):projectiles.append((dd,q,v,obj['kind']))
        projectiles=[(q,v,k) for _,q,v,k in sorted(projectiles,key=lambda item:item[0])[:32]]
        candidates=[direct]+DIR
        if self.variant=='movement' and projectiles and not hold:
            candidates=candidates+[(cos((i+.5)*pi/8),sin((i+.5)*pi/8)) for i in range(16)]
        if hold:candidates=[(0.,0.)]+candidates
        best=None;bestscore=-1e12
        # Plan with the speed that the movement mode is likely to use. For ground
        # boosts, score both speeds; never choose a boost that turns a clear dodge
        # into a predicted collision. Air boosting changes altitude, not walk speed.
        gravity=self.cfg['weapons']['mortar']['gravity']; splash=self.cfg['weapons']['mortar']['splash_radius']
        gd=distance(p,goal)
        ground_boost=me['grounded'] and not hold and (
            mode in ('escape','zone') and gd>12 and (energy>32 or self.boosting and energy>12)
            or mode=='loot' and gd>20 and (energy>(55 if nd>75 and me['cubes']<10 else 70) or self.boosting and energy>32)
            or mode=='drop' and gd>18 and (energy>45 or self.boosting and energy>25)
            or mode=='farm' and not recovering and nd>90 and gd>35 and energy>(78 if self.profile=='adaptive' and me['cubes']<4 and hp>.8 else 85) and me['cubes']<6
            or mode=='fight' and danger and ((nd<27 and energy>52 and 'lightning' not in kinds) or (self.profile=='aggressive' and nd>35 and nd<85 and energy>62 and 'lightning' in kinds and hp>.65))
            or mode=='patrol' and energy>90 and gd>70)
        if mode!='escape' or emergency_zone:self.escape_recharge=False
        elif energy<24:self.escape_recharge=True
        elif energy>=55:self.escape_recharge=False
        if self.escape_recharge and mode=='escape' and nd>28:ground_boost=False
        charge_mult=stats.get('charge_move_mult',.5) if any(w and w['kind']=='laser' and result['fire'][i] for i,w in enumerate(weapons)) else 1.
        if self.variant=='movement' and projectiles:
            # Cap the expensive fine search; closest threats first. For the
            # remainder use the existing native/Python risk estimate.
            primary=projectiles[:12]; rest=projectiles[12:]
            def risk_at(speed):
                fine=self.swept_risks(candidates,primary,p,me,speed)
                coarse=self.map.projectile_risks(candidates,rest,p,me,gravity,splash,speed)
                return [a+b for a,b in zip(fine,coarse)]
            risks=risk_at(stats['walk_speed']*charge_mult)
            fast_risks=risk_at(stats['boost_speed']*charge_mult) if ground_boost else risks
        else:
            risks=self.map.projectile_risks(candidates,projectiles,p,me,gravity,splash,stats['walk_speed']*charge_mult)
            fast_risks=self.map.projectile_risks(candidates,projectiles,p,me,gravity,splash,stats['boost_speed']*charge_mult) if ground_boost and projectiles else risks
        best_boost=False
        reloading_cover=(mode=='fight' and not recovering and near is not None and
            not any(result['fire']) and not any(w and (w['kind']!='gun' and w['cooldown']<.4 or w['kind']=='gun' and w.get('reload',0)<.35 and w.get('ammo',1)>0) for w in weapons))
        for (dx,dy),risk,fast_risk in zip(candidates,risks,fast_risks):
            score=0 if hold else 14*(dx*direct[0]+dy*direct[1]); score+=2*(dx*self.last_move[0]+dy*self.last_move[1]);
            if hold:score-=hypot(dx,dy)*(20 if mode=='repair' else 12)
            if hold and mode=='drop' and hypot(dx,dy)>.01:
                # Do not accidentally leave a nearly captured healing drop.
                q=(p[0]+dx*stats['walk_speed']*.35,p[1]+dy*stats['walk_speed']*.35)
                if distance(q,goal)>capture_radius-.5:score-=18
            if self.profile=='adaptive' and mode in ('escape','fight') and not hold and near and burst>.08:
                for e in exposed[:3]:
                    if distance(p,e['pos'])>90:continue
                    eyaw=e['aim'][0]; side=abs(dx*sin(eyaw)-dy*cos(eyaw))
                    if abs(delta(bearing(e['pos'],p),eyaw))<.35:score+=side*(5. if e.get('charging') else 2.)
            if mode=='fight' and near and near.get('charging'):
                ang=bearing(near['pos'],p); eyaw=near.get('aim',[0,0])[0]
                if abs(delta(ang,eyaw))<.35:score+=8*abs(dx*sin(eyaw)-dy*cos(eyaw))
            # terrain/wall checks at multiple distances; allow moving along roof edges.
            for dd,pen in (((3,65),(7,34),(13,15)) if hypot(dx,dy)>.01 else ()):
                xx=p[0]+dx*dd;yy=p[1]+dy*dd; top,ground,clearance=self.map.surface(xx,yy)
                if top>p[2]+stats['step_up']+.55:score-=pen
                elif clearance<stats['radius']+1 and p[2]<ground+3:score-=pen*.35
            xx=p[0]+dx*12; yy=p[1]+dy*12; future=(xx,yy,p[2]); zm=z['radius']-distance(future,z['center']);
            if zm<12:score-=max(0,12-zm)*(2.5 if urgency else 1.6)
            if t>=z['shrink_start'] and next_margin<25 and not hold:
                future_margin=next_r-distance(future,z['next_center']);score-=max(0,8-future_margin)*.24
            if self.profile=='adaptive' and not hold and mode in ('fight','escape','loot','zone') and hypot(dx,dy)>.01:
                # A soft second horizon, never overriding immediate collision checks.
                q=(p[0]+dx*24,p[1]+dy*24)
                score-=min(8.,max(0.,self.map.top(*q)-p[2]-stats['step_up']))
                score-=min(12.,max(0.,10-z['radius']+distance(q,z['center']))*.5)
                if mode=='escape':
                    for e in close[:2]:
                        ev=e.get('vel',(0.,0.,0.)); ep=(e['pos'][0]+ev[0],e['pos'][1]+ev[1])
                        score+=clip((distance(q,ep)-distance(p,ep))*.12,-3.,3.)
            if near:
                # Anticipate future exposure to a foe's current aim and favour
                # lateral movement, especially against a charging beam. Use
                # only the legal observed pose, not future opponent actions.
                if not hold and mode in ('fight','escape','loot'):
                    for e in exposed[:3]:
                        ep=e['pos']; ed=distance(p,ep)
                        if ed>95:continue
                        eyaw=e['aim'][0]; angular=abs(delta(bearing(ep,future),eyaw))
                        if abs(delta(bearing(ep,p),eyaw))<.30:
                            score+=min(.35,angular)*(15 if e.get('charging') else 5)
                for e in close[:5]:
                    old=distance(p,e['pos']); new=distance(future,e['pos']);
                    if self.profile=='adaptive' and not hold and (recovering or danger>=2) and old<85:
                        ev=e.get('vel',(0.,0.,0.)); ep=(e['pos'][0]+ev[0]*.35,e['pos'][1]+ev[1]*.35); new=.65*new+.35*distance(future,ep)
                    if recovering and not hold:score+=(new-old)*(policy['escape'] if old<70 else .55)
                    elif old<20:score+=(new-old)*.85
                    elif mode=='fight' and danger>=2 and e['id']!=(target['id'] if target else -1) and old<85:
                        score+=(new-old)*.48
                        if new<35:score-=max(0.,35-new)*.28
                    if (recovering or reloading_cover) and not hold and old<100 and not self.map.ray((xx,yy,p[2]+stats['eye_height']),(e['pos'][0],e['pos'][1],e['pos'][2]+self.target_height(e))):score+=policy['cover'] if recovering else 9
            if self.profile=='adaptive' and mode=='fight' and danger>=2 and not hold and not recovering:
                score+=self.fight_cover_value(p,future,me,target,close)
                if obs.get('alive',16)<=5:
                    # Stay away from secondary threats during the final circle.
                    for e in exposed[:4]:
                        if target and e['id']==target['id']:continue
                        score+=clip((distance(future,e['pos'])-distance(p,e['pos']))*.15,-2.,2.)
            can_boost=ground_boost and hypot(dx,dy)>.25 and self.map.top(p[0]+dx*4,p[1]+dy*4)<p[2]+stats['step_up']+.55
            # Modest progress bonus for sprinting toward the objective; oncoming
            # projectiles can instead make a walking direction preferable.
            fast_bonus=max(0.,dx*direct[0]+dy*direct[1])*3.5
            use_boost=bool(can_boost and fast_risk*policy['risk']<=risk*policy['risk']+fast_bonus)
            score+=fast_bonus if use_boost else 0.
            score-=(fast_risk if use_boost else risk)*policy['risk']
            if score>bestscore:bestscore=score;best=(dx,dy);best_boost=use_boost
        move=best or direct; jump=False;boost=False
        if mode in ('zone','loot','drop') and not hold and distance(p,goal)<8 and self.stuck<.5 and not (self.variant=='movement' and projectiles and min(risks)>0. and z['radius']>=18):
            # Slow near a target. In the final tiny circle, directly control the
            # desired velocity to settle at the center instead of orbiting it.
            if mode=='zone' and z['radius']<18:
                speed=max(1.,stats['walk_speed']); vx=(gx-p[0])*2.2-me['vel'][0]*.25; vy=(gy-p[1])*2.2-me['vel'][1]*.25
                mag=max(speed,hypot(vx,vy)); move=(vx/mag,vy/mag)
            else:
                factor=clip(distance(p,goal)/7,.08,1.);move=(move[0]*factor,move[1]*factor)
        if self.stuck>.70 and not hold and energy>32:
            self.jet_until=t+1.8
            # Vertical escape if the selected route is obstructed and walking has failed.
            if me['grounded']:jump=True
            else:boost=True
            if self.stuck>2.4:self.stuck=.3;self.path=[]
        if t<self.jet_until and not me['grounded'] and energy>15 and not hold:boost=True
        if altitude is not None and altitude>p[2]+3 and distance(p,goal)<35 and energy>25 and not hold:
            jump=me['grounded'];boost=not me['grounded']
            if self.roof_goal is not None and mode=='escape' and not me['grounded']:
                # Ascend next to the edge; pushing into it is harmless, but don't wander away.
                move=direct
        if not me['grounded'] and not hold and hypot(*move)>.15 and stats['height']>0 and energy>19 and self.map.top(p[0]+move[0]*9,p[1]+move[1]*9)>p[2]+1.5:boost=True
        if me['grounded'] and not jump and best_boost:boost=True
        self.boosting=boost
        if not target:
            if recovering and exposed:aim=[bearing(p,exposed[0]['pos']),0.]
            elif recovering and self.last_bearing is not None and t-self.last_damage<6:aim=[self.last_bearing,0.]
            elif t-self.last_damage<3 and self.last_bearing is not None:aim=[self.last_bearing,0.]
            elif near:aim=[bearing(p,near['pos']),0.]
            elif not recovering and any(s.get('dist')=='near' and s.get('kind') in ('gun','laser_charge','lightning','mortar','boost') for s in obs.get('sounds',[])):
                sound=min((s for s in obs['sounds'] if s.get('dist')=='near' and s.get('kind') in ('gun','laser_charge','lightning','mortar','boost')),key=lambda s:s.get('age',0)); aim=[sound['bearing'],0.]
            else:
                yaw=atan2(move[1],move[0]) if hypot(*move)>.1 else me['aim'][0];aim=[yaw+(1.85 if mode=='patrol' and not near else .55)*sin(t*1.05+self.slot),-.05]
        if target and recovering and near and target.get('kind')!='mech' and not drone_defense:aim=[bearing(p,near['pos']),0.]
        result.update(move=list(move),boost=bool(boost),jump=bool(jump),aim=[float(delta(aim[0],0)),float(clip(aim[1],stats['min_pitch'],stats['max_pitch']))]);self.last_move=move;self.last_mode=mode
        return result

class Candidate(Bot):
    variant='combat'

if __name__=='__main__':mf.run(Candidate)
