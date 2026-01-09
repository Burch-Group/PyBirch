"""
Migrate Existing Instruments to Database
========================================
Extracts instrument class definitions from Python files and inserts
them into the database as Driver records.

Usage:
    python scripts/migrate_instruments_to_database.py --db database/pybirch.db
    python scripts/migrate_instruments_to_database.py --db database/pybirch.db --dry-run
    python scripts/migrate_instruments_to_database.py --db database/pybirch.db --dir pybirch/Instruments
"""

import sys
import os
import inspect
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Type
import ast
import textwrap

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def get_class_source(cls: type) -> str:
    """Get the source code for a class."""
    try:
        source = inspect.getsource(cls)
        # Dedent in case the class is nested
        return textwrap.dedent(source)
    except (TypeError, OSError):
        return ""


def extract_class_info(cls: type, module_name: str) -> Optional[Dict]:
    """Extract information from an instrument class.
    
    Args:
        cls: The instrument class
        module_name: Name of the module containing the class
    
    Returns:
        Dictionary with class info, or None if not a valid instrument
    """
    # Determine base class and type
    base_class_name = None
    instrument_type = None
    
    # Check inheritance
    for base in cls.__mro__[1:]:
        base_name = base.__name__
        
        if base_name in ('FakeMeasurementInstrument', 'VisaBaseMeasurementInstrument', 
                         'BaseMeasurementInstrument', 'Measurement', 'VisaMeasurement'):
            base_class_name = base_name
            instrument_type = 'measurement'
            break
        elif base_name in ('FakeMovementInstrument', 'VisaBaseMovementInstrument',
                           'BaseMovementInstrument', 'Movement', 'VisaMovement'):
            base_class_name = base_name
            instrument_type = 'movement'
            break
    
    if not base_class_name:
        return None
    
    # Get source code
    source_code = get_class_source(cls)
    if not source_code:
        return None
    
    # Extract metadata from class
    try:
        instance = cls.__new__(cls)
        
        # Try to get default values without full initialization
        data_columns = getattr(cls, 'data_columns', None)
        if data_columns is None:
            data_columns = getattr(instance, 'data_columns', None)
        if hasattr(data_columns, 'tolist'):
            data_columns = data_columns.tolist()
        
        data_units = getattr(cls, 'data_units', None)
        if data_units is None:
            data_units = getattr(instance, 'data_units', None)
        if hasattr(data_units, 'tolist'):
            data_units = data_units.tolist()
        
        position_column = getattr(cls, 'position_column', None)
        if position_column is None:
            position_column = getattr(instance, 'position_column', None)
        
        position_units = getattr(cls, 'position_units', None)
        if position_units is None:
            position_units = getattr(instance, 'position_units', None)
        
    except Exception:
        data_columns = None
        data_units = None
        position_column = None
        position_units = None
    
    # Determine category from module path
    category = None
    if '/' in module_name or '\\' in module_name:
        parts = module_name.replace('\\', '/').split('/')
        if len(parts) >= 2:
            category = parts[-2]  # Parent folder name
    
    # Get docstring
    description = cls.__doc__
    if description:
        description = textwrap.dedent(description).strip()
    
    return {
        'name': cls.__name__,
        'display_name': getattr(cls, 'name', cls.__name__),
        'description': description,
        'instrument_type': instrument_type,
        'category': category,
        'manufacturer': None,  # Could be extracted from category
        'source_code': source_code,
        'base_class': base_class_name,
        'dependencies': None,  # Could be extracted from imports
        'data_columns': data_columns,
        'data_units': data_units,
        'position_column': position_column,
        'position_units': position_units,
        'is_builtin': True,
        'is_public': True,
        'is_approved': True,
    }


