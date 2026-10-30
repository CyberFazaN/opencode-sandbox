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
def opencode_versions(check: bool=typer.Option(False,"--check",help="Also query the npm registry: environments with the notify policy report available updates")):
    """OpenCode version and policy of every environment (running containers only; stopped ones are not started)."""
    from . import opencode_versions as v
    newest=v.latest() if check else None
    if newest: typer.echo(f"npm registry: {newest}")
    for item in v.versions():
        typer.echo(f"{item['name']}: {v.environment_line(item,newest)}")

@opencode_app.command("status")
def opencode_status(name: str):
    """OpenCode version running in one environment (a stopped container is not started)."""
    from . import opencode_versions as v
    typer.echo(v.environment_version(c.resolve(name)))

DISTRO_HELP="Distribution from the registry: "+", ".join(distros.REGISTRY)

@opencode_app.command("check")
def opencode_check(distro: str=typer.Option(distros.DEFAULT,"--distro",help=DISTRO_HELP)):
    """Compare a base image's OpenCode version with the newest release on the npm registry."""
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
def opencode_update_base(version: str=typer.Option("latest","--version",help="OpenCode 2.x version, or latest"), yes: bool=typer.Option(False,"--yes",help="Do not ask for confirmation"),
                         distro: str=typer.Option(distros.DEFAULT,"--distro",help=DISTRO_HELP)):
    """Rebuild a base image with another OpenCode version; keeps a rollback copy of the old one."""
    from . import opencode_versions as v
    image=distros.get(distro).image
    if not yes and not _confirm(f"Build, verify and replace base image {image} with OpenCode {version}?", docker=True):
        raise typer.Abort()
    typer.echo(v.update_base(version, distro))

@opencode_app.command("update")
def opencode_update(name: str, version: str=typer.Option("latest","--version",help="OpenCode 2.x version, or latest"), yes: bool=typer.Option(False,"--yes",help="Do not ask for confirmation")):
    """Update OpenCode in a stopped environment; on failure its system layer is rolled back to a checkpoint."""
    from . import opencode_versions as v
    m=c.resolve(name)
    typer.echo("Note: a checkpoint (docker commit) of the container's system layer is taken first; a failed update "
               "is rolled back to it, 'opencode rollback' undoes a successful one. /root and /workspace are not touched.")
    if not yes and not _confirm(f"Temporarily start stopped environment {name}, update OpenCode to {version}, then stop it?", docker=True):
        raise typer.Abort()
    result=v.update_environment(m,version)
    if result.get("unchanged"): typer.echo(f"OpenCode {result['version']} is already installed; nothing changed")
    else: typer.echo(f"Updated OpenCode {result['previous_version'] or 'unknown (opencode --version failed)'} -> {result['version']}; "
                     f"rollback point {result['checkpoint']}")

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
                                f"({record.get('to')} -> {record.get('from')})? The current system layer is kept as a snapshot.",
                                docker=True):
        raise typer.Abort()
    result=v.rollback_environment(m)
    typer.echo(f"Rolled back OpenCode {result['rolled_back_from']} -> {result['version']}"
               + (f"; previous system layer kept as {result['snapshot']}" if result["snapshot"] else ""))

@opencode_app.command("rollback-base")
def opencode_rollback_base(yes: bool=typer.Option(False,"--yes",help="Do not ask for confirmation"),
                           distro: str=typer.Option(distros.DEFAULT,"--distro",help=DISTRO_HELP)):
    """Swap a base image with its newest rollback copy (verified first); existing containers are not changed."""
    from . import opencode_versions as v
    image=distros.get(distro).image
    if not yes and not _confirm(f"Replace base image {image} with its newest rollback copy?", docker=True):
        raise typer.Abort()
    result=v.rollback_base(distro)
    typer.echo(f"{result['image']}: OpenCode {result['version']}"
               + (f"; replaced image kept as {result['previous_image']}" if result["previous_image"] else ""))

def pick(key:str | None):
    if key: return c.resolve(key)
    m=c.current_env()
    if not m: raise c.SandboxError("No environment bound to current directory. Supply NAME or ID.")
    return m

def msg(m): typer.echo(f"{m['name']} [{m['id']}] ({m['kind']})")

@app.command(rich_help_panel=HOST)
def build(distro: str=typer.Option(distros.DEFAULT,"--distro",help=DISTRO_HELP),
          opencode_version: str=typer.Option("latest","--opencode-version",help="OpenCode 2.x version (npm @opencode/cli)")):
    """Build or rebuild a distribution's agent image (requires rootless Docker)."""
    result=c.build(distro, opencode_version)
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

def _integration_hint(m):
    """After a failed, skipped or interrupted provisioning: how to add the integrations by hand."""
    from . import integrations
    result=(m.get("provisioning") or {}).get("result") or ""
    if result.startswith(("failed","skipped","interrupted")) or "failed" in result:
        lines=integrations.hint(m)
        if lines: typer.echo("To add them yourself (opencode-sandbox shell NAME):\n  "+"\n  ".join(lines))

