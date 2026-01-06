"""
Register PyBirch URI Scheme on Windows
======================================
This script registers the pybirch:// URI scheme with Windows,
allowing browser links to open in the PyBirch application.

IMPORTANT: This script must be run with administrator privileges
           to modify the Windows registry.

Usage:
    1. Open Command Prompt or PowerShell as Administrator
    2. Navigate to the PyBirch directory
    3. Run: python database/register_uri_scheme.py

To unregister:
    python database/register_uri_scheme.py --unregister
"""

import sys
import os
import winreg
import argparse
from pathlib import Path


def get_pybirch_command():
    """Get the command to launch PyBirch with a URI argument.
    
    Returns the path to the Python executable and the main PyBirch script.
    """
    # Get the Python executable
    python_exe = sys.executable
    
    # Get the PyBirch root directory (parent of database folder)
    pybirch_root = Path(__file__).parent.parent.absolute()
    
    # The main entry point - adjust this to your actual entry point
    # Option 1: Direct Python script
    main_script = pybirch_root / "GUI" / "app.py"
    
    # Option 2: If you have a pybirch.exe or launcher
    # launcher = pybirch_root / "pybirch.exe"
    
    if main_script.exists():
        # Use pythonw.exe for GUI apps (no console window)
        pythonw = python_exe.replace('python.exe', 'pythonw.exe')
        if os.path.exists(pythonw):
            return f'"{pythonw}" "{main_script}" "%1"'
        return f'"{python_exe}" "{main_script}" "%1"'
    
    # Fallback: just use python with the URI handler directly
    uri_handler = pybirch_root / "database" / "uri_handler.py"
    return f'"{python_exe}" "{uri_handler}" "%1"'


def register_uri_scheme():
    """Register the pybirch:// URI scheme in Windows registry."""
    
    command = get_pybirch_command()
    
    print("Registering pybirch:// URI scheme...")
    print(f"Command: {command}")
    
    try:
        # Create the protocol key
        key_path = r"pybirch"
        
        # Open or create HKEY_CLASSES_ROOT\pybirch
        key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, key_path)
        
        # Set the default value to describe the protocol
        winreg.SetValue(key, "", winreg.REG_SZ, "URL:PyBirch Protocol")
        
        # Set URL Protocol (empty string marks this as a URL protocol)
        winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
        
        # Create the shell\open\command subkey
        command_key = winreg.CreateKey(key, r"shell\open\command")
        
        # Set the command to execute
        winreg.SetValue(command_key, "", winreg.REG_SZ, command)
        
        # Close keys
        winreg.CloseKey(command_key)
        winreg.CloseKey(key)
        
        print("\n✓ Successfully registered pybirch:// URI scheme!")
        print("\nYou can now click pybirch:// links in your browser to open PyBirch.")
        print("Example links:")
        print("  pybirch://scan/1")
        print("  pybirch://queue/1")
        print("  pybirch://sample/1")
        
        return True
        
    except PermissionError:
        print("\n✗ Error: Permission denied!")
        print("  Please run this script as Administrator.")
        print("  Right-click Command Prompt and select 'Run as administrator'")
        return False
        
    except Exception as e:
        print(f"\n✗ Error registering URI scheme: {e}")
        return False


def unregister_uri_scheme():
    """Remove the pybirch:// URI scheme from Windows registry."""
    
    print("Unregistering pybirch:// URI scheme...")
    
    try:
        # Delete the entire pybirch key tree
        def delete_key_recursive(root, path):
            try:
                key = winreg.OpenKey(root, path, 0, winreg.KEY_ALL_ACCESS)
                
                # First, delete all subkeys
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, 0)
                        delete_key_recursive(root, f"{path}\\{subkey_name}")
                    except OSError:
                        break
                
                winreg.CloseKey(key)
                winreg.DeleteKey(root, path)
                
            except FileNotFoundError:
                pass  # Key doesn't exist
        
        delete_key_recursive(winreg.HKEY_CLASSES_ROOT, "pybirch")
        
        print("\n✓ Successfully unregistered pybirch:// URI scheme!")
        return True
        
    except PermissionError:
        print("\n✗ Error: Permission denied!")
        print("  Please run this script as Administrator.")
        return False
        
    except Exception as e:
        print(f"\n✗ Error unregistering URI scheme: {e}")
        return False


def check_registration():
    """Check if the pybirch:// URI scheme is registered."""
    
    try:
        key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"pybirch\shell\open\command")
        command, _ = winreg.QueryValueEx(key, "")
        winreg.CloseKey(key)
        
        print("✓ pybirch:// URI scheme is registered")
        print(f"  Command: {command}")
        return True
        
    except FileNotFoundError:
        print("✗ pybirch:// URI scheme is NOT registered")
        return False
        
    except Exception as e:
        print(f"? Error checking registration: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Register or unregister the pybirch:// URI scheme on Windows"
    )
    parser.add_argument(
        '--unregister', 
        action='store_true',
        help='Unregister the URI scheme instead of registering it'
    )
    parser.add_argument(
        '--check',
        action='store_true', 
        help='Check if the URI scheme is registered'
    )
    
    args = parser.parse_args()
    
    if sys.platform != 'win32':
        print("This script is for Windows only.")
        print("For macOS/Linux, you need different configuration.")
        sys.exit(1)
    
    if args.check:
        check_registration()
    elif args.unregister:
        unregister_uri_scheme()
    else:
        register_uri_scheme()


if __name__ == '__main__':
    main()
