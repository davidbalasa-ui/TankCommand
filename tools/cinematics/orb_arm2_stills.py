import sys; sys.path.insert(0,'/home/user/TankCommand/tools/cinematics')
import bpy, math, os
from mathutils import Vector
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
import orb_fighter as OF
sc=bpy.context.scene
sc.render.engine='CYCLES'; c=sc.cycles; c.samples=40; c.use_denoising=True; c.transparent_max_bounces=12
sc.render.resolution_x=1200; sc.render.resolution_y=750
sc.view_settings.view_transform='AgX'; sc.view_settings.look='AgX - Punchy'
w=bpy.data.worlds.new('W'); sc.world=w; w.use_nodes=True
w.node_tree.nodes['Background'].inputs['Color'].default_value=(0.006,0.007,0.012,1)
for nm,rot,e,col in [('Key',(55,0,35),3.5,(1,0.92,0.8)),('Rim',(110,0,200),2.5,(0.5,0.65,1.0))]:
    L=bpy.data.objects.new(nm,bpy.data.lights.new(nm,'SUN')); sc.collection.objects.link(L)
    L.rotation_euler=[math.radians(a) for a in rot]; L.data.energy=e; L.data.color=col
cam=bpy.data.objects.new('Cam',bpy.data.cameras.new('Cam')); sc.collection.objects.link(cam); sc.camera=cam
arm,root,legs=OF.orb_rig2('Orb')
N=OF.ARM_N
for L in legs: L['plume'].scale=(0.001,)*3
out='/mnt/project-files/cinematics/orb-fighter/arm-v2'; os.makedirs(out,exist_ok=True)
def shot(nm,pos,tgt,lens=35):
    cam.location=Vector(pos); cam.rotation_euler=(Vector(tgt)-Vector(pos)).to_track_quat('-Z','Y').to_euler(); cam.data.lens=lens
    sc.render.filepath=f'{out}/{nm}.png'; bpy.ops.render.render(write_still=True)
# 1: all straight (rest), 2: each arm in a different natural pose, 3: close on one arm in an S-bend
for L in legs: OF.pose_arm(arm,L,[(0,0)]*N)
shot('rest',(14,-24,10),(-3,0,0))
import random
rnd=random.Random(3)
for L in legs:
    kind=L['k']%4
    if kind==0: b=[(-14,0)]*N                                   # curl inward
    elif kind==1: b=[((12 if j<N//2 else -16),0) for j in range(N)]  # S-bend
    elif kind==2: b=[(-6-1.5*j,8*math.sin(j*0.6)) for j in range(N)]  # spiral reach
    else: b=[(4,-10+2*j) for j in range(N)]
    OF.pose_arm(arm,L,b)
shot('mixed',(14,-24,10),(-3,0,0))
shot('mixed_back',(-26,-12,9),(-4,0,0))
for L in legs: L['plume'].scale=(0.45,0.5,0.5)
shot('mixed_thrust',(14,-24,10),(-3,0,0))
for L in legs: L['plume'].scale=(0.001,)*3
OF.pose_arm(arm,legs[1],[((14 if j<N//2 else -18),3) for j in range(N)])
bpy.context.view_layer.update()
pb=arm.pose.bones[legs[1]['bones'][6]]
mid=arm.matrix_world@pb.head
shot('closeup',mid+Vector((3,-7,6)),mid,32)