def _integrations_help():
    from .integrations import CATALOG, DEFAULT
    return "; ".join(f"{i.name}{' (default)' if i.name in DEFAULT else ''}: {i.description}" for i in CATALOG.values())

WORKSPACE_PANEL, IMAGE_PANEL, INTEGRATIONS_PANEL = "Workspace", "Distribution or image", "Integrations (set up once at the first start)"
INTEGRATION=typer.Option(None,"--integration",rich_help_panel=INTEGRATIONS_PANEL,help="Integration from the catalog to set up once at the first start (repeatable; replaces the default). Catalog: "+_integrations_help())
NO_INTEGRATIONS=typer.Option(False,"--no-integrations",rich_help_panel=INTEGRATIONS_PANEL,help="Set up no integrations (opt out of the default context7)")
MCP_REMOTE=typer.Option(None,"--mcp-remote",rich_help_panel=INTEGRATIONS_PANEL,help="Custom remote MCP server NAME=URL, set up once (repeatable)")
MCP_LOCAL=typer.Option(None,"--mcp-local",rich_help_panel=INTEGRATIONS_PANEL,help="Custom local MCP server 'NAME=COMMAND ARGS', set up once (repeatable)")

def _distro_help():
    return "; ".join(f"{d.id}: {d.name} {d.version}{' (default)' if d.id==distros.DEFAULT else ''}" for d in distros.REGISTRY.values())

@app.command(rich_help_panel=ENVIRONMENTS)
def create(name:str,
           source:Path | None=typer.Option(None,"--source",help="Folder to copy into the workspace: a Git repository root is cloned (committed files only), other folders are copied without hidden files"),
           kind:str | None=typer.Option(None,"--kind",help="scratch (empty workspace) | project (a copy of --source) | quick (disposable). Default: project with --source or a direct workspace, otherwise scratch"),
           profile:str=typer.Option("default","--profile",help="Provider profile (see: providers list)"),
           distro:str | None=typer.Option(None,"--distro",rich_help_panel=IMAGE_PANEL,help="Base definitions: "+_distro_help()),
           image:str | None=typer.Option(None,"--image",rich_help_panel=IMAGE_PANEL,help="Custom image instead of a distribution (no tool or OS claims in Agent Context)"),
           workspace_mode:str=typer.Option("managed","--workspace-mode",rich_help_panel=WORKSPACE_PANEL,help="managed (default: empty or a copy of --source) | direct (not recommended: the agent works in your host folder itself)"),
           workspace:Path | None=typer.Option(None,"--workspace",rich_help_panel=WORKSPACE_PANEL,help="Existing host folder to mount as /workspace with --workspace-mode direct"),
           yes:bool=typer.Option(False,"--yes",rich_help_panel=WORKSPACE_PANEL,help="Consent to a direct workspace and its preflight without asking"),
           integration:list[str]=INTEGRATION, no_integrations:bool=NO_INTEGRATIONS,
           mcp_remote:list[str]=MCP_REMOTE, mcp_local:list[str]=MCP_LOCAL):
    """Create an environment: an empty scratch workspace, or a copy of a folder with --source.

    Without options: the default distribution and integrations. The original folder is never touched. Integrations are written once into the environment's OpenCode config at the first start and then belong to you (never re-applied or checked)."""
    from . import integrations
    from .config_plan import check_profile
    if integration and no_integrations: raise typer.BadParameter("--integration and --no-integrations exclude each other")
    check_profile(profile)  # as config apply: a mistyped name would leave the container without credentials
    provisioning=integrations.request([] if no_integrations else (integration or None),
                                      integrations.parse_custom(mcp_remote or (), mcp_local or ()))
    kind,_=c.creation_options(name,kind,source,distro=distro,image=image,workspace_mode=workspace_mode,workspace=workspace)
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
    m=c.create(name,kind,source,profile,distro=distro,image=image,workspace_mode=workspace_mode,
               workspace=workspace,consent=consent,provisioning=provisioning)
    msg(m)
    typer.echo(f"Workspace: {workspaces.describe(m)}\n"
               f"Distribution: {c.distribution_description(m)}\n"
               f"Provider profile: {m['profile']}\n"
               f"Integrations (set up once at the first start): {', '.join(provisioning['requested']) or 'none'}\n"
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

config_app=typer.Typer(help="Environment settings: resource limits, network, published ports, provider profile (show, plan, apply, recover).",no_args_is_help=True)
app.add_typer(config_app,name="config",rich_help_panel=DATA)

def _config_changes(cpus, memory, pids, network, publish, no_ports, profile):
    """Only the options given; config_plan merges them with the current values."""
    from .config_plan import parse_ports
    if publish and no_ports: raise typer.BadParameter("--publish and --no-ports exclude each other")
    ports=[] if no_ports else (parse_ports(publish) if publish else None)
    return {k: v for k, v in (("cpus", cpus), ("memory", memory), ("pids", pids), ("network", network),
                              ("ports", ports), ("profile", profile)) if v is not None}

CPUS=typer.Option(None,"--cpus",help="CPU limit")
MEMORY=typer.Option(None,"--memory",help="Memory limit, e.g. 8g")
PIDS=typer.Option(None,"--pids",help="Process limit")
NETWORK=typer.Option(None,"--network",help="bridge or none")
PUBLISH=typer.Option(None,"--publish",help="HOST:CONTAINER or HOST:CONTAINER/udp (default tcp); binds to 127.0.0.1; replaces all mappings")
NO_PORTS=typer.Option(False,"--no-ports",help="Remove all published ports")
PROFILE=typer.Option(None,"--profile",help="Provider profile")

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
                        profile: str | None = PROFILE, as_json: bool = typer.Option(False, "--json", help="Print the plan as JSON")):
    """Show what a change would do (category, steps, warnings) without changing anything."""
    from . import config_plan as cp
    p=cp.plan(c.resolve(name),_config_changes(cpus,memory,pids,network,publish,no_ports,profile))
    typer.echo(json.dumps(p.as_dict(),indent=2) if as_json else cp.describe(p))
    if p.blockers: raise typer.Exit(1)

