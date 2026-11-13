"""Grey-box layout: roads, kerbs, sidewalks, markings, building masses, poles, camera."""
import math
import random
import bpy
from mathutils import Vector, Euler
from . import config as C
from . import signals
from .util import (collection, box, cylinder, flat_mat, rounded_corner_polygon,
                   extrude_polygon, mesh_object)

QUADS = [(1, 1), (-1, 1), (1, -1), (-1, -1)]   # NE, NW, SE, SW
QNAME = {(1, 1): 'NE', (-1, 1): 'NW', (1, -1): 'SE', (-1, -1): 'SW'}


def build_ground(root):
    col = collection('Ground', root)
    road = flat_mat('GB_road', (0.18, 0.18, 0.18), 0.5)
    walk = flat_mat('GB_sidewalk', (0.45, 0.45, 0.43), 0.7)
    # One large road plane (asphalt everywhere; sidewalks sit on top of it).
    L = 1200
    mesh_object('Road', [(-L, -L * 0.25, 0), (L, -L * 0.25, 0), (L, L, 0), (-L, L, 0)],
                [(0, 1, 2, 3)], col, road)
    hw, hs = C.AVE_HALF, C.CROSS_HALF
    for sx, sy in QUADS:
        ylen = C.AVE_LEN_N if sy > 0 else C.AVE_LEN_S
        pts = rounded_corner_polygon(hw, hs, hw + C.CROSS_LEN, hs + ylen, C.KERB_RADIUS, 16)
        extrude_polygon(f'Sidewalk_{QNAME[(sx, sy)]}', col, pts, 0.0, C.KERB_H, walk, (sx, sy))
    return col


def _bar(name, col, x0, y0, x1, y1, mat, z=0.004):
    return mesh_object(name, [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)],
                       [(0, 1, 2, 3)], col, mat)


def build_markings(root):
    """US (MUTCD) markings: double-yellow centre lines, white dashed lane lines (3 m dash / 9 m gap),
    continental crosswalks (0.6 m bars), 0.45 m stop lines."""
    col = collection('Markings', root)
    white = flat_mat('GB_paint_white', (0.75, 0.75, 0.72), 0.5)
    yellow = flat_mat('GB_paint_yellow', (0.75, 0.55, 0.08), 0.5)
    hw, hs = C.AVE_HALF, C.CROSS_HALF
    sl_ave = C.stopline_pos(hs)      # avenue approaches (stop lines across the avenue)
    sl_x = C.stopline_pos(hw)        # cross-street approaches
    cw_ave = C.crosswalk_span(hs)
    cw_x = C.crosswalk_span(hw)
    # Avenue centre double yellow and lane lines, north and south of the intersection
    for sy, length in ((1, C.AVE_LEN_N), (-1, C.AVE_LEN_S)):
        y0, y1 = cw_ave[1] + 0.2, length
        for off in (-0.15, 0.15):
            a, b = sorted((sy * y0, sy * y1))
            _bar('Yellow', col, off - 0.05, a, off + 0.05, b, yellow)
        # dashed white between the two lanes of each direction
        y = sl_ave + 0.5
        while y < length:
            for sx in (1, -1):
                a, b = sorted((sy * y, sy * (y + 3.0)))
                _bar('Dash', col, sx * C.LANE - 0.06, a, sx * C.LANE + 0.06, b, white)
            y += 12.0
        # stop line across the approach lanes (right-hand traffic: approach lanes are on
        # the east side for northbound (south approach), west side for southbound)
        a, b = sorted((sy * (sl_ave - C.STOPLINE_W / 2), sy * (sl_ave + C.STOPLINE_W / 2)))
        if sy < 0:
            _bar('StopLine_S', col, 0.2, a, hw - 0.3, b, white)
        else:
            _bar('StopLine_N', col, -hw + 0.3, a, -0.2, b, white)
        # continental crosswalk across the full avenue
        x = -hw + 0.4
        a, b = sorted((sy * cw_ave[0], sy * cw_ave[1]))
        while x + 0.6 <= hw - 0.3:
            _bar('Zebra', col, x, a, x + 0.6, b, white)
            x += 1.2
    # Cross street: double yellow, stop lines, crosswalks
    for sx in (1, -1):
        x0, x1 = cw_x[1] + 0.2, C.CROSS_LEN
        for off in (-0.15, 0.15):
            a, b = sorted((sx * x0, sx * x1))
            _bar('Yellow', col, a, off - 0.05, b, off + 0.05, yellow)
        a, b = sorted((sx * (sl_x - C.STOPLINE_W / 2), sx * (sl_x + C.STOPLINE_W / 2)))
        if sx < 0:   # west approach = eastbound traffic, on the south half
            _bar('StopLine_W', col, a, -hs + C.PARKING, b, -0.2, white)
        else:
            _bar('StopLine_E', col, a, 0.2, b, hs - C.PARKING, white)
        # Parking lanes (both sides): solid 100 mm white line between the travel lane and the
        # parking lane, plus 'T' stall marks every 6.7 m (22 ft). No parking within 6 m (20 ft)
        # of the crosswalk, so the parking line starts at the crosswalk + 6 m.
        px0 = cw_x[1] + 6.0
        for side in (1, -1):
            yl = side * (hs - C.PARKING)
            a, b = sorted((sx * px0, sx * C.CROSS_LEN))
            _bar('ParkLine', col, a, yl - 0.05, b, yl + 0.05, white)
            xs = px0
            while xs <= C.CROSS_LEN:
                y_in, y_out = sorted((yl, yl + side * 0.6))
                _bar('ParkT', col, sx * xs - 0.05, y_in, sx * xs + 0.05, y_out, white)
                xs += 6.7
        y = -hs + 0.4
        a, b = sorted((sx * cw_x[0], sx * cw_x[1]))
        while y + 0.6 <= hs - 0.3:
            _bar('Zebra', col, a, y, b, y + 0.6, white)
            y += 1.2
    return col


