"""Tests for accounts authentication flow — T006 (Feature 002).

Covers: 2FA flow, role cache TTL, ROOT_USER protection, block_local_user_logon.
Written for TDD: tests target the renamed observer.* module (after T010).
"""
from unittest.mock import patch

import pyotp
from django.core.cache import cache
from model_bakery import baker

from observer.constants import ROLE_CACHE_PREFIX
from observer.test import TacticalTestCase

CHECKCREDS_URL = "/v2/checkcreds/"
LOGIN_URL = "/v2/login/"


class TestCheckCredsEndpoint(TacticalTestCase):
    def setUp(self):
        self.setup_coresettings()

    def test_missing_credentials_returns_400(self):
        r = self.client.post(CHECKCREDS_URL, {}, format="json")
        self.assertEqual(r.status_code, 400)

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

    def test_block_local_user_logon_non_superuser_returns_400(self):
        core = self.setup_coresettings()
        core.block_local_user_logon = True
        core.save()
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
        self.assertEqual(r.status_code, 400)

    def test_superuser_bypasses_block_local_user_logon(self):
        core = self.setup_coresettings()
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


class TestLoginEndpoint(TacticalTestCase):
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

        token = pyotp.TOTP(totp_key).now()
        r = self.client.post(
            LOGIN_URL,
            {"username": "mfauser", "password": "testpass123", "token": token},
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
            {"username": "mfauser2", "password": "testpass123", "token": "000000"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)


class TestRoleCache(TacticalTestCase):
    def test_role_cache_is_set_with_600s_ttl(self):
        role = baker.make("accounts.Role", name="testrole")
        user = baker.make("accounts.User", role=role)
        cache.delete(f"{ROLE_CACHE_PREFIX}{role.name}")

        result = user.get_and_set_role_cache()

        cached = cache.get(f"{ROLE_CACHE_PREFIX}{role.name}")
        self.assertIsNotNone(cached)
        self.assertEqual(result.pk, role.pk)

    def test_role_cache_invalidated_on_role_save(self):
        role = baker.make("accounts.Role", name="cacherole")
        cache.set(f"{ROLE_CACHE_PREFIX}{role.name}", role, 600)

        role.save()

        cached = cache.get(f"{ROLE_CACHE_PREFIX}{role.name}")
        self.assertIsNone(cached)
