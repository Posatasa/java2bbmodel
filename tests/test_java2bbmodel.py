"""Checks that the generated model places every vertex exactly where Minecraft would."""

import json
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import java2bbmodel as jb


def mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def ident():
    return [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]


def translate(x, y, z):
    m = ident()
    m[0][3], m[1][3], m[2][3] = x, y, z
    return m


def rotate(axis, angle):
    c, s = math.cos(angle), math.sin(angle)
    m = ident()
    if axis == 0:
        m[1][1], m[1][2], m[2][1], m[2][2] = c, -s, s, c
    elif axis == 1:
        m[0][0], m[0][2], m[2][0], m[2][2] = c, s, -s, c
    else:
        m[0][0], m[0][1], m[1][0], m[1][1] = c, -s, s, c
    return m


def apply(m, v):
    return [sum(m[i][k] * v[k] for k in range(4)) for i in range(4)]


def euler(rad):
    x, y, z = rad
    return mul(rotate(2, z), mul(rotate(1, y), rotate(0, x)))


def corners(lo, hi):
    return [[x, y, z, 1.0] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]


def minecraft_world(model, y_origin):
    cache = {}
    flip = [[-1.0, 0.0, 0.0, 0.0], [0.0, -1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]

    def matrix(name):
        if name in cache:
            return cache[name]
        bone = model.bones[name]
        local = mul(translate(*bone.pivot), euler(bone.rot))
        cache[name] = mul(matrix(bone.parent), local) if bone.parent in model.bones else local
        return cache[name]

    result = {}
    for name in model.order:
        bone = model.bones[name]
        for index, box in enumerate(bone.boxes):
            lo = (box.x, box.y, box.z)
            hi = (box.x + box.w, box.y + box.h, box.z + box.d)
            points = []
            for vertex in corners(lo, hi):
                world = apply(flip, apply(matrix(name), vertex))
                points.append([world[0], world[1] + y_origin, world[2]])
            key = name + "_cube" if index == 0 else "%s_cube_%d" % (name, index + 1)
            result[key] = sorted(points)
    return result


def blockbench_world(data):
    """Mirrors NodePreviewController.updateTransform + Outliner.loadJSON."""
    groups = {g["uuid"]: g for g in data["groups"]}
    parents = {}

    def walk(nodes, group_uuid):
        for node in nodes:
            uuid_ = node if isinstance(node, str) else node["uuid"]
            parents[uuid_] = group_uuid
            if isinstance(node, dict):
                walk(node["children"], uuid_)

    walk(data["outliner"], None)
    cache = {}

    def matrix(uuid):
        if uuid in cache:
            return cache[uuid]
        origin = groups[uuid]["origin"]
        parent_uuid = parents.get(uuid)
        if parent_uuid:
            shift = [a - b for a, b in zip(origin, groups[parent_uuid]["origin"])]
        else:
            shift = list(origin)
        local = mul(translate(*shift), euler([math.radians(v) for v in groups[uuid]["rotation"]]))
        cache[uuid] = mul(matrix(parent_uuid), local) if parent_uuid else local
        return cache[uuid]

    result = {}
    for element in data["elements"]:
        transform = matrix(parents[element["uuid"]])
        origin = element["origin"]
        points = [apply(transform, [v[0] - origin[0], v[1] - origin[1], v[2] - origin[2], 1.0])
                  for v in corners(element["from"], element["to"])]
        result[element["name"]] = sorted(points)
    return result


def compare(test, source, y_origin=24.0):
    model = jb.Model("model").parse(source)
    data = jb.build(model, y_origin)
    expected = minecraft_world(model, y_origin)
    actual = blockbench_world(json.loads(json.dumps(data)))
    test.assertEqual(sorted(expected), sorted(actual))
    for name in expected:
        for want, got in zip(expected[name], actual[name]):
            for a, b in zip(want, got):
                test.assertAlmostEqual(a, b, places=6, msg=name)


class Conversion(unittest.TestCase):
    def test_flat_model(self):
        compare(self, """
            public class ModelTest extends ModelBase {
                ModelRenderer body;
                ModelRenderer head;
                public ModelTest() {
                    textureWidth = 64;
                    textureHeight = 32;
                    (body = new ModelRenderer(this, 0, 0)).addBox(-4.0f, 0.0f, -2.0f, 8, 10, 4);
                    body.setRotationPoint(0.0f, 12.0f, 0.0f);
                    (head = new ModelRenderer(this, 0, 14)).addBox(-2.0f, -6.0f, -2.0f, 4, 6, 4);
                    head.setRotationPoint(0.0f, 2.0f, 0.0f);
                    setRotation(body, 0.0f, 0.0f, 0.0f);
                    setRotation(head, 0.5f, -0.25f, 0.125f);
                }
            }""")

    def test_nested_model(self):
        compare(self, """
            public class ModelTest extends MowzieModelBase {
                MowzieModelRenderer root;
                MowzieModelRenderer limb;
                MowzieModelRenderer tip;
                public ModelTest() {
                    textureWidth = 64;
                    textureHeight = 32;
                    root = new MowzieModelRenderer(this, 0, 0);
                    root.setRotationPoint(0.0F, 16.0F, 0.0F);
                    root.addBox(-3.0F, -3.0F, -3.0F, 6, 6, 6, 0.0F);
                    setRotateAngle(root, 0.31869712141416456F, 0.0F, 0.0F);
                    limb = new MowzieModelRenderer(this, 0, 12);
                    limb.setRotationPoint(1.5F, 3.5F, 0.5F);
                    limb.addBox(-0.5F, -0.3F, -0.5F, 1, 3, 1, 0.0F);
                    setRotateAngle(limb, -0.7740535232594852F, -0.18203784098300857F, 0.18203784098300857F);
                    tip = new MowzieModelRenderer(this, 8, 12);
                    tip.setRotationPoint(0.0F, 2.65F, 0.5F);
                    tip.addBox(-1.0F, 0.0F, -3.0F, 2, 0, 3, 0.0F);
                    setRotateAngle(tip, 0.2F, 0.0F, -0.4F);
                    root.addChild(limb);
                    limb.addChild(tip);
                }
            }""")

    def test_offsets_and_mirror(self):
        model = jb.Model("model").parse("""
            public class ModelTest extends ModelBase {
                public ModelTest() {
                    textureWidth = 32;
                    textureHeight = 32;
                    ModelRenderer part = new ModelRenderer(this);
                    part.setRotationPoint(1.0f, 2.0f, 3.0f);
                    part.setTextureOffset(4, 5).addBox(0.0f, 0.0f, 0.0f, 2, 3, 4);
                    part.mirror = true;
                    part.setTextureOffset(10, 11).addBox(-2.0f, 0.0f, 0.0f, 2, 3, 4);
                }
            }""")
        data = jb.build(model)
        self.assertEqual(data["resolution"], {"width": 32, "height": 32})
        first, second = data["elements"]
        self.assertEqual((first["uv_offset"], second["uv_offset"]), ([4, 5], [10, 11]))
        self.assertEqual(first["from"], [-3, 19, 3])
        self.assertEqual(first["to"], [-1, 22, 7])
        self.assertNotIn("mirror_uv", first)
        self.assertTrue(second["mirror_uv"])
        self.assertEqual(data["groups"][0]["origin"], [-1, 22, 3])

    def test_chained_constructor_keeps_uv(self):
        model = jb.Model("model").parse("""
            public class ModelTest extends ModelBase {
                ModelRenderer head;
                public ModelTest() {
                    textureWidth = 256;
                    textureHeight = 32;
                    (head = new ModelRenderer(this, 196, 0)).addBox(6.0f, -12.0f, -12.0f, 2, 10, 10);
                    head.setRotationPoint(0.0f, 12.0f, 4.0f);
                }
            }""")
        cube = jb.build(model)["elements"][0]
        self.assertEqual(cube["uv_offset"], [196, 0])
        self.assertEqual(cube["from"], [-8, 14, -8])
        self.assertEqual(cube["to"], [-6, 24, 2])
        self.assertEqual(cube["faces"]["north"]["uv"], [206, 10, 208, 20])

    def test_faces_follow_minecraft_layout(self):
        faces = jb.box_faces(196, 0, 2, 10, 10)
        self.assertEqual(faces["west"], [208, 10, 218, 20])
        self.assertEqual(faces["north"], [206, 10, 208, 20])
        self.assertEqual(faces["east"], [196, 10, 206, 20])
        self.assertEqual(faces["south"], [218, 10, 220, 20])
        self.assertEqual(faces["up"], [206, 0, 208, 10])
        self.assertEqual(faces["down"], [208, 0, 210, 10])

    def test_animation_is_ignored(self):
        model = jb.Model("model").parse("""
            public class ModelTest extends ModelBase {
                ModelRenderer leg;
                public ModelTest() {
                    (leg = new ModelRenderer(this, 0, 0)).addBox(-1.0f, 0.0f, -1.0f, 2, 6, 2);
                    leg.setRotationPoint(0.0f, 18.0f, 0.0f);
                }
                public void setRotationAngles(float swing, float amount, float f3, float f4, float f5, float f6, Entity e) {
                    leg.rotateAngleX = MathHelper.cos(swing * 0.6662f) * 1.4f * amount;
                }
            }""")
        data = jb.build(model)
        self.assertEqual(data["groups"][0]["rotation"], [0, 0, 0])
        self.assertEqual(model.animated, set())


if __name__ == "__main__":
    unittest.main()