def build_buildings(root, rng, greybox=True):
    """Grey-box building masses along both frontages of each block, plus a distant skyline."""
    col = collection('Buildings', root)
    mats = [flat_mat(f'GB_bldg{i}', (v, v, v * 0.97), 0.8) for i, v in
            enumerate((0.35, 0.42, 0.5, 0.3, 0.46))]
    hw, hs = C.AVE_HALF + C.SIDEWALK, C.CROSS_HALF + C.SIDEWALK
    bid = 0
    for sx, sy in (QUADS if greybox else ()):
        ylen = C.AVE_LEN_N if sy > 0 else C.AVE_LEN_S
        # Avenue frontage
        y = hs
        while y < ylen:
            w = rng.uniform(8, 20)
            floors = rng.randint(3, 11)
            h = C.GROUND_STOREY + (floors - 1) * C.STOREY
            d = rng.uniform(16, 26)
            box(f'Bldg_{bid:03d}', col, (d, w, h),
                (sx * (hw + d / 2), sy * (y + w / 2), C.KERB_H), rng.choice(mats))
            bid += 1
            y += w
        # Cross-street frontage (behind the corner building)
        x = hw + 22
        while x < C.CROSS_LEN:
            w = rng.uniform(8, 18)
            floors = rng.randint(3, 9)
            h = C.GROUND_STOREY + (floors - 1) * C.STOREY
            d = rng.uniform(14, 22)
            box(f'Bldg_{bid:03d}', col, (w, d, h),
                (sx * (x + w / 2), sy * (hs + d / 2), C.KERB_H), rng.choice(mats))
            bid += 1
            x += w
    # Distant skyline beyond the modelled avenue
    sky = collection('Skyline', root)
    for i in range(70):
        x = rng.uniform(-260, 260)
        y = rng.uniform(300, 900)
        if abs(x) < 25:
            continue
        h = rng.uniform(30, 160) * (0.6 + 0.4 * (y / 900))
        box(f'Sky_{i:03d}', sky, (rng.uniform(20, 45), rng.uniform(20, 45), h), (x, y, 0),
            rng.choice(mats))
    return col


