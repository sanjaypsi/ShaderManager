# -*- coding: utf-8 -*-
import maya.cmds as cmds
import json
import os
from core import udim_sampler
from core import shader_assigner

def ProcessAndSampleMissingData(json_path):
    """
    Reads JSON data. If 'samples' is null/empty, it uses the 
    Dominant Color Sampler to find the color and assign a shader.
    """
    # Initialize Core Classes
    sampler     = udim_sampler.UDIMSampler()
    assigner    = shader_assigner.ShaderAssigner()
    
    if not os.path.exists(json_path):
        cmds.error("JSON file not found: {}".format(json_path))
        return

    # Load the JSON data
    with open(json_path, 'r') as f:
        data = json.load(f)

    meshes = data.get("meshes", [])
    
    for mesh_entry in meshes:
        object_path = mesh_entry.get("object")
        uv_sets = mesh_entry.get("uv_sets", [])
        
        # Determine if any UV set has valid samples
        has_valid_samples = False
        for uv in uv_sets:
            if uv.get("samples"): # Checks if list is not None or empty
                has_valid_samples = True
                break
        
        # ---------------------------------------------------------
        # Logic: If samples are null, get Dominant Color from Object
        # ---------------------------------------------------------
        if not has_valid_samples:
            print("Samples null for {}. Triggering Dominant Color Sampler...".format(object_path))
            
            # Find the object in the scene using your existing search logic
            scene_obj = assigner.find_object_in_scene(object_path)
            
            if scene_obj and cmds.objExists(scene_obj):
                # Get the shader and texture info
                shader = sampler.get_shader_from_shape(scene_obj)
                if shader:
                    tex_info = sampler.get_file_texture_or_color_from_shader(shader)
                    
                    dominant_rgb = None
                    if tex_info and tex_info["type"] == "file":
                        path = sampler.get_texture_file_path(tex_info["value"])
                        if path and os.path.exists(path):
                            dominant_rgb = sampler.get_dominant_color(path)
                    
                    elif tex_info and tex_info["type"] == "color":
                        dominant_rgb = tuple(tex_info["value"])

                    # If a color was found, assign the shader
                    if dominant_rgb:
                        sg = assigner.get_or_create_shader_for_color(dominant_rgb)
                        assigner.assign_shader_to_object(scene_obj, sg)
                        print("Successfully applied dominant color to {}".format(scene_obj))
            else:
                print("Skipping: Object {} not found in scene.".format(object_path))
        else:
            # If samples existed, proceed with standard assignment
            assigner.process_json_and_assign_shaders(json_path)

    cmds.inViewMessage(amg='<hl>Processing Complete</hl>', pos='topCenter', fade=True)
