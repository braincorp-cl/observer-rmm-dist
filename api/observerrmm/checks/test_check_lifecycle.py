"""Tests for Check lifecycle — origin: F002 T008 (dist scaffold), ported in F008 (D-02 rescue).

Covers: failing/passing fail_count transitions with fails_b4_alert threshold,
diskspace/cpuload/memory warning/error thresholds.
Placed at app root (not checks/tests/) to avoid module/package collision
with the upstream checks/tests.py suite. Threshold tests adapted to the real
model fields (warning_threshold/error_threshold — the scaffold's single
`threshold` field never existed in this model).
"""

from model_bakery import baker

from observerrmm.constants import CheckStatus
from observerrmm.test import ObserverTestCase


class TestCheckLifecycle(ObserverTestCase):
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
        self.assertIn(
            result.status,
            [CheckStatus.PENDING, CheckStatus.PASSING, CheckStatus.FAILING],
        )

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


class TestCheckThresholds(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()

    def _make_check_with_thresholds(self, check_type, warning, error):
        site = baker.make("clients.Site")
        agent = baker.make("agents.Agent", site=site)
        return baker.make(
            "checks.Check",
            agent=agent,
            check_type=check_type,
            warning_threshold=warning,
            error_threshold=error,
            fails_b4_alert=1,
        )

    def test_diskspace_check_has_thresholds(self):
        check = self._make_check_with_thresholds("diskspace", 75, 90)
        self.assertEqual(check.warning_threshold, 75)
        self.assertEqual(check.error_threshold, 90)
        self.assertEqual(check.check_type, "diskspace")

    def test_cpuload_check_has_thresholds(self):
        check = self._make_check_with_thresholds("cpuload", 80, 95)
        self.assertEqual(check.warning_threshold, 80)
        self.assertEqual(check.error_threshold, 95)
        self.assertEqual(check.check_type, "cpuload")

    def test_memory_check_has_thresholds(self):
        check = self._make_check_with_thresholds("memory", 80, 95)
        self.assertEqual(check.warning_threshold, 80)
        self.assertEqual(check.error_threshold, 95)
        self.assertEqual(check.check_type, "memory")
