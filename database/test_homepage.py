"""Test the homepage route."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
print("Starting test...", file=sys.stderr)

from database.web.app import create_app
print("App imported", file=sys.stderr)

app = create_app()
app.config['TESTING'] = True
print("App created", file=sys.stderr)

with app.test_client() as client:
    print("Making request...", file=sys.stderr)
    response = client.get('/')
    print(f"Status: {response.status_code}", file=sys.stderr)
    if response.status_code >= 400:
        print("Error response:", file=sys.stderr)
        print(response.data.decode()[:2000], file=sys.stderr)
    else:
        print("Success!", file=sys.stderr)
