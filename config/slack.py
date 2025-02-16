import requests

class Slack:
    def __init__(self, _msg, _slack_token):
        response = requests.post("https://slack.com/api/chat.postMessage",
            headers={"Authorization": "Bearer " + _slack_token},
            data={"channel": "#upbit","text": _msg}
        )