import streamlit as st
from tesla_client import TeslaAPIClient
import json
import secrets
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import threading
import webbrowser
import requests
from datetime import datetime
import pickle
import os
from urllib.parse import parse_qs

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'client' not in st.session_state:
    st.session_state.client = None
if 'user_tokens' not in st.session_state:
    st.session_state.user_tokens = {}

# File to store user tokens
TOKENS_FILE = "user_tokens.pkl"

# Load existing tokens
if os.path.exists(TOKENS_FILE):
    with open(TOKENS_FILE, 'rb') as f:
        st.session_state.user_tokens = pickle.load(f)

def handle_navigation_request(username: str, destination: str):
    """Handle navigation requests from both UI and API"""
    try:
        if username not in st.session_state.user_tokens:
            return {"error": "User not authenticated"}
            
        user_data = st.session_state.user_tokens[username]
        client = TeslaAPIClient(
            st.secrets["TESLA_CLIENT_ID"],
            st.secrets["TESLA_CLIENT_SECRET"]
        )
        client.set_tokens(user_data['access_token'], user_data['refresh_token'])
        client.vehicle_id = user_data['vehicle_id']
        
        # Wake up vehicle
        client.wake_vehicle()
        
        # Send navigation request
        response = client.navigate_to_address(destination)
        
        if response.get('response', {}).get('result') == True:
            return {"status": "success", "message": f"Navigation request sent successfully to: {destination}"}
        else:
            return {"error": f"Navigation request failed: {response}"}
            
    except Exception as e:
        return {"error": str(e)}

# Check for API-like requests via query parameters
query_params = st.query_params
if 'api' in query_params and 'username' in query_params and 'destination' in query_params:
    username = query_params['username']
    destination = query_params['destination']
    result = handle_navigation_request(username, destination)
    st.json(result)
    st.stop()

def get_tesla_tokens(client_id, client_secret, port=8000):
    server = HTTPServer(('localhost', port), AuthHandler)
    state = secrets.token_urlsafe(16)
    
    auth_params = {
        'client_id': client_id,
        'redirect_uri': f'http://localhost:{port}/callback',
        'response_type': 'code',
        'scope': 'openid offline_access vehicle_device_data vehicle_cmds',
        'state': state
    }
    auth_url = f"https://auth.tesla.com/oauth2/v3/authorize?{'&'.join(f'{k}={v}' for k,v in auth_params.items())}"
    
    webbrowser.open(auth_url)
    server.serve_forever()
    
    if not AuthHandler.auth_code:
        raise Exception("Failed to get authorization code")
    
    response = requests.post(
        'https://auth.tesla.com/oauth2/v3/token',
        data={
            'grant_type': 'authorization_code',
            'client_id': client_id,
            'client_secret': client_secret,
            'code': AuthHandler.auth_code,
            'redirect_uri': f'http://localhost:{port}/callback'
        }
    )
    
    return response.json()

class AuthHandler(BaseHTTPRequestHandler):
    auth_code = None
    
    def do_GET(self):
        if 'callback' in self.path:
            query = parse_qs(urlparse(self.path).query)
            AuthHandler.auth_code = query.get('code', [None])[0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Authentication successful! You can close this window and return to the Streamlit app.")
            threading.Thread(target=self.server.shutdown).start()

def save_tokens():
    with open(TOKENS_FILE, 'wb') as f:
        pickle.dump(st.session_state.user_tokens, f)

def authenticate_tesla():
    try:
        with st.spinner("Opening Tesla authentication page..."):
            tokens = get_tesla_tokens(
                st.secrets["TESLA_CLIENT_ID"],
                st.secrets["TESLA_CLIENT_SECRET"]
            )
            
        client = TeslaAPIClient(
            st.secrets["TESLA_CLIENT_ID"],
            st.secrets["TESLA_CLIENT_SECRET"]
        )
        client.set_tokens(tokens['access_token'], tokens['refresh_token'])
        
        # Get vehicle ID
        vehicle_id = client.get_first_vehicle()
        
        # Store tokens and vehicle ID with timestamp
        user_data = {
            'access_token': tokens['access_token'],
            'refresh_token': tokens['refresh_token'],
            'vehicle_id': vehicle_id,
            'timestamp': datetime.now().isoformat()
        }
        
        st.session_state.user_tokens[st.session_state.username] = user_data
        save_tokens()
        
        st.session_state.authenticated = True
        st.session_state.client = client
        st.success("Successfully connected to Tesla account!")
        st.experimental_rerun()
        
    except Exception as e:
        st.error(f"Authentication failed: {str(e)}")

def main():
    st.title("Tesla Navigation App")
    
    # Simple user identification
    if 'username' not in st.session_state:
        st.session_state.username = st.text_input("Enter your name:", key="username_input")
        if st.session_state.username:
            st.experimental_rerun()
        return

    # Check if user has existing tokens
    if st.session_state.username in st.session_state.user_tokens:
        user_data = st.session_state.user_tokens[st.session_state.username]
        if not st.session_state.authenticated:
            client = TeslaAPIClient(
                st.secrets["TESLA_CLIENT_ID"],
                st.secrets["TESLA_CLIENT_SECRET"]
            )
            client.set_tokens(user_data['access_token'], user_data['refresh_token'])
            client.vehicle_id = user_data['vehicle_id']
            st.session_state.client = client
            st.session_state.authenticated = True

    if not st.session_state.authenticated:
        st.warning("Please connect your Tesla account to continue.")
        if st.button("Connect Tesla Account"):
            authenticate_tesla()
        return

    # Show authenticated user
    st.sidebar.success(f"Connected as: {st.session_state.username}")
    if st.sidebar.button("Disconnect Account"):
        if st.session_state.username in st.session_state.user_tokens:
            del st.session_state.user_tokens[st.session_state.username]
            save_tokens()
        st.session_state.authenticated = False
        st.session_state.client = None
        st.experimental_rerun()
        return

    # Navigation interface
    destination = st.text_input("Enter destination:")
    
    if st.button("Send to Tesla"):
        if destination:
            result = handle_navigation_request(st.session_state.username, destination)
            if "error" in result:
                st.error(result["error"])
            else:
                st.success(result["message"])
        else:
            st.warning("Please enter a destination")

    # Add API endpoint information
    with st.expander("Set up Siri Shortcuts"):
        st.markdown("""
        ### How to set up Siri Shortcuts:
        1. Open the Shortcuts app on your iPhone
        2. Create a new shortcut
        3. Add 'Get Contents of URL' action
        4. Set the URL to: `https://your-streamlit-app-url/?api=true&username=YOUR_USERNAME&destination=` 
           (URL will be provided after deployment)
        5. Add a Text action before the URL action
        6. Set the Text action to ask for the destination
        7. Add 'URL Encode' action after the Text action
        8. Add 'Combine Text' action to join:
           - The base URL above
           - The encoded destination text
        9. Set the combined URL as input to 'Get Contents of URL'
        10. Add a Siri phrase like "Navigate Tesla to..."
        """)

if __name__ == "__main__":
    main()