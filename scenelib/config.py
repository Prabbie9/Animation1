"""Single source of truth for dimensions (metres), timing and shot settings.

World axes: +X = east, +Y = north, +Z = up. Origin = centre of the intersection.
Country: USA (generic north-eastern city). Traffic drives on the RIGHT.
The avenue runs north-south (along Y); the cross street runs east-west (along X).
"""

FPS = 24
FRAME_START = 1
FRAME_END = 192            # 8 s * 24 fps
SEED = 1979

# --- Road geometry -----------------------------------------------------------
LANE = 3.3                 # m, travel lane width
AVE_LANES_EACH_WAY = 2
AVE_HALF = LANE * AVE_LANES_EACH_WAY          # 6.6 m  (road half-width of the avenue)
PARKING = 2.4              # m, parking lane on the cross street
CROSS_HALF = LANE + PARKING                   # 5.7 m  (road half-width of the cross street)
SIDEWALK = 4.0             # m
KERB_H = 0.15              # m
KERB_RADIUS = 4.5          # m, corner kerb radius
AVE_LEN_N = 260.0          # how far the avenue is modelled north / south of the centre
AVE_LEN_S = 60.0
CROSS_LEN = 90.0           # east and west

# Crosswalk / stop line positions (distance from the intersection centre along the approach)
CROSSWALK_W = 3.0
CROSSWALK_GAP = 0.6        # gap between the cross street road edge and the crosswalk
STOPLINE_W = 0.45
STOPLINE_GAP = 1.2         # gap between the stop line and the crosswalk

def crosswalk_span(road_half_other):
    """(near, far) distance from centre for the crosswalk on an approach."""
    near = road_half_other + KERB_RADIUS * 0.0 + CROSSWALK_GAP
    return near, near + CROSSWALK_W

def stopline_pos(road_half_other):
    """Distance from the centre to the centre of the stop line."""
    return crosswalk_span(road_half_other)[1] + STOPLINE_GAP + STOPLINE_W / 2

# --- Buildings -----------------------------------------------------------------
GROUND_STOREY = 4.6        # shop floor
STOREY = 3.25

# --- Camera ---------------------------------------------------------------------
CAM_FOCAL = 35.0           # mm
CAM_SENSOR = 36.0          # mm (full-frame width)
CAM_FSTOP = 2.0
CAM_HEIGHT = 1.70          # m eye height above the sidewalk surface
CAM_X = AVE_HALF + 0.50    # m, 0.5 m inside the kerb on the east sidewalk
CAM_Y0 = -29.0             # start
CAM_Y1 = -26.0             # end (3 m dolly forward, northwards)
CAM_YAW_DEG = 14.0         # turned left towards the avenue centre
CAM_PITCH_DEG = 3.0

# --- Reference figures -----------------------------------------------------------
HUMAN_H = 1.75
CAR_L, CAR_W, CAR_H = 4.75, 1.85, 1.50      # taxi-class sedan

# --- Signal timing (one clock for signals, traffic and rain: scene frames at 24 fps) -------------
# The shot sits at the END of the cross-street phase:
#   cross street (EB/WB): green -> amber at 3.0 s -> red at 6.0 s (3.0 s amber, MUTCD 30 mph)
#   all-red clearance 6.0 s -> 7.5 s (1.5 s)
#   avenue (NB/SB): red until 7.5 s, then green
SIG_CROSS_AMBER_T = 3.0
SIG_CROSS_RED_T = 6.0
SIG_AVE_GREEN_T = 7.5

def t2f(t):
    """seconds into the shot -> scene frame"""
    return FRAME_START + round(t * FPS)

# Exposure (EV over the physical scene-referred values, see lighting.py units). Set so that the
# lamp-lit wet asphalt sits around 0.10-0.18 in display values.
EXPOSURE_EV = 6.5

# Foreground puddle: a utility trench patch across the NB lanes has settled, so the rutted wheel
# paths of the kerb lane just north of it form a shallow depression that holds water. It sits on
# the mirror line between the camera and the taxi's tail lamps (reflection point of a 0.9 m
# lamp seen from 1.85 m: 2/3 of the way to the lamp -> (5.2, -20.4) at the dolly start,
# (5.2, -19.9) at the end), so it reflects the lamps instead of dark facades. No moving tyre
# crosses it (the Camry's right wheels run at x ~ 2.4).
TRENCH_PATCH = (0.4, -23.3, 6.4, -21.5)        # x0, y0, x1, y1
FG_PUDDLE = (5.0, -20.6, 0.95, 0.75)           # centre x, y, radius x, radius y (m)
