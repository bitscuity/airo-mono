"""Very basic Blender URDF importer.

Features:
- Only relative or absolute paths are supported in the URDF files, so not paths with //:package.
- Only imports .dae, .stl and .obj mesh files.
- Only joints that align with its parents axes are supported .
- The imported URDFs are not rigged, so they must be posed in a "forwards kinematics" manner.
- We return a dictionary with info over the free DoFs of the URDF, so that we can use it to generate random poses.

Implementation:
- We use xmltodict to parse the URDF file to a python dictionary.
  Child xml elements can be accessed from the dictionary by using the tag as key e.g. urdf_dict["robot"].
  Attributes can be accessed by using the "@" prefix e.g. link["@name"].
- Then we import all links as empty objects. The visual meshes are imported and set as children of the empties.
- By default we lock all degrees of freedom of the links.
- Joints are then parsed, which unlock degrees of freedom of their child link.
"""
import os

import airo_blender as ab
import bpy
import numpy as np
import xmltodict


def parse_vector_string(vector_string: str) -> list[float]:
    return [float(f) for f in vector_string.split(" ") if f]


def read_urdf_as_dictionary(urdf_path: str):
    file = open(urdf_path, "r")
    xml_content = file.read()
    urdf_dict = xmltodict.parse(xml_content)
    return urdf_dict


def create_empty_for_link(link: dict):
    bpy.ops.object.empty_add(type="ARROWS", radius=0.05)
    empty = bpy.context.object
    empty.name = link["@name"]
    return empty


def set_transform_from_origin(object: bpy.types.Object, origin: dict):
    if "@xyz" in origin:
        object.location = parse_vector_string(origin["@xyz"])
    if "@rpy" in origin:
        object.rotation_euler = parse_vector_string(origin["@rpy"])


def import_mesh_from_urdf(mesh_path: str) -> list[bpy.types.Object]:
    objects_before_import = set(bpy.context.scene.objects)

    if mesh_path.endswith(".dae"):
        bpy.ops.wm.collada_import(filepath=mesh_path)
    elif mesh_path.endswith(".stl"):
        bpy.ops.import_mesh.stl(filepath=mesh_path)
    elif mesh_path.endswith(".obj"):
        # There axes where chosen for partnet mobility, I hope it works for all URDFs with objs
        bpy.ops.wm.obj_import(filepath=mesh_path, validate_meshes=True, forward_axis="Y", up_axis="Z")

    objects_after_import = set(bpy.context.scene.objects)
    imported_objects = objects_after_import - objects_before_import

    geometry_objects = set([object for object in imported_objects if object.type == "MESH"])
    non_geometry_objects = list(imported_objects - geometry_objects)

    with bpy.context.temp_override(selected_objects=list(non_geometry_objects)):
        bpy.ops.object.delete()

    return list(geometry_objects)


def add_urdf_material_to_geometries(material: dict, geometry_objects: list[bpy.types.Object]):
    if "color" not in material:
        return
    if "@rgba" not in material["color"]:
        return

    rgba_color = material["color"]["@rgba"]
    rgba_color = parse_vector_string(rgba_color)

    for object in geometry_objects:
        ab.add_material(object, rgba_color)


def import_visual(visual: dict, parent: bpy.types.Object, urdf_dir: str) -> None:
    geometry = visual["geometry"]  # geometry is a required element of visual
    geometry_objects = []

    # Create the objects specified by the geometry element in this visual
    if "mesh" in geometry:
        relative_mesh_path = geometry["mesh"]["@filename"]
        mesh_path = os.path.join(urdf_dir, relative_mesh_path)
        geometry_objects = import_mesh_from_urdf(mesh_path)
        if "@scale" in geometry["mesh"]:
            scales = parse_vector_string(geometry["mesh"]["@scale"])
            for object in geometry_objects:
                object.scale = scales
            bpy.ops.object.transform_apply(
                {"selected_editable_objects": geometry_objects}, location=False, rotation=False, scale=True
            )

    # TODO test
    if "box" in geometry:
        bpy.ops.mesh.primitive_cube_add()
        box = bpy.context.object
        scales = parse_vector_string(geometry["box"]["@size"].split(" "))
        box.scale = scales
        bpy.ops.object.transform_apply(
            {"selected_editable_objects": [box]}, location=False, rotation=False, scale=True
        )
        geometry_objects.append(box)

    # Additional processing for all geometry objects in this visual
    for object in geometry_objects:
        if "origin" in visual:
            set_transform_from_origin(object, visual["origin"])

        object.lock_location = (True, True, True)
        object.lock_rotation = (True, True, True)
        object.parent = parent

    if "material" in visual:
        material = visual["material"]
        add_urdf_material_to_geometries(material, geometry_objects)


