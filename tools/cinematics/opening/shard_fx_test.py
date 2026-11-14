import sys; sys.path.insert(0,'/home/user/TankCommand/tools/cinematics/opening')
import bpy, math
from mathutils import Vector
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
import shard_hd, shard_fx
sc=bpy.context.scene
sc.render.engine='CYCLES'; c=sc.cycles; c.samples=int(sys.argv[2]) if len(sys.argv)>2 else 24; c.use_denoising=True
c.max_bounces=8; c.transmission_bounces=10; c.transparent_max_bounces=12; c.volume_bounces=1
sc.render.resolution_x=1600; sc.render.resolution_y=720
sc.view_settings.view_transform='AgX' if 'AgX' in [i.identifier for i in sc.view_settings.bl_rna.properties['view_transform'].enum_items] else 'Filmic'
sh=shard_hd.shard_hd('Shard',42.0)
bpy.ops.mesh.primitive_plane_add(size=2000, location=(0,0,4))
g=bpy.context.object; gm=bpy.data.materials.new('G'); gm.use_nodes=True
gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(0.12,0.09,0.08,1)
gm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=0.9; g.data.materials.append(gm)
w=bpy.data.worlds.new('W'); sc.world=w; w.use_nodes=True
bg=w.node_tree.nodes['Background']; bg.inputs['Color'].default_value=(0.012,0.01,0.025,1)
sun=bpy.data.objects.new('Sun',bpy.data.lights.new('Sun','SUN')); sc.collection.objects.link(sun)
sun.rotation_euler=(math.radians(78),0,math.radians(-40)); sun.data.energy=1.6; sun.data.color=(1.0,0.75,0.6)
# targets: dark tank-ish boxes
def box(at,s):
    bpy.ops.mesh.primitive_cube_add(size=1,location=at); b=bpy.context.object; b.scale=s
    m=bpy.data.materials.get('Tk') or bpy.data.materials.new('Tk'); m.use_nodes=True
    m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(0.05,0.06,0.07,1)
    m.node_tree.nodes['Principled BSDF'].inputs['Metallic'].default_value=0.7
    b.data.materials.append(m); return b
box((40,-30,5.2),(6,3.4,1.6)); box((-38,-26,5.2),(6,3.4,1.6)); box((30,-60,5.2),(6,3.4,1.6))
shard_fx.lightning((6,-4,30),(40,-30,6.2),seed=1)
shard_fx.lightning((-6,-3,26),(-38,-26,6.2),seed=2,width=0.45)
CH=shard_fx.charge((0,0,58),r=3.0)
BM=shard_fx.beam((0,0,60),(0,0,400),r=4.0)
shard_fx.crust((30,-60,4),7.0)
cam=bpy.data.objects.new('Cam',bpy.data.cameras.new('Cam')); sc.collection.objects.link(cam); sc.camera=cam
shots={'wide':((-60,-170,22),(0,-20,40),22),'bolt':((62,-52,10),(28,-22,10),28),'crust':((44,-76,10),(30,-60,7),30),
       'tip':((-22,-30,52),(0,0,58),30),'beam':((-30,-60,30),(0,0,75),24)}
only=sys.argv[1].split(',') if len(sys.argv)>1 and sys.argv[1] else list(shots)
for k in only:
    for o in CH: o.hide_render=(k not in ('tip',))
    for o in BM: o.hide_render=(k=='tip')
    p,t,lens=shots[k]; cam.location=p; cam.rotation_euler=(Vector(t)-Vector(p)).to_track_quat('-Z','Y').to_euler(); cam.data.lens=lens
    sc.render.filepath=f'/home/user/scratch/shardfx/{k}.png'; bpy.ops.render.render(write_still=True)
