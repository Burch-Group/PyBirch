"""Check routes and test trash API - simulating browser request."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

output_file = os.path.join(os.path.dirname(__file__), 'route_check_output.txt')

with open(output_file, 'w') as f:
    f.write("Trash API Test (simulating browser)\n")
    f.write("=" * 50 + "\n\n")
    
    try:
        from database.web.app import create_app
        app = create_app()
        app.config['TESTING'] = True
        f.write("App created OK\n\n")
    except Exception as e:
        import traceback
        f.write(f"Error creating app: {e}\n")
        f.write(traceback.format_exc())
        sys.exit(1)

    # First, restore any trashed scan
    from database.session import get_session
    from database.models import Scan
    
    with get_session() as session:
        scan = session.query(Scan).first()
        if scan:
            scan_id = scan.id
            scan_name = scan.scan_name or scan.scan_id
            f.write(f"Found scan: id={scan_id}, name={scan_name}, trashed_at={scan.trashed_at}\n\n")
            
            # Restore if trashed
            if scan.trashed_at:
                scan.trashed_at = None
                scan.trashed_by = None
                session.commit()
                f.write("Restored scan from trash\n\n")
        else:
            f.write("No scans found in database\n")
            scan_id = None

    with app.test_client() as client:
        # Test WITHOUT login first
        f.write("Testing WITHOUT login:\n")
        if scan_id:
            response = client.post(f'/api/trash/scan/{scan_id}',
                                   json={'cascade': True},
                                   content_type='application/json')
            f.write(f"  Status: {response.status_code}\n")
            f.write(f"  Content-Type: {response.content_type}\n")
            f.write(f"  Response: {response.data.decode()[:500]}\n\n")
        
        # Now login
        with client.session_transaction() as sess:
            sess['user_id'] = 1
        
        f.write("Testing WITH login (user_id=1):\n")
        
        if scan_id:
            # Test trash API for scan
            f.write(f"  POST /api/trash/scan/{scan_id}:\n")
            try:
                response = client.post(f'/api/trash/scan/{scan_id}',
                                       json={'cascade': True},
                                       content_type='application/json')
                f.write(f"    Status: {response.status_code}\n")
                f.write(f"    Content-Type: {response.content_type}\n")
                f.write(f"    Response: {response.data.decode()[:500]}\n")
            except Exception as e:
                import traceback
                f.write(f"    EXCEPTION: {e}\n")
                f.write(traceback.format_exc())
            
            # Now restore it
            f.write(f"\n  POST /api/trash/scan/{scan_id}/restore:\n")
            try:
                response = client.post(f'/api/trash/scan/{scan_id}/restore',
                                       json={'cascade': True},
                                       content_type='application/json')
                f.write(f"    Status: {response.status_code}\n")
                f.write(f"    Content-Type: {response.content_type}\n")
                f.write(f"    Response: {response.data.decode()[:500]}\n")
            except Exception as e:
                import traceback
                f.write(f"    EXCEPTION: {e}\n")
                f.write(traceback.format_exc())
        
        # Check registered routes for trash
        f.write("\n" + "=" * 50 + "\n")
        f.write("Registered trash API routes:\n")
        for rule in app.url_map.iter_rules():
            if 'trash' in rule.rule:
                f.write(f"  {rule.methods} {rule.rule} -> {rule.endpoint}\n")

print(f"Output written to: {output_file}")
