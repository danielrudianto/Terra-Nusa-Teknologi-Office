from dotenv import load_dotenv
load_dotenv()

from O365 import Account
from O365 import FileSystemTokenBackend
import os

client_id = os.getenv("MICROSOFT_CLIENT_ID")

token_backend = FileSystemTokenBackend(
    token_path="storage/tokens",
    token_filename="o365_token.txt"
)

account = Account(
    credentials=(client_id,),   # <-- CUMA SATU NILAI
    auth_flow_type='public',    # <-- WAJIB
    token_backend=token_backend
)

if account.authenticate(scopes=['message_all']):
    print("Authenticated & token saved!")
else:
    print("Authentication failed!")
