"""Test database instruments loading in GUI widget."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)

from GUI.widgets.instrument_autoload import InstrumentAutoLoadWidget
from database.services import DatabaseService

print("Testing GUI database instrument loading...")

db = DatabaseService('database/pybirch.db')
widget = InstrumentAutoLoadWidget('pybirch/setups', db_service=db)

print(f"\nDatabase classes loaded:")
for itype, classes in widget._database_classes.items():
    print(f"  {itype}: {len(classes)} instruments")
    for name, cls, defn in classes:
        print(f"    - {name} (id={defn.get('id')})")

# Check the tree structure
print(f"\nTree has {widget.tree.topLevelItemCount()} top-level items")
root = widget.tree.invisibleRootItem()
for i in range(root.childCount()):
    item = root.child(i)
    print(f"  - {item.text(0)}")
    for j in range(item.childCount()):
        child = item.child(j)
        print(f"      - {child.text(0)}")

print("\nDone!")
