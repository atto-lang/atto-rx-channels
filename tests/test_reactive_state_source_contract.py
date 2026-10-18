"""Source-shape guardrails for the staged Rx subscription state protocol.

These tests do NOT execute Oreslang or prove scheduler-level race freedom.
Real compiler-pinned guest fixtures and race stress remain mandatory.
"""
from pathlib import Path
import re
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "src" / "rx.ores")


class ReactiveStateSourceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = SOURCE.read_text(encoding="utf-8")
        cls.subscription = text.split("define class Subscription<T> as", 1)[1].split(
            "define class Observable<T> as", 1
        )[0]
        cls.sender = text.split("define class FramedSender<T> as", 1)[1].split(
            "define class FramedPipe<T>", 1
        )[0]

    def method(self, start, end):
        self.assertIn(start, self.subscription)
        self.assertIn(end, self.subscription)
        return self.subscription.split(start, 1)[1].split(end, 1)[0]

    def test_all_subscription_state_windows_are_short_and_released(self):
        windows = re.findall(
            r"writech self\.state_busy, true;([\s\S]*?)try readch self\.state_busy;",
            self.subscription,
        )
        self.assertEqual(len(windows), 7)
        for section in windows:
            for forbidden in ("self.pull()", "self.dispose()", "await "):
                self.assertNotIn(forbidden, section)

    def test_next_checks_terminal_and_claims_singleflight_under_same_gate(self):
        next_method = self.method("pub next_result(): Result<Option<T>, Object>", "pub next(): Option<T>")
        acquired = next_method.index("writech self.state_busy, true;")
        terminal_check = next_method.index("marked(self.cancelled)")
        pull_claim = next_method.index("try writech self.pulling, true")
        released = next_method.index("try readch self.state_busy")
        source_pull = next_method.index("self.pull_result()")
        self.assertTrue(acquired < terminal_check < pull_claim < released < source_pull)

    def test_cancel_terminal_claim_is_guarded_and_dispose_is_outside_gate(self):
        cancel = self.subscription.split("pub cancel(): bool", 1)[1]
        self.assertTrue(cancel.index("writech self.state_busy, true;")
                        < cancel.index("try writech self.cancelled, true")
                        < cancel.index("try readch self.state_busy")
                        < cancel.index("self.dispose_once()"))

    def test_natural_complete_claim_cannot_override_cancel(self):
        claim = self.method("claim_finished(): bool", "dispose_once(): void")
        self.assertIn("marked(self.cancelled)", claim)
        self.assertIn("marked(self.finished)", claim)
        self.assertIn("marked(self.failed)", claim)
        self.assertLess(claim.index("marked(self.cancelled)"),
                        claim.index("try writech self.finished, true"))

    def test_failure_claim_cannot_override_cancel_or_completion(self):
        claim = self.method("claim_failed(): bool", "dispose_once(): void")
        self.assertIn("marked(self.cancelled)", claim)
        self.assertIn("marked(self.finished)", claim)
        self.assertIn("marked(self.failed)", claim)
        self.assertLess(claim.index("marked(self.failed)"),
                        claim.index("try writech self.failed, true"))

    def test_terminal_probes_are_in_private_state_gate(self):
        for name, end in (
            ("pub is_cancelled(): bool", "pub is_complete(): bool"),
            ("pub is_complete(): bool", "pub is_failed(): bool"),
            ("pub is_failed(): bool", "pub next_event(): StreamEvent<T>"),
        ):
            method = self.method(name, end)
            self.assertIn("writech self.state_busy, true;", method)
            self.assertIn("try readch self.state_busy;", method)

    def test_checked_sender_exposes_only_credit_bounded_public_delivery(self):
        source_no_comments = "\n".join(
            line for line in self.sender.splitlines()
            if not line.lstrip().startswith("//")
        )
        self.assertNotIn("pub send(T value): Future<void>", source_no_comments)
        self.assertNotIn("pub complete(): Future<void>", source_no_comments)
        self.assertIn("send_admitted(T value): Future<void>", source_no_comments)
        self.assertIn("complete_admitted(): Future<void>", source_no_comments)

    def test_blocking_sender_holds_one_delivery_credit_until_settlement(self):
        for start, end, operation in (
            ("pub send_blocking(T value): void", "pub complete_blocking(): void", "self.send_admitted(value)"),
            ("pub complete_blocking(): void", "end", "self.complete_admitted()"),
        ):
            section = self.sender.split(start, 1)[1].split(end, 1)[0]
            acquired = section.index("readch self.delivery_credit")
            submitted = section.index(operation)
            settled = section.index("await delivery")
            released = section.index("writech self.delivery_credit, credit")
            self.assertTrue(acquired < submitted < settled < released)

    def test_sender_has_three_guarded_admission_turns(self):
        self.assertEqual(self.sender.count("readch self.admission"), 3)
        self.assertEqual(self.sender.count("writech self.admission, permit"), 3)

        # Await is required in the public *_blocking methods, but it must
        # never occur while the admission permit itself is held. A capacity-0
        # channel needs the consumer to run before settlement.
        windows = re.findall(
            r"readch self\.admission;([\s\S]*?)writech self\.admission, permit;",
            self.sender,
        )
        self.assertEqual(len(windows), 3)
        for section in windows:
            self.assertNotRegex(section, r"\bawait\b")


if __name__ == "__main__":
    unittest.main()
