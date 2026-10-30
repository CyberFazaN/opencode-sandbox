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

## Next

1. **I06**: the release decision report from CAMPAIGN (READY / READY WITH ACCEPTED RISKS /
   NOT READY). Expected risks: D09 host reboot BLOCKED (P2), the hosted CI matrix not yet run,
   Arch-only real host, one real model provider.
2. Finalization: move the evidence into the top-level records, remove this directory, re-date
   the CHANGELOG if it is published after 2026-10-30, rerun the quick checks.
3. Publication steps, each with the owner's explicit permission: ruleset update (owner), push
   and pull request (first hosted CI), merge commit, annotated tag, draft release, owner
   publishes, GitHub pipx smoke, post-release "Unreleased" section.
