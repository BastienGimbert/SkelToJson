from __future__ import annotations

import json
import sys
from pathlib import Path

from .binary_input import BinaryInput
from .constants import (
    ATTACHMENT_BOUNDINGBOX,
    ATTACHMENT_CLIPPING,
    ATTACHMENT_DEFORM,
    ATTACHMENT_LINKEDMESH,
    ATTACHMENT_MESH,
    ATTACHMENT_PATH,
    ATTACHMENT_POINT,
    ATTACHMENT_REGION,
    ATTACHMENT_SEQUENCE,
    BLEND_MODE_NAMES,
    BONE_INHERIT,
    BONE_ROTATE,
    BONE_SCALE,
    BONE_SCALEX,
    BONE_SCALEY,
    BONE_SHEAR,
    BONE_SHEARX,
    BONE_SHEARY,
    BONE_TIMELINE_NAMES,
    BONE_TRANSLATE,
    BONE_TRANSLATEX,
    BONE_TRANSLATEY,
    CURVE_BEZIER,
    CURVE_STEPPED,
    INHERIT_NAMES,
    PATH_MIX,
    PATH_POSITION,
    PATH_SPACING,
    PHYSICS_DAMPING,
    PHYSICS_GRAVITY,
    PHYSICS_INERTIA,
    PHYSICS_MASS,
    PHYSICS_MIX,
    PHYSICS_RESET,
    PHYSICS_STRENGTH,
    PHYSICS_WIND,
    POSITION_MODE_NAMES,
    ROTATE_MODE_NAMES,
    SEQUENCE_MODE_NAMES,
    SLOT_ALPHA,
    SLOT_ATTACHMENT,
    SLOT_RGB,
    SLOT_RGB2,
    SLOT_RGBA,
    SLOT_RGBA2,
    SPACING_MODE_NAMES,
)
from .helpers import (
    color_to_rgb_hex,
    color_to_rgba_hex,
    int32_to_rgb_hex,
    int32_to_rgba_hex,
    rf,
)


