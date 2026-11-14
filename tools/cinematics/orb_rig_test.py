import sys; sys.path.insert(0,'/home/user/TankCommand/tools/cinematics')
import bpy, math
from mathutils import Vector
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
import orb_fighter as OF
sc=bpy.context.scene
sc.render.engine='CYCLES'; c=sc.cycles; c.samples=12; c.use_denoising=True
sc.render.resolution_x=640; sc.render.resolution_y=400
w=bpy.data.worlds.new('W'); sc.world=w; w.use_nodes=True
w.node_tree.nodes['Background'].inputs['Color'].default_value=(0.006,0.007,0.012,1)
for nm,rot,e,col in [('Key',(55,0,35),3.5,(1,0.92,0.8)),('Rim',(110,0,200),2.5,(0.5,0.65,1.0))]:
    L=bpy.data.objects.new(nm,bpy.data.lights.new(nm,'SUN')); sc.collection.objects.link(L)
    L.rotation_euler=[math.radians(a) for a in rot]; L.data.energy=e; L.data.color=col
cam=bpy.data.objects.new('Cam',bpy.data.cameras.new('Cam')); sc.collection.objects.link(cam); sc.camera=cam
cam.data.lens=32
root,legs=OF.orb_rig('Orb')
OF.animate_orb(root,legs,[(1,'sprint'),(30,'grab'),(60,'turn'),(90,'sprint')],1,110)
pos=Vector((12,-20,8)); tgt=Vector((0,0,0))
cam.location=pos; cam.rotation_euler=(tgt-pos).to_track_quat('-Z','Y').to_euler()
for f in map(int,sys.argv[sys.argv.index('--')+1].split(',')):
    sc.frame_set(f); sc.render.filepath=f'/home/user/scratch/orbrig/f{f:03d}.png'; bpy.ops.render.render(write_still=True)
