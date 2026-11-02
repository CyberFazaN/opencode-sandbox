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

Press `?` again, Esc, or Close to dismiss Keys. Manager Settings (`g`, the Preferences button)
includes **Copy selected text**, off by default. Completed selections in displayed text and
read-only reports are copied once; editable/password fields keep normal editing behavior.
Available local Linux clipboard tools are used without installing anything. Otherwise the
terminal receives an OSC 52 request: the notification says acceptance is unverified because
terminals and multiplexers can reject it. Without a usable system clipboard, the application
retains its local copy buffer and reports the limitation; use your terminal's manual copy action.

The read-only Agent Context preview is titled **Agent Context — NAME**. If container inspection
fails, it shows the reason and previews the configured settings with unknown base OS provenance.
In that fallback, saved guidance is **not verified**, not assumed outdated. Opening the preview
does not rewrite the saved file or start the environment; guidance is regenerated before every
OpenCode launch. Agent Context, Updates Details, readiness and cleanup-result reports are scrollable;
use Tab to reach Close, or Esc to return to the dashboard.

## Updates

`v` opens **Updates**, with three tabs: **Manager**, **Base Images** and **Environments**.
Press `1`, `2` or `3` to change views; use Up/Down to select an item, `c` for **Check**, `C`
for **Check All**, `d` or Enter for **Details**, and Esc to close. Tab reaches buttons. Close
cancels owned checks and rejects late results, but temporary-start cleanup still completes.
Selection survives view changes; returning from Details restores the previous focus.

Opening Updates does **not** trigger npm/GitHub discovery, execute OpenCode, start an environment or run
an image helper. Installed manager/local metadata and cached evidence appear first; bounded
Docker inspections arrive independently. Saved environment status is not treated as actual
container state. Before identity can be inspected, history is explicitly unverified; stopped
environments show dated last verification or Unknown, never their base's build label as proof.

In either OpenCode view, Check queries npm availability once and inspects the selected installed
binary; Check All inspects all listed eligible objects. Overlapping requests are not duplicated.
A running environment stays running. An existing stopped environment is temporarily started,
inspected and stopped again; no interactive launch, integration provisioning or configuration
refresh occurs. Single Check needs no confirmation. Check All confirms its fixed target set if
any environment is stopped; changed identities/state require a new review. Missing containers
are not created. Owned base images use bounded helper probes, never labels as runtime proof.
Source and installed-version results/errors remain separate; a failed npm request does not
discard successful local checks or imply "up to date". Manual/Pinned allow requested comparisons.

Details discloses complete identities, observation source/time, provenance, definition revision,
errors and pending recovery, plus existing CLI guidance. Base OS/package freshness is not
assessed, and changing a base never migrates existing environments. Dashboard notices remain
owned by the dashboard but are shown as a compact notice count and full text in Updates Details,
instead of toasts covering the small-terminal controls.

**Optional daily discovery** defaults off. Preferences (`g`) → **Daily metadata discovery
(dashboard only)** enables independent GitHub/npm checks while the dashboard runs, with no service
or unsolicited short-CLI requests. Startup, saved preferences and a minute timer consider work;
each source persists at most one automatic attempt per 24 hours, failures/interruption included.
Restarting does not reset it. Explicit Check may run sooner but respects Retry-After/rate-reset;
overlapping callers in one data directory share results/failures. Canceling a waiter cannot cancel
another caller's request.

**Updates (N)** counts qualified Notify environments plus a newer manager release without probing
Docker. Manual/Pinned/Unknown/pending-recovery environments do not yield unsolicited counts, but
explicit comparisons remain available. Tooltip/Details qualify dated evidence; no availability
toast overwrites operation status. The indicator is not fresh runtime proof or install permission.

Disabling cancels owned automatic work and hides its indicator, not manual Updates. Unsafe storage
disables automatic requests with a reason in Details; manual bounded requests may work without
persistent coordination/throttling. Clearing cache resets discovery history, not installations or
recovery journals. Automatic discovery never starts containers or probes binaries/images.

### Manager release and installation checks

In **Manager** (`1`), opening shows the running version, cached release evidence and an
independent local installation inspection. **Check** queries published full releases from the
official GitHub repository and repeats that inspection. No GitHub login/token is needed or sent;
drafts, prereleases, invalid tags and unpublished checkouts are not release targets. Tags must be
exactly `vX.Y.Z`; numeric comparison never offers an implicit downgrade. The unchanged development
version is not treated as a new release. A missing/failed GitHub response means availability is
unknown (or dated cached evidence), not current; local inspection failures do not erase release
information or the installed version. GitHub Retry-After and reported rate-limit reset times also
apply to explicit Check. A full 100-entry page is refused rather than claiming a truncated latest
release; use the official release page manually in that case.

Local inspection reconciles package/source/pipx/interpreter/launcher/PATH records without running
pipx or changing files. **Verified official-tag pipx** means those local records agree, not public
source authentication, install permission or guaranteed rollback. Unsupported/custom/foreign/
shadowed installations need manual review; sensitive option values are never displayed and foreign
launchers are not taken over. Details shows source, time, bounded notes and the refusal reason.

When a newer version exists, Update remains available even if automatic updating is unsupported.
The manual-update dialog explains the reason. Only freshly verified official-tag pipx ownership
and settings produce an exact-tag command preserving Python and recognized locations. Confirm
copies that command and closes the dialog; it does not install anything. Other installation
methods receive guidance without an unsafe generic replacement command.

For a supported install and newer target, **Update** (`u`) prepares fresh exact source/tool/impact
review. Cancel is focused first; read it, accept the public-default policy and choose **Update &
close**. Finish active operations/sessions first. An independent helper waits for actual process
exit/exclusion, replaces the exact tag and verifies the installed result. No automatic restart,
Python switch, image rebuild or environment migration. **Wait for its final result** before reopening.

