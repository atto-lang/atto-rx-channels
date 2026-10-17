"""Source-free credit-stream protocol model. NOT Oreslang execution evidence.

Run: python3 -m unittest tests/test_credit_stream_reference_model.py -v
This checks invariant logic only. It cannot certify Channel, select, Future,
ownership, native image or any compiler.
"""
import itertools
import unittest
from collections import deque


class Rejected(Exception):
    pass


class CreditStreamModel:
    def __init__(self, capacity):
        if type(capacity) is not int or capacity < 0:
            raise ValueError("capacity")
        self.capacity = capacity
        self.read_claimed = False
        self.requested = False
        self.credit = False
        self.pending = None
        self.buffer = deque()
        self.claim = None
        self.terminal_seen = False
        self.cancelled = False
        self.writer_results = []
        self.events = []

    def subscribe(self):
        if self.read_claimed:
            return False
        self.read_claimed = True
        return True

    def request(self):
        if not self.read_claimed or self.requested or self.cancelled or self.terminal_seen:
            return False
        self.requested = True
        self.credit = True
        self._advance()
        return True

    def write(self, kind, value=None):
        if self.cancelled:
            return False
        if self.claim:
            raise Rejected("send after terminal")
        if self.pending is not None:
            raise Rejected("overlapping write")
        if kind not in ("next", "complete", "error"):
            raise Rejected("invalid event")
        if kind != "next":
            self.claim = kind
        self.pending = (kind, value)
        self._advance()
        return None if self.pending is not None else self.writer_results[-1]

    def _advance(self):
        if self.cancelled or not self.credit or self.pending is None:
            return
        if len(self.buffer) < self.capacity:
            self.buffer.append(self.pending)
            self.pending = None
            self.credit = False
            self.writer_results.append(True)
        # Capacity zero requires the receiver to rendezvous; this model
        # completes the handshake when read() runs, not by buffering.

    def read(self):
        if not self.requested:
            raise Rejected("next_event requires request")
        if self.cancelled:
            self.requested = False
            event = ("cancelled", None)
        elif self.buffer:
            self.requested = False
            event = self.buffer.popleft()
        elif self.credit and self.pending is not None:
            self.requested = False
            self.credit = False
            event = self.pending
            self.pending = None
            self.writer_results.append(True)
        else:
            return None  # Would suspend, never a false terminal.
        self.events.append(event)
        if event[0] in ("complete", "error"):
            self.terminal_seen = True
        return event

    def cancel(self):
        if self.cancelled or self.terminal_seen:
            return False
        self.cancelled = True
        self.credit = False
        if self.pending is not None:
            self.pending = None
            self.writer_results.append(False)
        return True


def canonical_signal(event):
    """Map the abstract event to Result<Option<T>, Option<E>> shape."""
    kind, value = event
    if kind == "next":
        return ("Ok", ("Some", value))
    if kind == "complete":
        return ("Ok", None)
    if kind == "cancelled":
        return ("Err", None)
    if kind == "error":
        return ("Err", ("Some", value))
    raise Rejected("unknown signal")


class CreditProtocolModelTests(unittest.TestCase):
    def test_four_distinct_events_and_nested_sum_data(self):
        for kind, payload in (("next", ("Err", "data")),
                              ("complete", None), ("error", "terminal")):
            m = CreditStreamModel(1)
            self.assertTrue(m.subscribe())
            self.assertTrue(m.request())
            self.assertTrue(m.write(kind, payload))
            self.assertEqual(m.read(), (kind, payload))
        m = CreditStreamModel(0)
        m.subscribe()
        m.request()
        m.cancel()
        self.assertEqual(m.read(), ("cancelled", None))

    def test_canonical_signal_is_four_way_and_preserves_sum_data(self):
        self.assertEqual(canonical_signal(("next", None)),
                         ("Ok", ("Some", None)))
        self.assertEqual(canonical_signal(("next", ("Err", "data"))),
                         ("Ok", ("Some", ("Err", "data"))))
        self.assertEqual(canonical_signal(("complete", None)),
                         ("Ok", None))
        self.assertEqual(canonical_signal(("cancelled", None)),
                         ("Err", None))
        self.assertEqual(canonical_signal(("error", "boom")),
                         ("Err", ("Some", "boom")))
        self.assertEqual(canonical_signal(("error", None)),
                         ("Err", ("Some", None)))
        self.assertNotEqual(canonical_signal(("error", None)),
                            canonical_signal(("cancelled", None)))

    def test_credit_one_and_subscription_one(self):
        m = CreditStreamModel(1)
        self.assertFalse(m.request())
        self.assertTrue(m.subscribe())
        self.assertFalse(m.subscribe())
        self.assertTrue(m.request())
        self.assertFalse(m.request())
        self.assertTrue(m.write("next", 42))
        self.assertEqual(m.read(), ("next", 42))
        self.assertTrue(m.request())

    def test_capacity_zero_rendezvous_and_cancel_pending(self):
        m = CreditStreamModel(0)
        m.subscribe()
        m.request()
        self.assertIsNone(m.write("next", 8))
        self.assertEqual(len(m.buffer), 0)
        self.assertEqual(m.read(), ("next", 8))
        self.assertEqual(m.writer_results, [True])
        m.request()
        self.assertIsNone(m.write("next", 9))
        self.assertTrue(m.cancel())
        self.assertEqual(m.writer_results[-1], False)
        self.assertEqual(m.read(), ("cancelled", None))

    def test_complete_requires_credit_and_cannot_overtake_value(self):
        m = CreditStreamModel(1)
        m.subscribe()
        m.request()
        self.assertTrue(m.write("next", 5))
        # Terminal is allowed to wait for the NEXT event's following credit,
        # but must not overtake the accepted buffered value.
        self.assertIsNone(m.write("complete"))
        self.assertEqual(m.read(), ("next", 5))
        self.assertTrue(m.request())
        self.assertEqual(m.read(), ("complete", None))
        self.assertFalse(m.request())
        self.assertFalse(m.cancel())

    def test_failed_or_cancelled_writer_not_replayed(self):
        m = CreditStreamModel(0)
        m.subscribe()
        self.assertIsNone(m.write("next", 5))
        self.assertTrue(m.cancel())
        self.assertEqual(m.writer_results, [False])
        self.assertFalse(m.request())
        self.assertFalse(m.write("next", 6))

    def test_bounded_state_all_small_histories(self):
        actions = ("subscribe", "request", "next", "complete", "error", "read", "cancel")
        total = 0
        for capacity in (0, 1, 2):
            for steps in itertools.product(actions, repeat=5):
                total += 1
                m = CreditStreamModel(capacity)
                for action in steps:
                    try:
                        if action == "subscribe":
                            m.subscribe()
                        elif action == "request":
                            m.request()
                        elif action in ("next", "complete", "error"):
                            m.write(action, 17)
                        elif action == "read":
                            if m.requested:
                                m.read()
                        else:
                            m.cancel()
                    except Rejected:
                        pass
                    self.assertLessEqual(len(m.buffer), capacity)
                    self.assertTrue(m.pending is None or
                                    isinstance(m.pending, tuple))
                    terminals = [i for i, x in enumerate(m.events)
                                 if x[0] in ("complete", "error", "cancelled")]
                    self.assertLessEqual(len(terminals), 1)
                    if terminals:
                        self.assertTrue(all(x[0] != "next" for
                                            x in m.events[terminals[0] + 1:]))
        self.assertEqual(total, 3 * (7 ** 5))


if __name__ == "__main__":
    unittest.main()
