import os
from O365 import Account
from dotenv import load_dotenv

class MailService:
    @staticmethod
    def send_email(email, subject, message, attachment=None):
        # Implement email sending logic here
        clientID = os.getenv('MICROSOFT_CLIENT_ID')
        clientSecret = os.getenv('MICROSOFT_CLIENT_SECRET')
        credentials = (clientID, clientSecret)

        account = Account(credentials)
        if account.authenticate(requested_scopes=['basic', 'message_all']):
            print('Authenticated!')