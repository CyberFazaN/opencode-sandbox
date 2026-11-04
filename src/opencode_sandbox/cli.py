"""Typer command-line interface; no-args starts Textual."""
import json
from pathlib import Path

import typer
from typer.core import TyperGroup

from . import core as c
from . import distros, workspaces
from . import workspace_io as wio


class _HelpOrder(TyperGroup):
    """Top-level help: everyday commands first, panels in ORDER (Typer lists groups last)."""
    def list_commands(self, ctx):
        return sorted(self.commands, key=lambda n: ORDER.index(n) if n in ORDER else len(ORDER))

app=typer.Typer(cls=_HelpOrder,help="Manage isolated OpenCode workspaces on rootless Docker.",no_args_is_help=False,add_completion=False)
# Help panels: the top level lists everyday commands; related operations are groups.
ENVIRONMENTS, SESSIONS, DATA, HOST = "Environments", "Sessions", "Settings, changes and data", "Maintenance"
profiles=typer.Typer(help="Provider profiles: named credentials for model providers (values never displayed).",no_args_is_help=True)
app.add_typer(profiles,name="providers",rich_help_panel=DATA)
opencode_configs_app=typer.Typer(help="User-maintained OpenCode Configs and whole-global-directory file transfers (not an effective-config resolver).",no_args_is_help=True)
app.add_typer(opencode_configs_app,name="opencode-configs",rich_help_panel=DATA)
manager_app=typer.Typer(help="Sandbox Manager releases, installation evidence and explicitly reviewed updates (not OpenCode/npm).",no_args_is_help=True)
app.add_typer(manager_app,name="manager",rich_help_panel=HOST)


@manager_app.command('status')
def manager_status(check: bool=typer.Option(False,'--check',help='Check official published full GitHub releases; never install')):
    """Show local installation classification and dated release evidence, without Docker or pipx execution."""
    from . import manager_installation as mi
    from . import manager_releases as mr
    installation = mi.classify()
    error = None
    release = mr.discovery()['release']
    if check:
        try: release = mr.latest()
        except c.SandboxError as exc: error = c.error_text(exc)
    typer.echo(c.printable(json.dumps({'installation': installation, 'discovery': mr.discovery(),
                                      'comparison': mr.comparison(installation['version'], release),
                                      'release': release, 'check_error': error}, indent=2)))
    if error: raise typer.Exit(2)


@manager_app.command('update')
def manager_update(tag: str=typer.Option(...,'--tag',help='Exact newer published full release tag vX.Y.Z; freshly revalidated, never latest or an implicit downgrade')):
    """Review an exact manager update in a real terminal, then exit for independent replacement.

    Confirmation requires a foreground terminal and defaults to Cancel. No automatic restart,
    image build or environment migration. Exit means handoff only; wait for the independent
    helper's final result/private record before restarting.
    """
    from . import manager_handoff as handoff
    from . import manager_review as review
    terminal = handoff.Terminal()  # refuse noninteractive/redirected invocations before any network
    prepared = review.prepare(tag)
    typer.echo(review.text(prepared, update=True))
    if not typer.confirm(f'Update only this Sandbox Manager {prepared.version} -> {prepared.target.version}, accept public-default network policy and exit now?', default=False):
        typer.echo('Canceled; no installation was changed.')
        return
    staged = handoff.prepare_update(review.Approval(prepared))
    if not staged['supported']: raise c.SandboxError(staged['reason'])
    handoff.complete_terminal_update(handoff.TerminalRequest(staged['artifact']), terminal)

opencode_app=typer.Typer(help="OpenCode versions: check, policy, update and roll back (base images and environments).",no_args_is_help=True)
app.add_typer(opencode_app,name="opencode",rich_help_panel=HOST)
changes_app=typer.Typer(help="Changes made in a managed workspace: show, export, bundle, review, apply or stage them in the original repository.",no_args_is_help=True)
app.add_typer(changes_app,name="changes",rich_help_panel=DATA)
backup_app=typer.Typer(help="Cold backups of environments: create, list, verify, prune and restore into a new environment.",no_args_is_help=True)
app.add_typer(backup_app,name="backup",rich_help_panel=DATA)
container_app=typer.Typer(help="The environment's container: resource usage, snapshots of its system layer, recreation.",no_args_is_help=True)
app.add_typer(container_app,name="container",rich_help_panel=DATA)
disk_app=typer.Typer(help="Disk usage of everything the manager owns, and safe cleanup of leftovers.",no_args_is_help=True)
app.add_typer(disk_app,name="disk",rich_help_panel=HOST)

def _print_version(value: bool):
    if value:
        from . import __version__
        typer.echo(f"opencode-sandbox {__version__}")
        raise typer.Exit()

@app.callback()
def _root(version: bool = typer.Option(False, "--version", callback=_print_version, is_eager=True,
                                       help="Show the manager version and exit.")):
    """Manage isolated OpenCode workspaces on rootless Docker."""

@opencode_app.command("versions")
def opencode_versions(check: bool=typer.Option(False,"--check",help="Query npm for the latest supported stable release; compare every policy without changing pins")):
    """OpenCode version/policy: probe running containers; retain dated stopped evidence, never start them.

    Available rows survive failed checks; errors go to stderr and exit status is 2.
    """
    from . import opencode_versions as v
    lines,errors=v.versions_report(check=check)
    for line in lines: typer.echo(line)
    for error in errors: typer.echo(error,err=True)
    if errors: raise typer.Exit(2)

@opencode_app.command("status")
def opencode_status(name: str):
    """Actual/last-verified version and evidence for one environment; never starts a stopped container."""
    from . import opencode_versions as v
    typer.echo(v.environment_version(c.resolve(name)))

DISTRO_HELP="Distribution from the registry: "+", ".join(distros.REGISTRY)

@opencode_app.command("check")
def opencode_check(distro: str=typer.Option(distros.DEFAULT,"--distro",help=DISTRO_HELP)):
    """Compare a base image's OpenCode version with npm's latest supported stable release."""
    from . import opencode_versions as v
    image=distros.get(distro).image
    current=v.image_version(image)
    newest=v.latest()
    typer.echo(f"Base image {image}: {current}; npm registry: {newest}")
    state=v.describe(current,newest)
    typer.echo("Up to date" if state=="current" else state[0].upper()+state[1:])

@opencode_app.command("policy")
def opencode_policy(name: str):
    """Show the update policy for an environment."""
    from . import opencode_versions as v
    typer.echo(v.policy(c.resolve(name)))

@opencode_app.command("policy-set")
def opencode_policy_set(name: str, mode: str, version: str | None = typer.Option(None, "--version", help="The version to pin (mode pinned)")):
    """Set notify (default), manual or pinned update policy."""
    from . import opencode_versions as v
    typer.echo(v.set_policy(c.resolve(name), mode, version))