def scan_directory(directory: str) -> List[Tuple[str, type]]:
    """Scan a directory for instrument classes.
    
    Args:
        directory: Path to directory to scan
    
    Returns:
        List of (module_name, class) tuples
    """
    from pybirch.scan.measurements import Measurement, VisaMeasurement
    from pybirch.scan.movements import Movement, VisaMovement
    
    try:
        from pybirch.Instruments.base import (
            BaseMeasurementInstrument, BaseMovementInstrument,
            FakeMeasurementInstrument, FakeMovementInstrument,
            VisaBaseMeasurementInstrument, VisaBaseMovementInstrument,
        )
    except ImportError:
        BaseMeasurementInstrument = type('BaseMeasurementInstrument', (), {})
        BaseMovementInstrument = type('BaseMovementInstrument', (), {})
        FakeMeasurementInstrument = type('FakeMeasurementInstrument', (), {})
        FakeMovementInstrument = type('FakeMovementInstrument', (), {})
        VisaBaseMeasurementInstrument = type('VisaBaseMeasurementInstrument', (), {})
        VisaBaseMovementInstrument = type('VisaBaseMovementInstrument', (), {})
    
    # Base classes to check for
    base_classes = (
        Measurement, VisaMeasurement, Movement, VisaMovement,
        BaseMeasurementInstrument, BaseMovementInstrument,
        FakeMeasurementInstrument, FakeMovementInstrument,
        VisaBaseMeasurementInstrument, VisaBaseMovementInstrument,
    )
    
    # Classes to exclude (base classes themselves)
    exclude_classes = set(base_classes) | {
        'Measurement', 'VisaMeasurement', 'Movement', 'VisaMovement',
        'BaseMeasurementInstrument', 'BaseMovementInstrument',
        'FakeMeasurementInstrument', 'FakeMovementInstrument',
        'VisaBaseMeasurementInstrument', 'VisaBaseMovementInstrument',
        'InstrumentSettingsMixin',
    }
    
    results = []
    directory = Path(directory)
    
    for py_file in directory.rglob('*.py'):
        if py_file.name.startswith('_'):
            continue
        if 'test' in py_file.name.lower():
            continue
        
        module_path = str(py_file.relative_to(directory.parent))
        
        try:
            # Add parent to path
            sys.path.insert(0, str(py_file.parent))
            
            # Import the module
            module_name = py_file.stem
            if module_name in sys.modules:
                module = sys.modules[module_name]
            else:
                import importlib.util
                spec = importlib.util.spec_from_file_location(module_name, py_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    try:
                        spec.loader.exec_module(module)
                    except Exception as e:
                        print(f"  Warning: Could not load {py_file}: {e}")
                        continue
                else:
                    continue
            
            # Find instrument classes
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if name in exclude_classes:
                    continue
                if obj.__module__ != module_name:
                    continue  # Skip imported classes
                
                try:
                    if issubclass(obj, base_classes) and obj not in base_classes:
                        results.append((module_path, obj))
                except TypeError:
                    pass
        
        except Exception as e:
            print(f"  Warning: Error scanning {py_file}: {e}")
        finally:
            if str(py_file.parent) in sys.path:
                sys.path.remove(str(py_file.parent))
    
    return results


def migrate(db_path: str, instruments_dir: str, dry_run: bool = False, filter_base: str = None):
    """Run the migration.
    
    Args:
        db_path: Path to the database
        instruments_dir: Path to instruments directory
        dry_run: If True, don't actually insert into database
        filter_base: If provided, only migrate instruments whose base class contains this string
    """
    print(f"Scanning {instruments_dir} for instruments...")
    if filter_base:
        print(f"Filtering for base classes containing '{filter_base}'")
    
    classes = scan_directory(instruments_dir)
    
    print(f"Found {len(classes)} instrument classes")
    
    if not classes:
        print("No instruments found to migrate.")
        return
    
    # Extract info from each class
    definitions = []
    for module_path, cls in classes:
        info = extract_class_info(cls, module_path)
        if info:
            # Apply filter if specified
            if filter_base and filter_base.lower() not in info['base_class'].lower():
                continue
            definitions.append(info)
            print(f"  ✓ {info['name']} ({info['instrument_type']}) from {module_path}")
        else:
            print(f"  ✗ {cls.__name__} - could not extract info")
    
    print(f"\nExtracted {len(definitions)} valid instrument definitions")
    
    if dry_run:
        print("\n[DRY RUN] Would insert the following:")
        for d in definitions:
            print(f"  - {d['name']}: {d['instrument_type']}, base={d['base_class']}")
        return
    
    # Insert into database
    print("\nInserting into database...")
    
    from database.services import DatabaseService
    db = DatabaseService(db_path)
    
    inserted = 0
    skipped = 0
    
    for defn in definitions:
        # Check if already exists
        existing = db.get_driver_by_name(defn['name'])
        if existing:
            print(f"  ⊘ {defn['name']} - already exists (id={existing['id']})")
            skipped += 1
            continue
        
        try:
            result = db.create_driver(defn)
            print(f"  ✓ {defn['name']} - inserted (id={result['id']})")
            inserted += 1
        except Exception as e:
            print(f"  ✗ {defn['name']} - error: {e}")
    
    print(f"\nMigration complete: {inserted} inserted, {skipped} skipped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate instruments to database")
    parser.add_argument("--db", required=True, help="Path to SQLite database")
    parser.add_argument("--dir", default="pybirch/Instruments", 
                        help="Path to instruments directory (default: pybirch/Instruments)")
    parser.add_argument("--dry-run", action="store_true", 
                        help="Don't actually insert, just show what would be done")
    parser.add_argument("--filter", type=str, default=None,
                        help="Only migrate instruments whose base class contains this string (e.g., 'Fake')")
    
    args = parser.parse_args()
    
    # Resolve paths relative to project root
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = project_root / db_path
    
    instruments_dir = Path(args.dir)
    if not instruments_dir.is_absolute():
        instruments_dir = project_root / instruments_dir
    
    if not instruments_dir.exists():
        print(f"Error: Instruments directory not found: {instruments_dir}")
        sys.exit(1)
    
    migrate(str(db_path), str(instruments_dir), args.dry_run, args.filter)