def build_poles(root):
    """Street-lamp poles (9 m cobra-heads) and signal mast arms. Grey-box only."""
    col = collection('Poles', root)
    steel = flat_mat('GB_steel', (0.25, 0.25, 0.25), 0.4, 1.0)
    hw = C.AVE_HALF
    lamps = []
    # Avenue lamps: 0.6 m back from the kerb, 32 m spacing, staggered sides.
    for sx, ys in ((1, (-40.0, 16.0, 48.0, 80.0, 112.0, 144.0, 176.0, 208.0, 240.0)),
                   (-1, (-28.0, 30.0, 62.0, 94.0, 126.0, 158.0, 190.0, 222.0, 254.0))):
        for y in ys:
            x = sx * (hw + 0.6)
            cylinder(f'LampPole', col, 0.09, 9.0, (x, y, C.KERB_H), steel, 12)
            arm = box('LampArm', col, (2.4, 0.08, 0.08), (x - sx * 1.2, y, C.KERB_H + 8.9), steel)
            head = box('LampHead', col, (0.75, 0.32, 0.12), (x - sx * 2.5, y, C.KERB_H + 8.85), steel)
            lamps.append((x - sx * 2.5, y, C.KERB_H + 8.85))
    # Signal mast arms: one per approach on the far-right corner (US practice).
    # (corner sx, sy, arm direction vector, heads over these lane centres)
    masts = [
        ((1, 1), (-1, 0), [(4.95, None), (1.65, None)], 'NB'),     # northbound, NE corner
        ((-1, -1), (1, 0), [(-4.95, None), (-1.65, None)], 'SB'),  # southbound, SW corner
        ((1, -1), (0, 1), [(None, -1.65)], 'EB'),                  # eastbound, SE corner
        ((-1, 1), (0, -1), [(None, 1.65)], 'WB'),                  # westbound, NW corner
    ]
    heads = []
    housing = flat_mat('GB_sig_housing', (0.03, 0.03, 0.03), 0.5)
    backplate = flat_mat('GB_sig_backplate', (0.02, 0.02, 0.02), 0.6)
    for (sx, sy), (dx, dy), lane_pts, name in masts:
        # Pole on the corner diagonal, 0.8 m behind the curved kerb face (on the sidewalk).
        ccx, ccy = C.AVE_HALF + C.KERB_RADIUS, C.CROSS_HALF + C.KERB_RADIUS
        d = (C.KERB_RADIUS - 0.8) / math.sqrt(2)
        px, py = sx * (ccx - d), sy * (ccy - d)
        cylinder(f'SigPole_{name}', col, 0.15, 7.2, (px, py, C.KERB_H), steel, 16)
        reach = 8.5 if dx else 7.0
        arm = box(f'SigArm_{name}', col, (reach, 0.14, 0.14),
                  (px + dx * reach / 2, py + dy * reach / 2, C.KERB_H + 6.6), steel,
                  rot_z=0 if dx else math.pi / 2)
        for lx, ly in lane_pts:
            hx = lx if lx is not None else px
            hy = ly if ly is not None else py
            # 3-section 300 mm head, bottom 5.2 m above the road, hung from the arm at 6.75 m
            signals.build_head(f'SigHead_{name}_{len(heads)}', col, name, (hx, hy, 5.2),
                               housing, backplate)
            box('SigHanger', col, (0.05, 0.05, 0.5), (hx, hy, 6.27), steel)
            heads.append((name, hx, hy))
    return col, lamps, heads


