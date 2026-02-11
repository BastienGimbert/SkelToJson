# ─── Attachment types ─────────────────────────────────────────────────────────

ATTACHMENT_REGION = 0
ATTACHMENT_BOUNDINGBOX = 1
ATTACHMENT_MESH = 2
ATTACHMENT_LINKEDMESH = 3
ATTACHMENT_PATH = 4
ATTACHMENT_POINT = 5
ATTACHMENT_CLIPPING = 6

# ─── Curve types ──────────────────────────────────────────────────────────────

CURVE_LINEAR = 0
CURVE_STEPPED = 1
CURVE_BEZIER = 2

# ─── Bone timeline types ─────────────────────────────────────────────────────

BONE_ROTATE = 0
BONE_TRANSLATE = 1
BONE_TRANSLATEX = 2
BONE_TRANSLATEY = 3
BONE_SCALE = 4
BONE_SCALEX = 5
BONE_SCALEY = 6
BONE_SHEAR = 7
BONE_SHEARX = 8
BONE_SHEARY = 9
BONE_INHERIT = 10

# ─── Slot timeline types ─────────────────────────────────────────────────────

SLOT_ATTACHMENT = 0
SLOT_RGBA = 1
SLOT_RGB = 2
SLOT_RGBA2 = 3
SLOT_RGB2 = 4
SLOT_ALPHA = 5

# ─── Path constraint timeline types ──────────────────────────────────────────

PATH_POSITION = 0
PATH_SPACING = 1
PATH_MIX = 2

# ─── Physics constraint timeline types ───────────────────────────────────────

PHYSICS_INERTIA = 0
PHYSICS_STRENGTH = 1
PHYSICS_DAMPING = 2
PHYSICS_MASS = 4
PHYSICS_WIND = 5
PHYSICS_GRAVITY = 6
PHYSICS_MIX = 7
PHYSICS_RESET = 8

# ─── Attachment deform/sequence ──────────────────────────────────────────────

ATTACHMENT_DEFORM = 0
ATTACHMENT_SEQUENCE = 1

# ─── Enum name tables ────────────────────────────────────────────────────────

INHERIT_NAMES = [
    "normal", "onlyTranslation", "noRotationOrReflection",
    "noScale", "noScaleOrReflection",
]
BLEND_MODE_NAMES = ["normal", "additive", "multiply", "screen"]
POSITION_MODE_NAMES = ["fixed", "percent"]
SPACING_MODE_NAMES = ["length", "fixed", "percent"]
ROTATE_MODE_NAMES = ["tangent", "chain", "chainScale"]
SEQUENCE_MODE_NAMES = [
    "hold", "once", "loop", "pingpong",
    "onceReverse", "loopReverse", "pingpongReverse",
]

BONE_TIMELINE_NAMES = {
    BONE_ROTATE: "rotate",
    BONE_TRANSLATE: "translate",
    BONE_TRANSLATEX: "translatex",
    BONE_TRANSLATEY: "translatey",
    BONE_SCALE: "scale",
    BONE_SCALEX: "scalex",
    BONE_SCALEY: "scaley",
    BONE_SHEAR: "shear",
    BONE_SHEARX: "shearx",
    BONE_SHEARY: "sheary",
    BONE_INHERIT: "inherit",
}
