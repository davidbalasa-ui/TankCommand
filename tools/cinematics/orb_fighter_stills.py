import sys; sys.path.insert(0,'/home/user/TankCommand/tools/cinematics')
import bpy, math
from mathutils import Vector
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
import orb_fighter
sc=bpy.context.scene
sc.render.engine='CYCLES'; c=sc.cycles; c.samples=32; c.use_denoising=True
sc.render.resolution_x=1200; sc.render.resolution_y=750
w=bpy.data.worlds.new('W'); sc.world=w; w.use_nodes=True
bg=w.node_tree.nodes['Background']; bg.inputs['Color'].default_value=(0.006,0.007,0.012,1)
for nm,rot,e,col in [('Key',(55,0,35),3.5,(1,0.92,0.8)),('Rim',(110,0,200),2.5,(0.5,0.65,1.0))]:
    L=bpy.data.objects.new(nm,bpy.data.lights.new(nm,'SUN')); sc.collection.objects.link(L)
    L.rotation_euler=[math.radians(a) for a in rot]; L.data.energy=e; L.data.color=col
cam=bpy.data.objects.new('Cam',bpy.data.cameras.new('Cam')); sc.collection.objects.link(cam); sc.camera=cam
cam.data.lens=40
variants=['C']
poses=sys.argv[1].split(',')
for v in variants:
    for p in poses:
        for o in list(bpy.data.objects):
            if o.type not in ('CAMERA','LIGHT'): bpy.data.objects.remove(o)
        ob=orb_fighter.orb_fighter('sprint' if p=='front' else p)
        tris=sum(len(x.data.polygons) for x in [ob]+list(ob.children) if x.type=='MESH')
        print('BUILT',v,p,tris)
        pos=Vector((9,-20,9)) if p not in('grab','front') else (Vector((19,-10,6)) if p=='grab' else Vector((16,-9,4)))
        cam.location=pos; tgt=Vector((-2,0,0)) if p not in('grab','front') else Vector((3,0,0))
        cam.rotation_euler=(tgt-pos).to_track_quat('-Z','Y').to_euler()
        sc.render.filepath=f'/home/user/scratch/orb/{p}.png'; bpy.ops.render.render(write_still=True)
