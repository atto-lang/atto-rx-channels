"""Host-only source guardrails for FutureSubscription cancellation.

These tests do not execute Oreslang or certify scheduler/runtime behavior.
The compiler-pinned guest fixtures remain the real execution gate.
"""
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "src" / "rx.ores"


class FutureSubscriptionSourceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = SOURCE.read_text(encoding="utf-8")
        cls.future = text.split(
            "define class FutureSubscription<T> extends Subscription<T> as", 1
        )[1].split("define class FutureObservable<T>", 1)[0]

    def test_uses_atomic_channel_future_select(self):
        self.assertIn("SelectCase.read(self.stopped)", self.future)
        self.assertIn("SelectCase.future(pending)", self.future)
        self.assertIn("nb select first from self.cases", self.future)

    def test_never_raw_awaits_shared_future(self):
        self.assertNotIn("await self.pending", self.future)

    def test_dispose_signals_private_stop_without_cancelling_producer(self):
        dispose = self.future.split("pub dispose(): void", 1)[1]
        self.assertIn("try writech self.stopped, true", dispose)
        self.assertNotIn(".cancel(", dispose)

    def test_future_failure_stays_result_data(self):
        pull = self.future.split(
            "pub pull_result(): Result<Option<T>, Object>", 1
        )[1].split("pub pull(): Option<T>", 1)[0]
        self.assertIn("catch (err)", pull)
        self.assertIn("return Err(err);", pull)


if __name__ == "__main__":
    unittest.main()
