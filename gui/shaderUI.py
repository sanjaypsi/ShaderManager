# -*- coding: utf-8 -*-
# =====================================================================================
# UDIM Sampler for Maya (Python 2.7 Compatible)
# =====================================================================================
"""
	Creation Date: 2025.07.10
	Author: Sanjay Kamble

	Shader Tool UI for Maya using PySide2 (Python 2.7)
	- Reads references from Maya scene
	- Supports asset types: char, set, prop
	- Dark themed stylesheet
"""

import os
import json

import maya.cmds as cmds
import maya.OpenMayaUI as omui
from shiboken2 import wrapInstance
from PySide2 import QtUiTools, QtWidgets, QtCore, QtGui
from PySide2.QtWidgets import (
	QMainWindow, QWidget, QMessageBox, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PySide2.QtCore import QFile

# ---------------------------------------------------------------------------------------------------
SCRIPT_LOC 		= os.path.dirname(__file__)
shader_ui_file 	= os.path.join(SCRIPT_LOC, "ui", "shaderUI.ui")
_root       	= os.path.abspath(os.path.join(SCRIPT_LOC, ".."))
config_path 	= os.path.join(_root, "config", "config.json")

from core import udim_sampler
from core import shader_assigner
from core import utils
from core import shader_re_assigner

reload(udim_sampler) 	# dev mode, reload the module
reload(shader_assigner) # dev mode, reload the module
reload(utils)
reload(shader_re_assigner)


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

# ---------------------------------------------------------------------------------------------------
# Helper function to get Maya's main window as a QWidget
# This is necessary to set the parent for the UI window
# ---------------------------------------------------------------------------------------------------
def get_maya_window():
	main_window_ptr = omui.MQtUtil.mainWindow()
	if not main_window_ptr:
		raise RuntimeError("Failed to obtain Maya's main window.")
	return wrapInstance(long(main_window_ptr), QWidget)

# ---------------------------------------------------------------------------------------------------
# Load UI from .ui file using QUiLoader
# ---------------------------------------------------------------------------------------------------
def load_ui(ui_file, parent=None):
	loader = QtUiTools.QUiLoader()
	ui_file = QFile(ui_file)
	if not ui_file.exists():
		raise IOError("UI file {} not found.".format(ui_file.fileName()))
	ui_file.open(QFile.ReadOnly)
	ui_widget = loader.load(ui_file, parent)
	ui_file.close()
	if not ui_widget:
		raise RuntimeError("Failed to load UI file {}.".format(ui_file.fileName()))
	return ui_widget


class ShaderToolWindow(QMainWindow):
	REFERENCE_COLUMN_WIDTH = 600

	# ---------------------------------------------------------------------------------------------------
	# Constructor
	# ---------------------------------------------------------------------------------------------------
	def __init__(self, parent=None):
		super(ShaderToolWindow, self).__init__(parent)

		# Load UI
		self.ui = load_ui(shader_ui_file, parent=self)
		self.setWindowTitle("Shader Tool")
		self.resize(1250, 500)
		
		self.ui.splitter.setSizes([200, 500, 200])

		# load_config
		try:
			self.config = load_config(config_path)
		except Exception as e:
			print("Error loading config: {}".format(e))
			self.config = {}

		# -- NETnetwork node 
		manager = utils.ReferenceShaderNodeManager()
		manager.process_all_references()

		# Apply Dark Theme
		self.apply_stylesheet()

		# Find UI elements
		self.checkbox 			= self.ui.findChild(QtWidgets.QCheckBox, "checkBox")
		self.table 				= self.ui.findChild(QtWidgets.QTableWidget, "tableWidget")
		self.generate_button 	= self.ui.findChild(QtWidgets.QPushButton, "pushButton")
		self.assign_button 		= self.ui.findChild(QtWidgets.QPushButton, "pushButton_2")
		self.re_assign_button 	= self.ui.findChild(QtWidgets.QPushButton, "ReAssigin_oldShader_BTN")

		# Enable Ctrl/Shift multi-selection
		self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)

		# Ensure full rows are selected (instead of individual cells)
		self.table.setSelectionBehavior(QAbstractItemView.SelectRows)

		# Connect signals
		self.generate_button.clicked.connect(self.get_selected_table_rows)
		self.assign_button.clicked.connect(self.assign_shader_to_objects)
		self.re_assign_button.clicked.connect(self.re_assign_old_shader)

		# Populate
		self._create_menu_bar()
		self.populate_table()
		self.get_data_from_table()
		self.add_result_to_table()

	# ---------------------------------------------------------------------------------------------------
	# Setup the main window
	# ---------------------------------------------------------------------------------------------------
	def _create_menu_bar(self):
		menu_bar = self.menuBar()

		# File Menu
		file_menu 		= menu_bar.addMenu("File")
		refresh_action 	= file_menu.addAction("Refresh")
		exit_action 	= file_menu.addAction("Exit")

		refresh_action.triggered.connect(self.populate_table)
		exit_action.triggered.connect(self.close)

		# Help Menu
		help_menu 		= menu_bar.addMenu("Help")
		about_action 	= help_menu.addAction("About")
		about_action.triggered.connect(self.show_about_dialog)

	# ---------------------------------------------------------------------------------------------------
	# Show About dialog
	# ---------------------------------------------------------------------------------------------------
	def show_about_dialog(self):
		QMessageBox.information(self, "About", "Shader Tool\nVersion 1.0\nAuthor: Sanjay Kamble")

    # ---------------------------------------------------------------------------------------------------
    # Safely get attribute with fallback
    # ---------------------------------------------------------------------------------------------------
	def safe_get_attr(self, node, attr_name, default="N/A"):
		full_attr = "%s.%s" % (node, attr_name)
		if cmds.objExists(full_attr):
			try:
				return cmds.getAttr(full_attr)
			except Exception:
				return default
		return default

	# ---------------------------------------------------------------------------------------------------
	# Gather all shader network node data
	# ---------------------------------------------------------------------------------------------------
	def get_network_node(self):
		network_nodes = cmds.ls(type="network")
		data = []

		if network_nodes:
			for node in network_nodes:
				if not cmds.attributeQuery("referenceFilePath", node=node, exists=True):
					continue  # Not a shader metadata node

				referenceFilePath   = self.safe_get_attr(node, "referenceFilePath")
				referenceNode       = self.safe_get_attr(node, "referenceNode")
				fileName            = self.safe_get_attr(node, "fileName")
				referenceNamespace  = self.safe_get_attr(node, "referenceNamespace")
				referenceType       = self.safe_get_attr(node, "referenceType")
				referenceRevision   = self.safe_get_attr(node, "referenceRevision")
				status              = self.safe_get_attr(node, "status", "False")

				asset_type = self._extract_asset_type(referenceFilePath)

				data.append({
					"reference_path" : referenceFilePath.replace("/", "\\"),
					"asset_type"     : referenceType,
					"assets_name"    : fileName,
					"revision"       : referenceRevision,
					"result"         : str(status),
				})

		return data

	# ---------------------------------------------------------------------------------------------------
	# Populate the table with data from network nodes
	# ---------------------------------------------------------------------------------------------------
	def populate_table(self):
		data = self.get_network_node()

		print(data)
		self.table.setRowCount(len(data))
		self.table.setColumnCount(5)
		self.table.setHorizontalHeaderLabels(["Reference_Path", 
											"Asset_Type", 
											"Assets_Name", 
											"Revision", 
											"Result"])

		for row, entry in enumerate(data):
			# Column 0: Reference Path
			item_path = QTableWidgetItem(entry["reference_path"])
			item_path.setFont(QtGui.QFont("Arial", 10))
			self.table.setItem(row, 0, item_path)

			# Column 1: Asset Type
			item_type = QTableWidgetItem(entry["asset_type"])
			item_type.setFont(QtGui.QFont("Arial", 10))
			item_type.setTextAlignment(QtCore.Qt.AlignCenter)
			self.table.setItem(row, 1, item_type)

			# Column 2: Asset Name
			item_name = QTableWidgetItem(entry["assets_name"])
			item_name.setFont(QtGui.QFont("Arial", 10))
			item_name.setTextAlignment(QtCore.Qt.AlignCenter)
			self.table.setItem(row, 2, item_name)

			# Column 3: Revision
			item_rev = QTableWidgetItem(entry["revision"])
			item_rev.setFont(QtGui.QFont("Arial", 10))
			item_rev.setTextAlignment(QtCore.Qt.AlignCenter)
			self.table.setItem(row, 3, item_rev)

			# Column 4: Result / Status
			item_result = QTableWidgetItem(entry["result"])
			item_result.setFont(QtGui.QFont("Arial", 10))
			item_result.setTextAlignment(QtCore.Qt.AlignCenter)
			self.table.setItem(row, 4, item_result)

		# Adjust column widths
		header = self.table.horizontalHeader()
		self.REFERENCE_COLUMN_WIDTH = 750 
		self.table.setColumnWidth(0, self.REFERENCE_COLUMN_WIDTH)
		header.setStretchLastSection(True)
		for i in range(1, self.table.columnCount()):
			header.setSectionResizeMode(i, QHeaderView.Stretch)

		print("Loaded %d shader metadata references." % len(data))

	# ---------------------------------------------------------------------------------------------------
	# Helper methods
	# ---------------------------------------------------------------------------------------------------
	def _extract_asset_type(self, path):
		"""Extract asset type from the path (char, set, prop)."""
		parts = path.replace("\\", "/").lower().split("/")
		for asset in ["character", "set", "setProp", "prop", "camera"]:
			if asset in parts:
				return asset
			
		return "unknown"

	# ---------------------------------------------------------------------------------------------------
	# Extract revision from the path (e.g., r0008)
	# ---------------------------------------------------------------------------------------------------
	def _extract_revision(self, path):
		"""Extract revision (e.g., r0008) from the path."""
		parts = path.replace("\\", "/").split("/")
		for part in parts:
			if part.lower().startswith("r") and part[1:].isdigit():
				return part
		return "N/A"

	# ---------------------------------------------------------------------------------------------------
	# Generate and assign shader methods
	# ---------------------------------------------------------------------------------------------------
	def generate_shader(self):
		selected_only = self.checkbox.isChecked()
		print("Generate Shader clicked. Selected only: {}".format(selected_only))
		rows = self.get_selected_rows() if selected_only else range(self.table.rowCount())

		for row in rows:
			asset_name = self.table.item(row, 2).text()
			print("Generating shader for: {}".format(asset_name))
			self.table.setItem(row, 4, QTableWidgetItem("Generated"))

		QMessageBox.information(self, "Shader Generation", "Shader generation completed.")

	# ---------------------------------------------------------------------------------------------------
	# Assign shader to selected rows
	# ---------------------------------------------------------------------------------------------------
	def assign_shader(self, status=None):
		"""Assign shader status to selected or all rows."""
		selected_only = self.checkbox.isChecked()
		rows = self.get_selected_rows() if selected_only else range(self.table.rowCount())

		for row in rows:
			asset_name = self.table.item(row, 2).text()

			# Determine status color and label
			if status == "NA":
				result_text = "NA"
				bg_color = QtGui.QColor("#c62828")  # Red

			elif status == "Shader-Generated":
				result_text = "Shader-Generated"
				bg_color = QtGui.QColor("#ff9800")  # Orange

			elif status == "Assigned":
				result_text = "Assigned"
				bg_color = QtGui.QColor("#2e7d32")  # Green

			else:
				result_text = status or "Unknown"
				bg_color = QtGui.QColor("#616161")  # Gray fallback

			result_item = QTableWidgetItem(result_text)
			result_item.setTextAlignment(QtCore.Qt.AlignCenter)
			result_item.setBackground(bg_color)
			result_item.setForeground(QtGui.QColor("#ffffff"))

			self.table.setItem(row, 4, result_item)

	# ---------------------------------------------------------------------------------------------------
	# Get selected rows from the table
	# ---------------------------------------------------------------------------------------------------
	def get_selected_rows(self):
		selected = self.table.selectionModel().selectedRows()
		return [index.row() for index in selected]

	# ---------------------------------------------------------------------------------------------------
	# Apply dark theme stylesheet
	# ---------------------------------------------------------------------------------------------------
	def apply_stylesheet(self):
		"""Apply a dark theme stylesheet."""

		dark_style = """
			QWidget { background-color: #2b2b2b; color: #ddd; font-size: 12px; }
			QPushButton { background-color: #444; border: 1px solid #555; padding: 4px; }
			QPushButton:hover { background-color: #555; }

			QHeaderView::section { background-color: #3a3a3a; color: #ccc; padding: 4px; }
			QHeaderView::section:horizontal,
			QHeaderView::section:vertical { border: 1px solid #555; }

			/* CheckBox styles */
			QCheckBox { padding: 2px; color: #ddd; }
			QCheckBox:hover { cursor: pointer; }

			QCheckBox::indicator {
				width: 16px;
				height: 16px;
				background-color: #444;
				border: 1px solid #555;
			}

			/* Checked states */
			QCheckBox::indicator:checked { background-color: #2e7d32; border: 1px solid #555; }
			QCheckBox::indicator:checked:hover { background-color: #388e3c; }
			QCheckBox::indicator:checked:pressed { background-color: #1b5e20; }
			QCheckBox::indicator:checked:disabled { background-color: #2e7d32; border: 1px solid #555; }

			/* Unchecked states */
			QCheckBox::indicator:unchecked { background-color: #c62828; border: 1px solid #555; }
			QCheckBox::indicator:unchecked:hover { background-color: #e53935; }
			QCheckBox::indicator:unchecked:pressed { background-color: #b71c1c; }
			QCheckBox::indicator:unchecked:disabled { background-color: #c62828; border: 1px solid #555; }
		"""

		self.setStyleSheet(dark_style)

	# ---------------------------------------------------------------------------------------------------
	# get populate table data
	# ---------------------------------------------------------------------------------------------------
	def get_data_from_table(self):
		"""Get data from the table as a list of dictionaries."""
		data = []
		for row in range(self.table.rowCount()):
			item = {
				"reference_path"	: self.table.item(row, 0).text(),
				"asset_type"		: self.table.item(row, 1).text(),
				"assets_name"		: self.table.item(row, 2).text(),
				"revision"			: self.table.item(row, 3).text(),
				"result"			: self.table.item(row, 4).text(),
			}
			data.append(item)

		return data
	
	# ---------------------------------------------------------------------------------------------------
	# add result to table
	# ---------------------------------------------------------------------------------------------------
	def add_result_to_table(self):
		"""Check shaderInfo.json exists for each reference and update the result column with color."""
		data = self.get_data_from_table()
		texture_paths = self.config.get("ShaderPath", "")

		for row, entry in enumerate(data):
			asset_type  = entry["asset_type"]
			assets_name = entry["assets_name"]
			revision    = entry["revision"]
			status      = entry["result"]

			# Initialize default values
			result_text = "Unknown"
			bg_color = QtGui.QColor("#616161")  # Gray for unknown

			if status == "NA":
				result_text = "NA"
				bg_color = QtGui.QColor("#c62828")  # Red
			elif status == "Shader-Generated":
				result_text = "Shader-Generated"
				bg_color = QtGui.QColor("#ff9800")  # Orange
			elif status == "Assigned":
				result_text = "Assigned"
				bg_color = QtGui.QColor("#2e7d32")  # Green

			result_item = QtWidgets.QTableWidgetItem(result_text)
			result_item.setTextAlignment(QtCore.Qt.AlignCenter)
			result_item.setBackground(bg_color)
			result_item.setForeground(QtGui.QColor("#ffffff"))

			self.table.setItem(row, 4, result_item)

	# ---------------------------------------------------------------------------------------------------
	# Get selected table items as a list of dictionaries
	# ---------------------------------------------------------------------------------------------------
	def get_selected_table_rows(self):
		"""Get selected rows from the table and save to JSON if shaderInfo is missing."""

		selected_only 	= self.checkbox.isChecked()
		selected_data 	= []
		json_data_list 	= []

		# Get data from selected or all rows
		if selected_only:
			selected_indexes = self.table.selectionModel().selectedRows()
			if not selected_indexes:
				QMessageBox.warning(self, "No Selection", "Please select at least one row.")
				return []
			rows = [index.row() for index in selected_indexes]
		else:
			rows = range(self.table.rowCount())

		# Extract data from rows
		for row in rows:
			row_data = {
				"reference_path"	: self.table.item(row, 0).text(),
				"asset_type"		: self.table.item(row, 1).text(),
				"assets_name"		: self.table.item(row, 2).text(),
				"revision"			: self.table.item(row, 3).text(),
				"result"			: self.table.item(row, 4).text(),
			}
			selected_data.append(row_data)

		# Process each selected row
		for data in selected_data:
			if data["result"] == "True":
				QMessageBox.information(self, "Result", "Shader Info exists for: {}".format(data["assets_name"]))
			
			else:
				# Prepare JSON data
				reference_path = data["reference_path"].replace("\\", "/")
				# get reference node from the path
				reference_node = cmds.file(reference_path, query=True, referenceNode=True)
				# get namespace from the reference node
				namespace = cmds.referenceQuery(reference_node, namespace=True)

				json_data = {
					"reference_path"	: data["reference_path"],
					"asset_type"		: data["asset_type"],
					"assets_name"		: data["assets_name"],
					"revision"			: data["revision"],
					"namespace"			: namespace,
					"reference_node"	: reference_node,

				}
				json_data_list.append(json_data)
				print("Shader Info missing, preparing JSON for:", data["assets_name"])

		# Save to JSON if there are items to generate
		if json_data_list:
			json_string = json.dumps(json_data_list, indent=4)

			# Save to Maya's temp directory
			temp_dir 	= cmds.internalVar(userTmpDir=True)
			temp_file 	= os.path.join(temp_dir, "shaderGeneration.json")

			try:
				with open(temp_file, "w") as f:
					f.write(json_string)

				# print("Shader info saved to:", temp_file)
				# QMessageBox.information(self, "Success", "Shader info saved to:\n{}".format(temp_file))

			except IOError as e:
				print("Failed to save shaderInfo.json:", e)
				QMessageBox.critical(self, "Error", "Failed to save JSON file:\n{}".format(e))
				return []
		else:
			print("All selected rows already have shaderInfo.json.")
	
		self.pass_shader_generation_json() # Call the method to process the JSON file
		# QMessageBox.information(self, "Shader Generation", "Shader generation completed for selected rows.")
		return selected_data
	
	# ---------------------------------------------------------------------------------------------------
	# get the shaderGeneration.json file path
	# ---------------------------------------------------------------------------------------------------
	def get_shader_generation_json_path(self):
		"""Load and return the contents of the shaderGeneration.json file as a dictionary."""
		
		# Get Maya's user temp directory and build the file path
		temp_dir = cmds.internalVar(userTmpDir=True)
		temp_file = os.path.join(temp_dir, "shaderGeneration.json").replace("\\", "/")
		
		# Check if the file exists
		if not os.path.exists(temp_file):
			QMessageBox.warning(self, "File Not Found", "Shader generation JSON file not found:\n{}".format(temp_file))
			return None

		# Attempt to open and load the JSON file
		try:
			with open(temp_file, "r") as f:
				data = json.load(f)

			return data
		
		except Exception as e:
			QMessageBox.critical(self, "Invalid JSON", "Failed to load JSON from file:\n{}\n\nError: {}".format(temp_file, e))
			return None

	# ---------------------------------------------------------------------------------------------------
	# pass the shaderGeneration.json file to udim_sampler
	# ---------------------------------------------------------------------------------------------------
	def pass_shader_generation_json(self):
		"""Pass the shaderGeneration.json file to the UDIM sampler."""
		data 			= self.get_shader_generation_json_path()
		self.config 	= load_config(config_path)
		texture_paths 	= self.config.get("ShaderPath", "")

		if not data:
			QMessageBox.warning(self, "No Data", "No data found in shaderGeneration.json.")
			return

		for item in data:
			reference_path 	= item["reference_path"]
			asset_type 		= item["asset_type"]
			assets_name 	= item["assets_name"]
			revision 		= item["revision"]
			namespace 		= item["namespace"]
			reference_node 	= item["reference_node"]

			# Construct the texture path
			# makeDir if not exists
			if not os.path.exists(os.path.join(texture_paths, asset_type, assets_name, revision).replace("\\", "/")):
				os.makedirs(os.path.join(texture_paths, asset_type, assets_name, revision).replace("\\", "/"))

			texture_path = os.path.join(texture_paths, asset_type, 
							   			assets_name, revision, "shaderInfo.json").replace("\\", "/")

			# Here you can call the UDIMSampler methods with the data
			# For example, you can create an instance of UDIMSampler and call its methods
			# Create an instance of UDIMSampler
			sampler = udim_sampler.UDIMSampler()

			# Sample and save all meshes
			try:
				result = sampler.sample_and_save_all_meshes(
					sample_count		=5,
					json_output_path	=texture_path,
					reference_node		=reference_node,
					namespace			=namespace
				)

				if os.path.isfile(result):
					namespace		= namespace.split(":")[1]
					node_name  		= namespace + "_shaderInfo.json"
					print(node_name)
					logs_path = os.path.join(texture_paths, asset_type, 
								assets_name, revision, node_name).replace("\\", "/")
					
					data = {
						"namespace": "Shader-Generated"
					}

					with open(logs_path, "w") as f:
						json.dump(data, f, indent=4)

					node_name  = namespace + "_shaderInfo"
					if cmds.objExists(node_name):
						cmds.setAttr("%s.status" % node_name, "Shader-Generated", type="string")
						self.assign_shader("Shader-Generated")

			except Exception as e:
				print("Error during UDIM sampling:", e)

	# ---------------------------------------------------------------------------------------------------
	# assign shader to objects
	# ---------------------------------------------------------------------------------------------------
	def assign_shader_to_objects(self):
		"""Assign shaders to objects based on the shaderGeneration.json file."""
		selected_only 	= self.checkbox.isChecked()
		selected_data 	= []

		# Get data from selected or all rows
		if selected_only:
			selected_indexes = self.table.selectionModel().selectedRows()
			if not selected_indexes:
				QMessageBox.warning(self, "No Selection", "Please select at least one row.")
				return []
			rows = [index.row() for index in selected_indexes]
		else:
			rows = range(self.table.rowCount())

		# Extract data from rows
		for row in rows:
			row_data = {
				"reference_path"	: self.table.item(row, 0).text(),
				"asset_type"		: self.table.item(row, 1).text(),
				"assets_name"		: self.table.item(row, 2).text(),
				"revision"			: self.table.item(row, 3).text(),
				"result"			: self.table.item(row, 4).text(),
			}
			selected_data.append(row_data)

		# Process each selected row
		self.config 	= load_config(config_path)
		texture_paths 	= self.config.get("ShaderPath", "")

		for data in selected_data:
			if data["result"] == "Shader-Generated":
				# Generate the texture path
				texture_path 	= os.path.join(texture_paths, data["asset_type"], 
									data["assets_name"], data["revision"], "shaderInfo.json").replace("\\", "/")
				
				assigner 		= shader_assigner.ShaderAssigner()
				assigner.process_json_and_assign_shaders(texture_path)
				QMessageBox.information(self, "Result", "Shader assigned for: {}".format(data["assets_name"]))

				reference_path 	= data["reference_path"].replace("\\", "/")
				# get reference node from the path
				reference_node 	= cmds.file(reference_path, query=True, referenceNode=True)
				# get namespace from the reference node
				namespace 		= cmds.referenceQuery(reference_node, namespace=True)
				namespace		= namespace.split(":")[1]
				node_name  		= namespace + "_shaderInfo.json"
				logs_path = os.path.join(texture_paths, data["asset_type"], 
							data["assets_name"], data["revision"], node_name).replace("\\", "/")
				
				data = {
					"namespace": "Assigned"
				}

				with open(logs_path, "w") as f:
					json.dump(data, f, indent=4)

				node_name  = namespace + "_shaderInfo"
				if cmds.objExists(node_name):
					cmds.setAttr("%s.status" % node_name, "Assigned", type="string")
					self.assign_shader("Assigned")

			else:
				QMessageBox.warning(self, "Result", "Shader Info missing for: {}".format(data["assets_name"]))
				continue

		# self.assign_shader("Assigned")  # Call the assign_shader method to update the UI

	# ---------------------------------------------------------------------------------------------------
	# re assign old shader
	# --------------------------------------------------------------------------------------------------
	def re_assign_old_shader(self):
		"""Reassign old shaders to objects based on the shaderGeneration.json file."""
		selected_only 	= self.checkbox.isChecked()
		selected_data 	= []

		# Get data from selected or all rows
		if selected_only:
			selected_indexes = self.table.selectionModel().selectedRows()
			if not selected_indexes:
				QMessageBox.warning(self, "No Selection", "Please select at least one row.")
				return []
			rows = [index.row() for index in selected_indexes]
		else:
			rows = range(self.table.rowCount())

		# Extract data from rows
		for row in rows:
			row_data = {
				"reference_path"	: self.table.item(row, 0).text(),
				"asset_type"		: self.table.item(row, 1).text(),
				"assets_name"		: self.table.item(row, 2).text(),
				"revision"			: self.table.item(row, 3).text(),
				"result"			: self.table.item(row, 4).text(),
			}
			selected_data.append(row_data)

		# Process each selected row
		self.config 	= load_config(config_path)
		texture_paths 	= self.config.get("ShaderPath", "")

		for data in selected_data:
			asset_type 		= (data.get("asset_type") or "").strip()
			assets_name 	= (data.get("assets_name") or "").strip()
			reference_path 	= (data.get("reference_path") or "").strip()
			revision 		= (data.get("revision") or "").strip()
			result 			= (data.get("result") or "").strip()
			shaderPath 		= os.path.join(texture_paths, asset_type, assets_name, revision, "OlderShader.json").replace("\\", "/")
			
			if result == "Assigned":
				# Reassign the old shader
				re_assigner = shader_re_assigner.ShaderReAssigner( shaderPath)
				QMessageBox.information(self, "Result", "Old shader reassigned for: {}".format(assets_name))

				# update Result
				self.table.item(row, 4).setText("Shader-Generated")
				bg_color = QtGui.QColor("#ff9800")  # Orange
				self.table.item(row, 4).setBackground(bg_color)

				# get network node update Status
				# join name wEBAtriumA_shaderInfo
				network_node = '_'.join([assets_name, "shaderInfo"])
				if cmds.objExists(network_node):
					cmds.setAttr("%s.status" % network_node, "Shader-Generated", type="string")


# ====================================================================================================
shader_tool_window = None
# ====================================================================================================
def show_shader_tool():
	global shader_tool_window
	try:
		shader_tool_window.close()
		shader_tool_window.deleteLater()
	except:
		pass

	shader_tool_window = ShaderToolWindow(parent=get_maya_window())
	shader_tool_window.show()
