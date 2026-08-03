"""Tests for Alert lifecycle — origin: F002 T009 (dist scaffold), ported in F008 (D-02 rescue).

Covers: create_or_return_availability_alert() idempotence, snooze (state
and expiration), alert.resolve() (clears snooze), alert types.
Placed at app root (not alerts/tests/) to avoid module/package collision
with the upstream alerts/tests.py suite.
"""

from datetime import timedelta

from django.utils import timezone as djangotime
from model_bakery import baker

from alerts.models import Alert
from observerrmm.constants import AlertType
from observerrmm.test import ObserverTestCase


class TestAvailabilityAlertIdempotence(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()

    def _make_agent(self):
        site = baker.make("clients.Site")
        return baker.make("agents.Agent", site=site)

    def test_creates_alert_when_none_exists(self):
        agent = self._make_agent()
        alert = Alert.create_or_return_availability_alert(agent)
        self.assertIsNotNone(alert)
        self.assertFalse(alert.resolved)

    def test_returns_existing_unresolved_alert(self):
        agent = self._make_agent()
        first = Alert.create_or_return_availability_alert(agent)
        second = Alert.create_or_return_availability_alert(agent)
        self.assertEqual(first.pk, second.pk)

    def test_creates_new_alert_after_previous_resolved(self):
        agent = self._make_agent()
        first = Alert.create_or_return_availability_alert(agent)
        first.resolve()
        second = Alert.create_or_return_availability_alert(agent)
        self.assertNotEqual(first.pk, second.pk)
        self.assertFalse(second.resolved)


class TestAlertSnooze(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()

    def _make_alert(self):
        site = baker.make("clients.Site")
        agent = baker.make("agents.Agent", site=site)
        return baker.make(
            "alerts.Alert",
            agent=agent,
            alert_type=AlertType.AVAILABILITY,
            resolved=False,
            snoozed=False,
        )

    def test_snooze_sets_snoozed_and_snooze_until(self):
        alert = self._make_alert()
        snooze_until = djangotime.now() + timedelta(hours=1)
        alert.snoozed = True
        alert.snooze_until = snooze_until
        alert.save(update_fields=["snoozed", "snooze_until"])
        alert.refresh_from_db()
        self.assertTrue(alert.snoozed)
        self.assertIsNotNone(alert.snooze_until)

    def test_snooze_until_can_expire(self):
        alert = self._make_alert()
        past = djangotime.now() - timedelta(hours=1)
        alert.snoozed = True
        alert.snooze_until = past
        alert.save(update_fields=["snoozed", "snooze_until"])
        alert.refresh_from_db()
        self.assertLess(alert.snooze_until, djangotime.now())


class TestAlertResolve(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()

    def test_resolve_sets_resolved_and_clears_snooze(self):
        site = baker.make("clients.Site")
        agent = baker.make("agents.Agent", site=site)
        alert = baker.make(
            "alerts.Alert",
            agent=agent,
            alert_type=AlertType.AVAILABILITY,
            resolved=False,
            snoozed=True,
            snooze_until=djangotime.now() + timedelta(hours=1),
        )
        alert.resolve()
        alert.refresh_from_db()
        self.assertTrue(alert.resolved)
        self.assertIsNotNone(alert.resolved_on)
        self.assertFalse(alert.snoozed)
        self.assertIsNone(alert.snooze_until)

    def test_resolve_is_idempotent(self):
        site = baker.make("clients.Site")
        agent = baker.make("agents.Agent", site=site)
        alert = baker.make(
            "alerts.Alert",
            agent=agent,
            alert_type=AlertType.AVAILABILITY,
            resolved=False,
        )
        alert.resolve()
        alert.resolve()
        alert.refresh_from_db()
        self.assertTrue(alert.resolved)


class TestAlertTypes(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()

    def test_availability_alert_type(self):
        site = baker.make("clients.Site")
        agent = baker.make("agents.Agent", site=site)
        alert = baker.make(
            "alerts.Alert",
            agent=agent,
            alert_type=AlertType.AVAILABILITY,
            resolved=False,
        )
        self.assertEqual(alert.alert_type, AlertType.AVAILABILITY)

    def test_check_alert_type(self):
        site = baker.make("clients.Site")
        agent = baker.make("agents.Agent", site=site)
        check = baker.make("checks.Check", agent=agent)
        alert = baker.make(
            "alerts.Alert",
            assigned_check=check,
            alert_type=AlertType.CHECK,
            resolved=False,
        )
        self.assertEqual(alert.alert_type, AlertType.CHECK)
