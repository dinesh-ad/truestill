"""Values the app's HTTP tests **import**, as opposed to fixtures pytest injects for them.

Split out of ``conftest.py`` deliberately. A conftest is a file pytest discovers and whose
fixtures it supplies by name; importing one by its bare module name works only by accident of
``sys.path`` and breaks the moment two of them are in the same session - which this repo proved
by resolving the app suite's ``from conftest import TOKEN`` against the browser suite's file.
See ``test_shared_test_helpers.py`` for the reproduction and the rule.

So the split is: **fixtures stay in ``conftest.py``, importable values live here**, under a
basename no other test directory claims.
"""

from __future__ import annotations

#: One value for every app test. The app mints a real token per process; tests only need it to
#: be consistent between the server they build and the requests they send.
#:
#: It is importable because several modules put it in a query string (``?token=...``) as well as
#: a header; that is a real second use, not a leak of a fixture's internals.
TOKEN = "test-token"
