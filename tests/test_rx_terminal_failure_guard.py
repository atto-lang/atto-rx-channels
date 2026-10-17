"""Fail-closed source gate: a failed subscription is NOT completion.

Host-only admission test. It does not prove guest-language runtime behavior.
"""
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "src" / "rx.ores"

class SubscriptionFailureAdmission(unittest.TestCase):
    def test_exception_path_must_not_claim_natural_completion(self):
        text = SOURCE.read_text(encoding="utf-8")
        subscription = text.split("define class Subscription<T> as", 1)[1].split(
            "define class Observable<T> as", 1
        )[0]
        caught = subscription.split("} catch (err) {", 1)[1].split(
            "} finally {", 1
        )[0]
        self.assertNotIn(
            "self.claim_finished();", caught,
            "P0: upstream failure must never transition to COMPLETE"
        )
        self.assertIn(
            "self.claim_failed();", caught,
            "P0: use distinct failure terminal claim"
        )

    def test_unsettled_unwind_must_not_claim_complete(self):
        text = SOURCE.read_text(encoding="utf-8")
        subscription = text.split("define class Subscription<T> as", 1)[1].split(
            "define class Observable<T> as", 1
        )[0]
        cleanup = subscription.split("if !marked(settled); then", 1)[1].split(
            "\n      fi", 1
        )[0]
        self.assertNotIn(
            "self.claim_finished();", cleanup,
            "P0: exceptional cleanup must not masquerade as clean EOF"
        )
        self.assertIn("self.claim_failed();", cleanup)

    def test_failed_subscription_is_checked_before_eof(self):
        text = SOURCE.read_text(encoding="utf-8")
        subscription = text.split("define class Subscription<T> as", 1)[1].split(
            "define class Observable<T> as", 1
        )[0]
        next_method = subscription.split(
            "pub next_result(): Result<Option<T>, Object>", 1
        )[1].split("pub next(): Option<T>", 1)[0]
        self.assertLess(
            next_method.index("marked(self.failed)"),
            next_method.index("marked(self.cancelled)")
        )
        self.assertIn("subscription previously failed", next_method)

    def test_all_terminal_claims_exclude_failed_state(self):
        text = SOURCE.read_text(encoding="utf-8")
        subscription = text.split("define class Subscription<T> as", 1)[1].split(
            "define class Observable<T> as", 1
        )[0]
        finished = subscription.split("claim_finished(): bool", 1)[1].split(
            "claim_failed(): bool", 1
        )[0]
        cancel = subscription.split("pub cancel(): bool", 1)[1]
        self.assertIn("marked(self.failed)", finished)
        self.assertIn("marked(self.failed)", cancel)

    def test_typed_signal_is_closed_and_legacy_event_projects_from_it(self):
        text = SOURCE.read_text(encoding="utf-8")
        subscription = text.split("define class Subscription<T> as", 1)[1].split(
            "define class Observable<T> as", 1
        )[0]
        signal = subscription.split(
            "pub next_signal(): Result<Option<T>, Option<Object>>", 1
        )[1].split("pub next_event_result():", 1)[0]
        self.assertIn("return Ok(frame);", signal)
        self.assertIn("return Ok(None);", signal)
        self.assertIn("return Err(None);", signal)
        self.assertIn("return Err(Some(err));", signal)

        legacy = subscription.split(
            "pub next_event_result(): Result<StreamEvent<T>, Object>", 1
        )[1].split("pub next_event(): StreamEvent<T>", 1)[0]
        self.assertIn("self.next_signal()", legacy)
        self.assertNotIn("self.next_result()", legacy)

    def test_failure_status_is_never_natural_complete(self):
        text = SOURCE.read_text(encoding="utf-8")
        subscription = text.split("define class Subscription<T> as", 1)[1].split(
            "define class Observable<T> as", 1
        )[0]
        self.assertIn("pub is_failed(): bool", subscription)
        complete = subscription.split("pub is_complete(): bool", 1)[1].split(
            "pub is_failed(): bool", 1
        )[0]
        self.assertIn("marked(self.failed)", complete)


if __name__ == "__main__":
    unittest.main()