def import_link(link: dict, urdf_dir: str) -> bpy.types.Object:
    empty = create_empty_for_link(link)

    if "visual" not in link:
        return empty

    # One link can contain multiple visuals.
    visuals = link["visual"]
    if not isinstance(link["visual"], list):
        visuals = [visuals]

    for visual in visuals:
        import_visual(visual, empty, urdf_dir)

    return empty


def set_up_relovute_joint(joint: dict, child: bpy.types.Object):
    axis = [1.0, 0.0, 0.0]  # Default axis from spec
    if "axis" in joint:
        axis = parse_vector_string(joint["axis"]["@xyz"])

    if np.count_nonzero(axis) > 1:
        name = joint["@name"]
        print(f"Ignoring joint {name}. Currently only joints with x,y or z aligned axes are supported.")
        return

    axis_index = np.where(np.array(axis) != 0)[0][0]  # Index of the non-zero axis

    child.lock_rotation[axis_index] = False
    child.empty_display_size = 0.1


def import_urdf(urdf_path: str):
    urdf_dict = read_urdf_as_dictionary(urdf_path)
    urdf_dir = os.path.dirname(urdf_path)

    links = urdf_dict["robot"]["link"]
    empties = {}  # URDF links are represented as empties in Blender
    for link in links:
        link_empty = import_link(link, urdf_dir)
        empties[link["@name"]] = link_empty
        # By default, we lock all degrees of freedom of a link.
        # Joints will be represented as unlocked degrees of freedom.
        link_empty.lock_rotation = (True, True, True)
        link_empty.lock_location = (True, True, True)

    joints = urdf_dict["robot"]["joint"]
    # joints_by_name = {joint["@name"]: joint for joint in joints}
    for joint in joints:
        parent = empties[joint["parent"]["@link"]]
        child = empties[joint["child"]["@link"]]
        child.parent = parent

        if "origin" in joint:
            set_transform_from_origin(child, joint["origin"])

        joint_type = joint["@type"]
        if joint_type == "fixed":
            pass  # Fixed joints are already set up correctly, because we lock all DoFs by default.
        elif joint_type == "revolute":
            set_up_relovute_joint(joint, child)
        elif joint_type == "prismatic":
            pass  # TODO
        else:
            print(f"Ignoring joint of type {joint_type}. Not implemented yet.")


if __name__ == "__main__":
    bpy.ops.object.delete()  # Delete the default cube

    urdf_path = "/home/idlab185/urdfpy/tests/data/ur5/ur5.urdf"
    # urdf_path = "/home/idlab185/robotiq_arg85_description/robots/robotiq_arg85_description.URDF"
    # urdf_path = "/home/idlab185/robotiq_2finger_grippers/robotiq_2f_85_gripper_visualization/urdf/robotiq2f85.urdf"
    # urdf_path = "/home/idlab185/partnet-mobility-sample/44853/mobility.urdf"  # cabinet
    # urdf_path = "/home/idlab185/partnet-mobility-sample/7128/mobility.urdf"
    # urdf_path = "/home/idlab185/partnet-mobility-sample/7130/mobility.urdf"
    # urdf_path = "/home/idlab185/partnet-mobility-sample/103452/mobility.urdf" # washing machine
    import_urdf(urdf_path)
