# -*- coding: utf-8 -*-
# =====================================================================================
# UDIM Sampler for Maya (Python 2.7 Compatible)

import maya.cmds as cmds
import json
import os

SCRIPT_LOC 		= os.path.dirname(__file__)
_root       	= os.path.abspath(os.path.join(SCRIPT_LOC, ".."))
config_path 	= os.path.join(_root, "config", "config.json")

# ---------------------------------------------------------------------------------------------------
# Helper function to load configuration from JSON
# ---------------------------------------------------------------------------------------------------
def load_config(config_path):
    """Load shader tool configuration from JSON."""
    if not os.path.exists(config_path):
        raise IOError("Config file not found: {}".format(config_path))

    with open(config_path, "r") as f:
        try:
            config_data = json.load(f)
        except Exception as e:
            raise ValueError("Failed to parse config file: {}".format(e))

    print("Loaded config from {}".format(config_path))
    return config_data

# ===============================================================================
# Utility function to get shader connections and object counts 
# from selected objects or a JSON file.
# This function is used to save shader connections and object counts to a JSON file.
# If a JSON file is provided, it reads mesh paths from it.
# Otherwise, it gets shapes from the current selection.
# It processes shaders and saves the information in a structured format.
# If no output path is provided, it saves to a temporary directory.
# ===============================================================================
def _get_oldShader_(output_path=None, jsonfile=None):
	"""
	Save shader connections and object counts to a JSON file.

	If a JSON file is provided, it reads mesh paths from it.
	Otherwise, it gets shapes from the current selection.
	"""
	# --------------------------------------
	# Load shapes from JSON if provided
	# --------------------------------------
	shapes = []
	if jsonfile:
		if not os.path.exists(jsonfile):
			cmds.error("JSON file does not exist: {}".format(jsonfile))
			return

		try:
			with open(jsonfile, 'r') as f:
				json_data = json.load(f)
			print("Loaded JSON data from:", jsonfile)

			mesh_entries = json_data.get("meshes", [])
			shapes = [entry["object"] for entry in mesh_entries if "object" in entry]

		except Exception as e:
			cmds.error("Failed to read JSON file: {}".format(e))
			return
	else:
		# --------------------------------------
		# Get selected objects from the scene
		# --------------------------------------
		selection = cmds.ls(selection=True, long=True, dag=True, type="mesh")
		if not selection:
			cmds.warning("No objects selected.")
			return
		shapes = selection

	# --------------------------------------
	# Process shaders
	# --------------------------------------
	shader_info = {}

	for shape in shapes:
		if not cmds.objExists(shape):
			print("Shape does not exist in scene:", shape)
			continue

		shading_engines = cmds.listConnections(shape, type="shadingEngine") or []
		for sg in shading_engines:
			shaders = cmds.listConnections(sg + ".surfaceShader", source=True) or []
			for shader in shaders:
				if shader not in shader_info:
					shader_info[shader] = {
						"connected_objects": [],
						"object_count": 0,
					}

				connected_objs = cmds.sets(sg, query=True) or []
				for obj in connected_objs:
					if obj not in shader_info[shader]["connected_objects"]:
						shader_info[shader]["connected_objects"].append(obj)

				shader_info[shader]["object_count"] = len(shader_info[shader]["connected_objects"])

	if not shader_info:
		cmds.warning("No shader connections found.")
		return

	json_data = {
		"shader_connections": shader_info
	}

	print("Shader connection data:", json.dumps(json_data, indent=4))

	output_path = os.path.dirname(jsonfile)
	output_path = os.path.join(output_path, "OlderShader.json").replace("\\", "/")

	try:
		with open(output_path, "w") as f:
			json.dump(json_data, f, indent=4)
		print("Shader connection data saved to:", output_path)
	except Exception as e:
		cmds.error("Failed to save JSON: {}".format(e))

	return output_path

