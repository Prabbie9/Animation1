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