@opencode_app.command("update-base")
def opencode_update_base(version: str=typer.Option("latest","--version",help="Exact OpenCode 2.x version, or latest supported stable"), yes: bool=typer.Option(False,"--yes",help="Do not ask for confirmation"),
                         distro: str=typer.Option(distros.DEFAULT,"--distro",help=DISTRO_HELP),
                         refresh: bool=typer.Option(False,"--refresh",help="Pull upstream image and bypass the build cache; never prune")):
    """Rebuild a base image with another OpenCode version; keeps a rollback copy of the old one.

    Every build upgrades the image's system packages, in cached and refresh mode."""
    from . import opencode_versions as v
    plan=v.prepare_base_build(version,distro,refresh=refresh)
    typer.echo(v.describe_base_build(plan))
    if not yes and not _confirm(f"Replace {plan.image} ({plan.current_id or 'missing'}) with exact OpenCode {plan.target}; "
                                f"{'Refresh & Rebuild' if refresh else 'Cached rebuild'}; keep rollback copy?", docker=True):
        raise typer.Abort()
    typer.echo(v.update_base(plan.target, distro, refresh=refresh, plan=plan))

@opencode_app.command("update")
def opencode_update(name: str, version: str=typer.Option("latest","--version",help="Exact OpenCode 2.x version, or latest supported stable"), yes: bool=typer.Option(False,"--yes",help="Do not ask for confirmation"),
                    update_system_packages: bool=typer.Option(False,"--update-system-packages",help="Upgrade the environment's installed system packages first; OpenCode is not updated if this fails")):
    """Update OpenCode in a stopped environment; on failure its system layer is rolled back to a checkpoint."""
    from . import opencode_versions as v
    m=c.resolve(name)
    plan=v.prepare_environment_update(m,version,system_packages=update_system_packages)
    typer.echo("Note: a checkpoint (docker commit) of the container's system layer is taken first; a failed update "
               "is rolled back to it, 'opencode rollback' undoes a successful one. /root and /workspace are not touched.")
    for line in v.system_upgrade_lines(m, plan.system_packages): typer.echo(line)
    if not yes and not _confirm(f"Temporarily start stopped environment {name}, "
                                f"{'upgrade its system packages, ' if plan.system_packages else ''}update OpenCode to {plan.target}, then stop it?", docker=True):
        raise typer.Abort()
    result=v.update_environment(m,plan.target,plan=plan)
    if result.get("unchanged"): typer.echo(f"OpenCode {result['version']} is already installed; nothing changed")
    else: typer.echo(("System packages upgraded; " if result.get("system_packages") else "")
                     + (f"OpenCode {result['version']} unchanged" if result['previous_version']==result['version'] else
                        f"Updated OpenCode {result['previous_version'] or 'unknown (opencode --version failed)'} -> {result['version']}")
                     + f"; rollback point {result['checkpoint']}")

@opencode_app.command("update-recover")
def opencode_update_recover(name: str):
    """Finish an interrupted OpenCode update by rolling back to its checkpoint."""
    from . import opencode_versions as v
    v.update_recover(c.resolve(name))
    typer.echo("Rolled back to the checkpoint; the container is recreated from it at the next start")

@opencode_app.command("rollback")
def opencode_rollback(name: str, yes: bool=typer.Option(False,"--yes",help="Do not ask for confirmation")):
    """Undo the last OpenCode update of a stopped environment (container recreated from its checkpoint)."""
    from . import opencode_versions as v
    m=c.resolve(name)
    record=m.get("opencode_update") or {}
    if not yes and not _confirm(f"Recreate {name} from the checkpoint before its last OpenCode update "
                                f"({record.get('to')} -> {record.get('from')})? The current system layer is kept as a snapshot."
                                + (" That update also upgraded system packages: their checkpointed versions return, but changes "
                                   "outside the system layer (home volume, workspace, migrated data) are not undone."
                                   if record.get("system_packages") else ""),
                                docker=True):
        raise typer.Abort()
    result=v.rollback_environment(m)
    typer.echo(f"Rolled back OpenCode {result['rolled_back_from']} -> {result['version']}"
               + (f"; previous system layer kept as {result['snapshot']}" if result["snapshot"] else ""))

@opencode_app.command("rollback-base")
def opencode_rollback_base(yes: bool=typer.Option(False,"--yes",help="Do not ask for confirmation"),
                            distro: str=typer.Option(distros.DEFAULT,"--distro",help=DISTRO_HELP),
                            copy: str | None=typer.Option(None,"--copy",help="Exact rollback tag or full sha256 image ID; required for several distinct copies, even with --yes"),
                            list_copies: bool=typer.Option(False,"--list",help="List distinct managed rollback images and their aliases; do not change anything")):
    """Swap a base with a selected, verified rollback copy; one distinct copy is the default, never the newest by date."""
    from . import opencode_versions as v
    if list_copies and copy is not None:
        raise c.SandboxError("--list cannot be combined with --copy")
    inventory=v.base_rollback_inventory(distro)
    if list_copies:
        for line in v.format_base_rollback_copies(inventory): typer.echo(line)
        return
    plan=v.select_base_rollback(inventory,copy)
    d=distros.get(distro)
    image=d.image
    typer.echo(f"Base image {image}: {plan.current_id or 'missing'}\nSelected copy: {plan.selected.image_id}")
    for tag in plan.selected.aliases: typer.echo(f"  {tag}")
    definition=plan.selected.definition
    typer.echo(f"Copy build: {definition.distro} {definition.version}, revision {definition.revision}; "
               f"OpenCode {plan.selected.version or 'unknown'} (build label). "
               f"Required definition: {d.name} {d.version}, revision {d.revision}.")
    typer.echo("The copy must pass the current definition's OS/tool/OpenCode checks. The replaced base is kept as a rollback copy. "
               "Existing containers and writable layers are unchanged; future base-based creation and file-only restores use this base, with pins still enforced.")
    if not yes and not _confirm(f"Replace {image} ({plan.current_id or 'missing'}) with {plan.selected.image_id}?", docker=True):
        raise typer.Abort()
    result=v.rollback_base(distro,plan=plan)
    typer.echo(f"{result['image']}: OpenCode {result['version']}"
               + (" (unchanged; selected image already current)" if result.get("unchanged") else "")
               + (f"; replaced image kept as {result['previous_image']}" if result["previous_image"] else ""))

def pick(key:str | None):
    if key: return c.resolve(key)
    m=c.current_env()
    if not m: raise c.SandboxError("No environment bound to current directory. Supply NAME or ID.")
    return m

def msg(m): typer.echo(f"{m['name']} [{m['id']}] ({m['kind']})")


@opencode_configs_app.command("list")
def opencode_configs_list():
    """Discover user-maintained directories/root symlinks; never edit a source profile."""
    from . import opencode_configs as oc
    typer.echo(f"User-maintained directories: {oc.profiles_directory()}\n"
               "Copy/Reload imports the whole directory once, never a live link. Profiles may contain secrets or executable plugins.\n"
               f"Root symlink example: ln -s ~/my-opencode-config {oc.profiles_directory()}/work")
    names=oc.profiles()
    for name in names: typer.echo(name)
    if not names: typer.echo("No profiles. Place named directories here; Local creation remains usable.")


