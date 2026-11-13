"""Traffic: every vehicle's motion as an analytic function of the shared clock (t = seconds into
the shot, frame = FRAME_START + t*FPS). Baked to one key per frame (linear), so nothing
overshoots or teleports; wheels spin with the distance travelled (theta = -s / r).

Signal plan (config.SIG_*): cross street green -> amber at 3.0 s -> red at 6.0 s; all-red
6.0-7.5 s; avenue green at 7.5 s. Right-hand traffic (USA).

Vehicles
  taxi      NB kerb lane, first at the stop line, stopped all shot, brake held
  camry     NB inner lane: cruises in at 8 m/s, brakes from t=1.0 s (smoothstep, 3.125 s, peak
            3.84 m/s^2 = 0.39 g, stopping distance 12.5 m), stops 0.7 m behind the taxi's front
  sb0-2     SB queue at the far stop line, stopped (avenue red until 7.5 s; with a ~1 s
            perception-reaction time they cannot move before the shot ends at 8.0 s)
  wb1       WB pickup, 11 m/s, through on green
  eb2       EB wagon, 11 m/s, through on green
  wb3       WB hatchback, 11 m/s, 3.3 m from its stop line at amber onset (needs 17.8 m to stop
            at 3.4 m/s^2), so it legally proceeds and clears before the all-red
  eb4       EB minivan, 11 m/s, 32.6 m from its stop position at amber onset: 0.9 s reaction,
            then a smoothstep stop (peak 4.0 m/s^2) ending 0.6 m behind the stop line at ~8.0 s
"""
import math
import bpy
from mathutils import Vector
from . import config as C
from . import assets
from .util import collection

CROSS_SPEED = 11.0       # m/s (25 mph)
COMFORT_DECEL = 3.4      # m/s^2 (AASHTO comfortable deceleration)


