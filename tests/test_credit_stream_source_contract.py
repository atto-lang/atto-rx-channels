"""Source-shape guardrails for the credit-gated typed stream candidate.

Host-only checks. They do not execute Oreslang or prove scheduler races.
"""
from pathlib import Path
import re
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "src" / "credit_stream.ores"


class CreditStreamSourceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SOURCE.read_text(encoding="utf-8")
        cls.pipe = cls.text.split("define pub class CreditPipe<T, E> as", 1)[1].split(
            "pub fnc credit_pipe<T, E>", 1
        )[0]

    def test_every_marker_probe_is_inside_state_gate(self):
        windows = re.findall(
            r"writech self\.state_busy, true;([\s\S]*?)try readch self\.state_busy;",
            self.pipe,
        )
        total_calls = self.pipe.count("credit_marked(self.")
        guarded_calls = sum(window.count("credit_marked(self.") for window in windows)
        self.assertGreater(total_calls, 0)
        self.assertEqual(total_calls, guarded_calls)
        for window in windows:
            self.assertNotIn("await ", window)
            self.assertNotIn("nb select", window)

    def test_public_signal_is_closed_four_way_sum(self):
        self.assertIn(
            "pub next_signal(): Result<Option<T>, Option<E>>", self.pipe
        )
        self.assertIn("return Err(None);", self.pipe)
        self.assertIn("return Err(Some(error));", self.pipe)
        self.assertIn("return Ok(value);", self.pipe)

    def test_cancellation_preserves_outstanding_request_until_observed(self):
        cancel = self.pipe.split("pub cancel(): bool", 1)[1].split(
            "pub is_cancelled(): bool", 1
        )[0]
        self.assertIn("try readch self.demand;", cancel)
        self.assertIn("try readch self.writing;", cancel)
        self.assertNotIn("try readch self.requested;", cancel)
        self.assertIn("try writech self.stop_reader, true;", cancel)
        self.assertIn("try writech self.stop_writer, true;", cancel)

    def test_failure_publication_uses_real_frame_type(self):
        fail = self.pipe.split(
            "pub fail(E error): Future<Option<SelectResult>>", 1
        )[1].split("pub cancel(): bool", 1)[0]
        self.assertIn("val Result<Option<T>, E> payload = Err(error);", fail)
        self.assertIn("return self.publish(payload, true);", fail)
        self.assertNotIn("CreditFrame", self.text)

    def test_select_control_arm_has_priority(self):
        self.assertIn(
            "SelectCase.read(self.stop_reader),\n        SelectCase.read(self.frames)",
            self.pipe,
        )
        self.assertIn(
            "SelectCase.read(self.stop_writer),\n      SelectCase.write(self.frames, frame)",
            self.pipe,
        )


if __name__ == "__main__":
    unittest.main()