# ===============================================================================
# Function to get the reference 
# This function checks if a reference node exists 
# If it exists, it returns the name of the reference node.
# If not, it returns None.
# ===============================================================================
def _get_allReferenceNode_():
	"""
	Get the reference node 
	
	Returns:
		str: Name of the reference node if it exists, otherwise None.
	"""
	
	reference_nodes = cmds.ls(type="reference")
	if reference_nodes:
		return reference_nodes
	else:
		print("No reference node found.")
		return None

# ===============================================================================
def get_network_node():
	refernce = _get_allReferenceNode_()
	for ref_node in refernce:
		ref_path = cmds.referenceQuery(ref_node, filename=True)


# ===============================================================================
# Function to create a protected network node for storing shader information
# This function creates a network node that is protected and has specific display attributes.
# It checks if the node already exists and returns it if found.
# If not, it creates a new network node with the specified attributes.
# ===============================================================================
def _create_shaderNode_():
	"""
	Create a protected network node to store information and assigned meshes.
	
	Args:
		node_name (str): Name of the network node to create.

	Returns:
		str: Name of the created network node.
	"""
	# --------------------------------------
	# Check if the node already exists
	# --------------------------------------
	node_name       = "ShaderNetwork"
	existing_nodes  = cmds.ls("ShaderNetwork", type="network")
	if existing_nodes:
		print("Network node already exists:", existing_nodes[0])
		return existing_nodes[0]
	
	else:
		print("Creating new network node:", node_name)
		# --------------------------------------
		# Create a network node
		node = cmds.createNode("network", name=node_name)
		cmds.setAttr(node + ".protected", 1)
		cmds.setAttr(node + ".displayHandle", 1)
		cmds.setAttr(node + ".displayType", 2)
		cmds.setAttr(node + ".displayColor", 17)  # Set a color for the node
		cmds.setAttr(node + ".displayLabel", "Shader Network")
		cmds.setAttr(node + ".displayName", "Shader Network")
		cmds.setAttr(node + ".displayIcon", "network.png")
		print("Network node created:", node)
		return node
	
