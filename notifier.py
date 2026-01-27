import requests

def send(webhook, title, description, color):
    payload = {
        "embeds": [{
            "title": title,
            "description": description,
            "color": color
        }]
    }
    requests.post(webhook, json=payload)
