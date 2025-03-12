import logging
from datetime import datetime
from typing import Optional
from fastapi.templating import Jinja2Templates
from fastapi import BackgroundTasks
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from config import get_settings
import traceback
import os

from email.utils import make_msgid


settings = get_settings()

# Configure a dedicated logger for email operations
email_logger = logging.getLogger("email")
email_logger.setLevel(logging.DEBUG)

# Create a file handler for email logs
file_handler = logging.FileHandler("email.log")
file_handler.setLevel(logging.DEBUG)

# Create a formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Add the handler to the logger
email_logger.addHandler(file_handler)

# Initialize Jinja2 templates for email rendering
templates = Jinja2Templates(directory="templates")

async def send_email(
    background_tasks: BackgroundTasks,
    to_email: str,
    subject: str,
    html_content: str
):
    """Send an email asynchronously in the background"""
    print(f"DEBUG email.py: Queuing email to {to_email} with subject: '{subject}'")
    email_logger.info(f"Queuing email to {to_email} with subject: '{subject}'")
    background_tasks.add_task(_send_email_task, to_email, subject, html_content)
    print(f"DEBUG email.py: Added email task to background tasks")

async def _send_email_task(to_email: str, subject: str, html_content: str):
    """Background task to send an email"""
    print(f"DEBUG email.py: Processing email to {to_email}")
    email_logger.info(f"Processing email to {to_email}")
    
    # Debug output for SMTP settings
    print(f"DEBUG email.py: SMTP_HOST={settings.SMTP_HOST}, SMTP_PORT={settings.SMTP_PORT}")
    print(f"DEBUG email.py: SMTP_USER={settings.SMTP_USER}, HAS_PASSWORD={'Yes' if settings.SMTP_PASSWORD else 'No'}")
    
    # If SMTP is not configured, log the email content
    if not settings.SMTP_HOST or not settings.SMTP_PORT:
        # Log the email instead if SMTP is not configured
        print(f"DEBUG email.py: SMTP not configured - logging email content instead")
        email_logger.warning(f"SMTP not configured. Email not sent to: {to_email}")
        email_logger.info(f"Email subject: {subject}")
        email_logger.debug(f"Email content (first 100 chars): {html_content[:100]}...")
        
        # Write the full email content to a file for inspection
        os.makedirs("email_output", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"email_output/email_{timestamp}.html"
        with open(filename, "w") as f:
            f.write(f"To: {to_email}\n")
            f.write(f"Subject: {subject}\n")
            f.write(f"Content-Type: text/html\n\n")
            f.write(html_content)
        print(f"DEBUG email.py: Email content written to {filename}")
        return
    
    try:
        print(f"DEBUG email.py: Preparing email with SMTP settings: {settings.SMTP_HOST}:{settings.SMTP_PORT}")
        email_logger.debug(f"Preparing email with SMTP settings: {settings.SMTP_HOST}:{settings.SMTP_PORT}")
        
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = settings.SMTP_USER or settings.FROM_EMAIL or "noreply@example.com"
        message["To"] = to_email
        message["Message-ID"] = make_msgid(domain=message["From"].split("@")[1])  # Generate a valid Message-ID

        
        # Attach HTML content
        html_part = MIMEText(html_content, "html")
        message.attach(html_part)
        
        print(f"DEBUG email.py: Connecting to SMTP server {settings.SMTP_HOST}:{settings.SMTP_PORT}")
        email_logger.debug(f"Connecting to SMTP server {settings.SMTP_HOST}:{settings.SMTP_PORT}")
        
        # Connect to SMTP server and send email
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_TLS:
                print(f"DEBUG email.py: Starting TLS connection")
                email_logger.debug("Starting TLS connection")
                server.starttls()
            
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                print(f"DEBUG email.py: Logging in as {settings.SMTP_USER} USING ||{settings.SMTP_PASSWORD}||")
                email_logger.debug(f"Logging in as {settings.SMTP_USER}")
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            
            print(f"DEBUG email.py: Sending email to {to_email}")
            email_logger.info(f"Sending email to {to_email}")
            server.sendmail(
                settings.SMTP_USER or settings.FROM_EMAIL or "noreply@example.com", 
                to_email, 
                message.as_string()
            )
        
        print(f"DEBUG email.py: Email sent successfully to {to_email}")
        email_logger.info(f"Email sent successfully to {to_email}")
    except Exception as e:
        print(f"DEBUG email.py: Failed to send email: {str(e)}")
        email_logger.error(f"Failed to send email to {to_email}: {str(e)}")
        print(traceback.format_exc())
        email_logger.error(traceback.format_exc())
        # Log the email content so it's not lost
        email_logger.debug(f"Failed email subject: {subject}")
        email_logger.debug(f"Failed email content (first 100 chars): {html_content[:100]}...")

async def send_verification_email(
    background_tasks: BackgroundTasks, 
    email: str, 
    name: Optional[str], 
    verify_url: str
):
    """Send email verification link to user"""
    print(f"DEBUG email.py: Preparing verification email for {email} with URL: {verify_url}")
    email_logger.info(f"Preparing verification email for {email} with URL: {verify_url}")
    
    try:
        # Check if the template directory exists
        template_path = os.path.join("templates", "emails", "verification.html")
        if not os.path.exists(template_path):
            print(f"DEBUG email.py: Template not found at: {template_path}")
            email_logger.error(f"Template not found at: {template_path}")
            # Use a fallback template string
            html_content = f"""
            <html>
            <body>
                <h1>Verify Your Email</h1>
                <p>Hello{' ' + name if name else ''},</p>
                <p>Please click on the link below to verify your email address:</p>
                <p><a href="{verify_url}">{verify_url}</a></p>
                <p>If you didn't create an account, you can ignore this email.</p>
            </body>
            </html>
            """
        else:
            print(f"DEBUG email.py: Found template at: {template_path}")
            # Render the template
            try:
                context = {
                    "name": name,
                    "verify_url": verify_url,
                    "current_year": datetime.now().year
                }
                print(f"DEBUG email.py: Rendering template with context: {context}")
                # Use direct file reading instead of Jinja2Templates
                with open(template_path, "r") as f:
                    template_content = f.read()
                    html_content = template_content.replace("{{ verify_url }}", verify_url)
                    html_content = html_content.replace("{{ current_year }}", str(datetime.now().year))
                    if name:
                        html_content = html_content.replace("{% if name %} {{ name }}{% endif %}", f" {name}")
                    else:
                        html_content = html_content.replace("{% if name %} {{ name }}{% endif %}", "")
                print(f"DEBUG email.py: Template rendered successfully")
            except Exception as template_error:
                print(f"DEBUG email.py: Error rendering template: {str(template_error)}")
                print(traceback.format_exc())
                # Use a fallback template string
                html_content = f"""
                <html>
                <body>
                    <h1>Verify Your Email</h1>
                    <p>Hello{' ' + name if name else ''},</p>
                    <p>Please click on the link below to verify your email address:</p>
                    <p><a href="{verify_url}">{verify_url}</a></p>
                    <p>If you didn't create an account, you can ignore this email.</p>
                </body>
                </html>
                """
        
        subject = "Verify Your Email Address"
        print(f"DEBUG email.py: Verification email prepared, calling send_email")
        await send_email(background_tasks, email, subject, html_content)
    except Exception as e:
        print(f"DEBUG email.py: Error preparing verification email: {str(e)}")
        email_logger.error(f"Error preparing verification email for {email}: {str(e)}")
        print(traceback.format_exc())
        email_logger.error(traceback.format_exc())

async def send_reset_password_email(
    background_tasks: BackgroundTasks, 
    email: str, 
    name: Optional[str], 
    reset_url: str
):
    """Send password reset link to user"""
    print(f"DEBUG email.py: Preparing password reset email for {email} with URL: {reset_url}")
    email_logger.info(f"Preparing password reset email for {email} with URL: {reset_url}")
    
    try:
        # Check if the template directory exists
        template_path = os.path.join("templates", "emails", "reset_password.html")
        if not os.path.exists(template_path):
            print(f"DEBUG email.py: Template not found at: {template_path}")
            email_logger.error(f"Template not found at: {template_path}")
            # Use a fallback template string
            html_content = f"""
            <html>
            <body>
                <h1>Reset Your Password</h1>
                <p>Hello{' ' + name if name else ''},</p>
                <p>Please click on the link below to reset your password:</p>
                <p><a href="{reset_url}">{reset_url}</a></p>
                <p>If you didn't request a password reset, you can ignore this email.</p>
            </body>
            </html>
            """
        else:
            print(f"DEBUG email.py: Found template at: {template_path}")
            # Render the template
            try:
                context = {
                    "name": name,
                    "reset_url": reset_url,
                    "current_year": datetime.now().year
                }
                print(f"DEBUG email.py: Rendering template with context: {context}")
                # Use direct file reading instead of Jinja2Templates
                with open(template_path, "r") as f:
                    template_content = f.read()
                    html_content = template_content.replace("{{ reset_url }}", reset_url)
                    html_content = html_content.replace("{{ current_year }}", str(datetime.now().year))
                    if name:
                        html_content = html_content.replace("{% if name %} {{ name }}{% endif %}", f" {name}")
                    else:
                        html_content = html_content.replace("{% if name %} {{ name }}{% endif %}", "")
                print(f"DEBUG email.py: Template rendered successfully")
            except Exception as template_error:
                print(f"DEBUG email.py: Error rendering template: {str(template_error)}")
                print(traceback.format_exc())
                # Use a fallback template string
                html_content = f"""
                <html>
                <body>
                    <h1>Reset Your Password</h1>
                    <p>Hello{' ' + name if name else ''},</p>
                    <p>Please click on the link below to reset your password:</p>
                    <p><a href="{reset_url}">{reset_url}</a></p>
                    <p>If you didn't request a password reset, you can ignore this email.</p>
                </body>
                </html>
                """
        
        subject = "Reset Your Password"
        print(f"DEBUG email.py: Password reset email prepared, calling send_email")
        await send_email(background_tasks, email, subject, html_content)
    except Exception as e:
        print(f"DEBUG email.py: Error preparing password reset email: {str(e)}")
        email_logger.error(f"Error preparing password reset email for {email}: {str(e)}")
        print(traceback.format_exc())
        email_logger.error(traceback.format_exc())