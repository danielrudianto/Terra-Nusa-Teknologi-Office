from O365 import Account, FileSystemTokenBackend
import os

class MailService:
    @staticmethod
    def send_email(to_email, subject, body, attachment_path):
        credentials = (
            os.getenv("MICROSOFT_CLIENT_ID"),
            os.getenv("MICROSOFT_CLIENT_SECRET"),
        )

        token_backend = FileSystemTokenBackend(
            token_path="storage/tokens",
            token_filename="o365_token.txt"
        )

        account = Account(credentials, token_backend=token_backend)

        if not account.is_authenticated:
            account.authenticate(scopes=['message_all'])

        mailbox = account.mailbox()
        message = mailbox.new_message()
        message.to.add(to_email)
        message.subject = subject
        message.body = body
        message.attachments.add(attachment_path)
        message.send()
