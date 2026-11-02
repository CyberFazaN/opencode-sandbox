# Review develop and prepare a release

Use this prompt only for explicit user release intent, including a request to assess whether a
release is warranted. Its existence or discoverability reference does not initiate a release;
a review/preparation request is not permission to publish.

## Authorities

Follow [AGENTS.md](../../AGENTS.md), applicable local instructions, and CONTRIBUTING's
[branch workflow](../../CONTRIBUTING.md#branch-workflow) and
[verification policy](../../CONTRIBUTING.md#verification-policy).
[RELEASING.md](../../docs/engineering/RELEASING.md) owns the release procedure;
[CHANGELOG.md](../../CHANGELOG.md) defines Semantic Versioning and supplies release notes.
Inspect the current [CI](../workflows/ci.yml) and [release](../workflows/release.yml) workflows.
These authorities, not this prompt, define preparation edits, validation, integration and
publication steps. If they conflict with each other or the request, stop and ask for clarification.

## 1. Assess independently, without release changes

- Check branch/worktree status and preserve unrelated work. Inspect current remote refs, published
  releases, tags, pull requests, CI and applicable branch protections using read-only operations.
  Identify the latest published stable release (not a draft, prerelease or merely the highest local
  tag) and the exact `develop` candidate commit. Reconcile the release, tag, `main` and changelog;
  disclose discrepancies, stale refs or unavailable access rather than assuming they agree.
- Review the commits and full diff from that stable tag to the candidate, not just changelog
  entries. Assess user value, incomplete work, open defects, compatibility and upgrade risks,
  including supported Python/dependencies, existing environments/data, images and OpenCode.
  Separate implementation completeness from release readiness; do not silently fix or add work.
- Review candidate-applicable evidence and blockers in
  [CAMPAIGN.md](../../docs/engineering/CAMPAIGN.md), with relevant
  [BASELINE.md](../../docs/engineering/BASELINE.md) and
  [ISSUES.md](../../docs/engineering/ISSUES.md) context. Apply the
  [release rule](../../AGENTS.md#release-rule): historical PASS rows or hosted CI alone do not
  qualify changed code. Identify missing validation, permissions and risks needing owner acceptance.
- Decide whether a release is justified. If not, explain why and stop without preparing one.
  If justified in principle, propose the next manager version `X.Y.Z` with a concise SemVer
  justification tied to the actual changes. Do not conflate the manager version with OpenCode,
  distribution, image revision or schema versions; the manager's source is
  [`__version__`](../../src/opencode_sandbox/__init__.py).

## 2. Mandatory owner approval checkpoint

Present a concise proposal containing:

- The release/no-release decision, stable baseline and candidate commit.
- The proposed version and justification; included scope and explicit exclusions.
- Incomplete work, compatibility concerns, blockers, residual risks and required risk acceptance.
- The validation and release plan under RELEASING, including branch/PR integration and automation
  handoffs. Identify required permissions for tests, pushes, remote PR/merge or ruleset changes,
  maintainer-created tags and GitHub Release publication; distinguish requested from granted steps.

**STOP and explicitly ask: "Do you approve version X.Y.Z and this release plan?" Wait for the
owner's answer before making any release-related changes.** Before that approval, do not create
release branches, edit versions/changelog/release documentation, commit release preparation,
merge, push, tag, change remote settings or publish anything.

Version/plan approval authorizes only the stated scope and explicitly approved operations; it
does not replace the separate permissions required by AGENTS and RELEASING. Ask before any
operation not yet authorized and hand maintainer-only steps to the maintainer. If the proposed
version or release scope changes materially, **STOP and request renewed approval** of the revised
version and plan. Do not silently include newer `develop` commits or unapproved fixes.

## 3. Execute only the approved plan

- Recheck the worktree, candidate commit and granted permissions, then follow RELEASING in order
  for required validation, version/changelog/documentation updates and release evidence. Preserve
  all required gates; stop on failures, unavailable verification or unaccepted blockers. Obtain
  dangerous-test permissions separately; never substitute mocks or old evidence for required proof.
- Use the documented protected release PR and merge-commit integration into `main`, with required
  reviews, resolved discussions and CI gates. Verify the current required-check configuration;
  request authorized maintainer action for stale checks, never bypass or weaken safeguards. Wait
  for the required `main` checks and hand release-tag creation to the maintainer as documented.
- Respect the tag-triggered release automation: wait for its checks and generated draft, review
  that draft and publish only with explicit publication authorization. Inspect existing runs/drafts
  before resuming so no publication step is duplicated. Do not create a competing release or add
  package, image or asset uploads outside the documented distribution model.

## 4. Verify and report

Follow RELEASING's post-publication verification and reviewed reconciliation back into `develop`.
Verify the public release is stable and no longer a draft, its tag targets the approved `main`
merge commit, its version/notes match the released tree, and required workflows succeeded. Perform
the documented clean GitHub-tag pipx smoke test; report its actual version and diagnostic results.
Report the release URL, version, tag/commit, PR and CI results, executed checks, skips/failures,
accepted risks and unfinished handoffs. If publication or any verification is blocked, say exactly
what remains; never claim an unpublished or unverified release succeeded or is production-ready.
