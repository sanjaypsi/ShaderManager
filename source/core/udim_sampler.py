# -*- coding: utf-8 -*-
# =====================================================================================
# UDIM Sampler for Maya (Python 2.7 Compatible)
# =====================================================================================
import maya.cmds as cmds
import os
import re
import math
import json

try:
    from PIL import Image, ImageFile
except ImportError:
    raise ImportError("PIL (Pillow) library is required. Please install it.")

from core import utils
reload(utils)

from PySide2 import QtWidgets, QtCore
import maya.OpenMayaUI as omui
from shiboken2 import wrapInstance

def get_maya_main_window():
    main_window_ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(long(main_window_ptr), QtWidgets.QWidget)

# =====================================================================================
# UDIM Sampler Class
# =====================================================================================
class UDIMSampler(object):
    def __init__(self):
        self.failed_textures = set()

    # ------------------------------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------------
    def get_all_mesh_shapes(self):
        return cmds.ls(type="mesh", long=True) or []

    # ------------------------------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------------
    def get_shader_from_shape(self, shape_node):
        shading_groups = cmds.listConnections(shape_node, type='shadingEngine') or []
        shaders = cmds.ls(cmds.listConnections(shading_groups), materials=True) or []
        return shaders[0] if shaders else None

    # ------------------------------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------------
    def get_file_texture_or_color_from_shader(self, shader):
        for attr in ["color", "diffuseColor", "diffuseLitColor", "albedoColor", "baseColor"]:
            if cmds.attributeQuery(attr, node=shader, exists=True):
                connections = cmds.listConnections("{}.{}".format(shader, attr), type='file')
                if connections:
                    return {"type": "file", "value": connections[0]}
                try:
                    color = cmds.getAttr("{}.{}".format(shader, attr))
                    if color:
                        return {"type": "color", "value": [int(c * 255) for c in color[0]]}
                except Exception as e:
                    print("Failed to get color: {}.{} -> {}".format(shader, attr, e))
        return None

    # ------------------------------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------------
    def get_texture_file_path(self, file_node):
        if not cmds.objExists(file_node + ".fileTextureName"):
            return None
        return cmds.getAttr(file_node + ".fileTextureName")

    # ------------------------------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------------
    def convert_to_udim_template(self, texture_path):
        folder, filename = os.path.split(texture_path)
        if "<f>" in filename:
            return os.path.join(folder, filename.replace("<f>", "<UDIM>")).replace("\\", "/")
        match = re.search(r'(\d{4})(?=\.[^.]+$)', filename)
        if not match:
            return texture_path
        udim_filename = filename[:match.start()] + "<UDIM>" + filename[match.end():]
        return os.path.join(folder, udim_filename).replace("\\", "/")

    # ------------------------------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------------
    def fix_and_reload_jpeg(self, path):
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        try:
            img = Image.open(path)
            img.load()
            temp_path = path + "_fixed.jpg"
            img.save(temp_path, "JPEG")
            os.remove(path)
            os.rename(temp_path, path)
            return Image.open(path).convert("RGB")
        except Exception as e:
            print("  Failed to fix image '{}': {}".format(path, e))
            return None

    # ------------------------------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------------
    def get_dominant_color(self, image_path):
        try:
            img = Image.open(image_path).convert("RGB")
            img = img.resize((1, 1))
            return img.getpixel((0, 0))
        except Exception as e:
            print("Failed to get dominant color: {}".format(e))
            return None

    # ------------------------------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------------
    def sample_using_dominant_color(self, shape_node, uv_set_name, f_template):
        """Sample UVs using dominant color from first available <f> tile."""
        # Detect actual texture file replacing <f> with real UDIM
        folder, base = os.path.split(f_template)
        base_regex = re.escape(base).replace("\\<f\\>", r"(\d{4})")  # Replace <f> with a regex group

        try:
            for fname in os.listdir(folder):
                match = re.match(base_regex, fname)
                if match:
                    udim_number = match.group(1)
                    texture_path = os.path.join(folder, fname).replace("\\", "/")
                    break
            else:
                print("No matching <f> tile found in: {}".format(folder))
                return []
        except Exception as e:
            print("Error searching for <f> tile: {}".format(e))
            return []

        # Use detected texture
        dominant_color = self.get_dominant_color(texture_path)
        if not dominant_color:
            print("⚠ Failed to extract dominant color from: {}".format(texture_path))
            return []

        # Sample UVs and apply dominant color
        uv_components = cmds.polyListComponentConversion(shape_node, toUV=True)
        uv_components = cmds.ls(uv_components, flatten=True)

        results = []
        for uv in uv_components:
            coords = cmds.polyEditUV(uv, query=True)
            if not coords:
                continue
            results.append({
                "uv": coords,
                "tile": int(udim_number),
                "pixel": None,
                "color": dominant_color,
            })

        return results

    # ------------------------------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------------
    def sample_uv_colors_from_udim(self, shape_node, uv_set_name, udim_template):
        available_uv_sets = cmds.polyUVSet(shape_node, query=True, allUVSets=True) or []
        if uv_set_name not in available_uv_sets:
            return []
        uv_components = cmds.ls(cmds.polyListComponentConversion(shape_node, toUV=True), flatten=True)
        original_uv_set = cmds.polyUVSet(shape_node, query=True, currentUVSet=True)[0]
        cmds.polyUVSet(shape_node, currentUVSet=True, uvSet=uv_set_name)
        image_cache, results = {}, []
        try:
            for uv in uv_components:
                coords = cmds.polyEditUV(uv, query=True)
                if not coords:
                    continue
                u, v = coords
                tile_u, tile_v = int(math.floor(u)), int(math.floor(v))
                udim_number = 1001 + tile_u + tile_v * 10
                texture_path = udim_template.replace("<UDIM>", str(udim_number)).replace("<f>", str(udim_number))
                if texture_path not in image_cache:
                    if not os.path.exists(texture_path):
                        self.failed_textures.add(texture_path)
                        image_cache[texture_path] = None
                        continue
                    try:
                        img = Image.open(texture_path).convert("RGB")
                        image_cache[texture_path] = img
                    except Exception as e:
                        if texture_path.lower().endswith(('.jpg', '.jpeg', '.jfif')):
                            img = self.fix_and_reload_jpeg(texture_path)
                            image_cache[texture_path] = img if img else None
                        else:
                            image_cache[texture_path] = None
                        continue
                img = image_cache[texture_path]
                if not img:
                    continue
                width, height = img.size
                px = min(int((u - tile_u) * width), width - 1)
                py = min(int((1.0 - (v - tile_v)) * height), height - 1)
                try:
                    color = img.getpixel((px, py))
                except Exception as e:
                    color = None
                results.append({"uv": [u, v], "tile": udim_number, "pixel": [px, py], "color": color})
        finally:
            cmds.polyUVSet(shape_node, currentUVSet=True, uvSet=original_uv_set)
        return results

    # ------------------------------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------------
    def sample_flat_color(self, shape_node, uv_set_name, rgb_color):
        uv_components = cmds.ls(cmds.polyListComponentConversion(shape_node, toUV=True), flatten=True)
        return [{"uv": cmds.polyEditUV(uv, query=True), "tile": None, "pixel": None, "color": rgb_color}
                for uv in uv_components if cmds.polyEditUV(uv, query=True)]

    # ------------------------------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------------
    def sample_and_save_all_meshes(self, sample_count=5, json_output_path=None, reference_node=None, namespace=None):
        shapes = self.get_all_mesh_shapes()
        if not shapes:
            return
        matched_meshes = []
        progress_dialog = QtWidgets.QProgressDialog("Sampling meshes...", "Cancel", 0, len(shapes), get_maya_main_window())
        progress_dialog.setWindowTitle("UDIM Sampler")
        progress_dialog.setMinimumWidth(400)
        progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
        progress_dialog.show()
        for idx, shape in enumerate(shapes):
            if progress_dialog.wasCanceled():
                return
            short_name = shape.split("|")[-1]
            if ":" in short_name:
                mesh_namespace = short_name.split(":")[0]
                if namespace and mesh_namespace not in namespace:
                    continue

            shader = self.get_shader_from_shape(shape)
            if not shader:
                continue

            shader_info = self.get_file_texture_or_color_from_shader(shader)
            if not shader_info:
                continue

            uv_sets = cmds.polyUVSet(shape, query=True, allUVSets=True) or []
            per_uv_samples = []
            for uv_set in uv_sets:
                if shader_info["type"] == "file":
                    texture_node = shader_info["value"]
                    texture_path = self.get_texture_file_path(texture_node)
                    if not texture_path:
                        continue

                    if "<f>" in texture_path:
                        uv_colors = self.sample_using_dominant_color(shape, uv_set, texture_path)

                    else:
                        udim_template   = self.convert_to_udim_template(texture_path)
                        uv_colors       = self.sample_uv_colors_from_udim(shape, uv_set, udim_template)

                else:
                    uv_colors = self.sample_flat_color(shape, uv_set, shader_info["value"])
                    
                per_uv_samples.append({"uv_set": uv_set, "samples": uv_colors[:sample_count]})
                
            if per_uv_samples:
                matched_meshes.append({"object": shape, "uv_sets": per_uv_samples})

            progress_dialog.setValue(idx + 1)
            QtWidgets.QApplication.processEvents()

        progress_dialog.close()
        json_data = {"meshes": matched_meshes}

        if not json_output_path:
            json_output_path = os.path.join(cmds.internalVar(userTmpDir=True), "udim_samples.json").replace("\\", "/")
       
        try:
            output_folder = os.path.dirname(json_output_path)
            if not os.path.exists(output_folder):
                os.makedirs(output_folder)
            with open(json_output_path, "w") as f:
                json.dump(json_data, f, indent=4)
        except Exception as e:
            cmds.error(" Failed to save UV sample data: {}".format(e))
            return
        
        utils._get_oldShader_(output_path=None, jsonfile=json_output_path)
        cmds.inViewMessage(amg='<hl>✔ UDIM Sampling complete</hl>', pos='topCenter', fade=True)
        return json_output_path
