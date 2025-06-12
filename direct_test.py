import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'hivmeet_backend.simple_settings'

# Test direct sans Django setup pour voir où ça bloque
print("Testing import...")
try:
    from resources.services import ResourceService
    print("SUCCESS: ResourceService imported!")
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()
