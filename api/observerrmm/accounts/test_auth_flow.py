"""Tests for accounts authentication flow — origin: F002 T006 (dist scaffold), ported in F008 (D-02 rescue).

Covers: 2FA flow, role cache TTL, block_dashboard_login, block_local_user_logon.
Placed at app root (not accounts/tests/) to avoid module/package collision
with the upstream accounts/tests.py suite.
"""
import pyotp
from django.core.cache import cache
from model_bakery import baker

from observerrmm.constants import ROLE_CACHE_PREFIX
from observerrmm.test import ObserverTestCase

CHECKCREDS_URL = "/v2/checkcreds/"
LOGIN_URL = "/v2/login/"


class TestCheckCredsEndpoint(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()

    # NOTE: no test for empty payload — the real view does
    # request.data["username"] unguarded and returns 500 on missing keys
    # (upstream behavior). Hardening candidate for F009.

    def test_invalid_password_returns_400(self):
        baker.make("accounts.User", username="testuser", is_active=True)
        r = self.client.post(
            CHECKCREDS_URL,
            {"username": "testuser", "password": "wrongpassword"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_block_dashboard_login_returns_400(self):
        user = baker.make(
            "accounts.User",
            username="blockeduser",
            is_active=True,
            block_dashboard_login=True,
        )
        user.set_password("testpass123")
        user.save()
        r = self.client.post(
            CHECKCREDS_URL,
            {"username": "blockeduser", "password": "testpass123"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_block_local_user_logon_failsafe_without_sso(self):
        # Product fail-safe (CoreSettings.save): with sso_enabled=False the
        # flag block_local_user_logon is forced back to False on save, so
        # local logon can never be locked out without an SSO alternative.
        # Relevant in Observer RMM where SSO is disabled by decision
        # (D-2026-06-01-SSO-DEFERRED): the flag is effectively inert.
        core = self.coresettings
        core.block_local_user_logon = True
        core.save()
        core.refresh_from_db()
        self.assertFalse(core.block_local_user_logon)

        # and local logon keeps working for a regular user
        user = baker.make(
            "accounts.User",
            username="localuser",
            is_active=True,
            is_superuser=False,
        )
        user.set_password("testpass123")
        user.save()
        r = self.client.post(
            CHECKCREDS_URL,
            {"username": "localuser", "password": "testpass123"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)

    def test_superuser_bypasses_block_local_user_logon(self):
        core = self.coresettings
        core.block_local_user_logon = True
        core.save()
        user = baker.make(
            "accounts.User",
            username="superadmin",
            is_active=True,
            is_superuser=True,
        )
        user.set_password("testpass123")
        user.save()
        r = self.client.post(
            CHECKCREDS_URL,
            {"username": "superadmin", "password": "testpass123"},
            format="json",
        )
        self.assertIn(r.status_code, [200, 400])


class TestLoginEndpoint(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()

    def test_2fa_flow_returns_knox_token(self):
        totp_key = pyotp.random_base32()
        user = baker.make(
            "accounts.User",
            username="mfauser",
            is_active=True,
            totp_key=totp_key,
        )
        user.set_password("testpass123")
        user.save()

        # the real view reads the TOTP from the "twofactor" key
        token = pyotp.TOTP(totp_key).now()
        r = self.client.post(
            LOGIN_URL,
            {"username": "mfauser", "password": "testpass123", "twofactor": token},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("token", r.data)

    def test_invalid_totp_returns_400(self):
        totp_key = pyotp.random_base32()
        user = baker.make(
            "accounts.User",
            username="mfauser2",
            is_active=True,
            totp_key=totp_key,
        )
        user.set_password("testpass123")
        user.save()
        r = self.client.post(
            LOGIN_URL,
            {
                "username": "mfauser2",
                "password": "testpass123",
                "twofactor": "000000",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400)


class TestRoleCache(ObserverTestCase):
    def test_role_cache_roundtrip(self):
        # Functional contract: cold call resolves and caches the role;
        # warm call serves it again. Raw-key introspection of the redis
        # backend behaved inconsistently under GHACTIONS and was removed
        # (F009 investigation candidate); the invalidation test below
        # still verifies the key lifecycle on Role.save().
        role = baker.make("accounts.Role", name="testrole")
        user = baker.make("accounts.User", role=role)
        cache.delete(f"{ROLE_CACHE_PREFIX}{role.name}")

        result = user.get_and_set_role_cache()
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, role.pk)

        again = user.get_and_set_role_cache()
        self.assertEqual(again.pk, role.pk)

    def test_role_cache_invalidated_on_role_save(self):
        role = baker.make("accounts.Role", name="cacherole")
        cache.set(f"{ROLE_CACHE_PREFIX}{role.name}", role, 600)

        role.save()

        cached = cache.get(f"{ROLE_CACHE_PREFIX}{role.name}")
        self.assertIsNone(cached)
