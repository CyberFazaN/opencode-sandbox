# The dashboard

```sh
opencode-sandbox        # in a terminal, without arguments
opencode-sandbox tui
```

![The dashboard with four environments; the selected one is a running project](images/dashboard.svg)

The dashboard is usable at 80x24 and larger. Focus starts on the environment table. The top row
of buttons acts on the manager as a whole, the bottom rows on the selected environment. The
details pane shows the selected environment's state, workspace, distribution, provider profile,
settings, last readiness result and last error.

The distribution family is shown without guessing an OS version from the current base
definition. Use `status NAME` for inspected base-image provenance; new-environment choices
name the current build definitions, not an assertion that an existing container uses them.

At start the dashboard checks the Docker daemon in the background. A slow
daemon gets up to 10 seconds with a waiting notice, not a premature failure. Navigation and
quit remain available; `r` retries prerequisites and clears their old warning on success.
Automatic metadata refresh stays Docker-free. OpenCode/Shell readiness runs before suspending
the dashboard, and Agent Context observation runs in a worker. When Docker is not usable, the
status line says "Docker is not ready" and a notification gives the reason; the dashboard stays
usable for everything that does not need Docker. `opencode-sandbox doctor` shows the details.

After the daemon is verified, the same worker checks managed base-image revisions. A
"Base images need attention" notice uses the same results and commands as `doctor`. It is
advisory, not a request to replace an existing environment, and never rebuilds an image.
Press `r` for fresh dashboard results after changing images, or rerun `doctor`;
[maintenance.md](maintenance.md#base-image-definitions) explains the cases.

The same worker also reports [resource-limit support](maintenance.md#resource-limit-support).
Missing support or unavailable evidence gets an advisory notice, not an identity failure or
an automatic host repair. CPU/memory/PID capability reports do not prove kernel enforcement.

Refresh replaces each checked category's old notice rather than stacking repeated warnings.
Success clears that category; an unavailable check replaces its old warning with an unverified
result, not a claim that the problem is fixed. A category skipped because Docker is unavailable
is not marked successful. Clearing one category leaves other notices intact and reveals any
remaining advisory in the status line. New advisories do not overwrite active operation progress;
clearing advisories or readiness waits does not erase an operation's completion/recovery result.
Metadata-only refresh does not recheck or clear these advisories.

## Keys

| Key | Action | Key | Action |
|---|---|---|---|
| `Enter` / `o` | OpenCode (`run`) | `s` | Shell (`shell`) |
| `F5` / `F6` | Start / Stop | `x` | Delete (confirmation) |
| `n` | New environment (`create`; distribution, workspace mode, provider profile and integrations under "More options") | `c` | Create a project from the current folder (the confirmation shows what is copied) |
| `/` | Filter | `r` | Refresh |
| `t` | Settings (`config apply`; shows the change plan first) | `u` | Usage (`container usage`) |
| `i` | Check (`check NAME`; the details pane shows the last result) | `a` | Agent Context preview |
| `d` | Changes (`changes show`, `bundle`, `stage`, `branch-diff`) | `e` / `b` | Export changes (`changes export`) / Backup (`backup create`, stopped environment) |
| `R` | Repair | `k` | Promote a quick session to a scratch environment (`promote`) |
| `B` | Backups (`backup list`, `backup restore`) | `v` | Updates (local/cached inventory; explicit version Check) |
| `p` / `g` | Provider profiles / dashboard preferences | `F8` | Recovery Center (interrupted operations and the command that finishes each) |
| `D` | Disk (`disk usage` / `disk cleanup`; removal only after a confirmation listing every object) | `?` | All keys |
| `Esc` | Close a dialog or screen | `q` | Quit |

Dialogs default to Cancel. Dashboard keys are inactive while a sub-screen is open. Promotion to a
project, `backup restore-check`, `backup restore-rollback` and custom images are only available
in the CLI.

The read-only Agent Context preview is titled **Agent Context — NAME**. If container inspection
fails, it shows the reason and previews the configured settings with unknown base OS provenance.
In that fallback, saved guidance is **not verified**, not assumed outdated. Opening the preview
does not rewrite the saved file or start the environment; guidance is regenerated before every
OpenCode launch. Agent Context, Updates Details, readiness and cleanup-result reports are scrollable;
use Tab to reach Close, or Esc to return to the dashboard.

## Updates

`v` opens **Updates**, with three compact views: **Sandbox Manager**, **Base Images** and
**Environment OpenCode**. Press `1`, `2` or `3` to change views; use Up/Down to select an item,
`c` for **Check**, `d` or Enter for **Details**, and Esc to close. Tab reaches the primary
buttons; **Cancel check** cancels this screen's read-only checks, not an installation or another
dashboard operation. Close cancels owned checks and rejects late results. Selection survives
view changes, and returning from Details restores focus to the inventory.

Opening Updates does **not** trigger npm/GitHub discovery, execute OpenCode, start an environment or run
an image helper. Installed manager/local metadata and cached evidence appear first; bounded
Docker inspections arrive independently. Saved environment status is not treated as actual
container state. Before identity can be inspected, history is explicitly unverified; stopped
environments show dated last verification or Unknown, never their base's build label as proof.

In either OpenCode view, Check queries npm for the latest supported stable release and checks
only the selected object. A running environment gets a bounded runtime probe; a stopped one
is **not** started. An owned base image gets an explicit bounded helper probe; its build label
alone is not a runtime verification. The two views share discovery, including dated cached
success after a failed request. Source/row errors and progress remain independent. A missing
registry result means availability unknown, not "up to date"; Manual/Pinned still allow requested
comparisons without changing policy or authorizing execution.

Details discloses complete identities, observation source/time, provenance, definition revision,
errors and pending recovery, plus existing CLI guidance. Base OS/package freshness is not
assessed, and changing a base never migrates existing environments. Dashboard notices remain
owned by the dashboard but are shown as a compact notice count and full text in Updates Details,
instead of toasts covering the small-terminal controls.

**Optional daily discovery** is off by default. In Preferences (`g`), enable **Daily metadata
discovery (dashboard only)** to check GitHub manager releases and npm independently while the
dashboard runs. The dashboard considers
discovery at startup, after saving Preferences and about once a minute, but attempts each source
at most once per 24 hours, including failures and interrupted requests. It persists a claim
before contacting the source; restarting does not reset that attempt. No background service is
installed, and short CLI commands do not start unsolicited discovery. Each source has its own
worker, claim, errors and rate limits; a failed/slow source does not block the other's result.

Explicit Check may refresh sooner, but overlapping dashboard/Updates/CLI requests for the same
source and data directory share the attempt's result or failure. Both explicit and automatic
checks respect numeric/date Retry-After, even pauses longer than 24 hours. Canceling a waiting
screen does not cancel another caller's request. An interrupted request retains an incomplete
attempt rather than inventing success; explicit Check can retry when rate limits permit.

With discovery enabled, a single **Updates (N)** button indicator counts Notify-policy
environments whose dated last verification is older than the discovered release, plus one for a
newer published manager release. It does not
probe Docker to calculate that count. Unknown versions, Manual/Pinned policies and pending
recovery do not generate general newer-version indicators. Explicit comparisons remain available
for all policies. The indicator is not a fresh runtime verification or install permission; its
tooltip/Details qualify cached discovery, including stale success after failure. It never creates
per-environment or repeated availability toasts, and never overwrites operation status.

Automatic discovery never starts containers or runs runtime/image probes. Disabling the preference
cancels owned automatic work and hides unsolicited availability; manual Updates remains usable.
If private scheduling storage is unsafe/unwritable, automatic checks fail closed and explain why
in Updates Details. Explicit checks can still use the bounded network path without persistence;
cross-process coalescing/throttling cannot be guaranteed without that storage. Clearing the
disposable cache resets discovery history/throttles, not installed software or recovery journals.

### Manager release and installation checks

In **Sandbox Manager** (`1`), opening shows the running version, cached release evidence and an
independent local installation inspection. **Check** queries published full releases from the
official GitHub repository and repeats that inspection. No GitHub login/token is needed or sent;
drafts, prereleases, invalid tags and unpublished checkouts are not release targets. Tags must be
exactly `vX.Y.Z`; numeric comparison never offers an implicit downgrade. The unchanged development
version is not treated as a new release. A missing/failed GitHub response means availability is
unknown (or dated cached evidence), not current; local inspection failures do not erase release
information or the installed version. GitHub Retry-After and reported rate-limit reset times also
apply to explicit Check. A full 100-entry page is refused rather than claiming a truncated latest
release; use the official release page manually in that case.

Installation inspection does not run pipx, import its internals, rewrite metadata or change Python.
It reconciles the actual running package/distribution/version, PEP 610 VCS URL/tag/commit, pipx
metadata, venv/source interpreter, application executable, exposed symlink, invocation and PATH.
Explicit custom pipx locations and pip's normal long/space-path launcher wrapper are recognized.
Only recognized metadata with default installation options is classified as **verified official-tag
pipx**. Custom options, injections, pins, suffixes, unknown settings/formats, editable/foreign
sources and missing/shadowed/ambiguous launchers require manual review; values of unsupported
options are not printed because they can contain secrets. Nothing takes over a foreign launcher.

This label means local provenance records agree, **not** authenticated public tag-to-commit
identity, an execution grant, preserved dependency versions or a promise of rollback. Details
shows the inspection time, source/commit/paths, release URL/notes (bounded plain text), unsupported
reason and [manual installation guidance](install.md#upgrade-or-change-the-version).
**Manager Update remains unavailable**, including for recognized installations. Early shared
[startup coordination](install.md#startup-coordination) is implemented; independent helper,
fresh-verification access, terminal handoff and replacement/recovery gates are still pending.
There is no installer, Python switch, automatic restart or universal Update All operation here.

### Environment actions

In **Environment OpenCode** (`3`), use **Start** (`s`), **Update** (`u`), **Policy** (`p`),
**Rollback** (`r`) or **Recover** (`e`). These buttons request a review, not permission inferred
from cached versions, availability or readiness. Target selection and live eligibility checks
run off the UI thread. The scrollable confirmation shows the exact operation and identities;
Cancel is focused first. Changed metadata, policy, container or checkpoint requires a new review.

- **Start** is explicit, may create a container, and **leaves it running**. Use Check afterward
  for fresh binary verification. It does not temporarily start/probe/stop. Normal pin, direct
  workspace, profile, ownership and pending-operation checks remain in force.
- **Update** accepts an exact compatible 2.x target or resolves the latest supported stable
  release to an exact version **before consent**. It requires an existing stopped, owned,
  network-enabled container. It never stops a running environment or changes network/policy for
  you. A full system-layer checkpoint is committed first; the container starts temporarily for
  npm installation and binary verification, then finishes stopped. Failure restores the checkpoint;
  success keeps it for explicit rollback. An already-installed exact version is verified without
  reinstalling. Pins still restrict the target; there is no silent target substitution.
- **Policy** changes Notify/Manual/Pinned and an exact pin only after separate confirmation.
  It installs nothing and does not bypass update, rollback or first-creation restrictions.
- **Rollback** restores the **entire checkpointed system layer**, not just the OpenCode binary.
  The present layer, including later system changes, is preserved as a snapshot first. It requires
  a stopped container (or a retained derived image) and compatible pin. No running replacement
  is started; explicitly Start afterward.
- **Recover** reviews an interrupted OpenCode update and invokes the existing checkpoint
  recovery handler. It never guesses whether npm finished. It may stop/remove the owned incomplete
  container, discarding unfinished update-layer changes; explicit Start is required afterward.
  Other journals route to the existing **Recovery Center**, preselecting the environment. Its
  **Recover selected** button handles OpenCode or configuration recovery as appropriate; other
  operation types retain their specific CLI next steps. The read-only scrollable result pane
  retains full recovery errors and guidance without pushing the controls off-screen.

Home, workspace and user OpenCode configuration are preserved, **not rolled back**. Binary rollback
cannot undo application-data changes or guarantee backward compatibility. Missing checkpoints and
failed recovery retain the journal/reason and name safe next steps. If recovery has progressed to
container recreation, the next action is `opencode-sandbox config recover NAME`, not another
OpenCode update-recover. Details rereads authoritative local journal metadata, even while Docker
inventory is still refreshing, and leads with operation results/recovery guidance.

**Cancel check** cancels read-only checks and operation-plan preparation, not an approved mutation.
Closing Updates also does not cancel an approved operation: it is owned by the dashboard, which
refuses conflicting operations and normal Quit until it finishes. If the manager is killed, use
the saved journal and indicated recovery command. Notifications remain owned by the dashboard but
do not cover operation forms or Updates Details at 80x24.

### Base image actions

In **Base Images** (`2`), **Build/Rebuild** (`b` or `u`) opens the target/mode form; **Rollback**
(`r`) reviews managed rollback copies. Check remains a read-only binary/registry check, never a
build, pull or package-freshness assessment. Opening the view still inspects only local metadata.

Build defaults to the latest supported stable OpenCode target, resolved to an exact version before
consent; an explicit compatible alternative is allowed. Choose **Cached rebuild** to reuse eligible
layers, or **Refresh & Rebuild** to pull current upstream inputs and bypass build cache. Refresh is
explicit, costs additional network/time/disk and never prunes the shared cache. Neither mode is
an OS/package security certification or reproducibility claim. The scrollable Cancel-first consent
names the distribution, definition, exact target, current image (or missing first build) and mode.
Unknown/unmanaged provenance is not permission to overwrite an image; the live handler refuses it.
Old/newer definitions remain distinct and visible, not inferred to be current from their tag.

The existing candidate handler verifies the immutable candidate's OS/tools/OpenCode, then rechecks
the consented current image and build definition/mode under shared guards before publishing. The
dashboard always preserves the replaced image as a rollback copy; an identical verified result is
reported unchanged without making a redundant copy. Changed/unconfirmed candidate identities are
left untouched with review guidance, not published or deleted based on a familiar name.

Rollback consolidates aliases of the same immutable image. A single distinct copy can go straight
to consent; multiple copies require an explicit selection in the copy form, **not** a default
newest image. Full IDs, aliases, definition and embedded-version labels are scrollable. The copy
must pass the current manager's OS/tool/OpenCode checks, and both it and the current base are
revalidated before swap. The replaced current image is kept so you can swap back. Old definition
copies remain listed but may fail verification; there is no implicit base OS downgrade.

Approved work belongs to the dashboard, not this screen. Close/Cancel check cannot cancel a build
or rollback, conflicting operations and normal Quit refuse while it runs, and reopening Updates
retains the phase/result. Details includes a bounded tail of build output; output never writes
directly over Textual. No invented percentage or short build timeout. After process death, inspect
the actual base/copies and any named candidate; there is no new base recovery journal.

Existing containers/writable layers, their pins, home/workspace/configuration and integrations do
not migrate. Future base-based creation and file-only restores use the changed base, with
not-yet-created pins still enforced. The CLI retains both rollback-preserving
`opencode update-base` and deliberately no-copy `build`, each with explicit `--refresh`; see
[base modes and limits](opencode.md#versions).

Manager installation remains unavailable; read-only release/installation checks are described
[above](#manager-release-and-installation-checks). No Update All, automatic installation or
background service is added.

## State

The State column is the manager's recorded state. The list updates within about 2 seconds after
the CLI changes environment metadata. A container stopped outside the manager (a plain
`docker stop`, an out-of-memory kill) still shows `running` until Repair (`R`) or the next start
or stop reconciles it.

Leaving OpenCode or a shell returns to the dashboard. Closing the terminal, or killing the
dashboard, hangs up the session inside the container
([concepts.md](concepts.md#where-things-live)).