class SkelConverter:
    """Converts Spine binary .skel data to a JSON-compatible dict."""

    def __init__(self):
        self.inp: BinaryInput = None  # type: ignore[assignment]
        self.bones: list[dict] = []
        self.slots: list[dict] = []
        self.ik_constraints: list[dict] = []
        self.transform_constraints: list[dict] = []
        self.path_constraints: list[dict] = []
        self.physics_constraints: list[dict] = []
        self.slider_constraints: list[dict] = []
        self.skins: list[dict] = []
        self.events: list[dict] = []
        self.nonessential: bool = False
        self.version: str = ""
        self.is_43: bool = False

    # ── Main entry point ──────────────────────────────────────────────────

    def convert(self, data: bytes) -> dict:
        """Convert binary skeleton data to JSON-compatible dict."""
        self.inp = BinaryInput(data)
        inp = self.inp

        result: dict = {}

        # ── Skeleton header ──
        skeleton: dict = {}
        low_hash = inp.read_int32()
        high_hash = inp.read_int32()
        if high_hash != 0 or low_hash != 0:
            lh = low_hash if low_hash >= 0 else low_hash + 0x100000000
            hh = high_hash if high_hash >= 0 else high_hash + 0x100000000
            skeleton["hash"] = f"{hh:x}{lh:x}"

        version = inp.read_string()
        if version:
            skeleton["spine"] = version
            self.version = version
            self.is_43 = version.startswith("4.3")
            if not (version.startswith("4.2") or version.startswith("4.3")):
                raise ValueError(
                    f"Unsupported Spine version: {version}. "
                    f"This converter supports Spine 4.2.x and 4.3.x binary formats."
                )

        skeleton["x"] = rf(inp.read_float())
        skeleton["y"] = rf(inp.read_float())
        skeleton["width"] = rf(inp.read_float())
        skeleton["height"] = rf(inp.read_float())
        skeleton["referenceScale"] = rf(inp.read_float())

        self.nonessential = inp.read_boolean()
        if self.nonessential:
            skeleton["fps"] = rf(inp.read_float())
            images_path = inp.read_string()
            if images_path:
                skeleton["images"] = images_path
            audio_path = inp.read_string()
            if audio_path:
                skeleton["audio"] = audio_path

        result["skeleton"] = skeleton

        # ── Strings table ──
        n = inp.read_varint(True)
        for _ in range(n):
            inp.strings.append(inp.read_string() or "")

        # ── Bones ──
        if self.is_43:
            self._read_bones_43(result)
        else:
            self._read_bones(result)

        # ── Slots ──
        self._read_slots(result)

        # ── Constraints ──
        if self.is_43:
            self._read_constraints_43(result)
        else:
            self._read_ik_constraints(result)
            self._read_transform_constraints(result)
            self._read_path_constraints(result)
            self._read_physics_constraints(result)

        # ── Skins ──
        self._read_skins(result)

        # ── Events ──
        self._read_events(result)

        # ── Animations ──
        self._read_animations(result)

        return result

    # ── Bones ─────────────────────────────────────────────────────────────

    def _read_bones(self, result: dict):
        """Read bones in Spine 4.2 format (flags-based optional fields)."""
        inp = self.inp
        n = inp.read_varint(True)
        bones_json = []

        for i in range(n):
            bone: dict = {}
            bone["name"] = inp.read_string() or f"bone{i}"

            if i > 0:
                parent_idx = inp.read_varint(True)
                bone["parent"] = (
                    self.bones[parent_idx]["name"]
                    if parent_idx < len(self.bones)
                    else f"bone{parent_idx}"
                )

            rotation = rf(inp.read_float())
            x = rf(inp.read_float())
            y = rf(inp.read_float())
            scale_x = rf(inp.read_float())
            scale_y = rf(inp.read_float())
            shear_x = rf(inp.read_float())
            shear_y = rf(inp.read_float())
            length = rf(inp.read_float())
            inherit = inp.read_varint(True)
            skin_required = inp.read_boolean()

            if rotation:
                bone["rotation"] = rotation
            if x:
                bone["x"] = x
            if y:
                bone["y"] = y
            if scale_x != 1:
                bone["scaleX"] = scale_x
            if scale_y != 1:
                bone["scaleY"] = scale_y
            if shear_x:
                bone["shearX"] = shear_x
            if shear_y:
                bone["shearY"] = shear_y
            if length:
                bone["length"] = length
            if inherit and inherit < len(INHERIT_NAMES):
                bone["inherit"] = INHERIT_NAMES[inherit]
            if skin_required:
                bone["skin"] = True

            self._read_bone_nonessential(bone, inp)
            self.bones.append(bone)
            bones_json.append(bone)

        if bones_json:
            result["bones"] = bones_json

    def _read_bones_43(self, result: dict):
        """Read bones in Spine 4.3 format (all fields present, inherit/length swapped)."""
        inp = self.inp
        n = inp.read_varint(True)
        bones_json = []

        for i in range(n):
            bone: dict = {}
            bone["name"] = inp.read_string() or f"bone{i}"

            if i > 0:
                parent_idx = inp.read_varint(True)
                bone["parent"] = (
                    self.bones[parent_idx]["name"]
                    if parent_idx < len(self.bones)
                    else f"bone{parent_idx}"
                )

            rotation = rf(inp.read_float())
            x = rf(inp.read_float())
            y = rf(inp.read_float())
            scale_x = rf(inp.read_float())
            scale_y = rf(inp.read_float())
            shear_x = rf(inp.read_float())
            shear_y = rf(inp.read_float())
            # 4.3: inherit (byte) before length (swapped from 4.2)
            inherit = inp.read_byte()
            length = rf(inp.read_float())
            skin_required = inp.read_boolean()

            if rotation:
                bone["rotation"] = rotation
            if x:
                bone["x"] = x
            if y:
                bone["y"] = y
            if scale_x != 1:
                bone["scaleX"] = scale_x
            if scale_y != 1:
                bone["scaleY"] = scale_y
            if shear_x:
                bone["shearX"] = shear_x
            if shear_y:
                bone["shearY"] = shear_y
            if length:
                bone["length"] = length
            if inherit and inherit < len(INHERIT_NAMES):
                bone["inherit"] = INHERIT_NAMES[inherit]
            if skin_required:
                bone["skin"] = True

            self._read_bone_nonessential(bone, inp)
            self.bones.append(bone)
            bones_json.append(bone)

        if bones_json:
            result["bones"] = bones_json

    def _read_bone_nonessential(self, bone: dict, inp: BinaryInput):
        if self.nonessential:
            color = inp.read_color_int()
            icon = inp.read_string()
            visible = inp.read_boolean()
            if color != 0x9B9B9BFF and color != -1684300801:
                bone["color"] = int32_to_rgba_hex(color)
            if icon:
                bone["icon"] = icon
            if not visible:
                bone["visible"] = False

    # ── Slots ─────────────────────────────────────────────────────────────

    def _read_slots(self, result: dict):
        inp = self.inp
        n = inp.read_varint(True)
        slots_json = []

        for i in range(n):
            slot: dict = {}
            slot["name"] = inp.read_string() or f"slot{i}"

            bone_idx = inp.read_varint(True)
            slot["bone"] = (
                self.bones[bone_idx]["name"]
                if bone_idx < len(self.bones)
                else f"bone{bone_idx}"
            )

            color = inp.read_color_int()
            dark_color = inp.read_color_int()
            attachment = inp.read_string_ref()
            blend_mode = inp.read_varint(True)

            if color != -1 and int32_to_rgba_hex(color) != "ffffffff":
                slot["color"] = int32_to_rgba_hex(color)
            if dark_color != -1:
                slot["dark"] = int32_to_rgb_hex(dark_color)
            if attachment:
                slot["attachment"] = attachment
            if blend_mode and blend_mode < len(BLEND_MODE_NAMES):
                slot["blend"] = BLEND_MODE_NAMES[blend_mode]

            if self.nonessential:
                visible = inp.read_boolean()
                if not visible:
                    slot["visible"] = False

            slot["_index"] = i
            self.slots.append(slot)
            slots_json.append({k: v for k, v in slot.items() if not k.startswith("_")})

        if slots_json:
            result["slots"] = slots_json

    # ── Constraints (4.2 separate) ────────────────────────────────────────

    def _read_ik_constraints(self, result: dict):
        inp = self.inp
        n = inp.read_varint(True)
        ik_json = []
        for _ in range(n):
            name = inp.read_string() or ""
            ik = self._read_ik_constraint_data(name)
            self.ik_constraints.append(ik)
            ik_json.append(ik)
        if ik_json:
            result["ik"] = ik_json

    def _read_transform_constraints(self, result: dict):
        inp = self.inp
        n = inp.read_varint(True)
        tc_json = []

        for _ in range(n):
            tc: dict = {}
            tc["name"] = inp.read_string() or ""
            tc["order"] = inp.read_varint(True)

            bone_count = inp.read_varint(True)
            tc["bones"] = [
                self.bones[inp.read_varint(True)]["name"] for _ in range(bone_count)
            ]

            target_idx = inp.read_varint(True)
            tc["target"] = self.bones[target_idx]["name"]

            flags = inp.read_byte()
            if flags & 1:
                tc["skin"] = True
            if flags & 2:
                tc["local"] = True
            if flags & 4:
                tc["relative"] = True
            if flags & 8:
                tc["rotation"] = rf(inp.read_float())
            if flags & 16:
                tc["x"] = rf(inp.read_float())
            if flags & 32:
                tc["y"] = rf(inp.read_float())
            if flags & 64:
                tc["scaleX"] = rf(inp.read_float())
            if flags & 128:
                tc["scaleY"] = rf(inp.read_float())

            flags2 = inp.read_byte()
            if flags2 & 1:
                tc["shearY"] = rf(inp.read_float())
            if flags2 & 2:
                tc["mixRotate"] = rf(inp.read_float())
            if flags2 & 4:
                tc["mixX"] = rf(inp.read_float())
            if flags2 & 8:
                tc["mixY"] = rf(inp.read_float())
            if flags2 & 16:
                tc["mixScaleX"] = rf(inp.read_float())
            if flags2 & 32:
                tc["mixScaleY"] = rf(inp.read_float())
            if flags2 & 64:
                tc["mixShearY"] = rf(inp.read_float())

            self.transform_constraints.append(tc)
            tc_json.append(tc)

        if tc_json:
            result["transform"] = tc_json

    def _read_path_constraints(self, result: dict):
        inp = self.inp
        n = inp.read_varint(True)
        pc_json = []

        for _ in range(n):
            pc = self._read_path_constraint_data(inp.read_string() or "")
            self.path_constraints.append(pc)
            pc_json.append({k: v for k, v in pc.items() if not k.startswith("_")})

        if pc_json:
            result["path"] = pc_json

    def _read_physics_constraints(self, result: dict):
        inp = self.inp
        n = inp.read_varint(True)
        ph_json = []
        for _ in range(n):
            name = inp.read_string() or ""
            ph = self._read_physics_constraint_data(name)
            self.physics_constraints.append(ph)
            ph_json.append(ph)
        if ph_json:
            result["physics"] = ph_json

    # ── Constraints (4.3 unified) ─────────────────────────────────────────

    _CONSTRAINT_IK = 0
    _CONSTRAINT_PATH = 1
    _CONSTRAINT_TRANSFORM = 2
    _CONSTRAINT_PHYSICS = 3
    _CONSTRAINT_SLIDER = 4

    def _read_constraints_43(self, result: dict):
        """Read unified constraints in Spine 4.3 format."""
        inp = self.inp
        n = inp.read_varint(True)

        ik_json: list[dict] = []
        tc_json: list[dict] = []
        pc_json: list[dict] = []
        ph_json: list[dict] = []

        for _ in range(n):
            name = inp.read_string() or ""
            ctype = inp.read_byte()

            if ctype == self._CONSTRAINT_IK:
                ik = self._read_ik_constraint_data(name)
                self.ik_constraints.append(ik)
                ik_json.append(ik)

            elif ctype == self._CONSTRAINT_TRANSFORM:
                tc = self._read_transform_constraint_data_43(name)
                self.transform_constraints.append(tc)
                tc_json.append(tc)

            elif ctype == self._CONSTRAINT_PATH:
                pc = self._read_path_constraint_data(name)
                self.path_constraints.append(pc)
                pc_json.append({k: v for k, v in pc.items() if not k.startswith("_")})

            elif ctype == self._CONSTRAINT_PHYSICS:
                ph = self._read_physics_constraint_data(name)
                self.physics_constraints.append(ph)
                ph_json.append(ph)

            elif ctype == self._CONSTRAINT_SLIDER:
                sl = self._read_slider_constraint_data(name)
                self.slider_constraints.append(sl)

        if ik_json:
            result["ik"] = ik_json
        if tc_json:
            result["transform"] = tc_json
        if pc_json:
            result["path"] = pc_json
        if ph_json:
            result["physics"] = ph_json

    # ── Shared constraint readers ─────────────────────────────────────────

    def _read_ik_constraint_data(self, name: str) -> dict:
        inp = self.inp
        ik: dict = {"name": name}
        ik["order"] = inp.read_varint(True)

        bone_count = inp.read_varint(True)
        ik["bones"] = [self.bones[inp.read_varint(True)]["name"] for _ in range(bone_count)]

        target_idx = inp.read_varint(True)
        ik["target"] = self.bones[target_idx]["name"]

        flags = inp.read_byte()
        if flags & 1:
            ik["skin"] = True
        if not (flags & 2):
            ik["bendPositive"] = False
        if flags & 4:
            ik["compress"] = True
        if flags & 8:
            ik["stretch"] = True
        if flags & 16:
            ik["uniform"] = True
        if flags & 32:
            mix = inp.read_float() if (flags & 64) else 1.0
        else:
            mix = 1.0
        softness = inp.read_float() if (flags & 128) else 0.0

        if rf(mix) != 1:
            ik["mix"] = rf(mix)
        if rf(softness) != 0:
            ik["softness"] = rf(softness)
        return ik

    def _read_transform_constraint_data_43(self, name: str) -> dict:
        """Read transform constraint in Spine 4.3 format (property mappings)."""
        inp = self.inp
        tc: dict = {"name": name}
        tc["order"] = inp.read_varint(True)

        bone_count = inp.read_varint(True)
        tc["bones"] = [self.bones[inp.read_varint(True)]["name"] for _ in range(bone_count)]

        source_idx = inp.read_varint(True)
        tc["target"] = self.bones[source_idx]["name"]

        flags = inp.read_byte()
        if flags & 1:
            tc["skin"] = True
        if flags & 2:
            tc["local"] = True
        if flags & 4:
            tc["relative"] = True

        _PROP_NAMES = {0: "Rotate", 1: "X", 2: "Y", 3: "ScaleX", 4: "ScaleY", 5: "ShearY"}

        prop_count = inp.read_varint(True)
        for _ in range(prop_count):
            from_prop = inp.read_byte()
            to_prop = inp.read_byte()
            offset = rf(inp.read_float())
            mix_val = rf(inp.read_float())
            from_name = _PROP_NAMES.get(from_prop, f"prop{from_prop}")
            to_name = _PROP_NAMES.get(to_prop, f"prop{to_prop}")
            if from_name == to_name:
                if offset:
                    tc[f"offset{from_name}"] = offset
                if mix_val != 0:
                    tc[f"mix{to_name}"] = mix_val
            else:
                if offset:
                    tc[f"offset{from_name}To{to_name}"] = offset
                if mix_val != 0:
                    tc[f"mix{from_name}To{to_name}"] = mix_val

        return tc

    def _read_path_constraint_data(self, name: str) -> dict:
        inp = self.inp
        pc: dict = {"name": name}
        pc["order"] = inp.read_varint(True)
        skin_required = inp.read_boolean()
        if skin_required:
            pc["skin"] = True

        bone_count = inp.read_varint(True)
        pc["bones"] = [self.bones[inp.read_varint(True)]["name"] for _ in range(bone_count)]

        target_idx = inp.read_varint(True)
        pc["target"] = (
            self.slots[target_idx]["name"]
            if target_idx < len(self.slots)
            else f"slot{target_idx}"
        )

        flags = inp.read_byte()
        position_mode = flags & 1
        spacing_mode = (flags >> 1) & 3
        rotate_mode = (flags >> 3) & 3

        if position_mode < len(POSITION_MODE_NAMES) and position_mode != 0:
            pc["positionMode"] = POSITION_MODE_NAMES[position_mode]
        if spacing_mode < len(SPACING_MODE_NAMES) and spacing_mode != 0:
            pc["spacingMode"] = SPACING_MODE_NAMES[spacing_mode]
        if rotate_mode < len(ROTATE_MODE_NAMES) and rotate_mode != 0:
            pc["rotateMode"] = ROTATE_MODE_NAMES[rotate_mode]

        if flags & 128:
            pc["rotation"] = rf(inp.read_float())

        position = rf(inp.read_float())
        spacing = rf(inp.read_float())
        mix_rotate = rf(inp.read_float())
        mix_x = rf(inp.read_float())
        mix_y = rf(inp.read_float())

        if position:
            pc["position"] = position
        if spacing:
            pc["spacing"] = spacing
        if mix_rotate != 1:
            pc["mixRotate"] = mix_rotate
        if mix_x != 1:
            pc["mixX"] = mix_x
        if mix_y != 1:
            pc["mixY"] = mix_y

        pc["_positionMode"] = position_mode
        pc["_spacingMode"] = spacing_mode
        return pc

    def _read_physics_constraint_data(self, name: str) -> dict:
        inp = self.inp
        ph: dict = {"name": name}
        ph["order"] = inp.read_varint(True)

        bone_idx = inp.read_varint(True)
        ph["bone"] = self.bones[bone_idx]["name"]

        flags = inp.read_byte()
        if flags & 1:
            ph["skin"] = True
        if flags & 2:
            ph["x"] = rf(inp.read_float())
        if flags & 4:
            ph["y"] = rf(inp.read_float())
        if flags & 8:
            ph["rotate"] = rf(inp.read_float())
        if flags & 16:
            ph["scaleX"] = rf(inp.read_float())
        if flags & 32:
            ph["shearX"] = rf(inp.read_float())

        limit = rf(inp.read_float()) if (flags & 64) else 5000
        if limit != 5000:
            ph["limit"] = limit

        step_byte = inp.read_byte()
        step = rf(1.0 / step_byte) if step_byte else 0
        if step:
            ph["step"] = step

        inertia = rf(inp.read_float())
        strength = rf(inp.read_float())
        damping = rf(inp.read_float())

        mass_inv = inp.read_float() if (flags & 128) else 1
        mass = rf(1.0 / mass_inv) if mass_inv != 0 else 0

        wind = rf(inp.read_float())
        gravity = rf(inp.read_float())

        if inertia:
            ph["inertia"] = inertia
        if strength:
            ph["strength"] = strength
        if damping:
            ph["damping"] = damping
        if mass != 1:
            ph["mass"] = mass
        if wind:
            ph["wind"] = wind
        if gravity:
            ph["gravity"] = gravity

        flags2 = inp.read_byte()
        if flags2 & 1:
            ph["inertiaGlobal"] = True
        if flags2 & 2:
            ph["strengthGlobal"] = True
        if flags2 & 4:
            ph["dampingGlobal"] = True
        if flags2 & 8:
            ph["massGlobal"] = True
        if flags2 & 16:
            ph["windGlobal"] = True
        if flags2 & 32:
            ph["gravityGlobal"] = True
        if flags2 & 64:
            ph["mixGlobal"] = True

        mix = rf(inp.read_float()) if (flags2 & 128) else 1
        if mix != 1:
            ph["mix"] = mix
        return ph

    def _read_slider_constraint_data(self, name: str) -> dict:
        """Read slider constraint data (new in Spine 4.3)."""
        inp = self.inp
        sl: dict = {"name": name}
        sl["order"] = inp.read_varint(True)

        bone_idx = inp.read_varint(True)
        sl["bone"] = self.bones[bone_idx]["name"]

        flags = inp.read_byte()
        if flags & 1:
            sl["skin"] = True
        if flags & 2:
            sl["loop"] = True
        if flags & 4:
            sl["additive"] = True

        return sl

    # ── Skins ─────────────────────────────────────────────────────────────

    def _read_skins(self, result: dict):
        inp = self.inp
        skins_json = []

        default_skin = self._read_skin(True)
        if default_skin:
            self.skins.append(default_skin)
            skins_json.append(default_skin)

        n = inp.read_varint(True)
        for _ in range(n):
            skin = self._read_skin(False)
            if skin:
                self.skins.append(skin)
                skins_json.append(skin)

        if skins_json:
            result["skins"] = skins_json

    def _read_skin(self, default_skin: bool) -> dict | None:
        inp = self.inp

        if default_skin:
            slot_count = inp.read_varint(True)
            if slot_count == 0:
                return None
            skin: dict = {"name": "default"}
        else:
            skin = {"name": inp.read_string() or ""}
            if self.nonessential:
                inp.read_color_int()

            # Bone references
            for _ in range(inp.read_varint(True)):
                inp.read_varint(True)

            if self.is_43:
                # 4.3: single unified constraint references array
                for _ in range(inp.read_varint(True)):
                    inp.read_varint(True)
            else:
                # 4.2: separate IK / transform / path / physics refs
                for _ in range(inp.read_varint(True)):
                    inp.read_varint(True)
                for _ in range(inp.read_varint(True)):
                    inp.read_varint(True)
                for _ in range(inp.read_varint(True)):
                    inp.read_varint(True)
                for _ in range(inp.read_varint(True)):
                    inp.read_varint(True)

            slot_count = inp.read_varint(True)

        attachments: dict = {}
        for _ in range(slot_count):
            slot_index = inp.read_varint(True)
            slot_name = (
                self.slots[slot_index]["name"]
                if slot_index < len(self.slots)
                else f"slot{slot_index}"
            )

            slot_attachments: dict = {}
            for _ in range(inp.read_varint(True)):
                attach_name = inp.read_string_ref() or ""
                att_data = self._read_attachment(attach_name)
                if att_data:
                    slot_attachments[attach_name] = att_data

            if slot_attachments:
                attachments[slot_name] = slot_attachments

        if attachments:
            skin["attachments"] = attachments

        return skin

    # ── Attachments ───────────────────────────────────────────────────────

    def _read_attachment(self, attachment_name: str) -> dict | None:
        inp = self.inp
        flags = inp.read_byte()
        name = inp.read_string_ref() if (flags & 8) else attachment_name
        att_type = flags & 0x7

        if att_type == ATTACHMENT_REGION:
            return self._read_region_attachment(name, flags)
        elif att_type == ATTACHMENT_BOUNDINGBOX:
            return self._read_boundingbox_attachment(flags)
        elif att_type == ATTACHMENT_MESH:
            return self._read_mesh_attachment(name, flags)
        elif att_type == ATTACHMENT_LINKEDMESH:
            return self._read_linkedmesh_attachment(name, flags)
        elif att_type == ATTACHMENT_PATH:
            return self._read_path_attachment(flags)
        elif att_type == ATTACHMENT_POINT:
            return self._read_point_attachment()
        elif att_type == ATTACHMENT_CLIPPING:
            return self._read_clipping_attachment(flags)
        else:
            print(
                f"  [WARN] Unknown attachment type {att_type} for '{name}'",
                file=sys.stderr,
            )
            return None

    def _read_region_attachment(self, name: str, flags: int) -> dict:
        inp = self.inp
        att: dict = {}

        path = inp.read_string_ref() if (flags & 16) else None
        color = inp.read_color_int() if (flags & 32) else -1
        sequence = self._read_sequence() if (flags & 64) else None
        rotation = rf(inp.read_float()) if (flags & 128) else 0
        x = rf(inp.read_float())
        y = rf(inp.read_float())
        scale_x = rf(inp.read_float())
        scale_y = rf(inp.read_float())
        width = rf(inp.read_float())
        height = rf(inp.read_float())

        if name and path and path != name:
            att["name"] = name
            att["path"] = path
        if path and path != name:
            att["path"] = path
        if rotation:
            att["rotation"] = rotation
        if x:
            att["x"] = x
        if y:
            att["y"] = y
        if scale_x != 1:
            att["scaleX"] = scale_x
        if scale_y != 1:
            att["scaleY"] = scale_y
        att["width"] = width
        att["height"] = height

        color_hex = int32_to_rgba_hex(color)
        if color_hex != "ffffffff":
            att["color"] = color_hex
        if sequence:
            att["sequence"] = sequence

        return att

    def _read_boundingbox_attachment(self, flags: int) -> dict:
        att: dict = {"type": "boundingbox"}
        vertices = self._read_vertices((flags & 16) != 0)
        att["vertexCount"] = vertices["count"]
        att["vertices"] = vertices["vertices"]
        if self.nonessential:
            self.inp.read_color_int()
        return att

    def _read_mesh_attachment(self, name: str, flags: int) -> dict:
        inp = self.inp
        att: dict = {"type": "mesh"}

        path = inp.read_string_ref() if (flags & 16) else name
        color = inp.read_color_int() if (flags & 32) else -1
        sequence = self._read_sequence() if (flags & 64) else None
        hull_length = inp.read_varint(True)

        vertices = self._read_vertices((flags & 128) != 0)
        uvs = [rf(inp.read_float()) for _ in range(vertices["length"])]
        tri_count = (vertices["length"] - hull_length - 2) * 3
        triangles = [inp.read_varint(True) for _ in range(tri_count)]

        edges: list = []
        width = 0
        height = 0
        if self.nonessential:
            edge_count = inp.read_varint(True)
            edges = [inp.read_varint(True) for _ in range(edge_count)]
            width = rf(inp.read_float())
            height = rf(inp.read_float())

        if path and path != name:
            att["path"] = path
        att["uvs"] = uvs
        att["triangles"] = triangles
        att["vertices"] = vertices["vertices"]
        att["hull"] = hull_length

        color_hex = int32_to_rgba_hex(color)
        if color_hex != "ffffffff":
            att["color"] = color_hex
        if edges:
            att["edges"] = edges
        if width:
            att["width"] = width
        if height:
            att["height"] = height
        if sequence:
            att["sequence"] = sequence

        return att

    def _read_linkedmesh_attachment(self, name: str, flags: int) -> dict:
        inp = self.inp
        att: dict = {"type": "linkedmesh"}

        path = inp.read_string_ref() if (flags & 16) else name
        color = inp.read_color_int() if (flags & 32) else -1
        sequence = self._read_sequence() if (flags & 64) else None
        inherit_timelines = (flags & 128) != 0
        skin_index = inp.read_varint(True)
        parent = inp.read_string_ref() or ""

        width = 0
        height = 0
        if self.nonessential:
            width = rf(inp.read_float())
            height = rf(inp.read_float())

        if path and path != name:
            att["path"] = path

        color_hex = int32_to_rgba_hex(color)
        if color_hex != "ffffffff":
            att["color"] = color_hex

        if skin_index < len(self.skins):
            att["skin"] = self.skins[skin_index]["name"]
        elif skin_index == 0:
            att["skin"] = "default"

        att["parent"] = parent
        if inherit_timelines:
            att["timelines"] = True
        if width:
            att["width"] = width
        if height:
            att["height"] = height
        if sequence:
            att["sequence"] = sequence

        return att

    def _read_path_attachment(self, flags: int) -> dict:
        inp = self.inp
        att: dict = {"type": "path"}

        closed = (flags & 16) != 0
        constant_speed = (flags & 32) != 0

        vertices = self._read_vertices((flags & 64) != 0)
        length_count = vertices["length"] // 6
        lengths = [rf(inp.read_float()) for _ in range(length_count)]

        if self.nonessential:
            inp.read_color_int()

        if closed:
            att["closed"] = True
        if not constant_speed:
            att["constantSpeed"] = False
        att["vertexCount"] = vertices["count"]
        att["vertices"] = vertices["vertices"]
        att["lengths"] = lengths

        return att

    def _read_point_attachment(self) -> dict:
        inp = self.inp
        att: dict = {"type": "point"}

        rotation = rf(inp.read_float())
        x = rf(inp.read_float())
        y = rf(inp.read_float())

        if self.nonessential:
            inp.read_color_int()

        if rotation:
            att["rotation"] = rotation
        if x:
            att["x"] = x
        if y:
            att["y"] = y

        return att

    def _read_clipping_attachment(self, flags: int) -> dict:
        inp = self.inp
        att: dict = {"type": "clipping"}

        end_slot_index = inp.read_varint(True)
        vertices = self._read_vertices((flags & 16) != 0)

        if self.nonessential:
            inp.read_color_int()

        if end_slot_index < len(self.slots):
            att["end"] = self.slots[end_slot_index]["name"]
        att["vertexCount"] = vertices["count"]
        att["vertices"] = vertices["vertices"]

        return att

    def _read_vertices(self, weighted: bool) -> dict:
        inp = self.inp
        vertex_count = inp.read_varint(True)
        length = vertex_count << 1

        if not weighted:
            verts = [rf(inp.read_float()) for _ in range(length)]
            return {"vertices": verts, "length": length, "count": vertex_count, "weighted": False}

        verts: list = []
        for _ in range(vertex_count):
            bone_count = inp.read_varint(True)
            verts.append(bone_count)
            for _ in range(bone_count):
                verts.append(inp.read_varint(True))
                verts.append(rf(inp.read_float()))
                verts.append(rf(inp.read_float()))
                verts.append(rf(inp.read_float()))

        return {"vertices": verts, "length": length, "count": vertex_count, "weighted": True}

    def _read_sequence(self) -> dict:
        inp = self.inp
        return {
            "count": inp.read_varint(True),
            "start": inp.read_varint(True),
            "digits": inp.read_varint(True),
            "setup": inp.read_varint(True),
        }

    # ── Events ────────────────────────────────────────────────────────────

    def _read_events(self, result: dict):
        inp = self.inp
        n = inp.read_varint(True)
        events_json: dict = {}

        for _ in range(n):
            event: dict = {}
            name = inp.read_string() or ""
            int_val = inp.read_varint(False)
            float_val = rf(inp.read_float())
            string_val = inp.read_string()
            audio_path = inp.read_string()

            if int_val:
                event["int"] = int_val
            if float_val:
                event["float"] = float_val
            if string_val:
                event["string"] = string_val
            if audio_path:
                event["audio"] = audio_path
                event["volume"] = rf(inp.read_float())
                event["balance"] = rf(inp.read_float())

            self.events.append({"name": name, **event})
            events_json[name] = event if event else {}

        if events_json:
            result["events"] = events_json

    # ── Animations ────────────────────────────────────────────────────────

    def _read_animations(self, result: dict):
        inp = self.inp
        n = inp.read_varint(True)
        animations: dict = {}

        for _ in range(n):
            anim_name = inp.read_string() or ""
            anim = self._read_animation()
            animations[anim_name] = anim

        if animations:
            result["animations"] = animations

    def _read_animation(self) -> dict:
        inp = self.inp
        anim: dict = {}

        inp.read_varint(True)  # timeline count

        # ── Slot timelines ──
        slots_data: dict = {}
        for _ in range(inp.read_varint(True)):
            slot_index = inp.read_varint(True)
            slot_name = (
                self.slots[slot_index]["name"]
                if slot_index < len(self.slots)
                else f"slot{slot_index}"
            )
            slot_tls: dict = {}

            for _ in range(inp.read_varint(True)):
                tl_type = inp.read_byte()
                frame_count = inp.read_varint(True)
                frame_last = frame_count - 1

                if tl_type == SLOT_ATTACHMENT:
                    slot_tls["attachment"] = self._read_attachment_timeline(frame_count)
                elif tl_type == SLOT_RGBA:
                    slot_tls["rgba"] = self._read_rgba_timeline(frame_count, frame_last)
                elif tl_type == SLOT_RGB:
                    slot_tls["rgb"] = self._read_rgb_timeline(frame_count, frame_last)
                elif tl_type == SLOT_RGBA2:
                    slot_tls["rgba2"] = self._read_rgba2_timeline(frame_count, frame_last)
                elif tl_type == SLOT_RGB2:
                    slot_tls["rgb2"] = self._read_rgb2_timeline(frame_count, frame_last)
                elif tl_type == SLOT_ALPHA:
                    slot_tls["alpha"] = self._read_alpha_timeline(frame_count, frame_last)

            if slot_tls:
                slots_data[slot_name] = slot_tls

        if slots_data:
            anim["slots"] = slots_data

        # ── Bone timelines ──
        bones_data: dict = {}
        for _ in range(inp.read_varint(True)):
            bone_index = inp.read_varint(True)
            bone_name = (
                self.bones[bone_index]["name"]
                if bone_index < len(self.bones)
                else f"bone{bone_index}"
            )
            bone_tls: dict = {}

            for _ in range(inp.read_varint(True)):
                tl_type = inp.read_byte()
                frame_count = inp.read_varint(True)
                frame_last = frame_count - 1
                tl_name = BONE_TIMELINE_NAMES.get(tl_type, f"unknown{tl_type}")

                if tl_type == BONE_INHERIT:
                    bone_tls[tl_name] = self._read_inherit_timeline(frame_count)
                elif tl_type in (
                    BONE_ROTATE,
                    BONE_TRANSLATEX,
                    BONE_TRANSLATEY,
                    BONE_SCALEX,
                    BONE_SCALEY,
                    BONE_SHEARX,
                    BONE_SHEARY,
                ):
                    inp.read_varint(True)  # bezier count
                    default_val = 1 if tl_type in (BONE_SCALEX, BONE_SCALEY) else 0
                    bone_tls[tl_name] = self._read_timeline1(
                        frame_count, frame_last, "value", default_val
                    )
                elif tl_type in (BONE_TRANSLATE, BONE_SCALE, BONE_SHEAR):
                    inp.read_varint(True)  # bezier count
                    default_val = 1 if tl_type == BONE_SCALE else 0
                    bone_tls[tl_name] = self._read_timeline2(
                        frame_count, frame_last, "x", "y", default_val
                    )

            if bone_tls:
                bones_data[bone_name] = bone_tls

        if bones_data:
            anim["bones"] = bones_data

        # ── IK constraint timelines ──
        ik_data: dict = {}
        for _ in range(inp.read_varint(True)):
            index = inp.read_varint(True)
            name = (
                self.ik_constraints[index]["name"]
                if index < len(self.ik_constraints)
                else f"ik{index}"
            )
            frame_count = inp.read_varint(True)
            frame_last = frame_count - 1
            inp.read_varint(True)  # bezier count

            flags = inp.read_byte()
            time = inp.read_float()
            mix = ((inp.read_float() if (flags & 2) else 1.0) if (flags & 1) else 0.0)
            softness = inp.read_float() if (flags & 4) else 0.0

            frames: list = []
            for frame in range(frame_count):
                f: dict = {}
                if rf(time):
                    f["time"] = rf(time)
                if rf(mix) != 1:
                    f["mix"] = rf(mix)
                if rf(softness):
                    f["softness"] = rf(softness)
                if not (flags & 8):
                    f["bendPositive"] = False
                if flags & 16:
                    f["compress"] = True
                if flags & 32:
                    f["stretch"] = True

                if frame == frame_last:
                    frames.append(f)
                    break

                flags = inp.read_byte()
                time2 = inp.read_float()
                mix2 = ((inp.read_float() if (flags & 2) else 1.0) if (flags & 1) else 0.0)
                softness2 = inp.read_float() if (flags & 4) else 0.0

                if flags & 64:
                    f["curve"] = "stepped"
                elif flags & 128:
                    curve = []
                    for _ in range(2):
                        curve.extend([
                            rf(inp.read_float()),
                            rf(inp.read_float()),
                            rf(inp.read_float()),
                            rf(inp.read_float()),
                        ])
                    f["curve"] = curve

                frames.append(f)
                time, mix, softness = time2, mix2, softness2

            ik_data[name] = frames

        if ik_data:
            anim["ik"] = ik_data

        # ── Transform constraint timelines ──
        transform_data: dict = {}
        for _ in range(inp.read_varint(True)):
            index = inp.read_varint(True)
            name = (
                self.transform_constraints[index]["name"]
                if index < len(self.transform_constraints)
                else f"tc{index}"
            )
            frame_count = inp.read_varint(True)
            frame_last = frame_count - 1
            inp.read_varint(True)  # bezier count

            time = inp.read_float()
            mix_rotate = inp.read_float()
            mix_x = inp.read_float()
            mix_y = inp.read_float()
            mix_scale_x = inp.read_float()
            mix_scale_y = inp.read_float()
            mix_shear_y = inp.read_float()

            frames = []
            for frame in range(frame_count):
                f = {}
                if rf(time):
                    f["time"] = rf(time)
                if rf(mix_rotate) != 1:
                    f["mixRotate"] = rf(mix_rotate)
                if rf(mix_x) != 1:
                    f["mixX"] = rf(mix_x)
                if rf(mix_y) != 1:
                    f["mixY"] = rf(mix_y)
                if rf(mix_scale_x) != 1:
                    f["mixScaleX"] = rf(mix_scale_x)
                if rf(mix_scale_y) != 1:
                    f["mixScaleY"] = rf(mix_scale_y)
                if rf(mix_shear_y):
                    f["mixShearY"] = rf(mix_shear_y)

                if frame == frame_last:
                    frames.append(f)
                    break

                time2 = inp.read_float()
                vals = [inp.read_float() for _ in range(6)]
                curve_type = inp.read_byte()

                if curve_type == CURVE_STEPPED:
                    f["curve"] = "stepped"
                elif curve_type == CURVE_BEZIER:
                    curve = []
                    for _ in range(6):
                        curve.extend([
                            rf(inp.read_float()),
                            rf(inp.read_float()),
                            rf(inp.read_float()),
                            rf(inp.read_float()),
                        ])
                    f["curve"] = curve

                frames.append(f)
                time = time2
                mix_rotate, mix_x, mix_y, mix_scale_x, mix_scale_y, mix_shear_y = vals

            transform_data[name] = frames

        if transform_data:
            anim["transform"] = transform_data

        # ── Path constraint timelines ──
        path_data: dict = {}
        for _ in range(inp.read_varint(True)):
            index = inp.read_varint(True)
            pc = self.path_constraints[index] if index < len(self.path_constraints) else {}
            name = pc.get("name", f"pc{index}")
            pc_tls: dict = {}

            for _ in range(inp.read_varint(True)):
                tl_type = inp.read_byte()
                frame_count = inp.read_varint(True)
                frame_last = frame_count - 1
                inp.read_varint(True)  # bezier count

                if tl_type == PATH_POSITION:
                    pc_tls["position"] = self._read_timeline1(frame_count, frame_last, "value", 0)
                elif tl_type == PATH_SPACING:
                    pc_tls["spacing"] = self._read_timeline1(frame_count, frame_last, "value", 0)
                elif tl_type == PATH_MIX:
                    pc_tls["mix"] = self._read_path_mix_timeline(frame_count, frame_last)

            if pc_tls:
                path_data[name] = pc_tls

        if path_data:
            anim["path"] = path_data

        # ── Physics constraint timelines ──
        physics_data: dict = {}
        _type_names = {
            PHYSICS_INERTIA: "inertia",
            PHYSICS_STRENGTH: "strength",
            PHYSICS_DAMPING: "damping",
            PHYSICS_MASS: "mass",
            PHYSICS_WIND: "wind",
            PHYSICS_GRAVITY: "gravity",
            PHYSICS_MIX: "mix",
            PHYSICS_RESET: "reset",
        }
        for _ in range(inp.read_varint(True)):
            index = inp.read_varint(True) - 1
            name = (
                self.physics_constraints[index]["name"]
                if 0 <= index < len(self.physics_constraints)
                else f"ph{index}"
            )
            ph_tls: dict = {}

            for _ in range(inp.read_varint(True)):
                tl_type = inp.read_byte()
                frame_count = inp.read_varint(True)
                tl_name = _type_names.get(tl_type, f"type{tl_type}")

                if tl_type == PHYSICS_RESET:
                    frames = []
                    for _ in range(frame_count):
                        f = {}
                        t = rf(inp.read_float())
                        if t:
                            f["time"] = t
                        frames.append(f)
                    ph_tls[tl_name] = frames
                else:
                    frame_last = frame_count - 1
                    inp.read_varint(True)  # bezier count
                    ph_tls[tl_name] = self._read_timeline1(frame_count, frame_last, "value", 0)

            if ph_tls:
                physics_data[name] = ph_tls

        if physics_data:
            anim["physics"] = physics_data

        # ── Slider constraint timelines (4.3 only) ──
        if self.is_43:
            _SLIDER_TIME = 0
            _SLIDER_MIX = 1
            for _ in range(inp.read_varint(True)):
                inp.read_varint(True)  # index
                for _ in range(inp.read_varint(True)):
                    tl_type = inp.read_byte()
                    frame_count = inp.read_varint(True)
                    frame_last = frame_count - 1
                    inp.read_varint(True)  # bezier count
                    default = 1 if tl_type == _SLIDER_MIX else 0
                    self._read_timeline1(frame_count, frame_last, "value", default)

        # ── Attachment timelines (deform / sequence) ──
        att_data: dict = {}
        for _ in range(inp.read_varint(True)):
            skin_index = inp.read_varint(True)
            skin_name = (
                self.skins[skin_index]["name"]
                if skin_index < len(self.skins)
                else f"skin{skin_index}"
            )

            for _ in range(inp.read_varint(True)):
                slot_index = inp.read_varint(True)
                slot_name = (
                    self.slots[slot_index]["name"]
                    if slot_index < len(self.slots)
                    else f"slot{slot_index}"
                )

                for _ in range(inp.read_varint(True)):
                    attach_name = inp.read_string_ref() or ""
                    tl_type = inp.read_byte()
                    frame_count = inp.read_varint(True)
                    frame_last = frame_count - 1

                    if tl_type == ATTACHMENT_DEFORM:
                        frames = self._read_deform_timeline(frame_count, frame_last)
                        att_data.setdefault(skin_name, {}).setdefault(
                            slot_name, {}
                        ).setdefault(attach_name, {})["deform"] = frames

                    elif tl_type == ATTACHMENT_SEQUENCE:
                        frames = self._read_sequence_timeline(frame_count)
                        att_data.setdefault(skin_name, {}).setdefault(
                            slot_name, {}
                        ).setdefault(attach_name, {})["sequence"] = frames

        if att_data:
            anim["attachments"] = att_data

        # ── Draw order timelines ──
        draw_order_count = inp.read_varint(True)
        if draw_order_count:
            draw_orders = []
            for _ in range(draw_order_count):
                time = rf(inp.read_float())
                offset_count = inp.read_varint(True)
                f: dict = {}
                if time:
                    f["time"] = time

                if offset_count > 0:
                    offsets = []
                    for _ in range(offset_count):
                        si = inp.read_varint(True)
                        off = inp.read_varint(True)
                        offsets.append({
                            "slot": (
                                self.slots[si]["name"]
                                if si < len(self.slots)
                                else f"slot{si}"
                            ),
                            "offset": off,
                        })
                    f["offsets"] = offsets

                draw_orders.append(f)
            anim["drawOrder"] = draw_orders

        # ── Event timelines ──
        event_count = inp.read_varint(True)
        if event_count:
            event_frames = []
            for _ in range(event_count):
                time = rf(inp.read_float())
                event_index = inp.read_varint(True)
                event_data = (
                    self.events[event_index] if event_index < len(self.events) else {}
                )

                int_val = inp.read_varint(False)
                float_val = rf(inp.read_float())
                string_val = inp.read_string()

                f = {}
                if time:
                    f["time"] = time
                f["name"] = event_data.get("name", "")

                if int_val != event_data.get("int", 0):
                    f["int"] = int_val
                if float_val != event_data.get("float", 0):
                    f["float"] = float_val
                if string_val is not None and string_val != event_data.get("string", ""):
                    f["string"] = string_val

                if event_data.get("audio"):
                    volume = rf(inp.read_float())
                    balance = rf(inp.read_float())
                    if volume != event_data.get("volume", 0):
                        f["volume"] = volume
                    if balance != event_data.get("balance", 0):
                        f["balance"] = balance

                event_frames.append(f)
            anim["events"] = event_frames

        return anim

    # ── Animation timeline readers ────────────────────────────────────────

    def _read_attachment_timeline(self, frame_count: int) -> list:
        inp = self.inp
        frames = []
        for _ in range(frame_count):
            time = rf(inp.read_float())
            name = inp.read_string_ref()
            f: dict = {}
            if time:
                f["time"] = time
            f["name"] = name
            frames.append(f)
        return frames

    def _read_rgba_timeline(self, frame_count: int, frame_last: int) -> list:
        inp = self.inp
        inp.read_varint(True)  # bezier count
        time = inp.read_float()
        r, g, b, a = inp.read_byte(), inp.read_byte(), inp.read_byte(), inp.read_byte()

        frames = []
        for frame in range(frame_count):
            f: dict = {}
            if rf(time):
                f["time"] = rf(time)
            f["color"] = color_to_rgba_hex(r, g, b, a)

            if frame == frame_last:
                frames.append(f)
                break

            time2 = inp.read_float()
            nr, ng, nb, na = inp.read_byte(), inp.read_byte(), inp.read_byte(), inp.read_byte()
            curve_type = inp.read_byte()

            if curve_type == CURVE_STEPPED:
                f["curve"] = "stepped"
            elif curve_type == CURVE_BEZIER:
                curve = []
                for _ in range(4):
                    curve.extend([rf(inp.read_float()), rf(inp.read_float()),
                                  rf(inp.read_float()), rf(inp.read_float())])
                f["curve"] = curve

            frames.append(f)
            time, r, g, b, a = time2, nr, ng, nb, na

        return frames

    def _read_rgb_timeline(self, frame_count: int, frame_last: int) -> list:
        inp = self.inp
        inp.read_varint(True)
        time = inp.read_float()
        r, g, b = inp.read_byte(), inp.read_byte(), inp.read_byte()

        frames = []
        for frame in range(frame_count):
            f: dict = {}
            if rf(time):
                f["time"] = rf(time)
            f["color"] = color_to_rgb_hex(r, g, b)

            if frame == frame_last:
                frames.append(f)
                break

            time2 = inp.read_float()
            nr, ng, nb = inp.read_byte(), inp.read_byte(), inp.read_byte()
            curve_type = inp.read_byte()

            if curve_type == CURVE_STEPPED:
                f["curve"] = "stepped"
            elif curve_type == CURVE_BEZIER:
                curve = []
                for _ in range(3):
                    curve.extend([rf(inp.read_float()), rf(inp.read_float()),
                                  rf(inp.read_float()), rf(inp.read_float())])
                f["curve"] = curve

            frames.append(f)
            time, r, g, b = time2, nr, ng, nb

        return frames

    def _read_rgba2_timeline(self, frame_count: int, frame_last: int) -> list:
        inp = self.inp
        inp.read_varint(True)
        time = inp.read_float()
        r, g, b, a = inp.read_byte(), inp.read_byte(), inp.read_byte(), inp.read_byte()
        r2, g2, b2 = inp.read_byte(), inp.read_byte(), inp.read_byte()

        frames = []
        for frame in range(frame_count):
            f: dict = {}
            if rf(time):
                f["time"] = rf(time)
            f["light"] = color_to_rgba_hex(r, g, b, a)
            f["dark"] = color_to_rgb_hex(r2, g2, b2)

            if frame == frame_last:
                frames.append(f)
                break

            time2 = inp.read_float()
            nr, ng, nb, na = inp.read_byte(), inp.read_byte(), inp.read_byte(), inp.read_byte()
            nr2, ng2, nb2 = inp.read_byte(), inp.read_byte(), inp.read_byte()
            curve_type = inp.read_byte()

            if curve_type == CURVE_STEPPED:
                f["curve"] = "stepped"
            elif curve_type == CURVE_BEZIER:
                curve = []
                for _ in range(7):
                    curve.extend([rf(inp.read_float()), rf(inp.read_float()),
                                  rf(inp.read_float()), rf(inp.read_float())])
                f["curve"] = curve

            frames.append(f)
            time = time2
            r, g, b, a = nr, ng, nb, na
            r2, g2, b2 = nr2, ng2, nb2

        return frames

    def _read_rgb2_timeline(self, frame_count: int, frame_last: int) -> list:
        inp = self.inp
        inp.read_varint(True)
        time = inp.read_float()
        r, g, b = inp.read_byte(), inp.read_byte(), inp.read_byte()
        r2, g2, b2 = inp.read_byte(), inp.read_byte(), inp.read_byte()

        frames = []
        for frame in range(frame_count):
            f: dict = {}
            if rf(time):
                f["time"] = rf(time)
            f["light"] = color_to_rgb_hex(r, g, b)
            f["dark"] = color_to_rgb_hex(r2, g2, b2)

            if frame == frame_last:
                frames.append(f)
                break

            time2 = inp.read_float()
            nr, ng, nb = inp.read_byte(), inp.read_byte(), inp.read_byte()
            nr2, ng2, nb2 = inp.read_byte(), inp.read_byte(), inp.read_byte()
            curve_type = inp.read_byte()

            if curve_type == CURVE_STEPPED:
                f["curve"] = "stepped"
            elif curve_type == CURVE_BEZIER:
                curve = []
                for _ in range(6):
                    curve.extend([rf(inp.read_float()), rf(inp.read_float()),
                                  rf(inp.read_float()), rf(inp.read_float())])
                f["curve"] = curve

            frames.append(f)
            time = time2
            r, g, b = nr, ng, nb
            r2, g2, b2 = nr2, ng2, nb2

        return frames

    def _read_alpha_timeline(self, frame_count: int, frame_last: int) -> list:
        inp = self.inp
        inp.read_varint(True)
        time = inp.read_float()
        a = inp.read_byte() / 255.0

        frames = []
        for frame in range(frame_count):
            f: dict = {}
            if rf(time):
                f["time"] = rf(time)
            if rf(a) != 1:
                f["alpha"] = rf(a)

            if frame == frame_last:
                frames.append(f)
                break

            time2 = inp.read_float()
            na = inp.read_byte() / 255.0
            curve_type = inp.read_byte()

            if curve_type == CURVE_STEPPED:
                f["curve"] = "stepped"
            elif curve_type == CURVE_BEZIER:
                f["curve"] = [
                    rf(inp.read_float()), rf(inp.read_float()),
                    rf(inp.read_float()), rf(inp.read_float()),
                ]

            frames.append(f)
            time, a = time2, na

        return frames

    def _read_inherit_timeline(self, frame_count: int) -> list:
        inp = self.inp
        frames = []
        for _ in range(frame_count):
            f: dict = {}
            time = rf(inp.read_float())
            inherit = inp.read_byte()
            if time:
                f["time"] = time
            if inherit < len(INHERIT_NAMES):
                f["value"] = INHERIT_NAMES[inherit]
            frames.append(f)
        return frames

    def _read_timeline1(
        self, frame_count: int, frame_last: int, value_key: str, default_value
    ) -> list:
        """Read single-value timeline (rotate, translatex, etc.)."""
        inp = self.inp
        time = inp.read_float()
        value = inp.read_float()

        frames = []
        for frame in range(frame_count):
            f: dict = {}
            if rf(time):
                f["time"] = rf(time)
            if rf(value) != default_value:
                f[value_key] = rf(value)

            if frame == frame_last:
                frames.append(f)
                break

            time2 = inp.read_float()
            value2 = inp.read_float()
            curve_type = inp.read_byte()

            if curve_type == CURVE_STEPPED:
                f["curve"] = "stepped"
            elif curve_type == CURVE_BEZIER:
                f["curve"] = [
                    rf(inp.read_float()), rf(inp.read_float()),
                    rf(inp.read_float()), rf(inp.read_float()),
                ]

            frames.append(f)
            time, value = time2, value2

        return frames

    def _read_timeline2(
        self, frame_count: int, frame_last: int, key1: str, key2: str, default_value
    ) -> list:
        """Read dual-value timeline (translate, scale, shear)."""
        inp = self.inp
        time = inp.read_float()
        value1 = inp.read_float()
        value2 = inp.read_float()

        frames = []
        for frame in range(frame_count):
            f: dict = {}
            if rf(time):
                f["time"] = rf(time)
            if rf(value1) != default_value:
                f[key1] = rf(value1)
            if rf(value2) != default_value:
                f[key2] = rf(value2)

            if frame == frame_last:
                frames.append(f)
                break

            time2 = inp.read_float()
            nv1 = inp.read_float()
            nv2 = inp.read_float()
            curve_type = inp.read_byte()

            if curve_type == CURVE_STEPPED:
                f["curve"] = "stepped"
            elif curve_type == CURVE_BEZIER:
                curve = []
                for _ in range(2):
                    curve.extend([
                        rf(inp.read_float()), rf(inp.read_float()),
                        rf(inp.read_float()), rf(inp.read_float()),
                    ])
                f["curve"] = curve

            frames.append(f)
            time, value1, value2 = time2, nv1, nv2

        return frames

    def _read_path_mix_timeline(self, frame_count: int, frame_last: int) -> list:
        inp = self.inp
        time = inp.read_float()
        mix_rotate = inp.read_float()
        mix_x = inp.read_float()
        mix_y = inp.read_float()

        frames = []
        for frame in range(frame_count):
            f: dict = {}
            if rf(time):
                f["time"] = rf(time)
            if rf(mix_rotate) != 1:
                f["mixRotate"] = rf(mix_rotate)
            if rf(mix_x) != 1:
                f["mixX"] = rf(mix_x)
            if rf(mix_y) != 1:
                f["mixY"] = rf(mix_y)

            if frame == frame_last:
                frames.append(f)
                break

            time2 = inp.read_float()
            nmr = inp.read_float()
            nmx = inp.read_float()
            nmy = inp.read_float()
            curve_type = inp.read_byte()

            if curve_type == CURVE_STEPPED:
                f["curve"] = "stepped"
            elif curve_type == CURVE_BEZIER:
                curve = []
                for _ in range(3):
                    curve.extend([
                        rf(inp.read_float()), rf(inp.read_float()),
                        rf(inp.read_float()), rf(inp.read_float()),
                    ])
                f["curve"] = curve

            frames.append(f)
            time, mix_rotate, mix_x, mix_y = time2, nmr, nmx, nmy

        return frames

    def _read_deform_timeline(self, frame_count: int, frame_last: int) -> list:
        inp = self.inp
        inp.read_varint(True)  # bezier count
        time = inp.read_float()

        frames = []
        for frame in range(frame_count):
            f: dict = {}
            if rf(time):
                f["time"] = rf(time)

            end_count = inp.read_varint(True)
            if end_count > 0:
                start = inp.read_varint(True)
                verts = [rf(inp.read_float()) for _ in range(end_count)]
                if start > 0:
                    f["offset"] = start
                f["vertices"] = verts

            if frame == frame_last:
                frames.append(f)
                break

            time2 = inp.read_float()
            curve_type = inp.read_byte()

            if curve_type == CURVE_STEPPED:
                f["curve"] = "stepped"
            elif curve_type == CURVE_BEZIER:
                f["curve"] = [
                    rf(inp.read_float()), rf(inp.read_float()),
                    rf(inp.read_float()), rf(inp.read_float()),
                ]

            frames.append(f)
            time = time2

        return frames

    def _read_sequence_timeline(self, frame_count: int) -> list:
        inp = self.inp
        frames = []
        for _ in range(frame_count):
            f: dict = {}
            time = rf(inp.read_float())
            mode_and_index = inp.read_int32()
            mode = mode_and_index & 0xF
            index = mode_and_index >> 4
            delay = rf(inp.read_float())

            if time:
                f["time"] = time
            if mode < len(SEQUENCE_MODE_NAMES):
                f["mode"] = SEQUENCE_MODE_NAMES[mode]
            f["index"] = index
            if delay:
                f["delay"] = delay
            frames.append(f)
        return frames


