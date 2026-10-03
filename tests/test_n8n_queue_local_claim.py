"""Offline regression for Phase 09 local claim coordination."""

import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from src.context import n8n_queue_local_claim as module


def valid_receipt():
    return {
        "request_id": "SOC-LAB-0001-Q12-Q13",
        "row_id": 1,
        "source_event_id": "LAB-0001",
        "historical_queue_id": 12,
        "current_queue_id": 13,
        "status": "QUEUED",
        "execution_mode": "DRY_RUN",
        "human_review_required": True,
        "human_review_completed": False,
        "model_execution_started": False,
        "table_mutation_attempted": False,
        "operational_dispatch_allowed": False,
        "notification_sent": False,
    }


class LocalClaimTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        lock_path = Path(self.temp.name) / "request.lock"

        guard_patch = patch.object(module, "LOCK_PATH", lock_path)
        guard_patch.start()
        self.addCleanup(guard_patch.stop)

        client_patch = patch.object(
            module,
            "fetch_lab_runtime_request",
            return_value=valid_receipt(),
        )

        self.client = client_patch.start()
        self.addCleanup(client_patch.stop)

    def test_valid_request_is_dry_run(self):
        result = module.run_local_claim_dry_run()

        self.assertTrue(result["local_guard_completed"])
        self.assertFalse(result["datatable_reservation_attempted"])
        self.assertFalse(result["model_execution_started"])
        self.assertFalse(result["notification_sent"])
        self.assertEqual(result["status_observed"], "QUEUED")

    def test_empty_queue_does_not_trigger_processing(self):
        self.client.return_value = None

        result = module.run_local_claim_dry_run()

        self.assertFalse(result["request_available"])
        self.assertFalse(result["model_execution_started"])

    def test_nested_guard_rejects_duplicate(self):
        with module.local_request_guard():
            with self.assertRaises(module.LocalClaimBusy):
                with module.local_request_guard():
                    pass

    def test_guard_releases_after_success(self):
        with module.local_request_guard():
            pass

        with module.local_request_guard():
            pass

    def test_guard_releases_after_exception(self):
        with self.assertRaisesRegex(ValueError, "synthetic"):
            with module.local_request_guard():
                raise ValueError("synthetic")

        with module.local_request_guard():
            pass

    def test_invalid_identity_rejected(self):
        with self.assertRaises(module.LocalClaimError):
            with module.local_request_guard("OTHER-REQUEST"):
                pass

        self.client.assert_not_called()

    def test_invalid_receipt_rejected_and_lock_released(self):
        self.client.return_value = {
            **valid_receipt(),
            "operational_dispatch_allowed": True,
        }

        with self.assertRaises(module.LocalClaimError):
            module.run_local_claim_dry_run()

        with module.local_request_guard():
            pass

    def test_invalid_row_id_rejected(self):
        self.client.return_value = {
            **valid_receipt(),
            "row_id": True,
        }

        with self.assertRaises(module.LocalClaimError):
            module.run_local_claim_dry_run()

    def test_two_concurrent_threads_do_not_both_enter(self):
        entered = threading.Event()
        release = threading.Event()
        outcomes = []

        def first_worker():
            try:
                with module.local_request_guard():
                    entered.set()
                    if not release.wait(timeout=5):
                        raise TimeoutError("Test synchronization timed out.")
                    outcomes.append("FIRST_COMPLETED")
            except Exception as exc:
                outcomes.append(type(exc).__name__)

        thread = threading.Thread(target=first_worker)
        thread.start()

        try:
            self.assertTrue(entered.wait(timeout=5))

            with self.assertRaises(module.LocalClaimBusy):
                with module.local_request_guard():
                    outcomes.append("SECOND_ENTERED")
        finally:
            release.set()
            thread.join(timeout=5)

        self.assertFalse(thread.is_alive())
        self.assertEqual(outcomes, ["FIRST_COMPLETED"])

        with module.local_request_guard():
            pass


    def test_independent_processes_and_crash_recovery(self):
        """Two independent Python processes share the same OS lock."""
        import os
        import subprocess
        import sys
        import time

        lock = module.LOCK_PATH
        ready = Path(self.temp.name) / "multiprocess.ready"

        child_code = """
import os
import sys
from pathlib import Path
from src.context import n8n_queue_local_claim as claim

claim.LOCK_PATH = Path(sys.argv[1])
mode = sys.argv[2]

try:
    with claim.local_request_guard():
        if mode == "hold":
            Path(sys.argv[3]).write_text("READY")
            sys.stdin.readline()
        elif mode == "crash":
            os._exit(23)
        else:
            print("ACQUIRED")
except claim.LocalClaimBusy:
    print("BUSY")
    sys.exit(21)
"""

        def command(mode):
            return [
                sys.executable,
                "-u",
                "-c",
                child_code,
                str(lock),
                mode,
                str(ready),
            ]

        first = subprocess.Popen(
            command("hold"),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            deadline = time.monotonic() + 5

            while not ready.exists():
                if first.poll() is not None:
                    self.fail(
                        "First process ended before acquiring the lock."
                    )

                if time.monotonic() >= deadline:
                    self.fail("First process did not acquire the lock.")

                time.sleep(0.05)

            second = subprocess.run(
                command("probe"),
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            self.assertEqual(second.returncode, 21)
            self.assertIn("BUSY", second.stdout)

            first.communicate(input="\n", timeout=5)
            self.assertEqual(first.returncode, 0)

            after_release = subprocess.run(
                command("probe"),
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            self.assertEqual(after_release.returncode, 0)
            self.assertIn("ACQUIRED", after_release.stdout)

            crashed = subprocess.run(
                command("crash"),
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            self.assertEqual(crashed.returncode, 23)

            recovered = subprocess.run(
                command("probe"),
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            self.assertEqual(recovered.returncode, 0)
            self.assertIn("ACQUIRED", recovered.stdout)

        finally:
            if first.poll() is None:
                first.kill()
                first.communicate(timeout=5)

    def test_unexpected_lock_error_is_not_busy(self):
        """An unexpected OS error must not be called contention."""
        import errno

        with patch.object(
            module,
            "_lock",
            side_effect=OSError(errno.EIO, "synthetic I/O failure"),
        ):
            with self.assertRaises(module.LocalClaimError):
                with module.local_request_guard():
                    pass

    def test_known_contention_error_is_busy(self):
        """A standard nonblocking contention code maps to busy."""
        import errno

        with patch.object(
            module,
            "_lock",
            side_effect=OSError(errno.EAGAIN, "synthetic contention"),
        ):
            with self.assertRaises(module.LocalClaimBusy):
                with module.local_request_guard():
                    pass

    def test_windows_access_denied_is_not_claimed_busy(self):
        """When Windows identifies access denied, classify as error."""
        exc = OSError(13, "synthetic access denied")
        exc.winerror = 5

        with patch.object(
            module,
            "_lock",
            side_effect=exc,
        ):
            with self.assertRaises(module.LocalClaimError):
                with module.local_request_guard():
                    pass

if __name__ == "__main__":
    unittest.main(verbosity=2)