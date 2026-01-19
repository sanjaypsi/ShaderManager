# -*- coding: utf-8 -*-
# ==============================================================================================================
# Re-assign shaders to objects based on a JSON mapping (for older format)
# ==============================================================================================================


import json
import select
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
            base_obj = obj.split(":")[-1]
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

# ==============================================================================================================

def re_assigner_selectedObjects(json_path, selectedObjs):
    """
    Reassign shaders (materials or shading groups) to selected objects in Maya.
    Fixes 'NOT A SET' by resolving shading groups if a material is given.
    Works in Python 2.7
    """

    if not selectedObjs:
        print("⚠ No objects selected.")
        return False
    

    getShape            = cmds.listRelatives(str(selectedObjs), shapes=True, fullPath=True) or []
    selectedObjShape    = getShape[0].split(":")[-1] if getShape else ""
    print("selectedObjShape ", selectedObjShape)
    # Load JSON
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
    except Exception as e:
        print("❌ Failed to parse JSON: {}".format(e))
        return False

    shader_connections = data.get("shader_connections", {})

    for shader, info in shader_connections.items():
        objects = info.get("connected_objects", [])

        if not cmds.objExists(shader):
            print("⚠ Shader not found: {}".format(shader))
            continue

        sg = get_shading_group(shader)
        if not sg or not cmds.objExists(sg):
            print("⚠ No shading group found for: {}".format(shader))
            continue

        for obj in objects:
            base_obj = obj.split(":")[-1]
            if base_obj != selectedObjShape:
                continue

            try:
                cmds.sets(getShape[0], e=True, forceElement=sg)
                print("✅ Assigned {} → {}".format(sg, selectedObjShape))
            except Exception as e:
                print("❌ Failed assigning {} → {} ({})".format(sg, selectedObjShape, e))

    return True

# ==============================================================================================================
# "E:\RTB\user\maya\textureTool\set\wEBAtriumA\r0008\OlderShader.json"
# ==============================================================================================================
def ShaderReAssigner(json_path):
    selectedObjs = cmds.ls(selection=True)

    if not selectedObjs:
        print(" No objects selected. Please select objects to re-assign shaders.")
        if json_path:
            re_assigner_old(json_path)

    else:
        for obj in selectedObjs:
            re_assigner_selectedObjects(json_path, obj)

        # print(" Re-assigning shaders to selected objects...", selectedObjs)