@opencode_configs_app.command("status")
def opencode_config_status(name: str):
    """OpenCode Config Editor status and exact persistent-on-host temporary export path."""
    from . import opencode_configs as oc
    result=oc.status(c.resolve(name))
    typer.echo(result["state"])
    if result["path"]: typer.echo(result["path"])
    typer.echo(oc.SCOPE + "\n" + oc.EXPORT_WARNING)


def _config_running_warning(m):
    from . import opencode_configs as oc
    if c.running(m): typer.echo(oc.RUNNING_WARNING, err=True)


@opencode_configs_app.command("export")
def opencode_config_export(name: str, yes: bool=typer.Option(False,"--yes",help="Confirm replacement of an existing export; host edits will be lost")):
    """Export the whole global tree to a private /tmp workspace; keep it across editor/manager closure."""
    from . import opencode_configs as oc
    m=c.resolve(name)
    exists=oc.status(m)["path"] is not None
    if exists and not yes and not _confirm("Replace Export? Existing host-side edits will be lost. Cancel preserves them.", docker=False):
        raise typer.Abort()
    typer.echo("Exporting/validating the entire global config tree…", err=True)
    typer.echo(oc.export(m,replace=exists and (yes or c._tty())))
    typer.echo(oc.EXPORT_WARNING)


@opencode_configs_app.command("apply")
def opencode_config_apply(name: str, overwrite: bool=typer.Option(False,"--overwrite",help="Explicitly accept observed container-side drift; never disables staging/recovery")):
    """Apply an edited export; compare container config with its saved baseline, never with host edits."""
    from . import opencode_configs as oc
    m=c.resolve(name)
    _config_running_warning(m)
    typer.echo("Staging/validating the entire edited export…", err=True)
    try: path=oc.apply(m)
    except oc.Conflict as exc:
        typer.echo(str(exc), err=True)
        if not overwrite:
            if not c._tty(): raise c.SandboxError("Canceled; both trees and baseline preserved. Review, then use --overwrite to choose Overwrite Anyway") from None
            if not typer.confirm("Overwrite Anyway?",default=False):
                typer.echo("Canceled; export and container config preserved."); return
        path=oc.apply(m,overwrite=exc.fingerprint)
    typer.echo(f"Applied. Export remains at {path}; its baseline now matches the installed container tree.")


@opencode_configs_app.command("delete-export")
def opencode_config_delete(name: str, yes: bool=typer.Option(False,"--yes",help="Confirm loss of unapplied host edits")):
    """Delete only a validated host export. Never changes the container config."""
    from . import opencode_configs as oc
    m=c.resolve(name)
    if not yes and not _confirm("Delete Export? Unapplied host edits will be lost; container config is untouched.",docker=False):
        raise typer.Abort()
    oc.delete_export(m,confirmed=True)
    typer.echo("Export deleted; container config unchanged.")


@opencode_configs_app.command("reload")
def opencode_config_reload(name: str, profile: str | None=typer.Option(None,"--profile",help="Freshly copy this whole profile; omitted selects the original profile if still available"),
                           empty: bool=typer.Option(False,"--empty",help="Completely clear the global config directory"),
                           yes: bool=typer.Option(False,"--yes",help="Confirm whole-directory replacement")):
    """Replace global config from a profile or Empty; system, Agent Context, workspace and auth/state outside it stay untouched."""
    from . import opencode_configs as oc
    if empty and profile is not None: raise c.SandboxError("Choose --profile or --empty, not both")
    m=c.resolve(name)
    source=profile if profile is not None else (None if empty else m.get("opencode_config_source"))
    if profile is None and source not in oc.profiles(): source=None
    if source is not None: oc.profile_path(source)
    typer.echo(oc.REPLACE_WARNING + "\n" + oc.SCOPE)
    typer.echo(f"Selected: {source or 'Empty — completely clear local configuration'}")
    _config_running_warning(m)
    if not yes and not _confirm("Reload and replace the entire global config directory?",docker=True): raise typer.Abort()
    typer.echo("Staging/validating the whole replacement tree…", err=True)
    result=oc.reload(m,source,confirmed=True)
    typer.echo(f"Reloaded: {result['source']}. No container or OpenCode restart.")


@opencode_configs_app.command("recover")
def opencode_config_recover(name: str):
    """Resolve an interrupted recoverable global-config replacement; never discard an unknown transaction."""
    from . import opencode_configs as oc
    typer.echo(oc.recover(c.resolve(name)))

@app.command(rich_help_panel=HOST)
def build(distro: str=typer.Option(distros.DEFAULT,"--distro",help=DISTRO_HELP),
          opencode_version: str=typer.Option("latest","--opencode-version",help="OpenCode 2.x version (npm @opencode/cli)"),
          refresh: bool=typer.Option(False,"--refresh",help="Pull upstream image and bypass the build cache; never prune")):
    """Build/rebuild an agent image without a rollback copy (use opencode update-base to keep one).

    Every build upgrades the image's system packages, in cached and refresh mode."""
    from . import opencode_versions as v
    plan=v.prepare_base_build(opencode_version,distro,refresh=refresh,keep_previous=False)
    typer.echo(v.describe_base_build(plan))
    result=c.build(distro, plan.target, refresh=refresh, plan=plan)
    typer.echo(f"{result['image']}: OpenCode {result['version']}"+(" (unchanged)" if result.get("unchanged") else ""))

@app.command(rich_help_panel=HOST)
def doctor():
    """Check host programs, daemon identity, resource-limit support, base images and storage (per environment: check NAME).

    Read-only; works without Docker. Exit status: 0 host programs and daemon verified (resource/image/storage warnings or unknown checks may remain); 3 the Docker socket is served by a proxy; 4 not your own rootless daemon; 5 the daemon is not reachable; 6 an unsupported endpoint; 7 a required program (Docker CLI, Git) is missing; 8 the Docker context is not configured.
    """
    from . import readiness as r
    from . import runtime_identity as rid
    typer.echo(f"Data: {c.BASE}\nConfig: {c.CONFIG}")
    host=r.host_checks()
    for line in r.format_report({"checks":[vars(x) for x in host]}):
        typer.echo(line)
    ident=c.verify_runtime(strict=False)
    typer.echo(ident.report())
    if not ident.verified:
        raise typer.Exit(rid.EXIT_CODES[ident.classification])
    for line in r.format_report({"checks":[vars(x) for x in (r.resource_support_check(),*r.image_checks(),r.storage_check())]}):
        typer.echo(line)
    df=c.docker("system","df","--format","{{.Type}}\t{{.Size}}\t{{.Reclaimable}}",capture=True,check=False)
    for line in (getattr(df,"stdout",None) or "").splitlines() if df.returncode==0 else ():
        kind,_,rest=line.partition("\t")
        if kind=="Build Cache":
            size,_,reclaimable=rest.partition("\t")
            typer.echo(f"Docker build cache: {size} (reclaimable {reclaimable}; 'docker builder prune' — affects all builds of this Docker daemon)")
    if any(x.status==r.FAILED for x in host):
        raise typer.Exit(rid.EXIT_CODES[rid.MISSING])