Follow [manager update and recovery](install.md#explicit-reviewed-manager-update) for supported
pipx/settings, host-code execution, private durable records and hard-interruption limits. Failed
verification blocks startup after helper death too; the frozen recovery command only verifies,
and any previous-tag reinstall is a separate manual action, not a guaranteed backup.

### Environment actions

In **Environments** (`3`), use **F5 Start**, **F6 Stop**, **Update** (`u`), **Policy** (`p`),
**Rollback** (`r`) or **Recover** (`e`). Actions request a review, not permission inferred
from cached versions, availability or readiness. Target selection and live eligibility checks
run off the UI thread. The scrollable confirmation shows the exact operation and identities;
Cancel is focused first. Changed metadata, policy, container or checkpoint requires a new review.

- **Start** is explicit, may create a container, and **leaves it running**. Use Check afterward
  for fresh binary verification. Normal pin, direct
  workspace, profile, ownership and pending-operation checks remain in force.
- **Stop** honors Manager Settings' stop-confirmation preference and preserves home/workspace.
- **Update** resolves an exact compatible target before consent and requires an owned,
  network-enabled container and matching pin. A running target gets **Caution** consent: it will
  be stopped and **will not restart afterward**, on success or rollback. After stopping, the
  update checkpoints the full system layer, temporarily
  starts for installation/verification and finishes stopped; failure restores that checkpoint.
  An identical target verifies without reinstalling. No implicit network/policy change.
- **Policy** changes Notify/Manual/Pinned and an exact pin only after separate confirmation.
  It installs nothing and does not bypass update, rollback or first-creation restrictions.
- **Rollback** restores the **entire system layer**, snapshotting the present layer first.
  Require a stopped container/retained image and compatible pin; explicitly Start afterward.
- **Recover** reviews an interrupted OpenCode update and invokes the existing checkpoint
  recovery handler. It never guesses whether npm finished. It may stop/remove the owned incomplete
  container, discarding unfinished update-layer changes; explicit Start is required afterward.
  Other journals route to **Recovery Center**, which handles OpenCode/configuration recovery
  and names the CLI next steps for other journals. Full errors remain scrollable at 80x24.

Home/workspace/user configuration are preserved, **not rolled back**; binary rollback cannot undo
application-data changes. Missing checkpoints/failures retain journals and guidance. A successor
container-recreation failure needs `opencode-sandbox config recover NAME`, not another OpenCode
update-recover. Details reads authoritative journals independently of delayed Docker inventory.
Full version/data-boundary rules: [OpenCode versions](opencode.md#versions).

Temporary checks retain the environment lock through restoration and target immutable container
IDs. A separate guardian also restores stopped state after manager death. Failed/unconfirmed
restoration is an error, not a successful check; inspect actual state and use F6 or the indicated
`stop` command. A manager-owned `version-check.json` beside metadata retains unresolved cleanup
evidence; explicit successful Stop reconciles it. Already-running environments are never stopped
by a version check. External Docker commands do not honor manager lifecycle locks.

Closing Updates does not cancel an approved operation: it is owned by the dashboard, which
refuses conflicting operations and normal Quit until it finishes. If the manager is killed, use
the saved journal and indicated recovery command. Notifications remain owned by the dashboard but
do not cover operation forms or Updates Details at 80x24.

### Base image actions

In **Base Images** (`2`), **Build/Rebuild** (`b` or `u`) opens the target/mode form; **Rollback**
(`r`) reviews managed rollback copies. Check remains a read-only binary/registry check, never a
build, pull or package-freshness assessment. Opening the view still inspects only local metadata.

Choose an exact compatible target or let latest resolve before consent. **Cached rebuild** reuses
eligible layers; **Refresh & Rebuild** explicitly pulls/bypasses cache with extra network/time/disk,
never pruning it, and includes system-package upgrades. **Update system packages** with a cached
build forces the package layer to run with fresh indexes and upgrades without forcing an upstream
image pull. Debian uses `apt-get update` plus `apt-get upgrade`; fresh Arch package layers always
use `pacman -Syu` to avoid unsupported partial upgrades, even when not forcing a cache refresh.
An unchecked cached build may reuse old package layers. Neither certifies package freshness/security
or reproducibility. Cancel-first
consent names distribution/definition/target/current image/mode; unknown ownership or changed
identities refuse. The verified immutable candidate is published only after live revalidation.
The dashboard keeps a rollback copy on replacement; identical verified results make no extra copy.

Rollback groups aliases of one immutable image. A single distinct copy proceeds to consent;
several need explicit selection, **never a default newest copy**. Review full IDs/aliases/provenance.
The current manager's OS/tool/binary verification must pass, and the replaced base is retained.
Old-definition copies can be listed yet fail verification: this is not an OS downgrade mechanism.

Approved work belongs to the dashboard, not this screen. Closing cannot cancel a build
or rollback, conflicting operations and normal Quit refuse while it runs, and reopening Updates
retains the phase/result. Details includes a bounded tail of build output; output never writes
directly over Textual. No invented percentage or short build timeout. After process death, inspect
the actual base/copies and any named candidate; there is no new base recovery journal.

Existing containers/writable layers, their pins, home/workspace/configuration and integrations do
not migrate. Future base-based creation and file-only restores use the changed base, with
not-yet-created pins still enforced. The CLI retains both rollback-preserving
`opencode update-base` and deliberately no-copy `build`, each with explicit `--refresh`; see
[base modes and limits](opencode.md#versions).

Manager review/update is independent of these base actions; see
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
