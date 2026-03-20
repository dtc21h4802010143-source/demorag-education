# EduChat - User Registration and Password Recovery Features

## 📋 Overview

This update adds comprehensive user authentication features including:
- **User Registration**: Self-service account creation
- **Password Recovery**: Email-based password reset functionality
- **User Database**: Persistent user accounts with email validation

## 🚀 New Features

### 1. User Registration Endpoint
**POST** `/auth/register`

Register a new user account with email verification.

**Request Body:**
```json
{
  "username": "johndoe",
  "email": "john@example.com",
  "password": "secure_password_123",
  "full_name": "John Doe"
}
```

**Response (200):**
```json
{
  "id": 1,
  "username": "johndoe",
  "email": "john@example.com",
  "full_name": "John Doe",
  "is_active": true,
  "created_at": "2026-03-18T10:30:00"
}
```

**Validation Rules:**
- Username: 3-50 characters, unique
- Email: Valid email format, unique
- Password: Minimum 6 characters
- Full name: Optional, max 255 characters

---

### 2. User Login Endpoint (Updated)
**POST** `/auth/user-login`

Login with username/password using the new database-backed authentication.

**Request Body:**
```json
{
  "username": "johndoe",
  "password": "secure_password_123"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

### 3. Password Reset Request
**POST** `/auth/password-reset-request`

Request a password reset by providing your email address. A reset link will be sent to your email.

**Request Body:**
```json
{
  "email": "john@example.com"
}
```

**Response (200):**
```json
{
  "message": "If an account with this email exists, a password reset link has been sent."
}
```

**Note:** For security, the endpoint doesn't reveal if an email exists in the system.

---

### 4. Password Reset Confirmation
**POST** `/auth/password-reset-confirm`

Reset your password using the token received via email.

**Request Body:**
```json
{
  "token": "reset_token_from_email",
  "email": "john@example.com",
  "new_password": "new_secure_password_123"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

## 📧 Email Configuration

The password recovery feature requires SMTP email configuration. Add these variables to your `.env` file:

```env
# Gmail SMTP Example
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-specific-password
SMTP_FROM_EMAIL=noreply@educhat.com
SMTP_FROM_NAME=EduChat
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES=30
FRONTEND_PASSWORD_RESET_URL=http://localhost:5173/reset-password
```

### Setting up Gmail SMTP

1. Enable 2-Step Verification on your Google Account
2. Generate an **App Password**: https://myaccount.google.com/apppasswords
3. Use the generated 16-character password as `SMTP_PASSWORD`

### Alternative Email Providers

For other email providers (Outlook, SendGrid, etc.), configure:
- `SMTP_HOST`: Your provider's SMTP host
- `SMTP_PORT`: Usually 587 (TLS) or 465 (SSL)
- `SMTP_USER`: Your email address
- `SMTP_PASSWORD`: Your password or API key

---

## 🗄️ Database Changes

New tables created automatically:

### `users` table
```sql
- id (Integer, Primary Key)
- username (String, Unique)
- email (String, Unique)
- hashed_password (String)
- full_name (String, Nullable)
- is_active (Boolean, Default: True)
- is_admin (Boolean, Default: False)
- created_at (DateTime)
- updated_at (DateTime)
```

### `password_resets` table
```sql
- id (Integer, Primary Key)
- user_id (Integer, Indexed)
- email (String, Indexed)
- token (String, Unique)
- expires_at (DateTime)
- created_at (DateTime)
```

---

## 🔐 Security Features

✅ **Password Hashing**: Passwords hashed with bcrypt (salted)
✅ **Tokens**: Secure reset tokens generated with `secrets.token_urlsafe`
✅ **Token Expiration**: Reset tokens expire after 30 minutes (configurable)
✅ **Email Validation**: RFC-compliant email validation
✅ **Rate Limiting**: Protected by existing rate limiter (120 req/min)
✅ **HTTPS**: Use HTTPS in production for all authentication endpoints

---

## 📱 Frontend Integration

### Registration Page
```typescript
const response = await fetch('/auth/register', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'johndoe',
    email: 'john@example.com',
    password: 'secure_password',
    full_name: 'John Doe'
  })
});
const user = await response.json();
```

### Login with New Credentials
```typescript
const response = await fetch('/auth/user-login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'johndoe',
    password: 'secure_password'
  })
});
const { access_token } = await response.json();
localStorage.setItem('token', access_token);
```

### Password Reset Flow
1. User enters email on "Forgot Password" page
2. App calls `POST /auth/password-reset-request`
3. User receives email with reset link: `http://localhost:5173/reset-password?token=XXX&email=john@example.com`
4. User enters new password on reset confirmation page
5. App calls `POST /auth/password-reset-confirm` with token, email, and new password
6. User receives new access token and is logged in

---

## 🔄 Migration Notes

Existing hardcoded authentication (admin/student login) still works for backward compatibility but is now deprecated. Users can:
1. Register new accounts via `/auth/register`, OR
2. Continue using admin and student credentials configured in `.env`

---

## 📝 API Documentation

Access the full API documentation at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

---

## ⚙️ Installation

1. Update dependencies:
```bash
pip install -r requirements.txt
```

2. Configure `.env` with email settings (optional but required for email features)

3. The database tables are created automatically on startup via `init_db()`

---

## 🧪 Testing

```bash
# Register a new user
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "securepass123",
    "full_name": "Test User"
  }'

# Login
curl -X POST "http://localhost:8000/auth/user-login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "securepass123"
  }'

# Request password reset
curl -X POST "http://localhost:8000/auth/password-reset-request" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'
```

---

## 🐛 Troubleshooting

**Email not sending?**
- Check SMTP credentials in `.env`
- Ensure SMTP host and port are correct
- For Gmail, verify app-specific password is enabled
- Check firewall/network access to SMTP port

**Reset token expired?**
- Tokens expire after 30 minutes (configurable)
- User must request a new reset link

**Username/Email already exists?**
- Choose a different username or email
- Reset password if you forgot credentials

---

## 📚 Files Modified/Created

**New Files:**
- `app/models/user.py` - User and PasswordReset models
- `app/services/email_service.py` - Email sending service
- `.env.example` - Configuration template

**Modified Files:**
- `app/schemas/auth.py` - New request/response schemas
- `app/api/auth.py` - New authentication endpoints
- `app/db/init_db.py` - Database initialization
- `requirements.txt` - New dependencies
- `app/core/config.py` - Email configuration settings

---

## 🎯 Next Steps

1. Install updated dependencies: `pip install -r requirements.txt`
2. Configure email settings in `.env`
3. Restart the backend server (tables auto-create)
4. Test registration and password reset flows
5. Integrate with frontend registration/password-reset pages

---

**Ready to go!** 🚀 Your EduChat system now has full user authentication with email-based password recovery.
