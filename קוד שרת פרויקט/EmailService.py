import smtplib
from email.message import EmailMessage


class EmailService:
    def __init__(self, admin_email, admin_password):
        self.admin_email = admin_email
        self.admin_password = admin_password
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 465

    def send_otp(self, target_email, otp_code):
        msg = EmailMessage()
        msg['Subject'] = "קוד אימות למערכת נצ\"ח"
        msg['From'] = self.admin_email
        msg['To'] = target_email


        content = f"""
        שלום,
        
        תודה שנרשמת למערכת נצ"ח.
        קוד האימות החד-פעמי שלך הוא: {otp_code}
        
        הקוד תקף ל-10 דקות הקרובות.
        אם לא ביקשת להירשם, אנא התעלם ממייל זה.
        
        בברכה,
        צוות נצ"ח
        """
        msg.set_content(content)

        try:
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as smtp:
                smtp.login(self.admin_email, self.admin_password)
                smtp.send_message(msg)
            print(f"[EmailService] OTP sent successfully to {target_email}")
            return True
        except Exception as e:
            print(f"[EmailService] Failed to send email: {e}")
            return False
