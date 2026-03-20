import re
from datetime import datetime, timedelta
import secrets
import asyncio
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import get_settings


class EmailService:
    def __init__(self):
        self.settings = get_settings()

    async def send_password_reset_email(self, email: str, username: str, reset_token: str, reset_url: str):
        """Send password reset email with token"""
        try:
            subject = "EduChat - Đặt lại mật khẩu"
            
            # Build reset link
            reset_link = f"{self.settings.frontend_password_reset_url}?token={reset_token}&email={email}"
            
            # HTML email template
            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif; background-color: #f5f5f5;">
                    <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <h2 style="color: #0f766e; text-align: center;">EduChat - Yêu cầu đặt lại mật khẩu</h2>
                        
                        <p>Xin chào <strong>{username}</strong>,</p>
                        
                        <p>Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản của bạn. Nếu bạn không thực hiện yêu cầu này, vui lòng bỏ qua email này.</p>
                        
                        <p>Để đặt lại mật khẩu của bạn, nhấp vào nút bên dưới:</p>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{reset_link}" style="background-color: #0f766e; color: white; padding: 12px 30px; text-decoration: none; border-radius: 4px; display: inline-block; font-weight: bold;">Đặt lại mật khẩu</a>
                        </div>
                        
                        <p>Hoặc sao chép đường link này vào trình duyệt của bạn:</p>
                        <p style="word-break: break-all; background-color: #f9f9f9; padding: 10px; border-left: 3px solid #0f766e;">
                            {reset_link}
                        </p>
                        
                        <p style="color: #666;">Link này sẽ hết hạn trong {self.settings.password_reset_token_expire_minutes} phút.</p>
                        
                        <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                        <p style="color: #999; font-size: 12px; text-align: center;">
                            © 2026 EduChat. Một dự án quản lý kiến thức thông minh.
                        </p>
                    </div>
                </body>
            </html>
            """
            
            # Plain text version
            plain_content = f"""
EduChat - Yêu cầu đặt lại mật khẩu

Xin chào {username},

Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản của bạn. Nếu bạn không thực hiện yêu cầu này, vui lòng bỏ qua email này.

Để đặt lại mật khẩu của bạn, truy cập đường link sau:
{reset_link}

Link này sẽ hết hạn trong {self.settings.password_reset_token_expire_minutes} phút.

---
© 2026 EduChat
            """
            
            await self._send_email(email, subject, plain_content, html_content)
            return True
        except Exception as e:
            print(f"Error sending password reset email: {e}")
            return False

    async def send_welcome_email(self, email: str, username: str):
        """Send welcome email to new user"""
        try:
            subject = "Chào mừng bạn đến với EduChat!"
            
            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif; background-color: #f5f5f5;">
                    <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <h2 style="color: #0f766e; text-align: center;">Chào mừng đến với EduChat!</h2>
                        
                        <p>Xin chào <strong>{username}</strong>,</p>
                        
                        <p>Cảm ơn bạn đã tạo tài khoản trên EduChat. Chúng tôi rất vui được phục vụ bạn.</p>
                        
                        <p>Bây giờ bạn có thể:</p>
                        <ul>
                            <li>Sử dụng trợ lý AI để hỏi đáp về kiến thức giáo dục</li>
                            <li>Tải lên tài liệu để tìm kiếm thông tin liên quan</li>
                            <li>Lưu trữ lịch sử cuộc trò chuyện của bạn</li>
                        </ul>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="http://localhost:5173" style="background-color: #0f766e; color: white; padding: 12px 30px; text-decoration: none; border-radius: 4px; display: inline-block; font-weight: bold;">Bắt đầu sử dụng EduChat</a>
                        </div>
                        
                        <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                        <p style="color: #999; font-size: 12px; text-align: center;">
                            © 2026 EduChat. Một dự án quản lý kiến thức thông minh.
                        </p>
                    </div>
                </body>
            </html>
            """
            
            plain_content = f"""
Chào mừng đến với EduChat!

Xin chào {username},

Cảm ơn bạn đã tạo tài khoản trên EduChat. Chúng tôi rất vui được phục vụ bạn.

Bây giờ bạn có thể:
- Sử dụng trợ lý AI để hỏi đáp về kiến thức giáo dục
- Tải lên tài liệu để tìm kiếm thông tin liên quan
- Lưu trữ lịch sử cuộc trò chuyện của bạn

Truy cập: http://localhost:5173

---
© 2026 EduChat
            """
            
            await self._send_email(email, subject, plain_content, html_content)
            return True
        except Exception as e:
            print(f"Error sending welcome email: {e}")
            return False

    async def _send_email(self, to_email: str, subject: str, plain_content: str, html_content: str):
        """Internal method to send email"""
        if not self.settings.smtp_user or not self.settings.smtp_password:
            print("Warning: SMTP credentials not configured. Email not sent.")
            return False

        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.settings.smtp_from_name} <{self.settings.smtp_from_email}>"
            message["To"] = to_email

            # Attach both versions
            part1 = MIMEText(plain_content, "plain")
            part2 = MIMEText(html_content, "html")
            message.attach(part1)
            message.attach(part2)

            # Send email
            async with aiosmtplib.SMTP(hostname=self.settings.smtp_host, port=self.settings.smtp_port) as smtp:
                await smtp.login(self.settings.smtp_user, self.settings.smtp_password)
                await smtp.sendmail(self.settings.smtp_from_email, to_email, message.as_string())
            
            return True
        except Exception as e:
            print(f"Error sending email via SMTP: {e}")
            # In development mode, you can still return True to allow testing
            # In production, ensure SMTP is properly configured
            return False


def generate_reset_token():
    """Generate a secure reset token"""
    return secrets.token_urlsafe(32)


def is_valid_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None
