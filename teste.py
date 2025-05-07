import requests


def testar_token(token):
    url = "https://api.deriv.com/binary"
    payload = {"authorize": token}
    response = requests.post(url, json=payload)
    print(response.json())
