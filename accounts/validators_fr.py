from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from django.contrib.auth.password_validation import (
UserAttributeSimilarityValidator,
MinimumLengthValidator,
CommonPasswordValidator,
NumericPasswordValidator,
)


class UserAttributeSimilarityValidatorFR(UserAttributeSimilarityValidator):
    default_msg = _("Votre mot de passe ne doit pas être trop similaire à vos informations personnelles.")
    def validate(self, password, user=None):
        try:
            super().validate(password, user)
        except ValidationError:
            raise ValidationError(self.default_msg, code="password_too_similar")
        def get_help_text(self):
            return self.default_msg


class MinimumLengthValidatorFR(MinimumLengthValidator):
    def validate(self, password, user=None):
        if len(password) < self.min_length:
            raise ValidationError(
            _("Votre mot de passe doit contenir au moins %(min_length)d caractères.") % {"min_length": self.min_length},
            code="password_too_short",
            )
    def get_help_text(self):
        return _("Votre mot de passe doit contenir au moins %(min_length)d caractères.") % {"min_length": self.min_length}


class CommonPasswordValidatorFR(CommonPasswordValidator):
    default_msg = _("Votre mot de passe ne peut pas être un mot de passe couramment utilisé.")
    def validate(self, password, user=None):
        try:
            super().validate(password, user)
        except ValidationError:
            raise ValidationError(self.default_msg, code="password_too_common")
        def get_help_text(self):
            return self.default_msg


class NumericPasswordValidatorFR(NumericPasswordValidator):
    default_msg = _("Votre mot de passe ne peut pas être entièrement numérique.")
    def validate(self, password, user=None):
        try:
            super().validate(password, user)
        except ValidationError:
            raise ValidationError(self.default_msg, code="password_entirely_numeric")
        def get_help_text(self):
            return self.default_msg