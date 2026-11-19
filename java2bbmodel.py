#!/usr/bin/env python3
"""Convert Minecraft Java entity model classes into Blockbench .bbmodel projects."""

from __future__ import annotations

import argparse
import ast
import json
import math
import re
import sys
import uuid
from pathlib import Path

Y_ORIGIN = 24.0


def strip_java(src):
    out = []
    i, n = 0, len(src)
    while i < n:
        ch = src[i]
        if ch in "\"'":
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == ch:
                    j += 1
                    break
                j += 1
            out.append('""' if ch == '"' else "''")
            i = j
        elif src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _eval_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _eval_node(node.operand)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp):
        left, right = _eval_node(node.left), _eval_node(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            return left ** right
    if isinstance(node, ast.Name) and node.id == "pi":
        return math.pi
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "rad":
        return math.radians(_eval_node(node.args[0]))
    raise ValueError("not a constant expression")


def to_number(expr):
    text = re.sub(r"(?<=[\d.])([fFdD])\b", "", expr.strip())
    text = text.replace("Math.toRadians", "rad").replace("Math.PI", "pi")
    text = re.sub(r"\((?:float|double|int|long)\)", "", text)
    text = re.sub(r"\s+", "", text)
    if not text:
        return None
    try:
        return _eval_node(ast.parse(text, mode="eval").body)
    except Exception:
        return None


def matching_paren(text, start):
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return len(text) - 1


def split_args(text):
    args, depth, current = [], 0, []
    for ch in text:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            args.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    tail = "".join(current).strip()
    if tail:
        args.append(tail)
    return args


def iter_calls(stmt):
    i = 0
    while True:
        open_at = stmt.find("(", i)
        if open_at < 0:
            return
        cursor = open_at - 1
        while cursor >= 0 and stmt[cursor].isspace():
            cursor -= 1
        name_end = cursor + 1
        while cursor >= 0 and (stmt[cursor].isalnum() or stmt[cursor] == "_"):
            cursor -= 1
        name = stmt[cursor + 1:name_end]
        close_at = matching_paren(stmt, open_at)
        if not name:
            for call in iter_calls(stmt[open_at + 1:close_at]):
                yield call
            i = close_at + 1
            continue
        owner = None
        probe = cursor
        while probe >= 0 and stmt[probe].isspace():
            probe -= 1
        if probe >= 0 and stmt[probe] == ".":
            probe -= 1
            while probe >= 0 and stmt[probe].isspace():
                probe -= 1
            owner_end = probe + 1
            while probe >= 0 and (stmt[probe].isalnum() or stmt[probe] == "_"):
                probe -= 1
            owner = stmt[probe + 1:owner_end] or None
        yield owner, name, stmt[open_at + 1:close_at]
        i = close_at + 1


def constructor_body(code, class_name):
    pattern = r"\b" + re.escape(class_name) + r"\s*\([^()]*\)\s*\{"
    found = re.search(pattern, code)
    if not found:
        found = re.search(r"\b(?:public|protected|private)\s+[\w.]+\s*\(\s*\)\s*\{", code)
    if not found:
        return ""
    start = code.index("{", found.end() - 1)
    depth = 0
    for i in range(start, len(code)):
        if code[i] == "{":
            depth += 1
        elif code[i] == "}":
            depth -= 1
            if depth == 0:
                return code[start + 1:i]
    return code[start + 1:]


class Box:
    def __init__(self, x, y, z, w, h, d, uv, inflate=0.0, mirror=False):
        self.x, self.y, self.z = x, y, z
        self.w, self.h, self.d = w, h, d
        self.uv = uv
        self.inflate = inflate
        self.mirror = mirror


class Bone:
    def __init__(self, name):
        self.name = name
        self.parent = None
        self.pivot = (0.0, 0.0, 0.0)
        self.rot = (0.0, 0.0, 0.0)
        self.uv = (0, 0)
        self.mirror = False
        self.boxes = []


class Model:
    def __init__(self, name):
        self.name = name
        self.width = 64
        self.height = 32
        self.bones = {}
        self.order = []
        self.animated = set()

    def bone(self, name):
        if name not in self.bones:
            self.bones[name] = Bone(name)
            self.order.append(name)
        return self.bones[name]

    def parse(self, src):
        code = strip_java(src)
        class_match = re.search(r"\bclass\s+(\w+)", code)
        if class_match:
            self.name = class_match.group(1)
        for field in re.finditer(r"\b\w*ModelRenderer\s+(\w+)\s*[;=]", code):
            self.bone(field.group(1))
        for stmt in constructor_body(code, self.name).split(";"):
            self.statement(re.sub(r"\bthis\.", "", stmt.strip()))
        return self

    def statement(self, stmt):
        if not stmt:
            return

        assign = re.fullmatch(r"(?:this\.)?(textureWidth|texWidth)\s*=\s*(\d+)", stmt)
        if assign:
            self.width = int(assign.group(2))
            return
        assign = re.fullmatch(r"(?:this\.)?(textureHeight|texHeight)\s*=\s*(\d+)", stmt)
        if assign:
            self.height = int(assign.group(2))
            return
        assign = re.fullmatch(r"(?:super|this)\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", stmt)
        if assign:
            self.width, self.height = int(assign.group(1)), int(assign.group(2))
            return

        for call in re.finditer(r"new\s+\w*ModelBox\s*\(([^()]*)\)", stmt):
            self.model_box(split_args(call.group(1)))

        current = None
        created = re.search(r"(\w+)\s*=\s*new\s+[\w.]*ModelRenderer\b", stmt)
        if created:
            current = created.group(1)
            self.bone(current)

        for owner, name, args in iter_calls(stmt):
            if name.endswith("ModelRenderer"):
                if current:
                    numbers = [a for a in split_args(args) if re.fullmatch(r"\d+", a.strip())]
                    if len(numbers) >= 2:
                        self.bone(current).uv = (int(numbers[0]), int(numbers[1]))
                continue

            if name in ("setRotation", "setRotateAngle", "setRotationAngle", "setRotationAngles"):
                parts = split_args(args)
                if len(parts) == 4 and parts[0] in self.bones:
                    angles = [to_number(p) for p in parts[1:]]
                    if None not in angles:
                        self.bones[parts[0]].rot = tuple(angles)
                continue

            if owner:
                if owner not in self.bones:
                    continue
                current = owner
            if current is None or current not in self.bones:
                continue
            bone = self.bones[current]

            if name in ("setRotationPoint", "setPos"):
                parts = [to_number(a) for a in split_args(args)]
                if len(parts) == 3 and None not in parts:
                    bone.pivot = tuple(parts)
            elif name == "addBox":
                self.add_box(bone, split_args(args))
            elif name in ("setTextureOffset", "texOffs"):
                parts = [to_number(a) for a in split_args(args)]
                if len(parts) >= 2 and None not in parts[:2]:
                    bone.uv = (int(parts[0]), int(parts[1]))
            elif name == "addChild":
                parts = split_args(args)
                child = self.bones.get(parts[0]) if parts else None
                if child is not None and child is not bone:
                    child.parent = bone.name

        mirror = re.search(r"(\w+)\.mirror\s*=\s*(true|false)", stmt)
        if mirror and mirror.group(1) in self.bones:
            self.bones[mirror.group(1)].mirror = mirror.group(2) == "true"

        rotation = re.search(r"(\w+)\.(rotateAngle[XYZ]|[xyz]Rot|pos[XYZ])\s*=\s*(.+)", stmt)
        if rotation and rotation.group(1) in self.bones:
            self.assign_component(self.bones[rotation.group(1)], rotation.group(2), rotation.group(3))

    def add_box(self, bone, parts):
        if len(parts) < 6:
            return
        values = [to_number(p) for p in parts[:6]]
        if None in values:
            return
        x, y, z, w, h, d = values
        inflate = to_number(parts[6]) if len(parts) > 6 else None
        mirror = bone.mirror
        if len(parts) > 7:
            flag = parts[7].strip()
            if flag in ("true", "false"):
                mirror = flag == "true"
        bone.boxes.append(Box(x, y, z, w, h, d, bone.uv, inflate or 0.0, mirror))

    def model_box(self, parts):
        if len(parts) < 9 or parts[0] not in self.bones:
            return
        bone = self.bones[parts[0]]
        uv = [to_number(p) for p in parts[1:3]]
        values = [to_number(p) for p in parts[3:9]]
        if None in uv or None in values:
            return
        inflate = to_number(parts[9]) if len(parts) > 9 else 0.0
        mirror = parts[10].strip() == "true" if len(parts) > 10 else bone.mirror
        bone.boxes.append(
            Box(*values, uv=(int(uv[0]), int(uv[1])), inflate=inflate or 0.0, mirror=mirror)
        )

    def assign_component(self, bone, attr, expr):
        value = to_number(expr)
        if value is None:
            self.animated.add(bone.name)
            return
        index = "XYZ".index(attr[-1])
        if attr.startswith("pos"):
            pivot = list(bone.pivot)
            pivot[index] = value
            bone.pivot = tuple(pivot)
        else:
            rot = list(bone.rot)
            rot[index] = value
            bone.rot = tuple(rot)

    def pivots(self):
        result = {}
        visiting = set()

        def resolve(name):
            if name in result:
                return result[name]
            if name in visiting:
                return (0.0, 0.0, 0.0)
            visiting.add(name)
            bone = self.bones[name]
            base = resolve(bone.parent) if bone.parent in self.bones else (0.0, 0.0, 0.0)
            result[name] = (base[0] + bone.pivot[0], base[1] + bone.pivot[1], base[2] + bone.pivot[2])
            visiting.discard(name)
            return result[name]

        for name in self.order:
            resolve(name)
        return result


def box_faces(u, v, w, h, d):
    return {
        "north": [u + d, v + d, u + d + w, v + d + h],
        "east": [u, v + d, u + d, v + d + h],
        "south": [u + d + w + d, v + d, u + d + w + d + w, v + d + h],
        "west": [u + d + w, v + d, u + d + w + d, v + d + h],
        "up": [u + d, v, u + d + w, v + d],
        "down": [u + d + w, v, u + d + w + w, v + d],
    }


def num(value):
    value = round(float(value), 6)
    if abs(value - round(value)) < 1e-9:
        return int(round(value))
    return value


def deg(value):
    return num(math.degrees(value))


def build(model, y_origin=Y_ORIGIN):
    pivots = model.pivots()
    parents = {bone.parent for bone in model.bones.values() if bone.parent in model.bones}
    order = [n for n in model.order if model.bones[n].boxes or n in parents]
    elements = []
    groups = {}

    for name in order:
        px, py, pz = pivots[name]
        bone = model.bones[name]
        groups[name] = {
            "name": name,
            "origin": [num(-px), num(y_origin - py), num(pz)],
            "rotation": [deg(-bone.rot[0]), deg(-bone.rot[1]), deg(bone.rot[2])],
            "uuid": str(uuid.uuid4()),
            "children": [],
        }

    for name in order:
        bone = model.bones[name]
        px, py, pz = pivots[name]
        group = groups[name]
        for index, box in enumerate(bone.boxes):
            x0, x1 = sorted((px + box.x, px + box.x + box.w))
            y0, y1 = sorted((py + box.y, py + box.y + box.h))
            z0, z1 = sorted((pz + box.z, pz + box.z + box.d))
            cube = {
                "name": name + "_cube" if index == 0 else "%s_cube_%d" % (name, index + 1),
                "type": "cube",
                "uuid": str(uuid.uuid4()),
                "from": [num(-x1), num(y_origin - y1), num(z0)],
                "to": [num(-x0), num(y_origin - y0), num(z1)],
                "origin": [num(-px), num(y_origin - py), num(pz)],
                "rotation": [0, 0, 0],
                "box_uv": True,
                "uv_offset": [num(box.uv[0]), num(box.uv[1])],
                "faces": {
                    key: {"uv": [num(value) for value in face]}
                    for key, face in box_faces(box.uv[0], box.uv[1], box.w, box.h, box.d).items()
                },
            }
            if box.inflate:
                cube["inflate"] = num(box.inflate)
            if box.mirror:
                cube["mirror_uv"] = True
            elements.append(cube)
            group["children"].append(cube["uuid"])

    for name in order:
        parent = model.bones[name].parent
        if parent in groups:
            groups[parent]["children"].append(groups[name]["uuid"])

    by_uuid = {groups[n]["uuid"]: n for n in order}

    def outliner_node(name):
        nodes = []
        for child in groups[name]["children"]:
            nodes.append(outliner_node(by_uuid[child]) if child in by_uuid else child)
        return {"uuid": groups[name]["uuid"], "isOpen": True, "children": nodes}

    return {
        "meta": {"format_version": "5.0", "model_format": "modded_entity", "box_uv": True},
        "name": model.name,
        "resolution": {"width": model.width, "height": model.height},
        "elements": elements,
        "outliner": [outliner_node(n) for n in order if model.bones[n].parent not in groups],
        "groups": [groups[n] for n in order],
        "textures": [],
    }


def convert_file(path, y_origin=Y_ORIGIN):
    source = Path(path).read_text(encoding="utf-8", errors="replace")
    model = Model(Path(path).stem).parse(source)
    if not model.order:
        raise ValueError("no ModelRenderer found in %s" % path)
    return build(model, y_origin), model


SKIP_DIRS = {".git", ".idea", ".venv", "venv", "__pycache__", "output", "build", "target", "node_modules"}


def discover(root):
    found = []
    for path in sorted(root.rglob("*.java")):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        found.append(path)
    return found


def plan(args):
    out = Path(args.output) if args.output else None
    if not args.inputs:
        root = Path(__file__).resolve().parent
        sources = discover(root)
        if not sources:
            raise SystemExit(
                "no .java found under %s\n"
                "drop your model classes there, or name them explicitly: "
                "java2bbmodel.py modelFoo.java -o out/" % root
            )
        target_root = out if out is not None else root / "output"
        print("found %d .java under %s -> %s" % (len(sources), root, target_root))
        return [(s, target_root / s.relative_to(root).with_suffix(".bbmodel")) for s in sources]

    entries = []
    for item in args.inputs:
        path = Path(item)
        if path.is_dir():
            entries.extend(sorted(path.glob("*.java")))
        elif path.is_file():
            entries.append(path)
        else:
            raise SystemExit("no such file or directory: %s" % item)
    if not entries:
        raise SystemExit("no .java files found")

    if out is not None and len(entries) == 1 and out.suffix in (".bbmodel", ".json"):
        return [(entries[0], out)]
    if out is not None:
        return [(source, out / source.with_suffix(".bbmodel").name) for source in entries]
    return [(source, source.with_suffix(".bbmodel")) for source in entries]


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="java2bbmodel",
        description="Convert Minecraft Java entity model classes into Blockbench .bbmodel projects.",
    )
    parser.add_argument("inputs", nargs="*", help=".java files or directories (default: scan the script folder)")
    parser.add_argument("-o", "--output", help="output file or directory")
    parser.add_argument("--y-origin", type=float, default=Y_ORIGIN,
                        help="height added to the model when flipping the Y axis (default: 24)")
    parser.add_argument("-q", "--quiet", action="store_true", help="suppress the summary")
    args = parser.parse_args(argv)

    for source, target in plan(args):
        try:
            data, model = convert_file(source, args.y_origin)
        except Exception as error:
            print("%s: %s" % (source, error), file=sys.stderr)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if not args.quiet:
            print("%s -> %s" % (source.name, target))
            if model.animated:
                print("  skipped animated rotations: %s" % ", ".join(sorted(model.animated)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