def build_reference(root):
    """Scale references: a 1.75 m human and a 4.75 m sedan (placeholder for the taxi)."""
    col = collection('Reference', root)
    skin = flat_mat('GB_ref_human', (0.7, 0.3, 0.2), 0.6)
    carm = flat_mat('GB_ref_car', (0.8, 0.6, 0.05), 0.4)
    tyre = flat_mat('GB_tyre', (0.03, 0.03, 0.03), 0.8)
    # Human on the east sidewalk near the corner
    hx, hy, z = 8.6, -12.5, C.KERB_H
    cylinder('RefHuman_legs', col, 0.14, 0.85, (hx, hy, z), skin, 12)
    cylinder('RefHuman_torso', col, 0.2, 0.65, (hx, hy, z + 0.85), skin, 12)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=(hx, hy, z + C.HUMAN_H - 0.12))
    h = bpy.context.active_object
    h.name = 'RefHuman_head'
    for c in h.users_collection:
        c.objects.unlink(h)
    col.objects.link(h)
    h.data.materials.append(skin)
    # Taxi placeholder stopped at the south stop line (northbound right lane)
    front = -(C.stopline_pos(C.CROSS_HALF) + C.STOPLINE_W / 2 + 0.6)
    cy = front - C.CAR_L / 2
    cx = C.AVE_HALF - C.LANE / 2
    box('RefCar_body', col, (C.CAR_W, C.CAR_L, 0.75), (cx, cy, 0.3), carm)
    box('RefCar_cabin', col, (C.CAR_W * 0.85, C.CAR_L * 0.5, 0.45), (cx, cy - 0.2, 1.05), carm)
    for wx in (-1, 1):
        for wy in (-1, 1):
            cylinder('RefCar_wheel', col, 0.34, 0.24,
                     (cx + wx * (C.CAR_W / 2 - 0.12) - 0.12 * wx, cy + wy * 1.42, 0.34), tyre, 20,
                     rot=(0, math.pi / 2, 0))
    # Two southbound cars waiting at the far stop line (facing the camera)
    for i, lx in enumerate((-C.LANE / 2, -C.LANE * 1.5)):
        cy2 = C.stopline_pos(C.CROSS_HALF) + C.STOPLINE_W / 2 + 0.8 + C.CAR_L / 2 + i * 1.5
        box(f'RefCarSB{i}', col, (C.CAR_W, C.CAR_L, 1.2), (lx, cy2, 0.25),
            flat_mat('GB_ref_car2', (0.2, 0.25, 0.35), 0.4))
    return col, (cx, cy)


def build_camera(root, focus_point):
    col = collection('Camera', root)
    cam_data = bpy.data.cameras.new('ShotCam')
    cam_data.lens = C.CAM_FOCAL
    cam_data.sensor_width = C.CAM_SENSOR
    cam_data.sensor_fit = 'HORIZONTAL'
    cam_data.clip_start = 0.1
    cam_data.clip_end = 2000
    cam_data.dof.use_dof = True
    cam_data.dof.aperture_fstop = C.CAM_FSTOP
    cam_data.dof.aperture_blades = 6
    cam_data.dof.aperture_rotation = math.radians(15)
    cam = bpy.data.objects.new('ShotCam', cam_data)
    col.objects.link(cam)
    # Focus target: rear bumper of the taxi
    tgt = bpy.data.objects.new('FocusTarget', None)
    tgt.location = focus_point
    col.objects.link(tgt)
    cam_data.dof.focus_object = tgt
    z = C.KERB_H + C.CAM_HEIGHT
    rot = Euler((math.radians(90 + C.CAM_PITCH_DEG), 0, math.radians(C.CAM_YAW_DEG)))
    cam.rotation_euler = rot
    # Constant-speed dolly (shot starts and ends mid-move): linear interpolation
    cam.location = (C.CAM_X, C.CAM_Y0, z)
    cam.keyframe_insert('location', frame=C.FRAME_START)
    cam.location = (C.CAM_X, C.CAM_Y1, z)
    cam.keyframe_insert('location', frame=C.FRAME_END)
    for fc in cam.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    bpy.context.scene.camera = cam
    return cam


def build(root, greybox=False):
    rng = random.Random(C.SEED)
    build_ground(root)
    build_markings(root)
    build_buildings(root, rng, greybox)
    _, lamps, heads = build_poles(root)
    _, (cx, cy) = build_reference(root)
    taxi_rear = -(C.stopline_pos(C.CROSS_HALF) + C.STOPLINE_W / 2 + 0.6) - 5.39
    cam = build_camera(root, (cx, taxi_rear, 0.9))
    return dict(lamps=lamps, heads=heads, camera=cam)
