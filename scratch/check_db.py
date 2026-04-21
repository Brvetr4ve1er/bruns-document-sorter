import os, sys
try:
    import db
    print("db found")
except ImportError as e:
    print(f"db not found: {e}")

print("Current dir:", os.getcwd())
print("sys.path[0]:", sys.path[0])