agent_context_app=typer.Typer(help="Agent Context: the guidance the manager gives OpenCode about the sandbox (show, verify, refresh).",no_args_is_help=True)
app.add_typer(agent_context_app,name="agent-context",rich_help_panel=DATA)

def _guidance_inputs(m):
    """Observe the container when Docker answers; otherwise describe the configuration."""
    try:
        with c.runtime_feedback(timeout=0.25, progress=None):
            return c.guidance_inputs(m)
    except c.SandboxError as exc:
        typer.echo(f"Note: container not inspected ({exc}); using the configured runtime settings.", err=True)
        return c.guidance_inputs(m, observe=False)

@agent_context_app.command("show")
def agent_context_show(name: str):
    """Preview exact guidance for an environment (read-only)."""
    from . import agent_context as ac
    m=c.resolve(name)
    typer.echo(ac.render(m,**_guidance_inputs(m)))

@agent_context_app.command("verify")
def agent_context_verify(name: str):
    """Compare persisted guidance with current metadata and container (read-only)."""
    from . import agent_context as ac
    m=c.resolve(name)
    good=ac.verify(m,c.env_dir,**_guidance_inputs(m))
    typer.echo("Current" if good else "Missing or outdated; run agent-context refresh")
    if not good: raise typer.Exit(1)

@agent_context_app.command("refresh")
def agent_context_refresh(name: str):
    """Rewrite guidance on disk; running containers see it at once (read-only directory mount)."""
    from . import agent_context as ac
    m=c.resolve(name)
    with c.lock(m["id"]):
        m=c.resolve(m["id"])
        target=ac.refresh(m,c.env_dir,**_guidance_inputs(m))
    typer.echo(f"Updated {target}. Running containers see it at /run/ocs-agent/context.md; run also refreshes it before every launch.")

SUPERSEDED=typer.Option(False,"--superseded",help="Also remove unused OpenCode update checkpoints, old runtime images and base rollback copies")

@disk_app.command("usage")
def disk_command():
    """Disk usage of everything the manager owns (approximate sizes) and what cleanup would remove; read-only."""
    from . import cleanup
    for line in cleanup.format_inventory(cleanup.inventory()): typer.echo(line)

@disk_app.command("cleanup")
def cleanup_command(yes: bool = typer.Option(False, "--yes", help="Remove the listed objects (default: preview only)"),
                    superseded: bool = SUPERSEDED):
    """Preview (default) or remove orphaned and leftover manager objects of this data directory.

    Never removes environments (use delete), snapshots of existing environments, base images, direct workspaces, exports, backups, the Docker build cache or objects without this data directory's labels; never forces a removal Docker refuses."""
    from . import cleanup
    inv=cleanup.inventory()
    for line in inv.errors: typer.secho(f"WARNING: {line}", fg=typer.colors.YELLOW, err=True)
    items=inv.eligible(superseded)
    if not items:
        typer.echo("Nothing to clean up." + ("" if superseded else " (--superseded also covers unused update checkpoints, old runtime images and base rollback copies)"))
        return
    if not yes:
        chain=any(i.category=="image" and i.status==cleanup.ORPHAN for i in items)
        typer.echo(f"Would remove {len(items)} object(s), freeing {cleanup.human(cleanup.reclaimable(items))}"
                   + (" (plus untagged earlier layers of the same deleted environments that removing an image exposes)" if chain else "") + ":")
        for line in cleanup.format_preview(items): typer.echo(line)
        typer.echo(f"Rerun 'disk cleanup --yes{' --superseded' if superseded else ''}' to remove them"
                   + ("" if superseded else "; --superseded also covers unused update checkpoints, old runtime images and base rollback copies") + ".")
        return
    failed=0
    for item, error in cleanup.apply([i.key for i in items], superseded=superseded):
        label=item if isinstance(item, str) else f"{item.kind} {item.name}"
        if error is None: typer.echo(f"Removed: {label}")
        elif error.startswith("skipped: "):  # re-checked and left alone on purpose: not a failure
            typer.echo(f"Skipped: {label} ({error.removeprefix('skipped: ')})")
        else:
            failed+=1; typer.echo(f"Not removed: {label} ({error})")
    if failed: raise typer.Exit(1)

@app.command("list",rich_help_panel=ENVIRONMENTS)
def list_envs():
    """List the environments."""
    for m in c.all_envs(): msg(m)
    for path in c.invalid_metadata():
        typer.secho(f"WARNING: ignoring {path}: {c.metadata_error(path) or 'invalid metadata'}",fg=typer.colors.YELLOW,err=True)

WORKSPACE_PANEL, IMAGE_PANEL = "Workspace", "Distribution or image"

def _distro_help():
    return "; ".join(f"{d.id}: {d.name} {d.version}{' (default)' if d.id==distros.DEFAULT else ''}" for d in distros.REGISTRY.values())

