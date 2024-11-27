import requests
from flask import session

from auth_config import pyrebase_auth


class APIClient:
    def __init__(self, base_url):
        self.base_url = base_url

    def _get_headers(self):
        """Obtiene los encabezados con el token de autorización."""
        id_token = session.get("idToken")
        if not id_token:
            raise ValueError("No se encontró un token de autenticación en la sesión.")
        return {
            "Authorization": f"Bearer {id_token}",
            "Content-Type": "application/json"
        }

    def get(self, endpoint, params=None):
        """Realiza una solicitud GET a la API."""
        try:
            url = f"{self.base_url}/{endpoint}"
            headers = self._get_headers()
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error GET {endpoint}: {e}")
            return None

    def post(self, endpoint, data=None, json=None):
        """Realiza una solicitud POST a la API."""
        try:
            url = f"{self.base_url}/{endpoint}"
            headers = self._get_headers()
            response = requests.post(url, json=json, data=data, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error POST {endpoint}: {e}")
            return None

    def put(self, endpoint, data=None, json=None):
        """Realiza una solicitud PUT a la API."""
        try:
            url = f"{self.base_url}/{endpoint}"
            headers = self._get_headers()
            response = requests.put(url, json=json, data=data, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error PUT {endpoint}: {e}")
            return None

    def delete(self, endpoint, data=None, json=None):
        """Realiza una solicitud DELETE a la API."""
        try:
            url = f"{self.base_url}/{endpoint}"
            headers = self._get_headers()
            response = requests.delete(url, json=json, data=data, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error DELETE {endpoint}: {e}")
            return None

    def patch(self, endpoint, json=None, data=None):
        """Realiza una solicitud PATCH a la API."""
        try:
            url = f"{self.base_url}/{endpoint}"
            headers = self._get_headers()
            response = requests.patch(url, json=json, data=data, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error PATCH {endpoint}: {e}")
            return None
