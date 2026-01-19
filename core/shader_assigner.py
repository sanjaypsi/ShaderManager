# -*- coding: utf-8 -*-
# =====================================================================================
# UDIM Sampler for Maya (Python 2.7 Compatible)


import maya.cmds as cmds
import json
import os

#================================================================================================================================
# ShaderAssigner Class
#================================================================================================================================
class ShaderAssigner(object):
    def __init__(self):
        # Cache shaders by color tuple
        self.shader_cache = {}

    def load_json_data(self, json_path):
        if not os.path.exists(json_path):
            print("JSON file not found:", json_path)
            return None
        try:
            with open(json_path, "r") as f:
                data = json.load(f)
            print("Loaded JSON data from:", json_path)
            return data
        except Exception as e:
            print("Failed to load JSON: {}".format(e))
            return None

    # ---------------------------------------------------------------------------------------------------------------------------
    # Find an object in the Maya scene by its path
    # ---------------------------------------------------------------------------------------------------------------------------
    def find_object_in_scene(self, object_path):
        short_name = object_path.split("|")[-1].split(":")[-1]  # Extract short name without namespace or path

        # First try: search for shape nodes (any namespace)
        matches = cmds.ls("*:{}*".format(short_name), long=True) or []
        if matches:
            try:
                # If it's a reference, print the namespace for info
                reference_node = cmds.referenceQuery(matches[0], referenceNode=True)
                if reference_node:
                    namespace = cmds.referenceQuery(reference_node, namespace=True)
                    # print("Found in reference namespace '{}': {}".format(namespace, matches[0]))
            except:
                pass  # Not referenced, or failed to query, ignore

            # print("Found matching shape(s):", matches)
            return self.get_parent_transform(matches[0])

        # Second try: search for transform nodes (any namespace)
        matches = cmds.ls("*:{}*".format(short_name.replace("Shape", "")), long=True, type="transform") or []
        if matches:
            print("Found matching transform(s):", matches)
            return matches[0]

        print("No matching object found for path:", object_path)
        return None

    # ---------------------------------------------------------------------------------------------------------------------------
    # Get the parent transform of a node, or return the node itself if it's not a
    # shape node
    # ---------------------------------------------------------------------------------------------------------------------------
    def get_parent_transform(self, node):
        """
        If the node is a shape, return its parent transform. Otherwise return the node itself.
        """
        node_type = cmds.nodeType(node)
        if node_type in ["mesh", "nurbsSurface", "subdiv"]:
            parent = cmds.listRelatives(node, parent=True, fullPath=True)
            if parent:
                # print(" Using parent transform: {}".format(parent[0]))
                return parent[0]
        return node

    # ---------------------------------------------------------------------------------------------------------------------------
    # Create a new Lambert shader with the specified name and RGB color
    # ---------------------------------------------------------------------------------------------------------------------------
    def create_lambert_shader(self, shader_name, rgb_color):
        shader = cmds.shadingNode("lambert", asShader=True, name=shader_name)
        sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=shader + "SG")
        cmds.connectAttr(shader + ".outColor", sg + ".surfaceShader", force=True)

        # Set color
        color_normalized = [float(c) / 255.0 for c in rgb_color]
        cmds.setAttr(shader + ".color", color_normalized[0], color_normalized[1], color_normalized[2], type="double3")

        # print(" Created shader '{}', color {}".format(shader, rgb_color))
        return shader, sg

    # ---------------------------------------------------------------------------------------------------------------------------
    # Assign a shader to an object in the Maya scene
    # ---------------------------------------------------------------------------------------------------------------------------
    def assign_shader_to_object(self, object_name, shading_group):
        try:
            cmds.sets(object_name, edit=True, forceElement=shading_group)
            # print(" Assigned shader to object:", object_name)
        except Exception as e:
            print(" Failed to assign shader to '{}': {}".format(object_name, e))

    # ---------------------------------------------------------------------------------------------------------------------------
    # Check if two RGB colors match within a given tolerance
    # ---------------------------------------------------------------------------------------------------------------------------
    def colors_match(self, color1, color2, tolerance=2):
        for c1, c2 in zip(color1, color2):
            if abs(c1 - c2) > tolerance:
                return False
        return True

    # ---------------------------------------------------------------------------------------------------------------------------
    # Get or create a shader for a given RGB color, checking the cache first
    # ---------------------------------------------------------------------------------------------------------------------------
    def get_or_create_shader_for_color(self, color_rgb, tolerance=2):
        """
        Check if a shader for this color (within tolerance) already exists.
        """
        for cached_color, sg in self.shader_cache.items():
            if self.colors_match(color_rgb, cached_color, tolerance):
                # print(" Reusing shader for color {} (matched with {})".format(color_rgb, cached_color))
                return sg

        # Create new shader
        shader_name     = "shader_{:03d}_{:03d}_{:03d}".format(*color_rgb)
        shader, sg      = self.create_lambert_shader(shader_name, color_rgb)
        self.shader_cache[tuple(color_rgb)] = sg
        return sg

    # ---------------------------------------------------------------------------------------------------------------------------
    # Process the JSON data and assign shaders to objects based on their sample colors
    # ---------------------------------------------------------------------------------------------------------------------------
    def process_json_and_assign_shaders(self, json_path):
        data = self.load_json_data(json_path)
        if not data:
            return

        meshes = data.get("meshes", [])
        if not meshes:
            print("No 'meshes' found in JSON.")
            return

        for mesh_data in meshes:
            object_path = mesh_data.get("object")
            uv_sets = mesh_data.get("uv_sets", [])

            if not object_path:
                print(" No object path found for a mesh entry.")
                continue
            if not uv_sets:
                print("No UV sets found for object: {}".format(object_path))
                continue

            # Find the object in the scene
            object_in_scene = self.find_object_in_scene(object_path)
            if not object_in_scene:
                continue

            # Try to get the first valid sample color from any UV set
            color = None
            for uv in uv_sets:
                samples = uv.get("samples", [])
                if samples:
                    color = samples[0].get("color")
                    if color:
                        break

            if not color:
                print(" No sample color found for object: {}".format(object_path))
                continue

            # Get or create shader
            shading_group = self.get_or_create_shader_for_color(color, tolerance=2)

            # Assign shader
            self.assign_shader_to_object(object_in_scene, shading_group)
