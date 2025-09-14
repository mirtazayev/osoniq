import os
from email.message import EmailMessage

import aiosmtplib
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr, ValidationError
from sqlalchemy.orm import Session

from database import SessionLocal, Subscriber

load_dotenv()  # Load .env file

app = FastAPI(title="Osoniq Landing Page")
templates = Jinja2Templates(directory="templates")


# --- Database session ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Background email sender ---
async def send_thank_you_email(email: str):
    message = EmailMessage()
    message["From"] = os.getenv("EMAIL_USER")
    message["To"] = email
    message["Subject"] = "🎉 Thanks for Joining Osoniq!"

    # HTML email content
    html_content = f"""
    <html>
        <body style="font-family: 'Nunito', sans-serif; color: #2d3748; line-height: 1.6;">
            <div style="max-width: 600px; margin: auto; padding: 20px; border-radius: 12px; 
                        background: #f7f7f7; text-align: center; border: 2px solid #6A8F6B;">
                <h2 style="color: #6A8F6B;">Welcome to Osoniq! 🎉</h2>
                <p>Hi there!</p>
                <p>Thank you for signing up for Osoniq notifications. We're excited to keep you updated on our latest features, updates, and premium detailing tips.</p>
                <p style="margin-top: 20px;">
                    <a href="https://osoniq.com" 
                       style="display:inline-block; padding: 12px 25px; background-color:#6A8F6B; color:white; 
                              border-radius:8px; text-decoration:none; font-weight:600;">
                        Visit Our Website
                    </a>
                </p>
                <p style="margin-top: 20px; font-size: 0.9rem; color: #718096;">You received this email because you subscribed to Osoniq notifications. No spam, ever.</p>
            </div>
        </body>
    </html>
    """

    # Set the content as HTML
    message.add_alternative(html_content, subtype="html")

    try:
        await aiosmtplib.send(
            message,
            hostname=os.getenv("SMTP_HOST", "smtp.gmail.com"),
            port=int(os.getenv("SMTP_PORT", 587)),
            username=os.getenv("EMAIL_USER"),
            password=os.getenv("EMAIL_PASSWORD"),
            start_tls=True,
        )
        print(f"✅ Email successfully sent to {email}")
    except Exception as e:
        print(f"❌ Failed to send email to {email}: {e}")


# --- Pydantic model for validation ---
class SubscribeModel(BaseModel):
    email: EmailStr


# --- Routes ---
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/subscribe", response_class=HTMLResponse)
async def subscribe(
        request: Request,
        background_tasks: BackgroundTasks,
        email: str = Form(...),
        db: Session = Depends(get_db),
):
    # Validate email
    try:
        data = SubscribeModel(email=email)
    except ValidationError:
        return templates.TemplateResponse(
            "index.html", {"request": request, "error": "Invalid email address"}
        )

    valid_email = data.email.lower()  # normalize to lowercase

    # Check if subscriber exists
    if db.query(Subscriber).filter(Subscriber.email == valid_email).first():
        return templates.TemplateResponse(
            "index.html", {"request": request, "message": "Email already subscribed."}
        )

    # Save new subscriber
    new_subscriber = Subscriber(email=valid_email)
    try:
        db.add(new_subscriber)
        db.commit()
        db.refresh(new_subscriber)
    except Exception as e:
        db.rollback()
        return templates.TemplateResponse(
            "index.html", {"request": request, "error": f"Database error: {str(e)}"}
        )

    # Send email in background
    background_tasks.add_task(send_thank_you_email, valid_email)

    return templates.TemplateResponse(
        "index.html", {"request": request, "message": "Thank you! You've been subscribed."}
    )
