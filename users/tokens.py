from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Timestamped token invalidated immediately after email verification."""

    key_salt = "crm_invoice_app.users.EmailVerificationTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        return "|".join(
            [
                str(user.pk),
                str(timestamp),
                user.password,
                user.email,
                str(user.email_verified_at or ""),
            ]
        )


email_verification_token = EmailVerificationTokenGenerator()
