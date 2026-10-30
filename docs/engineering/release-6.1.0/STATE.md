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
| Version, CHANGELOG and documents were still pre-release | Resolved on this branch; the owner confirmed the CHANGELOG date 2026-10-30 |
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

## I04 (2026-10-30)

Owner consent for every row, including the privileged rows and C10, and an owner-provided,
budget-limited OpenRouter key for one real-provider check. Result: **PASS**. The complete
campaign through a pipx installation of a local `v6.1.0` test tag passed 56 tests / 513 checks
with nothing skipped. No-cache builds of both images and the real-provider check (13 checks)
also passed; details are in BASELINE ("6.1.0 release tree"). The first attempt stopped at two
harness setup gaps: pipx was missing from the runner venv, and the volatile runtime unit
directory was absent after a reboot. RELEASING now names both. The key was kept out of every
file and log and deleted after the check. The owner may revoke it.

The user documents no longer say that no real provider was tested. README, `docs/opencode.md`
and `docs/providers.md` name the one tested provider.

## I06 release decision (2026-10-30)

**Verdict: READY WITH ACCEPTED RISKS.**

Basis:
- CAMPAIGN has 84 rows: P0 46/46 PASS, P1 33/33 PASS, P2 4 PASS and D09 PASS in part.
- Every real row's module ran and passed in the I04 release-tree campaign; rows that cited only
  the candidate now cite that rerun.
- The unit, package, pipx, static and pre-tag scan layers (gitleaks git/dir, detect-secrets,
  personal-data search) ran on the release tree; ARCHITECTURE names every module.

Accepted risks, which the owner accepts by publishing:
1. D09: the host reboot is BLOCKED (P2, accepted earlier). Next step: reboot, then `start` and
   `check` on a test environment.
2. Real-Docker evidence exists only on an Arch Linux host (D-046 documents this).
3. One real model provider (OpenRouter `z-ai/glm-5.3-flash` on Debian 13). The automated
   first-prompt rows use a fake provider.
4. The other items under BASELINE "Unverified behaviour": Python 3.12/3.13 separately, other
   pipx versions, the scheduled image build, another user's real rootless dockerd, the Click 9
   lower-bound warning.
5. Retained Debian 12 environments stay on Debian 12 (LTS-only until 2028-06-30). The README
   names the date; the CHANGELOG says that existing containers and system backups keep their
   OS.

Preconditions for publication, which are not risks to accept:
- The owner updates the `main` ruleset's required checks (RELEASING step 3.1).
- The new hosted CI matrix passes on the release pull request (its first run). A failure means
  fix, rerun the affected layers, and decide again.
- This directory is removed before the release commit is tagged.

Non-blocking: TODO "Optional Polish" (signal-test isolation, `status` distribution line, the
deadline message).

## Next

1. Finalization: move the durable evidence into the top-level records, remove this directory,
   rerun the quick checks.
2. Publication steps, each with the owner's explicit permission: ruleset update (owner), push
   and pull request (first hosted CI), merge commit, annotated tag, draft release, owner
   publishes, GitHub pipx smoke, post-release "Unreleased" section.
