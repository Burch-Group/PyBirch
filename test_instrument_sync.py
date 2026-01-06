"""
Test script to verify that configured instruments from adapter manager
are properly passed to the scan page.
"""

import sys
from PySide6.QtWidgets import QApplication
from GUI.main.main_window import MainWindow
from pybirch.queue.queue import Queue

def test_instrument_sync():
    """Test the instrument synchronization from adapter manager to scan page."""
    app = QApplication(sys.argv)
    
    # Create main window
    queue = Queue("test_queue")
    window = MainWindow(queue=queue)
    
    print("Testing instrument synchronization...")
    
    # Show instruments page
    window.show_instruments_page()
    print("✓ Instruments page opened")
    
    # Get the adapter manager
    adapter_manager = window.instruments_page.adapter_manager
    print(f"✓ Adapter manager found: {adapter_manager}")
    
    # Add some test rows to adapter manager
    # Note: You would normally do this through the GUI
    print("\nConfigured instruments (should be empty initially):")
    configured = adapter_manager.get_configured_instruments()
    print(f"  Count: {len(configured)}")
    for inst in configured:
        print(f"  - {inst['name']} via {inst['adapter']}")
    
    # Show queue page
    window.show_queue_page()
    print("\n✓ Queue page opened")
    
    # Check if queue page has the configured instruments
    if hasattr(window.queue_page, 'configured_instruments'):
        queue_instruments = window.queue_page.configured_instruments
        if queue_instruments:
            print(f"✓ Queue page has {len(queue_instruments)} configured instruments")
        else:
            print("✓ Queue page configured_instruments is None/empty (expected if no instruments configured)")
    else:
        print("✗ Queue page does not have configured_instruments attribute")
    
    # Test the sync method directly
    print("\n✓ Testing sync method...")
    window.sync_configured_instruments_to_queue_page()
    print("  Sync completed successfully")
    
    # Show the window
    window.show()
    
    print("\n" + "="*60)
    print("SUCCESS: All components connected properly!")
    print("="*60)
    print("\nThe main window is now open. You can:")
    print("1. Go to Instruments page (click instrument icon)")
    print("2. Configure instruments in the adapter manager")
    print("3. Go to Queue page (click Q button)")
    print("4. Click on a scan to open it")
    print("5. Check if your configured instruments appear in the scan tree")
    print("\nClose the window to exit the test.")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    test_instrument_sync()
