# -*- coding: utf-8 -*-
import maya.cmds as cmds
import os
import json
import udim_sampler
import shader_assigner

# Reloading to ensure latest logic is used
# reload(udim_sampler)
# reload(shader_assigner)

def get_selected_dominant_colors():
    """
    Analyzes selected objects, finds their textures, and returns a dictionary 
    mapping each object to its dominant RGB color.
    """
    # 1. Initialize core classes
    sampler = udim_sampler.UDIMSampler()
    
    # 2. Get current selection (long names to avoid ambiguity)
    selection = cmds.ls(selection=True, long=True)
    if not selection:
        cmds.warning("Please select at least one mesh.")
        return {}

    results = {}

    for obj in selection:
        # Ensure we are working with the shape node
        shapes = cmds.listRelatives(obj, shapes=True, fullPath=True) or [obj]
        shape = shapes[0]
        
        if cmds.nodeType(shape) != "mesh":
            continue

        # 3. Get shader and texture information
        shader = sampler.get_shader_from_shape(shape)
        if not shader:
            print("No shader found for: {}".format(obj))
            continue

        shader_info = sampler.get_file_texture_or_color_from_shader(shader)
        if not shader_info:
            continue

        dominant_rgb = None

        # 4. Handle File Textures vs. Flat Colors
        if shader_info["type"] == "file":
            texture_node = shader_info["value"]
            texture_path = sampler.get_texture_file_path(texture_node)
            
            if texture_path and os.path.exists(texture_path):
                # Extract color from the image
                dominant_rgb = sampler.get_dominant_color(texture_path)
            else:
                print("Texture path not found for {}: {}".format(obj, texture_path))
        
        elif shader_info["type"] == "color":
            # Already a flat color
            dominant_rgb = tuple(shader_info["value"])

        if dominant_rgb:
            results[obj] = dominant_rgb
            print("Object: {} | Dominant Color: {}".format(obj, dominant_rgb))

    return results

def apply_dominant_color_as_shader():
    """
    Utility function to sample selection and immediately assign a 
    new placeholder shader based on the dominant color.
    """
    color_data = get_selected_dominant_colors()
    assigner = shader_assigner.ShaderAssigner()

    for obj, rgb in color_data.items():
        # Get or create a lambert with this color
        # Tolerance of 2 prevents duplicate shaders for nearly identical colors
        sg = assigner.get_or_create_shader_for_color(rgb, tolerance=2)
        
        # Assign to the object
        assigner.assign_shader_to_object(obj, sg)

    cmds.inViewMessage(amg='<hl>Dominant Colors Applied to Selection</hl>', pos='topCenter', fade=True)

# ---------------------------------------------------------------------------------------------------
# Reads JSON data. If 'samples' are null/empty, it uses the
# Dominant Color Sampler to find the color and assign a shader.
# ---------------------------------------------------------------------------------------------------
def assign_select_object(json_path):
    """
    Reads JSON data. If 'samples' is null/empty, it uses the
    Dominant Color Sampler to find the color and assign a shader.
    """

    if not os.path.exists(json_path):
        cmds.error("JSON file not found: {}".format(json_path))
        return

    # Load the JSON data
    with open(json_path, 'r') as f:
        data = json.load(f)

    meshes = data.get("meshes", [])

    for mesh_entry in meshes:
        object_path = mesh_entry.get("object")
        uv_sets     = mesh_entry.get("uv_sets", [])

        for uv in uv_sets:
            if not uv.get("samples"):
                if cmds.objExists(object_path):
                    cmds.select(object_path, replace=True)
                    apply_dominant_color_as_shader()
                else:
                    print("Skipping: Object {} not found in scene.".format(object_path))

            if uv.get("samples"):
                samples = uv.get("samples", [])
                if samples:
                    color = samples[0].get("color")
                    if color == [0,0,0]:
                        if cmds.objExists(object_path):
                            cmds.select(object_path, replace=True)
                            apply_dominant_color_as_shader()
                        else:
                            print("Skipping: Object {} not found in scene.".format(object_path))





