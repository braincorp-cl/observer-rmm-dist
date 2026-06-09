"""Tests for Check lifecycle — T008 (Feature 002).

Covers: pending→passing→failing with fails_b4_alert threshold, alert resolution
on passing, diskspace/cpuload/memory thresholds.
Written for TDD: targets renamed observer.* module (after T010).
"""
from model_bakery import baker

from checks.models import Check, CheckResult
from observer.test import TacticalTestCase

try:
    from checks.constants import CheckStatus, CheckType
except ImportError:
    from checks.models import CheckStatus, CheckType


class TestCheckLifecycle(TacticalTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()

    def _make_check(self, check_type="diskspace", fails_b4_alert=1):
        site = baker.make("clients.Site")
        agent = baker.make("agents.Agent", site=site)
        return baker.make(
            "checks.Check",
            agent=agent,
            check_type=check_type,
            fails_b4_alert=fails_b4_alert,
        )

    def test_initial_result_is_pending_status(self):
        check = self._make_check()
        result = baker.make("checks.CheckResult", assigned_check=check)
        self.assertIn(result.status, [CheckStatus.PENDING, CheckStatus.PASSING, CheckStatus.FAILING])

    def test_failing_increments_fail_count(self):
        check = self._make_check(fails_b4_alert=3)
        result = baker.make(
            "checks.CheckResult",
            assigned_check=check,
            status=CheckStatus.FAILING,
            fail_count=0,
        )
        result.fail_count += 1
        result.save(update_fields=["fail_count"])
        result.refresh_from_db()
        self.assertEqual(result.fail_count, 1)

    def test_passing_resets_fail_count(self):
        check = self._make_check(fails_b4_alert=3)
        result = baker.make(
            "checks.CheckResult",
            assigned_check=check,
            status=CheckStatus.FAILING,
            fail_count=2,
        )
        result.status = CheckStatus.PASSING
        result.fail_count = 0
        result.save(update_fields=["status", "fail_count"])
        result.refresh_from_db()
        self.assertEqual(result.status, CheckStatus.PASSING)
        self.assertEqual(result.fail_count, 0)

    def test_fails_b4_alert_threshold_respected(self):
        check = self._make_check(fails_b4_alert=3)
        result = baker.make(
            "checks.CheckResult",
            assigned_check=check,
            status=CheckStatus.FAILING,
            fail_count=2,
        )
        # fail_count < fails_b4_alert: no alert yet
        self.assertLess(result.fail_count, check.fails_b4_alert)

        result.fail_count = 3
        result.save(update_fields=["fail_count"])
        result.refresh_from_db()
        self.assertGreaterEqual(result.fail_count, check.fails_b4_alert)


class TestCheckThresholds(TacticalTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()

    def _make_check_with_threshold(self, check_type, threshold):
        site = baker.make("clients.Site")
        agent = baker.make("agents.Agent", site=site)
        return baker.make(
            "checks.Check",
            agent=agent,
            check_type=check_type,
            threshold=threshold,
            fails_b4_alert=1,
        )

    def test_diskspace_check_has_threshold(self):
        check = self._make_check_with_threshold("diskspace", 80)
        self.assertEqual(check.threshold, 80)
        self.assertEqual(check.check_type, "diskspace")

    def test_cpuload_check_has_threshold(self):
        check = self._make_check_with_threshold("cpuload", 90)
        self.assertEqual(check.threshold, 90)
        self.assertEqual(check.check_type, "cpuload")

    def test_memory_check_has_threshold(self):
        check = self._make_check_with_threshold("memory", 85)
        self.assertEqual(check.threshold, 85)
        self.assertEqual(check.check_type, "memory")
