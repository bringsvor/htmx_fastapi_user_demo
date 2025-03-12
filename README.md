
---Authentication Flow Implementation Summary:

1. Email Verification
   - User registers with email/password
   - System marks user as unverified
   - Verification token is generated
   - Email with verification link is sent
   - User clicks link to verify their email
   - System marks user as verified
   - User can now log in

2. Forgot Password
   - User requests password reset
   - System generates reset token
   - Email with reset link is sent
   - User clicks link and sets new password
   - User can log in with new password

3. Integration Points
   - UserManager handles email sending
   - Templates for emails stored in templates/emails/
   - Background tasks for sending emails asynchronously

4. Authentication Options
   - Local email/password (with verification)
   - Google OAuth
   - Vipps OAuth (if configured)

5. Security Notes
   - Passwords are securely hashed
   - Email confirmation required for local accounts
   - Authentication status passed via secure cookies
