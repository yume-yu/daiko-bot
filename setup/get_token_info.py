from pprint import pprint

from google_auth_oauthlib.flow import Flow

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

try:

    # Googleの認証ライブラリを使って認証トークンを取る
    # 参考: https://google-auth-oauthlib.readthedocs.io/en/latest/reference/google_auth_oauthlib.flow.html?highlight=SCOPES#module-google_auth_oauthlib.flow

    flow = Flow.from_client_secrets_file(
        "./client_secret.json", SCOPES, redirect_uri="http://localhost:8080/"
    )

    # Tell the user to go to the authorization URL.
    auth_url, _ = flow.authorization_url(prompt="consent")

    print("Please go to this URL: {}".format(auth_url))

    # The user will get an authorization code. This code is used to get the
    # access token.
    code = input("Enter the authorization code: ")
    cred = flow.fetch_token(code=code)

    pprint(cred)
except FileNotFoundError:
    print('Error: "client_secret.json" is not found.')
