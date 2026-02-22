import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.db import connection
cursor = connection.cursor()
cursor.execute("DROP DATABASE IF EXISTS test_hivmeet_db;")
print("✅ Test database dropped")
