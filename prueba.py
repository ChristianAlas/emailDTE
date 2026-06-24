import requests

from msal import PublicClientApplication

print(">>> Script started")

CLIENT_ID = "htalpctmordslmfd"

AUTHORITY = "https://login.microsoftonline.com/common"

SCOPES = ["Mail.Read"]

app = PublicClientApplication(

    client_id=CLIENT_ID,

    authority=AUTHORITY

)

result = app.acquire_token_interactive(scopes=SCOPES)

if "access_token" in result:

    print(">>> Access token acquired")

    access_token = result["access_token"]

    graph_endpoint = "https://graph.microsoft.com/v1.0/me/messages"

    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.get(graph_endpoint, headers=headers)

    emails = response.json()

    print(">>> Emails received:")

    for message in emails.get("value", []):

        subject = message.get("subject", "No subject")

        sender = message.get("from", {}).get("emailAddress", {}).get("address", "Unknown sender")

        print("Subject:", subject)

        print("From:", sender)

        print("-" * 40)

else:

    print(" Authentication failed.")

    print("Details:")

    print(result)