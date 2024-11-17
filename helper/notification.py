import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import sys

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server_properties


def send_notification(subject, body, to_email):
    msg = MIMEMultipart()
    msg['From'] = server_properties.MAIL_USERNAME
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    print(msg.as_string())

    try:
        server = smtplib.SMTP(server_properties.MAIL_HOST, server_properties.MAIL_PORT)
        if server_properties.MAIL_USE_TLS:
            server.starttls()
        server.login(server_properties.MAIL_USERNAME, server_properties.MAIL_PASSWORD)
        server.sendmail(server_properties.MAIL_USERNAME, to_email, msg.as_string())
        server.quit()
        print("Notification sent successfully.")
    except Exception as e:
        print(f"Failed to send notification: {e}")

# Main method for testing
if __name__ == "__main__":
    test_subject = "Test Email"
    test_body = "This is a test email body."
    test_recipient = "rrouthu23@gmail.com"  # Replace with a valid email address

    send_notification(test_subject, test_body, test_recipient)
