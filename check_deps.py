#!/usr/bin/env python
"""Check if required WebSocket dependencies are installed."""

import sys

required_packages = ['daphne', 'channels', 'channels_redis']
missing = []

for pkg in required_packages:
    try:
        __import__(pkg)
        print(f"✓ {pkg} is installed")
    except ImportError:
        print(f"✗ {pkg} is NOT installed")
        missing.append(pkg)

if missing:
    print(f"\nMissing packages: {', '.join(missing)}")
    print("\nInstall them with:")
    print(f"  pip install {' '.join(missing)}")
    sys.exit(1)
else:
    print("\n✓ All WebSocket dependencies are installed!")
    sys.exit(0)