def smoothstep(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


class Brake:
    """Cruise at v0 until tb, then brake to rest over T with a smoothstep speed profile:
    v(t) = v0 (1 - S((t-tb)/T)), a_peak = 1.5 v0 / T, distance = v0 T / 2."""

    def __init__(self, v0, tb, T, s_stop):
        self.v0, self.tb, self.T, self.s_stop = v0, tb, T, s_stop

    def s(self, t):
        v0, tb, T = self.v0, self.tb, self.T
        stop_dist = v0 * T / 2
        if t <= tb:
            return self.s_stop - stop_dist - v0 * (tb - t)
        u = min((t - tb) / T, 1.0)
        # integral of (1 - 3u^2 + 2u^3) du = u - u^3 + u^4/2
        return self.s_stop - stop_dist + v0 * T * (u - u ** 3 + u ** 4 / 2)

    def v(self, t):
        if t <= self.tb:
            return self.v0
        return self.v0 * (1 - smoothstep((t - self.tb) / self.T))

    def a(self, t):
        if t <= self.tb or t >= self.tb + self.T:
            return 0.0
        u = (t - self.tb) / self.T
        return -self.v0 * 6 * u * (1 - u) / self.T

    def braking(self, t):
        return t >= self.tb


class Cruise:
    def __init__(self, v, s0):
        self.v0, self.s0 = v, s0

    def s(self, t):
        return self.s0 + self.v0 * t

    def v(self, t):
        return self.v0

    def a(self, t):
        return 0.0

    def braking(self, t):
        return False


class Parked:
    def s(self, t):
        return 0.0

    def v(self, t):
        return 0.0

    def a(self, t):
        return 0.0

    def braking(self, t):
        return True


def pitch_response(motion, frames, k_deg_per_ms2=0.4, f_n=1.4, zeta=0.45):
    """Body pitch (deg, nose-down negative) from a damped spring driven by the deceleration:
    static gain 0.4 deg per m/s^2 (~1.5 deg at 0.4 g), natural frequency 1.4 Hz, damping 0.45,
    so the nose dips under braking and rocks back gently after the stop."""
    w = 2 * math.pi * f_n
    x = xd = 0.0
    out = {}
    dt = 1.0 / (C.FPS * 10)
    t = -2.0
    fi = 0
    targets = [(f, (f - C.FRAME_START) / C.FPS) for f in frames]
    while fi < len(targets):
        target = k_deg_per_ms2 * motion.a(t)        # a < 0 when braking -> nose down
        xdd = w * w * (target - x) - 2 * zeta * w * xd
        xd += xdd * dt
        x += xd * dt
        t += dt
        while fi < len(targets) and t >= targets[fi][1]:
            out[targets[fi][0]] = x
            fi += 1
    return out


# ------------------------------------------------------------------------------- setup
def stop_line_front(sign):
    """Front-bumper coordinate of the first car waiting at a cross-street stop line (0.6 m back),
    measured along that approach's travel direction from the intersection centre."""
    return -(C.stopline_pos(C.AVE_HALF) + C.STOPLINE_W / 2 + 0.6)


def add_cross_traffic(root, vehicles):
    """Creates the cross-street cars (linked duplicates) and returns their motion specs."""
    col = bpy.data.collections['Vehicles']
    lane = C.LANE / 2          # travel-lane centre offset from the centre line (1.65 m)
    specs = {}
    # (name, key, direction (+1 = EB, travelling +X), lane y, motion builder)
    # s is the coordinate of the car's centre along its travel direction, 0 = intersection centre
    def through(t_centre):
        # passes the intersection centre at t_centre
        return Cruise(CROSS_SPEED, -CROSS_SPEED * t_centre)
    plan = [
        ('wb1', 'car_pickup', -1, through(1.3)),
        ('eb2', 'car_wagon', +1, through(2.3)),
        # wb3: front 3.3 m before its stop line at t=3.0 -> centre position then:
        ('wb3', 'car_hatch', -1, Cruise(CROSS_SPEED, stop_line_front(-1) - 3.3 - assets.size('car_hatch')[1] / 2
                                        - CROSS_SPEED * C.SIG_CROSS_AMBER_T)),
    ]
    # eb4: brakes for the amber. Perception-reaction 0.9 s after amber onset, then a smoothstep
    # stop with peak 4.0 m/s^2 (0.41 g): T = 1.5 v0 / a_peak = 4.125 s, distance v0 T / 2 = 22.7 m.
    # It was 0.9*11 + 22.7 = 32.6 m from its stop position at amber onset, stops at t ~ 8.0 s,
    # 0.6 m behind the stop line, and never reaches the line.
    L4 = assets.size('car_minivan')[1]
    s_stop4 = stop_line_front(+1) - L4 / 2
    T4 = 1.5 * CROSS_SPEED / 4.0
    tb4 = C.SIG_CROSS_AMBER_T + 0.9
    plan.append(('eb4', 'car_minivan', +1, Brake(CROSS_SPEED, tb4, T4, s_stop4)))
    for name, key, d, motion in plan:
        L = assets.size(key)[1]
        y = -lane if d > 0 else lane
        rot = -math.pi / 2 if d > 0 else math.pi / 2       # +Y-facing asset -> face +X / -X
        v = assets.copy(key, name, col, (0, y, 0), rot)
        v['key'] = key
        vehicles[name] = v
        specs[name] = dict(motion=motion, dir=Vector((d, 0, 0)), origin=Vector((0, y, 0)))
    return specs


def avenue_specs(vehicles):
    specs = {}
    # Camry: stop position = where dressing placed it; s measured along +Y from that point
    cam = vehicles['camry']
    specs['camry'] = dict(motion=Brake(8.0, 1.0, 3.125, 0.0), dir=Vector((0, 1, 0)),
                          origin=cam['root'].location.copy())
    for name in ('taxi', 'sb0', 'sb1', 'sb2'):
        v = vehicles[name]
        d = Vector((0, 1, 0)) if name == 'taxi' else Vector((0, -1, 0))
        specs[name] = dict(motion=Parked(), dir=d, origin=v['root'].location.copy())
    return specs


# ------------------------------------------------------------------------------- bake
def wheel_radius(w):
    return max(w.dimensions.y, w.dimensions.z) / 2


def animate(vehicles, specs):
    frames = list(range(C.FRAME_START, C.FRAME_END + 1))
    for name, sp in specs.items():
        v = vehicles[name]
        root, body = v['root'], v['body']
        mo, d, o = sp['motion'], sp['dir'], sp['origin']
        pitch = pitch_response(mo, frames) if not isinstance(mo, Parked) else {}
        radii = {k: wheel_radius(w) for k, w in v['wheels'].items()}
        rest_rot = {k: w.rotation_euler.x for k, w in v['wheels'].items()}
        lamps = v.get('lamps', [])
        for f in frames:
            t = (f - C.FRAME_START) / C.FPS
            s = mo.s(t)
            root.location = o + d * s
            root.keyframe_insert('location', frame=f)
            for k, w in v['wheels'].items():
                w.rotation_euler.x = rest_rot[k] - s / radii[k]
                w.keyframe_insert('rotation_euler', index=0, frame=f)
            if pitch:
                # pivot about the centre of gravity (~0.55 m): rotate and compensate height
                p = math.radians(pitch[f])
                body.rotation_euler.x = p
                body.location.z = 0.55 * (1 - math.cos(p)) - 0.004 * abs(pitch[f])
                body.keyframe_insert('rotation_euler', index=0, frame=f)
                body.keyframe_insert('location', index=2, frame=f)
            br = 1.0 if mo.braking(t) else 0.0
            for ob in (root, body):
                ob['brake'] = br
                ob.keyframe_insert('["brake"]', frame=f)
            for lo in lamps:
                lo.data.energy = lo.data['tail_W'] + br * lo.data['brake_W']
                lo.data.keyframe_insert('energy', frame=f)
        for ob in [root, body] + list(v['wheels'].values()) + [lo.data for lo in lamps]:
            ad = ob.animation_data
            if ad and ad.action:
                for fc in ad.action.fcurves:
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'LINEAR'
                    if fc.data_path == '["brake"]' or fc.data_path == 'energy':
                        for kp in fc.keyframe_points:
                            kp.interpolation = 'CONSTANT'
    return specs
