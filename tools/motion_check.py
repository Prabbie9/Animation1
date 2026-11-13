"""Frame-by-frame motion audit of scene.blend (no rendering).
blender -b scene.blend -P tools/motion_check.py
Checks: speeds/decelerations and stopping distances; wheel ground contact (float/sink) and
rolling without slip; vehicle-vehicle, vehicle-pedestrian, vehicle-pole/prop overlaps and
vehicles mounting the kerb; signal compliance at every stop-line crossing; camera sway
amplitude and frame-to-frame smoothness."""
import math, os, sys, bpy
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scenelib import config as C
from scenelib import signals as SIG

sc = bpy.context.scene
F = list(range(C.FRAME_START, C.FRAME_END + 1))
roots = {o.name.split('.')[0][:-5]: o for o in bpy.data.objects
         if o.name.split('.')[0].endswith('_root') and o.parent is None
         and o.users_collection and o.users_collection[0].name == 'Vehicles'}
peds = [o for o in bpy.data.objects if o.name.startswith('Ped_')]
posts = [o for o in bpy.data.objects if o.name.startswith(('SigPole', 'LampPole', 'XPole', 'Hydrant', 'Trash',
                                                          'Newsboxes'))]
problems = []


def obb(root):
    sx, sy, _ = root['size']
    m = root.matrix_world
    c = m.translation
    a = m.to_3x3() @ Vector((1, 0, 0)); b = m.to_3x3() @ Vector((0, 1, 0))
    return [c + a * (i * sx / 2) + b * (j * sy / 2) for i, j in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def sat_overlap(p, q):
    def axes(poly):
        return [Vector((-(poly[(i + 1) % 4] - poly[i]).y, (poly[(i + 1) % 4] - poly[i]).x)).normalized() for i in range(2)]
    for ax in axes(p) + axes(q):
        pa = [v.xy.dot(ax) for v in p]; qa = [v.xy.dot(ax) for v in q]
        if max(pa) < min(qa) or max(qa) < min(pa):
            return False
    return True


def on_sidewalk(x, y):
    hw, hs, r = C.AVE_HALF, C.CROSS_HALF, C.KERB_RADIUS
    x, y = abs(x), abs(y)
    if x <= hw or y <= hs:
        return False
    if x < hw + r and y < hs + r:
        return math.hypot(x - (hw + r), y - (hs + r)) <= r
    return True


track = {n: [] for n in roots}
wheel_err = {n: 0.0 for n in roots}
contact = {n: [1e9, -1e9] for n in roots}
cam_rot = []
prev_wheels = {}
for f in F:
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    for n, r in roots.items():
        track[n].append(r.matrix_world.translation.copy())
        # wheels
        for w in [c for c in r.children if '_wheel_' in c.name]:
            we = w.evaluated_get(dg)
            zs = [(we.matrix_world @ Vector(cn)).z for cn in we.bound_box]
            contact[n][0] = min(contact[n][0], min(zs)); contact[n][1] = max(contact[n][1], min(zs))
            key = (n, w.name)
            ang = w.rotation_euler.x
            rad = max(w.dimensions.y, w.dimensions.z) / 2
            if key in prev_wheels:
                pa, ppos = prev_wheels[key]
                ds = (r.matrix_world.translation - ppos).length
                wheel_err[n] = max(wheel_err[n], abs(abs(ang - pa) * rad - ds))
            prev_wheels[key] = (ang, r.matrix_world.translation.copy())
    # overlaps
    boxes = {n: obb(r) for n, r in roots.items()}
    names = sorted(boxes)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if sat_overlap(boxes[names[i]], boxes[names[j]]):
                problems.append(f'f{f}: vehicles {names[i]} and {names[j]} overlap')
        for c in boxes[names[i]]:
            if on_sidewalk(c.x, c.y):
                problems.append(f'f{f}: {names[i]} corner on the sidewalk at ({c.x:.2f},{c.y:.2f})')
                break
        for o in peds + posts:
            p = o.matrix_world.translation
            poly = boxes[names[i]]
            ctr = sum(poly, Vector()) / 4
            # point-in-OBB with 0.3 m margin
            a = (poly[1] - poly[0]); b = (poly[3] - poly[0])
            d = p - poly[0]
            u, v = d.xy.dot(a.xy) / a.length ** 2, d.xy.dot(b.xy) / b.length ** 2
            m_u, m_v = 0.3 / a.length, 0.3 / b.length
            if -m_u < u < 1 + m_u and -m_v < v < 1 + m_v:
                problems.append(f'f{f}: {names[i]} within 0.3 m of {o.name}')
    cam_rot.append(sc.camera.matrix_world.to_euler())

# kinematics
print('=== Kinematics (from evaluated positions) ===')
for n, pts in track.items():
    v = [(pts[i + 1] - pts[i]).length * C.FPS for i in range(len(pts) - 1)]
    a = [(v[i + 1] - v[i]) * C.FPS for i in range(len(v) - 1)]
    moved = (pts[-1] - pts[0]).length
    print(f'{n:6s} travel={moved:6.2f} m  v_start={v[0]:5.2f} v_end={v[-1]:5.2f} m/s  '
          f'max decel={-min(a + [0]):4.2f} m/s^2  max accel={max(a + [0]):4.2f}  '
          f'max |jerk-step|={max([abs(a[i + 1] - a[i]) for i in range(len(a) - 1)] + [0]):.2f}  '
          f'wheel slip max={wheel_err[n] * 1000:.1f} mm/frame  wheel bottom z=[{contact[n][0]:+.3f},{contact[n][1]:+.3f}] m')
    if moved > 0.01:
        stop_i = next((i for i in range(len(v)) if v[i] < 0.02), None)
        if stop_i is not None:
            brake_i = next((i for i in range(1, len(v)) if v[i] < v[0] - 0.01), 0)
            print(f'        braking from f{F[brake_i]} at {v[brake_i - 1]:.2f} m/s, stopped by f{F[stop_i]}, '
                  f'stopping distance {(pts[stop_i] - pts[brake_i - 1]).length:.2f} m')
    if contact[n][0] < -0.03 or contact[n][1] > 0.03:
        problems.append(f'{n}: wheel bottoms {contact[n]} not on the road (float/sink > 3 cm)')
    if wheel_err[n] > 0.005:
        problems.append(f'{n}: wheel rolling error {wheel_err[n]*1000:.1f} mm/frame (slip)')

# signal compliance for cross traffic
print('=== Stop-line crossings ===')
sl = C.stopline_pos(C.AVE_HALF)
for n, pts in track.items():
    if not n.startswith(('eb', 'wb')):
        continue
    d = 1 if n.startswith('eb') else -1
    half = roots[n]['size'][1] / 2
    approach = 'EB' if d > 0 else 'WB'
    crossed = None
    for i, p in enumerate(pts):
        front = p.x * d + half
        if front > -sl:
            crossed = F[i]
            break
    if crossed is None:
        last_front = pts[-1].x * d + half
        print(f'{n}: never crosses its stop line (front stays {(-sl) - last_front:.2f} m behind it)')
        continue
    st = SIG.state_at(approach, crossed)
    print(f'{n}: front crosses the stop line at f{crossed} (t={(crossed - 1) / C.FPS:.2f} s) on {st.upper()}')
    if st == 'red':
        problems.append(f'{n} ENTERS ON RED at f{crossed}')
    if st == 'amber':
        ta = C.SIG_CROSS_AMBER_T
        ia = int(ta * C.FPS)
        dist = -sl - (pts[ia].x * d + half)
        need = 11.0 ** 2 / (2 * 3.4)
        print(f'      at amber onset it was {dist:.1f} m from the line; comfortable stop needs {need:.1f} m '
              f'-> {"proceeding is correct" if dist < need else "SHOULD HAVE STOPPED"}')
        if dist >= need:
            problems.append(f'{n} should have stopped for the amber')
    # clears before all-red?
    far = sl + 3.0
    clear = next((F[i] for i, p in enumerate(pts) if p.x * d - half > far - 3.0 - C.CROSSWALK_W), None)

# camera sway
base = cam_rot[0]
yaw = [math.degrees(r.z) for r in cam_rot]; pit = [math.degrees(r.x) for r in cam_rot]
roll = [math.degrees(r.y) for r in cam_rot]
def stats(name, s):
    m = sum(s) / len(s)
    d1 = max(abs(s[i + 1] - s[i]) for i in range(len(s) - 1))
    d2 = max(abs(s[i + 1] - 2 * s[i] + s[i - 1]) for i in range(1, len(s) - 1))
    print(f'camera {name}: range {max(s) - min(s):.3f} deg (max dev {max(abs(x - m) for x in s):.3f})  '
          f'max step {d1:.4f} deg/frame  max 2nd diff {d2:.5f}')
    return max(abs(x - m) for x in s)
print('=== Camera ===')
devs = [stats('pitch', pit), stats('yaw', yaw), stats('roll', roll)]
if max(devs) > 1.0:
    problems.append('camera sway exceeds 1 degree')
print('=== Problems ===')
print('\n'.join(problems) if problems else 'none')
