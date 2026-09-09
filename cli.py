"""
Command Line Interface for Indian Fundamental News & Analysis (FNA) Engine.
CLI wrapper delegating to main.py.
Zero API keys, zero web server, 100% terminal-based.
"""

import sys
import os

# Delegate directly to main.py
from main import main

if __name__ == "__main__":
    main()
