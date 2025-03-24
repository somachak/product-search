import requests
import json
import sys
import warnings
import urllib3

# Suppress the urllib3 warning about SSL
warnings.filterwarnings('ignore', category=urllib3.exceptions.NotOpenSSLWarning)

try:
    # Test the console_test endpoint
    response = requests.post(
        'http://localhost:10000/console_test',
        json={'ingredient': 'Polyglyceryl-3 Polyricinoleate'},
        timeout=30  # Add a timeout to prevent hanging
    )
    
    print(f"Status Code: {response.status_code}")
    print("\nRaw Response Text:")
    print(response.text)
    
    try:
        json_response = response.json()
        print("\nParsed JSON Response:")
        print(json.dumps(json_response, indent=2))
    except json.JSONDecodeError:
        print("\nCould not parse response as JSON")
    
except requests.exceptions.ConnectionError:
    print("Error: Could not connect to the server. Make sure your Flask app is running on port 10000.")
    sys.exit(1)
except requests.exceptions.Timeout:
    print("Error: Request timed out. The server might be busy or not responding.")
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)