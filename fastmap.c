/* Optional native acceleration. Uses only the public map cache and current query. */
#include <stdint.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>
#define MAXN 20000
#define MAXQ 20000
struct entry { double f,g; int n; };
static int less(struct entry a,struct entry b){return a.f<b.f || (a.f==b.f && (a.g<b.g || (a.g==b.g&&a.n<b.n)));}
int fast_ray(const int16_t *d,int nx,int ny,double mx,double my,double inv,double ax,double ay,double az,double bx,double by,double bz){
 double dx=bx-ax,dy=by-ay,dz=bz-az; int n=(int)(hypot(dx,dy)/3)+1;if(n<2)n=2;
 for(int i=1;i<n;i++){double f=(double)i/n;int ix=(int)((ax+dx*f-mx)*inv+.5),iy=(int)((ay+dy*f-my)*inv+.5); double top=(ix>=0&&ix<nx&&iy>=0&&iy<ny)?d[nx*ny+iy*nx+ix]*.01:1000.; if(top>az+dz*f+.25)return 0;}return 1;
}
static double h(int n,int w,int gx,int gy){return hypot(n%w-gx,n/w-gy);}
int fast_route(int w,int count,const int32_t *adj,const double *costs,int start,int goal,int *out){
 if(count>MAXN||start<0||goal<0||start>=count||goal>=count)return -1;
 double g[MAXN];int parent[MAXN];struct entry q[MAXQ];int size=1,steps=0,best=start,gx=goal%w,gy=goal/w; double bh=h(start,w,gx,gy);
 for(int i=0;i<count;i++){g[i]=1e9;parent[i]=-1;}g[start]=0;q[0]=(struct entry){bh,0,start};
 while(size&&steps<1800){struct entry a=q[0],last=q[--size];int j=0;
  while(j*2+1<size){int k=j*2+1;if(k+1<size&&less(q[k+1],q[k]))k++;if(!less(q[k],last))break;q[j]=q[k];j=k;}if(size)q[j]=last;
  if(a.g!=g[a.n])continue;
  steps++;double hh=h(a.n,w,gx,gy);if(hh<bh){best=a.n;bh=hh;}if(a.n==goal){best=goal;break;}
  for(int i=0;i<8;i++){int e=a.n*8+i,k=adj[e];if(k<0)break;double ng=a.g+costs[e*2]+costs[e*2+1];if(ng>=g[k])continue;g[k]=ng;parent[k]=a.n;if(size>=MAXQ)return -1;struct entry b={ng+1.12*h(k,w,gx,gy),ng,k};j=size++;while(j&&less(b,q[(j-1)/2])){q[j]=q[(j-1)/2];j=(j-1)/2;}q[j]=b;}
 }
 int n=0;while(best!=start&&parent[best]>=0){out[n++]=best;best=parent[best];if(n>=MAXN)return -1;}for(int i=0;i<n/2;i++){int a=out[i];out[i]=out[n-i-1];out[n-i-1]=a;}return n;
}
/* Evaluate the full candidate set in one call, avoiding Python's nested loops. */
void projectile_risk(const double *cand,int nc,const double *shots,int ns,double px,double py,double pz,double speed,double vx0,double vy0,double accel,double height,double radius,double gravity,double splash,double *out){
 for(int i=0;i<nc;i++){
  double vx=cand[2*i]*speed,vy=cand[2*i+1]*speed,dx=vx-vx0,dy=vy-vy0;
  double dv=sqrt(dx*dx+dy*dy),turn=accel>0?fmin(.8,dv/accel):.8,risk=0;
  for(int j=0;j<ns;j++){
   const double *s=shots+7*j; double rx=s[0]-px,ry=s[1]-py,rvx=s[3]-vx,rvy=s[4]-vy,den=rvx*rvx+rvy*rvy;
   double t=den>1?fmax(0,fmin(.8,-(rx*rvx+ry*rvy)/den)):0;
   if(t<.015)continue;
   /* Account for acceleration: the mech cannot change velocity instantly. */
   double lag=turn>1e-8?(t<turn?t*(1-.5*t/turn):.5*turn):0;
   double vertical=s[2]+s[5]*t-(pz+height*.5)-(s[6]>.5?.5*gravity*t*t:0);
   if(fabs(vertical)>height*.65+3)continue;
   double x=rx+rvx*t+dx*lag,y=ry+rvy*t+dy*lag;
   double r=radius+(s[6]>.5?splash:1.4)+3,miss2=x*x+y*y;
   if(miss2<r*r)risk+=(r-sqrt(miss2))*4;
  }
  out[i]=risk;
 }
}