@app.command(rich_help_panel=ENVIRONMENTS)
def create(name:str,
           source:Path | None=typer.Option(None,"--source",help="Folder to copy: Git roots are cloned (committed only by default); other folders exclude hidden files"),
           include_working_changes:bool=typer.Option(False,"--include-working-changes",rich_help_panel=WORKSPACE_PANEL,help="Project Git import: include staged, unstaged and non-ignored untracked files; show a status preview"),
           kind:str | None=typer.Option(None,"--kind",help="scratch (empty workspace) | project (a copy of --source) | quick (disposable). Default: project with --source or a direct workspace, otherwise scratch"),
           profile:str=typer.Option("default","--profile",help="Provider profile (see: providers list)"),
           distro:str | None=typer.Option(None,"--distro",rich_help_panel=IMAGE_PANEL,help="Base definitions: "+_distro_help()),
           image:str | None=typer.Option(None,"--image",rich_help_panel=IMAGE_PANEL,help="Custom image instead of a distribution (no tool or OS claims in Agent Context)"),
           workspace_mode:str=typer.Option("managed","--workspace-mode",rich_help_panel=WORKSPACE_PANEL,help="managed (default: empty or a copy of --source) | direct (not recommended: the agent works in your host folder itself)"),
           workspace:Path | None=typer.Option(None,"--workspace",rich_help_panel=WORKSPACE_PANEL,help="Existing host folder to mount as /workspace with --workspace-mode direct"),
           yes:bool=typer.Option(False,"--yes",rich_help_panel=WORKSPACE_PANEL,help="Consent to a direct workspace and its preflight without asking"),
            opencode_config:str | None=typer.Option(None,"--opencode-config",help="Copy this user-maintained OpenCode config profile once; omitted = Local"),
            agent_context:bool=typer.Option(True,"--agent-context/--no-agent-context",help="Include specialized Agent Context; the file remains available when disabled")):
    """Create an environment: an empty scratch workspace, or a copy of a folder with --source.

    Without options: the default distribution, Local OpenCode config and Agent Context enabled. The original folder is never touched."""
    from .config_plan import check_profile
    check_profile(profile)  # as config apply: a mistyped name would leave the container without credentials
    kind,_=c.creation_options(name,kind,source,distro=distro,image=image,workspace_mode=workspace_mode,workspace=workspace,
                             include_working_changes=include_working_changes)
    fingerprint=None
    if include_working_changes:
        from . import git_import
        plan=git_import.preview(source)
        typer.echo(plan.describe())
        fingerprint=plan.fingerprint
    consent=False
    if workspace_mode==workspaces.DIRECT and workspace is not None:
        target=workspaces.check_direct(workspace)  # explain refusals before asking
        c.verify_runtime()  # the preflight needs the daemon: check it before asking for consent
        typer.secho(f"{workspaces.LABEL}.",fg=typer.colors.YELLOW,bold=True)
        typer.echo(DIRECT_CONSENT.format(path=target))
        if yes: consent=True
        elif not c._tty(): raise typer.BadParameter("A direct workspace needs consent; confirm with --yes")
        else: consent=typer.confirm("Use this directory directly?")
        if not consent: raise typer.Exit(1)
    if opencode_config is not None:
        typer.echo("Validating/copying the entire OpenCode config profile before creation…", err=True)
    m=c.create(name,kind,source,profile,distro=distro,image=image,workspace_mode=workspace_mode,
                workspace=workspace,consent=consent,opencode_config=opencode_config,agent_context_enabled=agent_context,
                include_working_changes=include_working_changes,import_fingerprint=fingerprint)
    msg(m)
    typer.echo(f"Workspace: {workspaces.describe(m)}\n"
               f"Distribution: {c.distribution_description(m)}\n"
               f"Provider profile: {m['profile']}\n"
                f"OpenCode config: {opencode_config or 'Local'}; Agent Context: {'enabled' if agent_context else 'disabled'}\n"
               f"Next: opencode-sandbox run {m['name']}")

DIRECT_CONSENT=("The agent in the container can read, change and delete every file in\n  {path}\n"
                "immediately, with your user's permissions on the host. Nothing is copied: there is no review "
                "step, no undo, and 'backup' leaves the directory out unless --include-workspace is given. "
                "Deleting the environment never touches the directory.\n"
                "It can also write files that programs on your host run or act on later in this directory "
                "(Git hooks and Git configuration, editor, direnv and build settings): review them before you run "
                "Git, an editor or a build tool there.\n"
                "Preflight: a temporary container of the environment's image writes, checks and removes one file "
                "named .ocs-preflight-<random> in that directory, to prove that files there stay yours.")

config_app=typer.Typer(help="Environment settings: limits, network, ports, provider profile and Agent Context (show, plan, apply, recover).",no_args_is_help=True)
app.add_typer(config_app,name="config",rich_help_panel=DATA)

def _config_changes(cpus, memory, pids, network, publish, no_ports, profile, agent_context=None):
    """Only the options given; config_plan merges them with the current values."""
    from .config_plan import parse_ports
    if publish and no_ports: raise typer.BadParameter("--publish and --no-ports exclude each other")
    ports=[] if no_ports else (parse_ports(publish) if publish else None)
    return {k: v for k, v in (("cpus", cpus), ("memory", memory), ("pids", pids), ("network", network),
                              ("ports", ports), ("profile", profile), ("agent_context_enabled", agent_context)) if v is not None}

CPUS=typer.Option(None,"--cpus",help="CPU limit")
MEMORY=typer.Option(None,"--memory",help="Memory limit, e.g. 8g")
PIDS=typer.Option(None,"--pids",help="Process limit")
NETWORK=typer.Option(None,"--network",help="bridge or none")
PUBLISH=typer.Option(None,"--publish",help="HOST:CONTAINER or HOST:CONTAINER/udp (default tcp); binds to 127.0.0.1; replaces all mappings")
NO_PORTS=typer.Option(False,"--no-ports",help="Remove all published ports")
PROFILE=typer.Option(None,"--profile",help="Provider profile")
AGENT_CONTEXT=typer.Option(None,"--agent-context/--no-agent-context",help="Include specialized Agent Context; file remains mounted either way")

@config_app.command("show")
def config_show(name: str):
    """Configured settings and, when a container exists, what Docker reports for it."""
    from .config_plan import current
    m=c.resolve(name)
    typer.echo(json.dumps({"configured": current(m), "workspace": workspaces.info(m),
                           "container": c.observed_runtime(m)}, indent=2))

@config_app.command("plan")
def config_plan_command(name: str, cpus: float | None = CPUS, memory: str | None = MEMORY, pids: int | None = PIDS,
                        network: str | None = NETWORK, publish: list[str] = PUBLISH, no_ports: bool = NO_PORTS,
                         profile: str | None = PROFILE, agent_context: bool | None = AGENT_CONTEXT, as_json: bool = typer.Option(False, "--json", help="Print the plan as JSON")):
    """Show what a change would do (category, steps, warnings) without changing anything."""
    from . import config_plan as cp
    p=cp.plan(c.resolve(name),_config_changes(cpus,memory,pids,network,publish,no_ports,profile,agent_context))
    typer.echo(json.dumps(p.as_dict(),indent=2) if as_json else cp.describe(p))
    if p.blockers: raise typer.Exit(1)

@config_app.command("apply")
def config_apply(name: str, cpus: float | None = CPUS, memory: str | None = MEMORY, pids: int | None = PIDS,
                 network: str | None = NETWORK, publish: list[str] = PUBLISH, no_ports: bool = NO_PORTS,
                  profile: str | None = PROFILE, agent_context: bool | None = AGENT_CONTEXT, yes: bool = typer.Option(False, "--yes", help="Apply without asking")):
    """Plan and apply a change. Changes that stop or recreate a container ask first (or need --yes)."""
    from . import config_plan as cp
    m=c.resolve(name)
    changes=_config_changes(cpus,memory,pids,network,publish,no_ports,profile,agent_context)
    p=cp.plan(m,changes)
    typer.echo(cp.describe(p))
    if p.blockers: raise typer.Exit(1)
    if not p.changes: return
    if p.category in ("restart","recreate") and not yes:
        if not c._tty(): raise typer.BadParameter(f"This change {'restarts' if p.category=='restart' else 'recreates'} the container; confirm with --yes")
        if not typer.confirm("Apply?"): raise typer.Exit(1)
    result=cp.apply(m,changes,confirmed=p)
    typer.echo(f"Applied ({result['category']}).")

