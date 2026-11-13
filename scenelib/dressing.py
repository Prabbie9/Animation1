"""Static set dressing and vehicle placement (positions only; animation lives in traffic.py)."""
import math
import random
from . import config as C
from . import assets
from .util import collection

N, S, E, W = 0.0, math.pi, -math.pi / 2, math.pi / 2      # rot_z that makes a +Y-facing asset face N/S/E/W


def stop_front(approach_sign):
    """y of the front bumper of the first car waiting at the avenue stop line (0.6 m back)."""
    return approach_sign * (C.stopline_pos(C.CROSS_HALF) + C.STOPLINE_W / 2 + 0.6)


def build_vehicles(root):
    col = collection('Vehicles', root)
    v = {}
    hw, lane = C.AVE_HALF, C.LANE
    # Hero taxi: northbound kerb lane, first at the stop line
    L = assets.size('taxi_cvpi')[1]
    v['taxi'] = assets.copy('taxi_cvpi', 'taxi', col, (hw - lane / 2, stop_front(-1) - L / 2, 0), N)
    v['taxi']['key'] = 'taxi_cvpi'
    # Northbound inner lane: Camry (it arrives and stops during the shot; traffic.py animates it)
    L = assets.size('camry')[1]
    v['camry'] = assets.copy('camry', 'camry', col, (lane / 2, stop_front(-1) - 0.7 - L / 2, 0), N)
    v['camry']['key'] = 'camry'
    # Southbound queue at the far stop line, facing the camera
    y = stop_front(1)
    for i, (key, lx, gap) in enumerate((('car_suv', -lane / 2, 0.0), ('car_sedan', -lane * 1.5, 0.4),
                                         ('car_minivan', -lane / 2, None))):
        L = assets.size(key)[1]
        if gap is None:   # second car in the inner lane queue
            y2 = stop_front(1) + assets.size('car_suv')[1] + 2.1 + L / 2
        else:
            y2 = y + gap + L / 2
        v[f'sb{i}'] = assets.copy(key, f'sb{i}', col, (lx, y2, 0), S)
        v[f'sb{i}']['key'] = key
    return col, v


def build_parked(root, rng):
    """Cars parked along the cross street's parking lanes (both sides, both arms)."""
    col = collection('ParkedCars', root)
    keys = ['car_hatch', 'car_wagon', 'car_pickup', 'car_sedan', 'car_suv', 'car_minivan']
    px0 = C.crosswalk_span(C.AVE_HALF)[1] + 6.0
    y_park = C.CROSS_HALF - C.PARKING / 2
    n = 0
    for sx in (1, -1):
        for sy in (1, -1):
            # north side = westbound kerb -> cars face west; south side faces east
            rot = W if sy > 0 else E
            x = px0
            while x + 6.7 <= C.CROSS_LEN - 5:
                if rng.random() < 0.75:
                    key = rng.choice(keys)
                    jitter = rng.uniform(-0.4, 0.4)
                    assets.instance(key, f'Parked_{n:02d}', col,
                                    (sx * (x + 3.35 + jitter), sy * (y_park + rng.uniform(-0.12, 0.05)), 0),
                                    rot + rng.uniform(-0.015, 0.015))
                    n += 1
                x += 6.7
    return col


def build_props(root, rng):
    col = collection('Props', root)
    z = C.KERB_H
    k = C.AVE_HALF   # kerb line of the avenue (east side at +k)
    # Foreground east sidewalk (camera side)
    assets.instance('hydrant', 'Hydrant_SE', col, (k + 0.65, -19.5, z), math.radians(12))
    assets.instance('newsbox', 'Newsboxes_SE', col, (k + 0.95, -15.2, z), W + math.radians(3))
    assets.instance('trash', 'Trash_SE', col, (k + 0.75, -11.6, z), math.radians(8))
    # Opposite corners
    assets.instance('trash', 'Trash_NW', col, (-k - 0.75, 11.8, z), math.radians(-20))
    assets.instance('hydrant', 'Hydrant_NE', col, (k + 0.6, 17.5, z), math.radians(70))
    assets.instance('newsbox', 'Newsboxes_NE', col, (k + 0.9, 13.6, z), W)
    # Utility covers in the carriageway (sewer manholes sit roughly on lane centres)
    for i, (x, y) in enumerate(((3.1, -23.0), (-2.4, 19.5), (1.3, 47.0), (-4.2, -3.0))):
        assets.instance('manhole', f'Manhole_{i}', col, (x, y, 0.002), rng.uniform(0, math.pi))
    return col


def build_people(root):
    col = collection('People', root)
    # Waiting to cross the cross street (DON'T WALK, because the avenue is red... the parallel
    # avenue phase is red, so pedestrians crossing the cross street must wait).
    assets.instance('ped_umbrella', 'Ped_umbrella_NW', col, (-C.AVE_HALF - 1.3, C.CROSS_HALF + 5.2, C.KERB_H), 0.0)
    assets.instance('ped_coat', 'Ped_coat_NW', col, (-C.AVE_HALF - 2.6, C.CROSS_HALF + 5.9, C.KERB_H), 0.25)
    return col


def build(root):
    rng = random.Random(C.SEED + 7)
    _, vehicles = build_vehicles(root)
    build_parked(root, rng)
    build_props(root, rng)
    build_people(root)
    return vehicles
