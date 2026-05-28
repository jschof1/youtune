# Release checklist

Use this checklist whenever publishing youtune so PyPI, piwheels, GitHub, and Homebrew stay in sync.

## 1. Version consistency

Update these together:

- `pyproject.toml` → `project.version`
- `youtune/__init__.py` → `__version__`
- `CHANGELOG.md` → add a dated entry for the same version
- `README.md` → update any literal `youtune v...` examples

Then run:

```bash
python -m pytest -q
python -m build
python -m twine check dist/*
```

The test suite includes version consistency checks, so a missed local version reference should fail CI.

## 2. GitHub release

Create and push a signed tag:

```bash
git tag -s vX.Y.Z -m "youtune X.Y.Z"
git push origin vX.Y.Z
```

Publishing a GitHub release from that tag triggers the PyPI workflow in this repository.

## 3. PyPI

Preferred path: use GitHub Trusted Publishing via `.github/workflows/publish.yml`.

One-time PyPI setup:

- Add this GitHub repository as a trusted publisher for the `youtune` PyPI project.
- Workflow name: `publish.yml`
- Environment: `pypi`

Manual fallback:

```bash
python -m build
python -m twine check dist/*
python -m twine upload dist/*
```

After upload, verify:

- https://pypi.org/project/youtune/
- https://www.piwheels.org/project/youtune/

piwheels mirrors PyPI automatically; it is not published separately.

## 4. Homebrew

If youtune is distributed from a tap, update the tap formula after the PyPI sdist is live.
Use `packaging/homebrew/youtune.rb.template` as the starting point for the tap formula.

Get the sdist URL and checksum:

```bash
curl -L -o youtune-X.Y.Z.tar.gz https://files.pythonhosted.org/packages/source/y/youtune/youtune-X.Y.Z.tar.gz
shasum -a 256 youtune-X.Y.Z.tar.gz
```

Update the tap formula:

- `url` points at the new PyPI sdist
- `sha256` matches the downloaded sdist
- Python resource blocks are refreshed if dependencies changed

Validate locally from the tap:

```bash
brew audit --strict --online youtune
brew test youtune
brew install youtune
youtune --version
```

## 5. Post-release smoke checks

```bash
python -m venv /tmp/youtune-smoke
/tmp/youtune-smoke/bin/python -m pip install --upgrade pip
/tmp/youtune-smoke/bin/python -m pip install youtune
/tmp/youtune-smoke/bin/youtune --version
/tmp/youtune-smoke/bin/youtune search "Rick Astley - Never Gonna Give You Up"
```

Also verify the Homebrew install path if a tap formula was updated:

```bash
brew reinstall youtune
youtune --version
```