@config_app.command("recover")
def config_recover(name: str):
    """Finish an interrupted configuration change or container recreation."""
    from . import config_plan as cp
    typer.echo(json.dumps(cp.recover(c.resolve(name)), indent=2))

@container_app.command("usage")
def runtime_usage(name: str):
    """One-shot resource usage reported by Docker (CPU, memory, processes, network)."""
    typer.echo(json.dumps(c.runtime_usage(c.resolve(name)),indent=2))

@app.command(rich_help_panel=SESSIONS)
def run(name:str | None=typer.Argument(None)):
    """Open OpenCode in the environment (without NAME: the environment of the current folder)."""
    raise typer.Exit(c.interactive(pick(name)))

@app.command(rich_help_panel=SESSIONS)
def shell(name:str | None=typer.Argument(None)):
    """Open a root shell in the environment (without NAME: the environment of the current folder)."""
    raise typer.Exit(c.interactive(pick(name),shell=True))

@app.command("exec",rich_help_panel=SESSIONS,context_settings={"allow_extra_args":True,"ignore_unknown_options":True})
def exec_command(ctx:typer.Context,name:str):
    """Execute a command: exec NAME -- command \\[args]. Use ocs-opencode to load the provider profile."""
    if not ctx.args: raise c.SandboxError("Missing command")
    if Path(ctx.args[0]).name=="opencode":
        typer.secho(f"Note: plain opencode does not load the provider profile; use 'exec {name} -- ocs-opencode' or managed run.",
                    fg=typer.colors.YELLOW,err=True)
    raise typer.Exit(c.exec_cmd(c.resolve(name),ctx.args))

@app.command(rich_help_panel=ENVIRONMENTS)
def start(name:str):
    """Start or create the persistent container and reconcile Agent Context activation."""
    c.start(c.resolve(name))

@app.command(rich_help_panel=ENVIRONMENTS)
def stop(name:str):
    """Stop the container; packages, workspace and home volume stay."""
    c.stop(c.resolve(name))

@app.command(rich_help_panel=ENVIRONMENTS)
def status(name:str):
    """Metadata, container state, network and the last readiness result."""
    m=c.resolve(name); msg(m)
    typer.echo(f"Workspace: {workspaces.describe(m)}\n"
               f"Provider profile: {m.get('profile')}\nContainer: {c.cname(m)}\n"
               f"Image: {c.env_image(m)}")
    c.ensure_runtime(False)
    typer.echo("Running: "+str(c.running(m)))
    from . import readiness as r
    try:
        inputs=c.guidance_inputs(m)
        observed,definition=inputs["observed"],inputs["definition"]
    except c.SandboxError: observed,definition=r.UNKNOWN,None
    typer.echo(f"Distribution: {c.distribution_description(m,definition)}")
    for line in r.network_lines(m,observed): typer.echo(line)
    typer.echo(f"Readiness: {r.cached_line(m)} (full check: opencode-sandbox check {m['name']})")
    update=m.get("opencode_update") or {}
    if update:
        typer.echo(f"Last OpenCode update: {update.get('result') or 'in progress'} ({update.get('at')})"
                   + (f"; rollback point {update['checkpoint']}" if update.get("state")=="done" else ""))
    warning=c.profile_mismatch(m)
    if warning: typer.secho(f"WARNING: {warning}",fg=typer.colors.YELLOW)

@app.command("check",rich_help_panel=ENVIRONMENTS)
def check_command(name: str):
    """Read-only readiness check of one environment, including measured network reachability.

    Nothing is started or changed; reachability is measured from inside a running container. Results are passed, warning, failed, not checked or not applicable; exit 1 if any check failed."""
    from . import readiness as r
    m=c.resolve(name)
    report=r.run(m)
    typer.echo(f"Readiness of {m['name']} [{m['id']}]")
    for line in r.format_report(report): typer.echo(line)
    typer.echo("Summary: "+r.summary(report))
    if r.failed(report): raise typer.Exit(1)

@app.command(rich_help_panel=HOST)
def repair(name:str | None=typer.Argument(None), cleanup:bool=typer.Option(False,"--cleanup",help="Remove an owned container that never started or is dead; retain volume and workspace"), all_pending:bool=typer.Option(False,"--all",help="Reconcile all interrupted/error environments")):
    """Reconcile an environment's recorded state with Docker; names the command for interrupted operations."""
    if all_pending:
        if name or cleanup: raise c.SandboxError("--all cannot be combined with NAME or --cleanup")
        for eid, result, error in c.repair_all():
            typer.echo(f"{eid}: {error or result}")
        return
    typer.echo(c.repair(pick(name),cleanup=cleanup))

@changes_app.command("show")
def changes_show(name:str):
    """Commits, changed files and working tree status since the import (read-only)."""
    m=c.resolve(name)
    if not workspaces.is_direct(m) and wio.is_git_workspace(workspaces.managed_path(m)):
        c.require_program("git")  # the preview elsewhere tolerates it; here it is the whole command
    typer.echo(c.printable(c.git_changes(m)))

@changes_app.command("export")
def export(name:str,destination:Path | None=typer.Option(None,"--destination",help="Directory for the archive (default: exports/ in the data directory)")):
    """Archive the changes (Git: commits, staged, unstaged and untracked files; otherwise the whole workspace) as .tar.gz."""
    typer.echo(c.export(c.resolve(name),destination))

@changes_app.command("bundle")
def changes_export(name: str, destination: Path | None = typer.Option(None, "--destination", help="Directory for the bundle (default: changes/ in the data directory)")):
    """Create a checksummed binary patch and untracked-files bundle."""
    from .gitflow import export_changes
    typer.echo(export_changes(c.resolve(name), destination))

@changes_app.command("review")
def changes_review(bundle: Path, source: Path):
    """Validate a change bundle and preflight a clean source; no writes."""
    from .gitflow import review_apply
    typer.echo(__import__('json').dumps(review_apply(bundle, source), indent=2))

@changes_app.command("apply")
def changes_apply(bundle: Path, source: Path, yes: bool = typer.Option(False, "--yes", help="Explicitly modify source after preflight")):
    """Apply to a clean source at exactly the recorded base commit."""
    from .gitflow import review_apply
    if not yes:
        typer.echo("This writes to the original repository. Run 'changes review' first.")
        if not _confirm("Apply changes to source?"):
            raise typer.Exit(1)
    typer.echo(__import__('json').dumps(review_apply(bundle, source, apply=True), indent=2))

@changes_app.command("inspect")
def changes_inspect(bundle: Path):
    """Print complete patch and list untracked files before review."""
    from .gitflow import inspect_changes
    info = inspect_changes(bundle)
    # Everything shown comes from the sandbox: control characters are escaped.
    typer.echo(c.printable(f"Base: {info['base']}\nHead: {info['head']}\nHistory bundle: {info['has_history']}"))
    typer.echo("Untracked files: " + ", ".join(c.printable(n).replace("\n", "\\n") for n in info["untracked"]))
    for name, target in sorted(info["symlinks"].items()):
        typer.echo(f"Untracked symlink: {name!r} -> {target!r}")
    if info["attention"]:
        typer.echo("Review with care (host tools act on these, or they are links or executable):")
        for line in info["attention"]:
            typer.echo("  " + c.printable(line).replace("\n", "\\n"))
    typer.echo(c.printable(info["patch"]))

