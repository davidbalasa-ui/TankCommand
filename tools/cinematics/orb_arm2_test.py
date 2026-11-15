"""Orb leg-motion test: the Orb swoops, swings and jinks along a path; camera rides alongside.
python orb_rig_test.py -- FRAMES(comma list or A-B) [OUTDIR]"""
import sys; sys.path.insert(0,'/home/user/TankCommand/tools/cinematics')
import bpy, math, os
from mathutils import Vector, Quaternion
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
import orb_fighter as OF
sc=bpy.context.scene
sc.render.engine='CYCLES'; c=sc.cycles; c.samples=8; c.use_denoising=True
c.transparent_max_bounces=12
sc.render.resolution_x=640; sc.render.resolution_y=360; sc.render.resolution_percentage=75
sc.view_settings.view_transform='AgX'; sc.view_settings.look='AgX - Punchy'
w=bpy.data.worlds.new('W'); sc.world=w; w.use_nodes=True
w.node_tree.nodes['Background'].inputs['Color'].default_value=(0.004,0.005,0.01,1)
for nm,rot,e,col in [('Key',(55,0,35),3.5,(1,0.92,0.8)),('Rim',(110,0,200),2.5,(0.5,0.65,1.0))]:
    L=bpy.data.objects.new(nm,bpy.data.lights.new(nm,'SUN')); sc.collection.objects.link(L)
    L.rotation_euler=[math.radians(a) for a in rot]; L.data.energy=e; L.data.color=col
arm,root,legs,teth=OF.orb_rig2('Orb',core='orb')
NF=168
# path: cruise, hard swing up and over (arc), three dodges, a grab, sprint off
def P(t):
    x=60*t
    y=14*math.sin(t*1.1)+ (5*math.copysign(1,math.sin(t*9)) if 3.6<t<4.6 else 0)
    z=10*math.sin(t*0.8+1)
    return Vector((x,y,z))
pos={}
for f in range(-6,NF+9):
    t=f/24; pos[f]=P(t)
# smooth the jinks a little (still snappy)
sm={f:(pos[f-1]+pos[f]*2+pos[f+1])/4 for f in range(-5,NF+8)}
root.rotation_mode='QUATERNION'
prev=None
for f in range(-1,NF+3):
    root.location=sm[f]; root.keyframe_insert('location',frame=f)
    d=(sm[f+2]-sm[f-2]).normalized()
    q=d.to_track_quat('X','Z')
    if prev is not None and q.dot(prev)<0: q=-q
    root.rotation_quaternion=q; root.keyframe_insert('rotation_quaternion',frame=f); prev=q
hold=Vector((OF.ORB_RC+2.5,0,0))
OF.animate_orb(root,legs,1,NF,grabs=[dict(f_reach=118,f_grab=128,f_tear=146,hold=hold,legs=[0,1,3,4,6])],seed=5,arm=arm,tethers=teth)
cam=bpy.data.objects.new('Cam',bpy.data.cameras.new('Cam')); sc.collection.objects.link(cam); sc.camera=cam
cam.data.lens=30
for f in range(1,NF+1):
    sc.frame_set(f); p=root.matrix_world.translation
    cp=p+Vector((-3,-27,8)); cam.location=cp
    cam.rotation_euler=(p+Vector((3,0,0))-cp).to_track_quat('-Z','Y').to_euler()
    cam.keyframe_insert('location',frame=f); cam.keyframe_insert('rotation_euler',frame=f)
a=sys.argv[sys.argv.index('--')+1]
fs=list(range(int(a.split('-')[0]),int(a.split('-')[1])+1)) if '-' in a else list(map(int,a.split(',')))
out=sys.argv[sys.argv.index('--')+2] if len(sys.argv)>sys.argv.index('--')+2 else '/home/user/scratch/orbarm2'
os.makedirs(out,exist_ok=True)
for f in fs:
    sc.frame_set(f); sc.render.filepath=f'{out}/f{f:03d}.png'; bpy.ops.render.render(write_still=True)
