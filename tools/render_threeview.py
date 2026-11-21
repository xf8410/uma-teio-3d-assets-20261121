"""Headless Blender: orthographic front / side / back views of a GLB.

Usage:
  blender -b -noaudio --factory-startup --python tools/render_threeview.py -- \
      MODEL.glb YAW_DEG OUTDIR [WIDTH] [HEIGHT] [SAMPLES] [BASE_CLEAR]
"""
import sys
import os
import math
import json

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if not argv:
    raise SystemExit("need MODEL.glb")
glb = os.path.abspath(argv[0])
yaw = float(argv[1]) if len(argv) > 1 else 40.0
outdir = os.path.abspath(argv[2]) if len(argv) > 2 else os.path.abspath("out")
res_x = int(argv[3]) if len(argv) > 3 else 800
res_y = int(argv[4]) if len(argv) > 4 else 1160
samples = int(argv[5]) if len(argv) > 5 else 24
os.makedirs(outdir, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

bpy.ops.import_scene.gltf(filepath=glb)
meshes = [o for o in scene.objects if o.type == "MESH"]
if not meshes:
    raise SystemExit("no mesh imported")

deps = bpy.context.evaluated_depsgraph_get()
pts = []
tri = 0
for ob in meshes:
    ev = ob.evaluated_get(deps)
    me = ev.to_mesh()
    mw = ev.matrix_world
    me.calc_loop_triangles()
    tri += len(me.loop_triangles)
    for v in me.vertices:
        pts.append(mw @ v.co)
    ev.to_mesh_clear()

xs = [p.x for p in pts]
ys = [p.y for p in pts]
zs = [p.z for p in pts]
center = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2))
height = max(ys) - min(ys)

views = [("FRONT", yaw), ("SIDE", yaw + 90.0), ("BACK", yaw + 180.0)]
frames = []
for name, deg in views:
    a = math.radians(deg)
    fwd = Vector((math.sin(a), 0.0, math.cos(a)))
    up = Vector((0.0, 1.0, 0.0))
    right = fwd.cross(up).normalized()
    upv = right.cross(fwd).normalized()
    u_min = v_min = 1e9
    u_max = v_max = -1e9
    for p in pts:
        d = p - center
        uu = d.dot(right)
        vv = d.dot(upv)
        u_min = min(u_min, uu); u_max = max(u_max, uu)
        v_min = min(v_min, vv); v_max = max(v_max, vv)
    frames.append({"name": name, "deg": deg, "fwd": fwd, "right": right, "up": upv,
                   "u_min": u_min, "u_max": u_max, "v_min": v_min, "v_max": v_max})

max_half_w = max((fr["u_max"] - fr["u_min"]) / 2 for fr in frames)
g_v_min = min(fr["v_min"] for fr in frames)
g_v_max = max(fr["v_max"] for fr in frames)
span_v = g_v_max - g_v_min

cam_data = bpy.data.cameras.new("OrthoCam")
cam_data.type = "ORTHO"
cam = bpy.data.objects.new("OrthoCam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

world = bpy.data.worlds.new("W")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.86, 0.86, 0.88, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.85
scene.world = world


def add_light(name, kind, loc, energy, size=3.0):
    ld = bpy.data.lights.new(name, type=kind)
    ld.energy = energy
    if kind == "AREA":
        ld.size = size
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    ob.rotation_euler = (center - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(ob)
    return ob


add_light("Key", "AREA", (center.x - 2.2, center.y + 2.6, center.z + 2.4), 900, 4.0)
add_light("Fill", "AREA", (center.x + 2.6, center.y + 0.8, center.z + 0.6), 260, 5.0)
add_light("Rim", "AREA", (center.x + 0.4, center.y + 1.2, center.z - 2.6), 180, 4.0)

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = samples
scene.cycles.use_denoising = True
scene.render.resolution_x = res_x
scene.render.resolution_y = res_y
scene.render.resolution_percentage = 100
scene.render.film_transparent = False
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.view_settings.view_transform = "Standard"

aspect = res_x / res_y
cam_data.ortho_scale = max(span_v * 1.10, (max_half_w * 2 * 1.10) / aspect)

dist = max(height, 1.0) * 4.0
v_mid = (g_v_min + g_v_max) / 2
for fr in frames:
    cam.location = center - fr["fwd"] * dist
    cam.rotation_euler = fr["fwd"].to_track_quat("-Z", "Y").to_euler()
    frame_mid = (fr["v_min"] + fr["v_max"]) / 2
    cam.location = cam.location + fr["up"] * (frame_mid - v_mid)
    path = os.path.join(outdir, fr["name"].lower() + ".png")
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("rendered", fr["name"], path)

meta = {
    "model": os.path.basename(glb),
    "triangles": tri,
    "vertices": len(pts),
    "height_units": round(height, 5),
    "yaw_deg": yaw,
    "views": [{"name": f["name"], "deg": f["deg"]} for f in frames],
    "resolution": [res_x, res_y],
    "ortho_scale": round(cam_data.ortho_scale, 5),
    "engine": "cycles-cpu",
    "samples": samples,
}
with open(os.path.join(outdir, "meta.json"), "w", encoding="utf-8") as fh:
    json.dump(meta, fh, ensure_ascii=False, indent=2)
print("META", json.dumps(meta, ensure_ascii=False))