@changes_app.command("stage")
def changes_stage(bundle: Path, source: Path, branch: str | None = typer.Option(None, "--branch", help="Review branch name, starting with ocs/review- (default: ocs/review-<environment id>)")):
    """Safely publish changes as a review branch; never modify source files."""
    from .gitflow import stage_changes
    typer.echo(__import__('json').dumps(stage_changes(bundle, source, branch), indent=2))

@changes_app.command("branch-diff")
def changes_diff(source: Path, branch: str):
    """Show the full diff of a staged review branch without checking it out."""
    from .gitflow import review_branch_diff
    typer.echo(c.printable(review_branch_diff(source, branch)))

@changes_app.command("unstage")
def changes_unstage(source: Path, branch: str, commit: str):
    """Remove a review branch, only if it still points to the expected commit."""
    from .gitflow import drop_review_branch
    drop_review_branch(source, branch, expected_commit=commit)
    typer.echo("Review branch removed; original worktree untouched")

@backup_app.command("create")
def backup_command(name:str, destination:Path | None=typer.Option(None,"--destination",help="Directory for the backup (default: backups/ in the data directory)"), stop:bool=typer.Option(False,"--stop",help="Stop a running container first (it stays stopped)"), no_system:bool=typer.Option(False,"--no-system",help="Leave out the container's system layer (installed packages)"),
                   include_workspace:bool=typer.Option(False,"--include-workspace",help="Direct workspace: also archive the host directory (read only)")):
    """Verified cold backup of workspace, home volume and system layer.

    A direct workspace is included only with --include-workspace."""
    from .backup import backup, backup_notes
    m=c.resolve(name)
    direct=workspaces.is_direct(m)
    if include_workspace and not direct: raise typer.BadParameter("--include-workspace applies to direct workspaces; a managed one is always included")
    target=backup(m,destination,stop_running=stop,include_system=not no_system,include_workspace=include_workspace if direct else None)
    typer.echo(target)
    for note in backup_notes(target):
        typer.echo(f"Note: {note}")
    if direct and not include_workspace:
        typer.echo(f"Note: the direct workspace {m['workspace']['path']} is not in this backup.")

@backup_app.command("verify")
def backup_verify(path:Path):
    """Validate checksums and archive paths without restoring."""
    from .backup import verify
    result=verify(path)
    typer.echo(f"Valid backup: {result['created']} ({len(result['files'])} components)")

@backup_app.command("restore")
def restore_command(path:Path, name:str, no_system:bool=typer.Option(False,"--no-system",help="Restore files only, without container system image")):
    """Restore a backup into a NEW environment (never over existing work)."""
    from .backup import restore
    m=restore(path,name,restore_system=not no_system)
    msg(m)
    for warning in m.get("restore_warnings") or []:
        typer.secho(f"WARNING: {warning}",fg=typer.colors.YELLOW,err=True)

@backup_app.command("list")
def backups_command(directory:Path | None=typer.Option(None,"--directory",help="Backup directory (default: backups/ in the data directory)")):
    """List backups and their sizes."""
    from .backup import backup_info, list_backups
    for path in list_backups(directory):
        try:
            info=backup_info(path)
            typer.echo(f"{info['created']}  {info['name']}  {info['bytes']/1024/1024:.1f} MiB  {path}")
        except (c.SandboxError,OSError) as exc: typer.echo(f"INVALID {path}: {exc}",err=True)  # like backup prune

@backup_app.command("prune")
def backup_prune(keep:int=typer.Option(5,min=0,help="Keep the newest N verified backups per environment (by recorded creation time)"),
                 directory:Path | None=typer.Option(None,"--directory",help="Backup directory (default: backups/ in the data directory)"),yes:bool=typer.Option(False,"--yes",help="Delete (without it: preview only)")):
    """Preview backup retention; use --yes to delete old verified backups."""
    from .backup import prune
    paths,skipped=prune(directory,keep=keep,dry_run=not yes,on_delete=lambda p: typer.echo(f"Deleted: {p}"))
    if not yes:
        for path in paths: typer.echo(f"Would delete: {path}")
    for path,reason in skipped: typer.echo(f"Skipped (not a verifiable backup, never deleted): {path}: {reason}")
    typer.echo(f"{len(paths)} backup(s) {'deleted' if yes else 'eligible for deletion'}")

@backup_app.command("restore-check")
def restore_check(name:str):
    """Start a restored environment and smoke-test OpenCode and mounts."""
    from .backup import check_restored
    check_restored(c.resolve(name))
    typer.echo('Restored environment smoke check: OK')

@backup_app.command("restore-resume")
def restore_resume(name:str):
    """Retry a restore only when its target is still empty; otherwise fail safely."""
    from .backup import resume_restore
    msg(resume_restore(c.resolve(name)))

@backup_app.command("restore-rollback")
def restore_rollback(name:str,yes:bool=typer.Option(False,"--yes",help="Do not ask for confirmation")):
    """Delete an incomplete restore (only that), after confirmation."""
    from .backup import rollback_restore
    m=c.resolve(name)
    if not yes and not _confirm(f"Delete failed restore {m['name']} and its data?", docker=True):
        raise typer.Abort()
    rollback_restore(m)
    typer.echo('Failed restore removed')

@container_app.command("snapshot")
def snapshot(name:str,tag:str | None=typer.Option(None,"--tag",help="A new image tag outside the manager's repositories, or ocs-snapshot:<id>-NAME (default: ocs-snapshot:<id>-<time>-<random>); an existing tag is never replaced")):
    """Commit the container's system layer to an image (NOT the workspace or the /root home volume)."""
    typer.echo(c.snapshot(c.resolve(name),tag))

@container_app.command("recreate")
def recreate(name:str,yes:bool=typer.Option(False,"--yes",help="Recreate without asking")):
    """Replace the container from a snapshot of its system layer; workspace and home volume stay."""
    m=c.resolve(name)
    if not yes:
        typer.echo("A running container is stopped first (its processes end), its system layer is committed to a "
                   "snapshot and the new container is created from it and started; workspace and home volume stay.",err=True)
        if not _confirm(f"Recreate the container of {name}?", docker=True): raise typer.Abort()
    c.recreate(m,confirm=True)

@container_app.command("recreate-recover")
def recreate_recover(name: str):
    """Finish an interrupted recreation from its preserved snapshot."""
    typer.echo(c.recreate_recover(c.resolve(name)))