# ─── Public API ───────────────────────────────────────────────────────────────


def convert_skel_to_json(
    skel_path: str,
    json_path: str | None = None,
    indent: str = "\t",
) -> dict:
    """Convert a .skel file to .json.

    Args:
        skel_path: Path to the input .skel file.
        json_path: Output .json path.  Defaults to ``<skel_path>.json``.
        indent: JSON indentation string.

    Returns:
        The converted skeleton data as a dict.
    """
    skel_path_p = Path(skel_path)
    json_path_p = Path(json_path) if json_path else skel_path_p.with_suffix(".json")

    print(f"Reading: {skel_path_p}")
    data = skel_path_p.read_bytes()

    converter = SkelConverter()
    try:
        result = converter.convert(data)
    except Exception as e:
        print(f"  [ERROR] Failed to parse: {e}", file=sys.stderr)
        raise

    json_path_p.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path_p, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=indent, ensure_ascii=False)

    print(f"  -> {json_path_p} ({json_path_p.stat().st_size:,} bytes)")
    return result


def convert_directory(dir_path: str, output_dir: str | None = None):
    """Convert all .skel files in a directory."""
    dir_path_p = Path(dir_path)
    output_dir_p = Path(output_dir) if output_dir else dir_path_p

    skel_files = list(dir_path_p.glob("*.skel"))
    if not skel_files:
        print(f"No .skel files found in {dir_path_p}")
        return

    print(f"Found {len(skel_files)} .skel files in {dir_path_p}")
    success = 0
    failed = 0

    for skel_file in sorted(skel_files):
        json_file = output_dir_p / skel_file.with_suffix(".json").name
        try:
            convert_skel_to_json(str(skel_file), str(json_file))
            success += 1
        except Exception as e:
            print(f"  [FAILED] {skel_file.name}: {e}", file=sys.stderr)
            failed += 1

    print(f"\nDone: {success} converted, {failed} failed")
