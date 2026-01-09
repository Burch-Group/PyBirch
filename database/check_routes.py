"""Check routes and test image upload API."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

output_file = os.path.join(os.path.dirname(__file__), 'route_check_output.txt')

with open(output_file, 'w') as f:
    f.write("Image Upload API Test\n")
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

    # Check for image upload routes
    f.write("Image upload routes:\n")
    for rule in app.url_map.iter_rules():
        if 'image' in rule.rule.lower() and 'upload' in rule.rule.lower():
            f.write(f"  {rule.methods} {rule.rule} -> {rule.endpoint}\n")
    
    f.write("\n")
    
    # Get a sample to test with
    from database.session import get_session
    from database.models import Sample
    
    with get_session() as session:
        sample = session.query(Sample).first()
        if sample:
            sample_id = sample.id
            sample_name = sample.sample_id
            f.write(f"Found sample: id={sample_id}, name={sample_name}\n\n")
        else:
            f.write("No samples found in database\n")
            sample_id = None

    if sample_id:
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = 1
            
            f.write("Testing base64 image upload API:\n")
            
            # Create a tiny test image (1x1 red PNG)
            import base64
            # This is a valid 1x1 red PNG
            tiny_png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
            image_data = f"data:image/png;base64,{tiny_png_b64}"
            
            response = client.post(f'/api/images/sample/{sample_id}/upload-base64',
                                   json={
                                       'image_data': image_data,
                                       'name': 'Test Visualization',
                                       'description': 'Test upload from check_routes'
                                   },
                                   content_type='application/json')
            f.write(f"  Status: {response.status_code}\n")
            f.write(f"  Content-Type: {response.content_type}\n")
            f.write(f"  Response: {response.data.decode()[:500]}\n")

print(f"Output written to: {output_file}")
