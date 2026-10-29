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
   rebuilt by an upgrade (`opencode-sandbox build`). A `doctor` warning for outdated base images
   is a deferred item (`TODO.md`) that should land before the first such release.

## 2. Verify

On the branch:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m build --outdir dist . && .venv/bin/twine check --strict dist/*
```

Then the real campaign on the maintainer's disposable Arch Linux VM (`CONTRIBUTING.md`):

```sh
OCS_TEST_DOCKER=1 OCS_TEST_PRIVILEGED=1 OCS_TEST_PIPX_BUILD=1 \
  .venv/bin/python -m pytest -rA tests/integration
```

and the campaign against a pipx installation of a local test tag (`OCS_TEST_MANAGER`, see
`BASELINE.md`). Record the results in `BASELINE.md` ("Verification") and the status column of
`CAMPAIGN.md`. Release only when every P0 and P1 row is PASS with real evidence, or BLOCKED with
an accepted risk and a reproducible next step (`AGENTS.md`, "Release rule"). New defects: fix
them with a regression test and re-run the affected layers.

Before tagging, scan the tree for secrets and personal data: `gitleaks git` and `gitleaks dir`,
`detect-secrets scan --all-files` (the tests contain deliberate dummy values), and a search for
your home path, user and host names, private network addresses and e-mail addresses (only
rootlesskit's `10.0.2.2` and `example.invalid`/`example.org` addresses are expected).

## 3. Tag and publish

1. Merge the release branch into `main` with a merge commit; push `main` and wait for CI.
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
