import pickle
import sys
import os
sys.path.insert(0, '.')

preset_dir = 'config/presets/queue'
for filename in os.listdir(preset_dir):
    filepath = os.path.join(preset_dir, filename)
    print(f"\n=== {filename} ===")
    
    # Check file size
    size = os.path.getsize(filepath)
    print(f"File size: {size} bytes")
    
    if size == 0:
        print("  -> Empty file, skipping")
        continue
    
    try:
        with open(filepath, 'rb') as f:
            q = pickle.load(f)

        print(f"Queue ID: {q.QID}")
        print(f"Number of scans: {len(q.scans)}")

        for i, s in enumerate(q.scans):
            print(f"\nScan {i}: {s.scan_settings.scan_name}")
            if hasattr(s.scan_settings, 'scan_tree'):
                tree = s.scan_settings.scan_tree
                print(f"  Has scan_tree: True")
                print(f"  Root item: {tree.root_item}")
                print(f"  Root children count: {len(tree.root_item.child_items)}")
                
                def show_tree(item, indent=2):
                    name = getattr(item, 'name', 'unnamed')
                    instr_obj = getattr(item, 'instrument_object', None)
                    deser_data = getattr(item, 'deserialized_instrument_data', None)
                    print(f"{' ' * indent}Item: name='{name}', instrument_object={instr_obj is not None}, deserialized_data={deser_data is not None}")
                    if deser_data:
                        print(f"{' ' * indent}  -> deserialized_data keys: {list(deser_data.keys()) if isinstance(deser_data, dict) else type(deser_data)}")
                    for child in getattr(item, 'child_items', []):
                        show_tree(child, indent + 2)
                
                show_tree(tree.root_item)
            else:
                print(f"  Has scan_tree: False")
    except Exception as e:
        print(f"  Error loading: {e}")
