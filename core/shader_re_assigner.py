# -*- coding: utf-8 -*-
# ==============================================================================================================
# Re-assign shaders to objects based on a JSON mapping (for older format)
# ==============================================================================================================


import json
import maya.cmds as cmds

# ==============================================================================================================
# Helper function to get the shading group for a given shader or shading group
# ==============================================================================================================
def get_shading_group(shader_or_sg):
    """
    Ensure we return a shading group from either a shading group name or a material.
    """
    if cmds.objExists(shader_or_sg) and cmds.nodeType(shader_or_sg) == "shadingEngine":
        return shader_or_sg  # already SG
    
    # If it's a material, find its connected shading group(s)
    sgs = cmds.listConnections(shader_or_sg, type="shadingEngine") or []
    if sgs:
        return sgs[0]
    
    return None

# ==============================================================================================================
# Delete unused shaders
# ==============================================================================================================
def delete_unused_shaders():
    """
    Deletes unused shading groups and their materials.
    Keeps Maya default safe nodes.
    """
    safe_nodes = set([
        "lambert1", "particleCloud1", "shaderGlow1",
        "initialShadingGroup", "initialParticleSE"
    ])

    shading_groups = cmds.ls(type="shadingEngine")
    deleted = []

    for sg in shading_groups:
        if sg in safe_nodes:
            continue

        members = cmds.sets(sg, q=True) or []
        if members:
            continue

        materials = cmds.listConnections(sg + ".surfaceShader") or []
        try:
            cmds.delete([sg] + materials)
            deleted.append(sg)
        except:
            pass

    if deleted:
        print("🗑️ Deleted unused shaders: {0}".format(", ".join(deleted)))

# ==============================================================================================================
# re-assign shaders to objects
# ==============================================================================================================
def re_assigner_old(json_path):
    """
    Reassign shaders (materials or shading groups) to connected objects in Maya.
    Fixes "NOT a set" by resolving the shading group if a material is given.
    Works in Python 2.7.
    """
    # Load JSON
    with open(json_path, "r") as f:
        try:
            data = json.load(f)
        except Exception as e:
            print("❌ Failed to parse JSON: {0}".format(e))
            return False

    shader_connections = data.get("shader_connections", {})

    for shader, info in shader_connections.items():
        objects = info.get("connected_objects", [])
        if not cmds.objExists(shader):
            print("   ⚠️ Shader not found: {0}".format(shader))
            continue

        sg = get_shading_group(shader)
        if not sg or not cmds.objExists(sg):
            print("⚠️ No shading group found for: {0}".format(shader))
            continue

        for obj in objects:
            base_obj = obj.split(".")[0]
            if not cmds.objExists(base_obj):
                print("   ⚠️ Object not found: {0}".format(obj))
                continue

            try:
                cmds.sets(obj, e=True, forceElement=sg)
                print("✅ Assigned {0} → {1}".format(sg, obj))
            except Exception as e:
                print("❌ Failed assigning {0} → {1} ({2})".format(sg, obj, e))

    # Cleanup pass after ALL assignments
    delete_unused_shaders()
    return True


# "E:\RTB\user\maya\textureTool\set\wEBAtriumA\r0008\OlderShader.json"
def ShaderReAssigner(json_path):
    if json_path:
        re_assigner_old(json_path)