# 6.1.0 release — working state

Running-effort record (D-045): it holds the release review's findings, decisions and progress
while the 6.1.0 release is prepared, and is **removed from the tree before the release is
tagged**. Current-state facts belong in the top-level records.

## Branch

`release/6.1.0`, based on `main` = tag `v6.0.0`. It contains the 6.1.0 changes (D-047..D-055),
the D-044 correction about the verified installation from GitHub, and this record. Not merged,
not pushed, not tagged.

## Review findings and decisions

An independent review of every change since 6.0.0 found no product defect that blocks the
release. Findings and their state:

| Finding | State |
|---|---|
| Planned 6.0.1 contradicted the declared Semantic Versioning (new functionality, a changed default, a removed installer) | Resolved: 6.1.0 (D-055) |
| Version, CHANGELOG and documents were still pre-release | Resolved on this branch; CHANGELOG dated 2026-10-30 (re-date if published later) |
| Stabilization working records in the release tree | Resolved: condensed into the top-level records (D-055) |
| Four of the six required CI check names of the `main` ruleset no longer exist after the matrix change | Open, owner: update the ruleset before the release pull request (RELEASING step 3.1) |
| Host-process signal tests count every watchdog on the host and assume a default SIGINT disposition | Open, TODO "Optional Polish"; run suites serially in the foreground (RELEASING) |
| `status NAME` omits the distribution line without Docker; one deadline path is reported as a CLI failure | Open, TODO "Optional Polish"; no release change |

Owner decisions (2026-10-30): version 6.1.0; status stays Beta; stabilization records condensed
into the top-level records.

## Verification of this branch (2026-10-30)

Fresh venvs (Python 3.11.18 and 3.14.8): four serial suites 969 passed / 56 opt-in skips each
(current and lowest direct dependencies); Ruff, actionlint, offline zizmor clean; both-endpoint
sdist/wheel, strict twine, `check_dist.py`, `release_check.py v6.1.0`; `git+file` pipx
installation on both endpoints with `pipx_smoke.sh`, 27-file byte comparison and real read-only
`doctor` exit 0; scoped real Docker `test_20`, `test_35` and `test_65`: 4 tests, 66 checks,
0 failed, nothing left behind. Details: BASELINE ("6.1.0 release tree").

## Next

1. **I04**: the full real campaign on this branch through an installed pipx manager, both base
   images built under a test-only namespace (RELEASING "Verify"), the retained Debian 12 row
   with the published `v6.0.0` installed separately as `OCS_TEST_LEGACY_MANAGER`. The
   privileged rows and C10 (`ocs-test-act-*` units, renamed and not yet rerun) need the owner's
   renewed consent.
2. **I06**: release decision from CAMPAIGN; then the owner updates the ruleset, re-dates the
   CHANGELOG if needed, and this directory is removed before the release commit is tagged.
3. No push, tag, release or upload without explicit authorization.
