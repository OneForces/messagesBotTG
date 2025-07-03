# main.py
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.templates import parse_template
from gui.main_window import launch_gui

if __name__ == "__main__":
    launch_gui()
