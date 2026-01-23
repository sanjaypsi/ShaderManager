# from PIL import Image
# import sys
# sys.path.append(r"E:\Sanjay\tools\maya2022\ShaderManager\source")

# from core import udim_sampler
# reload(udim_sampler)
# udim_sampler._run_udim_sampler()


# from core import shader_assigner
# reload(shader_assigner)
# assigner = shader_assigner.ShaderAssigner()
# assigner.process_json_and_assign_shaders("E:/Sanjay/tools/maya2022/ShaderManager/source/config/udim_samples.json")

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