@config_app.command("apply")
def config_apply(name: str, cpus: float | None = CPUS, memory: str | None = MEMORY, pids: int | None = PIDS,
                 network: str | None = NETWORK, publish: list[str] = PUBLISH, no_ports: bool = NO_PORTS,
                 profile: str | None = PROFILE, yes: bool = typer.Option(False, "--yes", help="Apply without asking")):
    """Plan and apply a change. Changes that stop or recreate a container ask first (or need --yes)."""
    from . import config_plan as cp
    m=c.resolve(name)
    changes=_config_changes(cpus,memory,pids,network,publish,no_ports,profile)
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
    """Execute a command: exec NAME -- command \\[args]. Provider profile and Agent Context are NOT applied; use run for OpenCode."""
    if not ctx.args: raise c.SandboxError("Missing command")
    if Path(ctx.args[0]).name=="opencode":
        typer.secho(f"Note: generic exec does not load the provider profile or Agent Context; use 'opencode-sandbox run {name}' for managed OpenCode.",
                    fg=typer.colors.YELLOW,err=True)
    raise typer.Exit(c.exec_cmd(c.resolve(name),ctx.args))

@app.command(rich_help_panel=ENVIRONMENTS)
def start(name:str):
    """Start or create the persistent container (the first start sets up the requested integrations once)."""
    provisioned=c.start(c.resolve(name))
    if provisioned:
        typer.echo(f"Initial integrations: {provisioned}")
        _integration_hint(c.resolve(name))

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
    record=m.get("provisioning") or {}
    if record.get("requested"):
        state=record.get("result") if record.get("state")=="done" else "pending (first start)"
        typer.echo(f"Initial integrations (history, not current state): {', '.join(record['requested'])}: {state}")
        if record.get("state")=="done": _integration_hint(m)
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
    existing=c.profile_read(name)
    existing[key]=typer.prompt("Secret value",hide_input=True)
    c.profile_set(name,existing)
    typer.echo(f"Stored {key} in profile {name}. Containers using this profile see the change after a restart.")

@app.command(rich_help_panel=SESSIONS)
def tui():
    """Open the dashboard (also: opencode-sandbox without arguments in a terminal)."""
    if not c._tty():
        raise c.SandboxError("the dashboard needs an interactive terminal; in scripts use the commands (see --help)")
    from .tui import Dashboard
    Dashboard().run()

ORDER=("create","list","status","check","start","stop","promote","delete","run","shell","exec","quick","tui",
       "config","changes","backup","container","agent-context","providers","repair","opencode","disk","build","doctor")


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
    if sys.argv[1:2] not in ([], ["tui"]):  # Textual handles its own signals
        for sig in (signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, _exit_on_signal)
    try:
        if len(sys.argv)==1:
            if sys.stdin.isatty() and sys.stdout.isatty():
                from .tui import Dashboard
                Dashboard().run()
            else: app(args=["--help"])
        else: app()
    except c.PrerequisiteError as exc:  # its own exit status (see doctor --help)
        typer.secho(f"Error: {exc}",fg=typer.colors.RED,err=True)
        raise SystemExit(exc.exit_code)
    except c.SandboxError as exc:
        typer.secho(f"Error: {exc}",fg=typer.colors.RED,err=True)
        raise SystemExit(2)
    except OSError as exc:  # e.g. permission denied in a target: a message, not a traceback
        typer.secho(f"Error: {exc}",fg=typer.colors.RED,err=True)
        raise SystemExit(2)

if __name__=="__main__": main()
