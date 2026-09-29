"""TMA Holdings operating system.

A small, dependency-free engine for running a one-person AI roll-up holdco:

* every client job moves intake -> preparer -> reviewer -> a named human -> client,
* only a human can approve or send (enforced in code, not by convention),
* every human fix is logged, repeated fixes become rules, and every accepted
  rule becomes a regression test built from the original input and the
  accepted output.

Run ``python3 -m holdco demo`` to watch the whole loop work end to end.
"""

__version__ = "0.1.0"
