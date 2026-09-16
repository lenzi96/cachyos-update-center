#!/usr/bin/env python3
"""
Entry point for CachyOS Update Center.
"""
import os
import sys

# Ensure local package can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if any(arg in sys.argv for arg in ("--download-and-install", "-h", "--help")):
    import argparse
    parser = argparse.ArgumentParser(description="CachyOS Update Center")
    parser.add_argument("--download-and-install", action="store_true")
    parser.add_argument("--version", default="")
    parser.add_argument("--asset-url", default="")
    parser.add_argument("--tarball-url", default="")
    parser.add_argument("--token", default="")
    args, _ = parser.parse_known_args()
    if args.download_and_install:
        from cachyos_update_center.updater import download_and_install_release
        sys.exit(download_and_install_release(args.version, args.asset_url, args.tarball_url, args.token))

from cachyos_update_center.app import main

if __name__ == "__main__":
    main()
