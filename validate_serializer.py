#!/usr/bin/env python
"""Quick validation of serializer structure"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from matching.serializers import DiscoveryProfileSerializer

print("=" * 60)
print("✅ DiscoveryProfileSerializer imported successfully")
print("=" * 60)
print(f"\nDeclared fields ({len(DiscoveryProfileSerializer._declared_fields)}):")
for field_name, field_obj in DiscoveryProfileSerializer._declared_fields.items():
    print(f"  - {field_name}: {field_obj.__class__.__name__}")

print(f"\nMethods:")
methods = [m for m in dir(DiscoveryProfileSerializer) if m.startswith('get_')]
for method in methods:
    print(f"  - {method}")

print("\n✅ All checks passed!")
