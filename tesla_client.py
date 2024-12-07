# tesla_client.py

import requests
import json
import time
from typing import Optional, Dict, Any

class TeslaAPIClient:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.refresh_token = None
        self.vehicle_id = None
        self.base_url = "https://fleet-api.prd.na.vn.cloud.tesla.com/api/1"

    def set_tokens(self, access_token: str, refresh_token: str):
        """Set authentication tokens directly"""
        self.access_token = access_token
        self.refresh_token = refresh_token

    def get_first_vehicle(self) -> str:
        """Get first vehicle ID from account"""
        vehicles = self.get_vehicles()
        if vehicles['count'] > 0:
            self.vehicle_id = vehicles['response'][0]['id']
            return self.vehicle_id
        raise Exception("No vehicles found")

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    def get_vehicles(self) -> Dict[str, Any]:
        response = requests.get(
            f"{self.base_url}/vehicles",
            headers=self.headers
        )
        return response.json()
       
    def wake_vehicle(self) -> bool:
        """Wake up vehicle and wait for it to come online"""
        print("Sending wake up command...")
        response = requests.post(
            f"{self.base_url}/vehicles/{self.vehicle_id}/wake_up",
            headers=self.headers
        )
       
        attempts = 0
        max_attempts = 10
       
        while attempts < max_attempts:
            print(f"Checking vehicle state... (Attempt {attempts + 1}/{max_attempts})")
            response = requests.get(
                f"{self.base_url}/vehicles/{self.vehicle_id}/vehicle_data",
                headers=self.headers
            )
           
            if response.status_code == 200:
                data = response.json()
                if 'response' in data and data['response'].get('state') == 'online':
                    print("Vehicle is online!")
                    return True
           
            attempts += 1
            if attempts < max_attempts:
                print("Vehicle not ready yet, waiting 5 seconds...")
                time.sleep(5)
       
        raise Exception("Failed to wake vehicle after maximum attempts")
       
    def navigate_to_coords(self, lat: float, lon: float) -> Dict[str, Any]:
        payload = {
            "lat": lat,
            "lon": lon,
            "order": 0
        }
       
        response = requests.post(
            f"{self.base_url}/vehicles/{self.vehicle_id}/command/navigation_gps_request",
            headers=self.headers,
            json=payload
        )
        return response.json()

    def navigate_to_address(self, address: str) -> Dict[str, Any]:
        """Send navigation command using address string"""
        payload = {
            "type": "share_ext_content_raw",
            "value": {
                "android.intent.extra.TEXT": address
            },
            "locale": "en-US",
            "timestamp_ms": str(int(time.time() * 1000))
        }
       
        response = requests.post(
            f"{self.base_url}/vehicles/{self.vehicle_id}/command/navigation_request",
            headers=self.headers,
            json=payload
        )
        return response.json()

    def get_vehicle_data(self) -> Dict[str, Any]:
        response = requests.get(
            f"{self.base_url}/vehicles/{self.vehicle_id}/vehicle_data",
            headers=self.headers
        )
        return response.json()