@app.command(rich_help_panel=ENVIRONMENTS)
def promote(name:str,kind:str=typer.Argument(...,help="project or scratch"),new_name:str | None=typer.Option(None,"--new-name",help="Rename it as well")):
    """Keep a quick session: turn it into a persistent project or scratch environment."""
    c.promote(c.resolve(name),kind,new_name)

@app.command(rich_help_panel=ENVIRONMENTS)
def delete(name:str,export_first:bool=typer.Option(False,"--export-first",help="Run 'changes export' first"),yes:bool=typer.Option(False,"--yes",help="Do not ask to type the name")):
    """Show the changes, optionally export them, then permanently delete the environment."""
    m=c.resolve(name)
    typer.echo(c.printable(c.git_changes(m)))
    if workspaces.is_direct(m): typer.echo(f"The direct workspace {m['workspace']['path']} is not touched.")
    if export_first: typer.echo(f"Exported: {c.export(m)}")
    c.verify_runtime()  # before asking: a confirmed deletion must not fail for a missing daemon
    if not yes:
        if not c._tty(): raise c.SandboxError(f"No terminal to confirm the deletion of {m['name']}; confirm with --yes")
        if typer.prompt(f"Type {m['name']} to delete")!=m["name"]: raise typer.Abort()
    c.delete(m,force=True)

@app.command(rich_help_panel=SESSIONS)
def quick(source:Path | None=typer.Option(None,"--source",help="Folder to copy into the disposable workspace"),shell:bool=typer.Option(False,"--shell",help="Open a root shell instead of OpenCode")):
    """Disposable session; afterwards export, promote, delete or keep it."""
    if not c._tty():  # before create: every scripted call left a preserved quick environment
        raise c.SandboxError("quick needs an interactive terminal; for scripts use create + exec")
    m=c.create("quick-"+__import__("secrets").token_hex(3), "quick",source)
    try:
        c.interactive(m,shell=shell)
        typer.echo("Session ended. Environment remains until you choose an action.")
        choice=typer.prompt("Action: [e]xport changes and delete, [p]romote to scratch, [d]elete, [k]eep as a quick session",default="k").lower()
        if choice=="e":
            typer.echo(c.export(m)); c.delete(m,force=True)
        elif choice=="p": c.promote(m,"scratch",f"scratch-{m['id'][:6]}")
        elif choice=="d":
            if typer.confirm("Permanently delete quick session?"): c.delete(m,force=True)
        else: typer.echo(f"Kept; continue with: opencode-sandbox run {m['id']}")
    except BaseException:
        typer.echo(f"Quick environment preserved for recovery: {m['id']}",err=True)
        raise

@profiles.command("list")
def provider_list():
    """Provider profiles and their variable names (never the values)."""
    for n in c.profile_list(): typer.echo(n+": "+", ".join(c.profile_keys(n)))

@profiles.command("set")
def provider_set(name:str,key:str=typer.Option(...,"--key",prompt="Environment variable name",help="Variable name, e.g. OPENROUTER_API_KEY (asked if omitted)")):
    """Prompt for a credential (hidden input) and store it in the profile (a 0600 host file)."""
    if not c._tty():
        raise c.SandboxError("providers set reads the value at a hidden prompt and needs an interactive terminal")
    c._validate_profile({key: ""})  # refuse reserved/invalid names before asking for a secret
    existing=c.profile_read(name)
    existing[key]=typer.prompt("Secret value",hide_input=True)
    c.profile_set(name,existing)
    typer.echo(f"Stored {key} in profile {name}. Containers using this profile see the change after a restart.")

@app.command(rich_help_panel=SESSIONS)
def tui():
    """Open the dashboard (also: opencode-sandbox without arguments in a terminal)."""
    if not c._tty():
        raise c.SandboxError("the dashboard needs an interactive terminal; in scripts use the commands (see --help)")
    _dashboard()


def _dashboard():
    """One exit boundary for implicit/explicit dashboards; ordinary return never grants handoff."""
    from . import manager_handoff as handoff
    from .tui import Dashboard
    try: terminal = handoff.Terminal()
    except (OSError, ValueError, c.SandboxError): terminal = None
    dashboard = Dashboard()
    result = dashboard.run()
    if result is None: return
    if type(result) is not handoff.TerminalRequest or type(result.artifact) is not handoff.Artifact or result is not dashboard._manager_fixture \
            or dashboard.is_running or dashboard.return_code != 0:
        raise c.SandboxError('Dashboard did not complete a clean fixture handoff; nothing was armed')
    from textual.drivers.linux_driver import LinuxDriver
    driver = dashboard._driver
    if type(driver) is not LinuxDriver or driver.is_headless or driver.is_inline \
            or any(thread is None or thread.is_alive() for thread in (driver._key_thread, driver._writer_thread)):
        raise c.SandboxError('Local terminal driver shutdown could not be verified; nothing was armed')
    if result.artifact.update: handoff.complete_terminal_update(result, terminal)
    else: handoff.complete_terminal_fixture(result, terminal)

ORDER=("create","list","status","check","start","stop","promote","delete","run","shell","exec","quick","tui",
       "config","changes","backup","container","agent-context","providers","repair","opencode","manager","disk","build","doctor")


def _confirm(question, docker=False):
    """A confirmation that --yes gives in scripts. Without a terminal it refuses instead of reading
    end-of-input; with docker=True the daemon is verified first, so nobody confirms an operation
    that cannot run."""
    if docker: c.verify_runtime()
    if not c._tty(): raise c.SandboxError(f"No terminal to confirm: {question} Confirm with --yes.")
    return typer.confirm(question)

def _exit_on_signal(signum, frame):
    # Default SIGTERM/SIGHUP handling kills Python without running cleanup: interrupted
    # backups left GB-sized temp dirs and their docker children kept running.
    raise SystemExit(128 + signum)

def main():
    import signal
    import sys

    from . import installation_locks
    if sys.argv[1:2] not in ([], ["tui"]):  # Textual handles its own signals
        for sig in (signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, _exit_on_signal)
    try:
        # Also cover python -m ...cli and previously generated cli:main console wrappers.
        # The new bootstrap takes this lease before importing the CLI at all.
        installation_locks.acquire_usage()
        if len(sys.argv)==1:
            if sys.stdin.isatty() and sys.stdout.isatty():
                _dashboard()
            else: app(args=["--help"])
        else: app()
    except c.PrerequisiteError as exc:  # its own exit status (see doctor --help)
        typer.secho(f"Error: {exc}",fg=typer.colors.RED,err=True)
        raise SystemExit(exc.exit_code)
    except (c.SandboxError, installation_locks.Error) as exc:
        typer.secho(f"Error: {exc}",fg=typer.colors.RED,err=True)
        raise SystemExit(2)
    except OSError as exc:  # e.g. permission denied in a target: a message, not a traceback
        typer.secho(f"Error: {exc}",fg=typer.colors.RED,err=True)
        raise SystemExit(2)

if __name__=="__main__": main()
