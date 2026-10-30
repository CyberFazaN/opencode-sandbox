# Releasing

A release is a version tag `vX.Y.Z` on `main` and a GitHub Release whose notes are the version's
`CHANGELOG.md` section. Users install it with
`pipx install git+https://github.com/CyberFazaN/opencode-sandbox.git@vX.Y.Z` (D-042); nothing is
uploaded to a package index, and no wheels are attached. Only the maintainer creates tags.

## 1. Prepare the release branch

1. Branch `release/X.Y.Z` from `main`.
2. Set `__version__` in `src/opencode_sandbox/__init__.py` (the single source, D-001).
3. In `CHANGELOG.md`, rename "Unreleased" to `X.Y.Z — YYYY-MM-DD` and check the entries.
4. Replace the release tag in the install commands of `README.md` and `docs/install.md`
   (`@vX.Y.Z`); `tests/test_user_docs.py` fails until they name the new version.
5. Update the tested versions in `README.md` ("Tested environment") and `BASELINE.md`
   ("Supported environments") if the test platform changed.
6. If an image definition changed in a way that needs a rebuild (`image-revision` in
   `src/opencode_sandbox/distros.py`), say so in the CHANGELOG: existing base images are not
   rebuilt by an upgrade (`opencode-sandbox build`). Verify the shared `doctor`/dashboard
   revision warning and explicit rebuild hint (D-050); never require migrating existing
   containers just to clear a base-tag warning.

Historical PASS rows of an earlier release do not establish changed behaviour (for example a new
Python floor or base definition); verify the changed paths and the final release tree.

## 2. Verify

On the branch:

Run the suite and package checks on the lowest supported Python (3.11) and the current Arch
Python (CI also pins 3.14 as an explicit endpoint), with the current and the lowest direct
dependencies. Do not infer a full Docker/OpenCode campaign on every Python from those tests.
Run the suites serially and in the foreground: the host-process signal tests count every
session watchdog on the host and need a default SIGINT disposition (`TODO.md`).

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m build --outdir dist . && .venv/bin/twine check --strict dist/*
```

Then the real campaign on the maintainer's disposable Arch Linux VM (`CONTRIBUTING.md`):

For retained-OS compatibility (`test_12_image_compatibility.py`), install the previous release's
manager separately against a retained base of its definition and set `OCS_TEST_LEGACY_MANAGER`
to its launcher. Without it that row explicitly skips and cannot establish the compatibility
gate. To build and test new base images without replacing the user's base tags, run the
campaign against disposable installed test venvs whose site-packages carry a test-only hook
that sets `distros.REPOSITORY` to an `ocs-test-*` name from `OCS_TEST_IMAGE_REPOSITORY`; the
product has no such override and the hook must never ship. Run the both-image gates on the
selected release tree.

```sh
OCS_TEST_DOCKER=1 OCS_TEST_PRIVILEGED=1 OCS_TEST_PIPX_BUILD=1 \
  OCS_TEST_SOCKET_ACTIVATION=1 \
  .venv/bin/python -m pytest -rA tests/integration
```

C10's extra opt-in authorizes temporary `ocs-test-act-*` user units and a separate no-network
rootless daemon, not a restart of the existing daemon. It needs `dockerd-rootless.sh` and
`rootlesskit` on PATH, a working user systemd manager/runtime unit directory, and the existing
`ubuntu:24.04` custom-test image. The row re-establishes cold state before each manager call;
the campaign's initial doctor cannot count as cold-start evidence. Without this opt-in C10
skips and is not a PASS. `test_36_socket_activation.py` records and cleans only its named units,
runtime directory, isolated Docker objects and manager data; read its scope before granting it.

Also run the campaign against a pipx installation of a local test tag (`OCS_TEST_MANAGER`, see
`BASELINE.md`). Record the results in `BASELINE.md` ("Verification") and the status column of
`CAMPAIGN.md`. Release only when every P0 and P1 row is PASS with real evidence, or BLOCKED with
an accepted risk and a reproducible next step (`AGENTS.md`, "Release rule"). New defects: fix
them with a regression test and re-run the affected layers.

Before tagging, scan the tree for secrets and personal data: `gitleaks git` and `gitleaks dir`,
`detect-secrets scan --all-files` (the tests contain deliberate dummy values), and a search for
your home path, user and host names, private network addresses and e-mail addresses (only
rootlesskit's `10.0.2.2` and `example.invalid`/`example.org` addresses are expected).

## 3. Tag and publish

1. If CI job names changed since the last release, update the required status checks of the
   `main` ruleset first; otherwise the pull request waits for checks that no longer report.
   Merge the release branch into `main` with a merge commit; push `main` and wait for CI.
2. Create and push an annotated tag on that merge commit:

   ```sh
   git tag -a vX.Y.Z -m "OpenCode Sandbox X.Y.Z"
   git push origin vX.Y.Z
   ```

3. The release workflow (`.github/workflows/release.yml`) checks that the tag equals
   `__version__` and that `CHANGELOG.md` has the section, runs the CI checks against the tag,
   installs the tag with pipx, and creates a **draft** GitHub Release with the CHANGELOG section as
   its notes.
4. Review the draft and publish it.
5. Smoke test from GitHub in a clean environment:

   ```sh
   export PIPX_HOME="$(mktemp -d)" PIPX_BIN_DIR="$(mktemp -d)"
   pipx install git+https://github.com/CyberFazaN/opencode-sandbox.git@vX.Y.Z
   "$PIPX_BIN_DIR/opencode-sandbox" --version
   "$PIPX_BIN_DIR/opencode-sandbox" doctor
   ```

6. Add a new "Unreleased" section to `CHANGELOG.md` on `main`.

## A bad release

Never move or delete a published tag: pipx installations are pinned to it. Release a fixed
`X.Y.Z+1` instead, and add a warning to the bad release's notes that names the fixed version.
Users go back to an earlier release with `pipx install --force …@vOLDER`
([docs/install.md](../install.md#upgrade-or-change-the-version)).
