"""Test EE SSO unlock — T022 (Feature 002).

Verifies that after removing the token_is_valid() guard from CoreSettings.save(),
sso_enabled=True persists without being reverted.
Requires PostgreSQL (ArrayField usage in related models).
"""
from core.models import CoreSettings
from observer.test import TacticalTestCase


class TestEESSOUnlock(TacticalTestCase):
    def setUp(self):
        self.authenticate()

    def test_sso_enabled_persists_without_license_check(self):
        settings = self.setup_coresettings()
        settings.sso_enabled = False
        settings.save()

        settings.refresh_from_db()
        settings.sso_enabled = True
        settings.save()

        settings.refresh_from_db()
        self.assertTrue(
            settings.sso_enabled,
            "sso_enabled should be True — EE guard was removed (T012)",
        )

    def test_sso_disabled_persists(self):
        settings = self.setup_coresettings()
        settings.sso_enabled = True
        settings.save()

        settings.refresh_from_db()
        settings.sso_enabled = False
        settings.save()

        settings.refresh_from_db()
        self.assertFalse(settings.sso_enabled)