# ===============================================================================
# Class to manage shader nodes for references
# This class processes all reference nodes in the scene and creates shader metadata nodes.
# It provides methods to get all reference nodes, sanitize names, add attributes,
# extract asset type and revision from file paths, and create shader nodes with metadata.
# The shader nodes store information about the reference file path, type, namespace, and revision.
# It also handles errors during processing and prints status messages.
# ===============================================================================
class ReferenceShaderNodeManager(object):
	def __init__(self):

		self.config 	= load_config(config_path)
		self.ShaderPath = self.config.get("ShaderPath", "")

		self.created_nodes = []

	# ---------------------------------------------------------------------------
	# Process all reference nodes and create shader metadata nodes
	# ---------------------------------------------------------------------------
	def process_all_references(self):
		"""Process all reference nodes in the scene and create shader metadata nodes."""
		ref_nodes = self.get_all_reference_nodes()
		for ref_node in ref_nodes:
			self.create_shader_node_for_reference(ref_node)

		print("\n Done. Created %d shader network nodes." % len(self.created_nodes))
		return self.created_nodes

	# ---------------------------------------------------------------------------
	def get_all_reference_nodes(self):
		"""Return all user reference nodes, excluding internal ones like sharedReferenceNode."""
		all_refs = cmds.ls(type='reference')
		return [ref for ref in all_refs if not ref.startswith('sharedReferenceNode')]

	# ---------------------------------------------------------------------------
	def sanitize_name(self, name):
		"""Sanitize names to be safe for Maya node naming."""
		return name.replace(" ", "_").replace("-", "_").replace(".", "_")

	# ---------------------------------------------------------------------------
	def add_string_attr(self, node, attr_name, value):
		"""Add a string attribute to the node safely."""
		if not cmds.attributeQuery(attr_name, node=node, exists=True):
			cmds.addAttr(node, longName=attr_name, dataType="string")
		cmds.setAttr(node + "." + attr_name, value, type="string")

	# ---------------------------------------------------------------------------
	def add_bool_attr(self, node, attr_name, value):
		"""Add a boolean attribute to the node safely."""
		if not cmds.attributeQuery(attr_name, node=node, exists=True):
			cmds.addAttr(node, longName=attr_name, attributeType="bool")
		cmds.setAttr(node + "." + attr_name, bool(value))

	# ---------------------------------------------------------------------------
	def _extract_asset_type(self, file_path):
		"""Extract asset type from file path, e.g., 'assets/char/hero/hero_rig.ma' → 'char'."""
		file_path = file_path.lower().replace("\\", "/")
		parts = file_path.split("/")
		if "assets" in parts:
			idx = parts.index("assets")
			if idx + 1 < len(parts):
				return parts[idx + 1]
		return "unknown"

	# ---------------------------------------------------------------------------
	def _extract_revision(self, path):
		"""Extract revision (e.g., r0008) from the path."""
		parts = path.replace("\\", "/").split("/")
		for part in parts:
			if part.lower().startswith("r") and part[1:].isdigit():
				return part
		return "N/A"
	
	# ---------------------------------------------------------------------------
	def create_shader_node_for_reference(self, ref_node):
		try:
			if not cmds.referenceQuery(ref_node, isLoaded=True):
				print(" Skipping unloaded reference: %s" % ref_node)
				return None

			ref_file_path  = cmds.referenceQuery(ref_node, filename=True)
			ref_namespace  = cmds.referenceQuery(ref_node, namespace=True)
			asset_type     = self._extract_asset_type(ref_file_path)

			if asset_type in ["character", "camera"]:
				return None

			file_name     = os.path.splitext(os.path.basename(ref_file_path))[0]
			ref_revision  = self._extract_revision(ref_file_path)
			parts         = self.sanitize_name(ref_namespace).split(":")
			clean_ns      = parts[-1] if parts else "unknownNS"

			node_name     = clean_ns + "_shaderInfo"
			jsonfile_name = node_name + ".json"

			asset_path    = os.path.join(self.ShaderPath, asset_type, file_name, ref_revision, jsonfile_name).replace("\\", "/")
			shader_path   = os.path.join(self.ShaderPath, asset_type, file_name, ref_revision, "shaderInfo.json").replace("\\", "/")

			if cmds.objExists(node_name):
				if os.path.isfile(asset_path):
					with open(asset_path, "r") as f:
						data  	= json.load(f)
						value 	= data.get("namespace", "NA")
						status 	= cmds.getAttr("%s.status" % node_name)
						# if status == "Assigned":
						# 	pass
						# else:
						# 	cmds.setAttr("%s.status" % node_name, value.encode("utf-8"), type="string")

				return node_name

			shader_node = cmds.createNode("network", name=node_name)

			# Metadata
			self.add_string_attr(shader_node, "referenceFilePath", ref_file_path)
			self.add_string_attr(shader_node, "referenceNode", ref_node)
			self.add_string_attr(shader_node, "fileName", file_name)
			self.add_string_attr(shader_node, "referenceType", asset_type)
			self.add_string_attr(shader_node, "referenceNamespace", ref_namespace)
			self.add_string_attr(shader_node, "referenceRevision", ref_revision)
			self.add_string_attr(shader_node, "status", "NA")
			
			if os.path.isfile(asset_path):
				attr_name = "{}.status".format(node_name)
				with open(asset_path, "r") as f:
					data  	= json.load(f)
					value 	= data.get("namespace", "NA")
					cmds.setAttr(attr_name, value, type="string")

			if os.path.isfile(shader_path):
				attr_name 	= "{}.status".format(node_name)
				value 		= "Shader-Generated"
				cmds.setAttr(attr_name, value, type="string")

			if not cmds.attributeQuery("annotation", node=shader_node, exists=True):
				cmds.addAttr(shader_node, longName="annotation", dataType="string")
			cmds.setAttr(shader_node + ".annotation", "Shader Network Node", type="string")

			print(" Created shader node: %s" % shader_node)
			self.created_nodes.append(shader_node)
			return shader_node

		except Exception as e:
			print(" Error processing %s: %s" % (ref_node, str(e)))
			return None


