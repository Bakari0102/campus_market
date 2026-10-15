# Campus Market (CSE 720 coursework)

**Business model: B2C.** Verified campus businesses sell products (with stock quantities) to students.
Students can browse, compare prices and order; they cannot list products.

Business onboarding: a business registers (Register -> "I am a business") -> an admin checks its CAC
record -> `python manage.py verify-vendor business@example.com` -> it can now add products.
`python manage.py pending-vendors` lists businesses waiting for verification.

NOTE: the database schema changed for B2C. Delete any old `campus_market.db` before the first run.

Run the app:   `pip install -r requirements.txt && python main.py`
Run the tests: `pytest -v`

Layers: `main.py` (UI) -> `services/` (logic) -> `data/` (repositories + SQLite).
Optional: `CAMPUS_EMAIL_DOMAIN=student.youruni.edu.ng` restricts sign-up to campus emails.
Online-store prices are MOCK data (see services/price_search.py).

## Accessibility (WCAG 2.2 Level AA)
Automated: `pytest tests/test_accessibility.py` (contrast of every palette pair, both modes).
Debug the semantics tree: `FLET_A11Y_DEBUG=1 python main.py`.

Manual checks (record results in the report):
- [ ] Screen reader (TalkBack on Android / VoiceOver on iOS / NVDA on web): log in, search, post an item
- [ ] Keyboard only (Tab / Shift+Tab / Enter): every action reachable, focus always visible
- [ ] Text size 200% in OS settings: nothing cut off, no horizontal scrolling
- [ ] Colour-blindness simulation: errors and statuses still clear without colour
- [ ] Zoom/reflow at 320 px width
- [ ] Error messages are announced, and say how to fix the problem
- [ ] Tools: Android Accessibility Scanner; Lighthouse/axe on the web build

## Security (minimum standard: OWASP ASVS Level 1, OWASP Top 10:2025)
Implemented: scrypt password hashing, parameterized SQL, login lock-out (5 failures / 15 min),
ISBN + photo-link validation, upload pipeline (size limit, extension allow-list, magic bytes,
ClamAV scan, random filenames), fail-closed behaviour when the scanner is down.

Run ClamAV locally (the first start downloads virus signatures and takes a few minutes):

    docker run -d --name clamav -p 3310:3310 clamav/clamav:stable

Environment variables: `CLAMAV_HOST` (default 127.0.0.1), `CLAMAV_PORT` (default 3310).
Development without ClamAV: `ALLOW_UNSCANNED_UPLOADS=1` (never in production).
Real end-to-end check: upload the standard EICAR test file (from eicar.org) and confirm it is refused.

## Design
Idea: a campus market stall. The one bold element is the highlighter-yellow price tag; the rest is
quiet ink-navy and paper. Type: Hanken Grotesk (SIL Open Font License, bundled in `assets/fonts/`
with its licence file). Colours live in `ui/accessibility.py` (palettes) and are mapped to Flutter
colour roles in `ui/theme.py`, so light and dark mode both work. Reusable pieces are in
`ui/components.py` (product card, badges, price tag, header block, form card, empty state).
To restyle the whole app, change the palette values; `pytest` re-checks every colour pairing.

## Efficiency (measured with `python -m scripts.benchmark 20000`)
Same machine, 20,000 products:

| Operation | Before | After |
|---|---|---|
| Search (typical query) | 22,459 ms | 0.85 ms |
| Browse one page of 20 | 21.2 ms | 0.48 ms |
| Browse one category | 22.0 ms | 0.40 ms |
| Category counts | 12.2 ms | 1.7 ms |
| Reserve + cancel an order | 5.3 ms | 4.2 ms |
| Create a product | 2.4 ms | 2.5 ms (unchanged; now atomic) |
| First search after the catalogue changes | n/a | 157 ms (index rebuild) |
| Test suite | ~9 s | ~4 s |

What changed: an index on product images (the missing index caused a full scan per product, an
O(n^2) join); a cached search index rebuilt only when a database counter says searchable data
changed; paging ("Show more"); WAL mode and lock waiting; one transaction per action; stores are
asked in parallel with a time limit and a 5-minute cache; cover-image checks are remembered;
password hashes store their own cost; CI runs the tests on every push.
Not yet done (recommended next): FTS5 once the catalogue passes ~100k products, Redis for the
login lock-out and caches when running several servers, image thumbnails, background tasks for
slow network calls.

Background work: store-price lookups run off the screen's thread (`page.run_thread`) with a
"Checking online stores..." indicator; a late answer for an old search is discarded.
