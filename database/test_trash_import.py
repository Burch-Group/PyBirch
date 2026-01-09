"""Test trash service import."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

output_file = os.path.join(os.path.dirname(__file__), 'trash_import_output.txt')


print("Testing TrashService Import\n")
print("=" * 50 + "\n\n")

try:
    from database.trash_service import TrashService
    print("TrashService import: SUCCESS\n")
    
    ts = TrashService()
    print("TrashService instantiation: SUCCESS\n")
except Exception as e:
    import traceback
    print(f"ERROR: {e}\n\n")
    print(traceback.format_exc())


print("Testing routes.py import step by step\n\n")

# Check routes.py line by line around the trash section
routes_file = os.path.join(os.path.dirname(__file__), 'web', 'routes.py')
with open(routes_file, 'r', encoding='utf-8') as rf:
    lines = rf.readlines()

print(f"Total lines in routes.py: {len(lines)}\n\n")

# Find the Trash Management section
for i, line in enumerate(lines):
    if "Trash Management" in line:
        print(f"Found 'Trash Management' at line {i+1}\n")
        print(f"Line content: {repr(line)}\n\n")
        
        # Show lines around it
        print("Context (20 lines after):\n")
        for j in range(i, min(len(lines), i+25)):
            print(f"  {j+1}: {lines[j].rstrip()[:80]}")
        break
else:
    print("'Trash Management' NOT FOUND in file\n")
    print("\nLast 30 lines of file:\n")
    for j in range(max(0, len(lines)-30), len(lines)):
        print(f"  {j+1}: {lines[j].rstrip()[:80]}")