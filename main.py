#!/usr/bin/env python3
"""
Entry point for CachyOS Update Center.
"""
import os
import sys

# Ensure local package can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cachyos_update_center.app import main

if __name__ == "__main__":
    main()
