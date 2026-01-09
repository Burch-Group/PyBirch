"""Test trash service import."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

output_file = os.path.join(os.path.dirname(__file__), 'trash_import_output.txt')

with open(output_file, 'w') as f:
    f.write("Testing TrashService Import\n")
    f.write("=" * 50 + "\n\n")
    
    try:
        from database.trash_service import TrashService
        f.write("TrashService import: SUCCESS\n")
        
        ts = TrashService()
        f.write("TrashService instantiation: SUCCESS\n")
    except Exception as e:
        import traceback
        f.write(f"ERROR: {e}\n\n")
        f.write(traceback.format_exc())
    
    f.write("\n" + "=" * 50 + "\n")
    f.write("Testing routes.py import step by step\n\n")
    
    # Check routes.py line by line around the trash section
    routes_file = os.path.join(os.path.dirname(__file__), 'web', 'routes.py')
    with open(routes_file, 'r', encoding='utf-8') as rf:
        lines = rf.readlines()
    
    f.write(f"Total lines in routes.py: {len(lines)}\n\n")
    
    # Find the Trash Management section
    for i, line in enumerate(lines):
        if "Trash Management" in line:
            f.write(f"Found 'Trash Management' at line {i+1}\n")
            f.write(f"Line content: {repr(line)}\n\n")
            
            # Show lines around it
            f.write("Context (20 lines after):\n")
            for j in range(i, min(len(lines), i+25)):
                f.write(f"  {j+1}: {lines[j].rstrip()[:80]}\n")
            break
    else:
        f.write("'Trash Management' NOT FOUND in file\n")
        f.write("\nLast 30 lines of file:\n")
        for j in range(max(0, len(lines)-30), len(lines)):
            f.write(f"  {j+1}: {lines[j].rstrip()[:80]}\n")

# Print to file then read and print to console
with open(output_file, 'r') as f:
    print(f.read())
