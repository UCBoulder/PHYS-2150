---
name: release
description: Create a new release of the PHYS 2150 Measurement Suite
argument-hint: "[version]"
disable-model-invocation: true
---

# Release Process for PHYS 2150 Measurement Suite

Create a new release with version `$ARGUMENTS` (if provided) or determine the appropriate version bump.

## Version Number Management

**CRITICAL:** The version number must be updated in multiple places:

- **`app/pyproject.toml`**: `[project].version = "X.Y.Z"` - Python package version
- **`app/build/installer.iss`**: `#define MyAppVersion "X.Y.Z"` - Installer metadata

The launcher reads the version from `importlib.metadata.version("phys2150")`, which gets embedded by PyInstaller from `pyproject.toml`. You **must rebuild the PyInstaller executable** after updating `pyproject.toml`, not just the installer.

## Version Bump Rules

- **MAJOR** (X.0.0): Incompatible API changes or breaking architectural changes
- **MINOR** (x.Y.0): Backward-compatible new functionality
- **PATCH** (x.y.Z): Backward-compatible bug fixes

## Release Steps

### 1. Ensure develop is up to date and tested

```bash
git checkout develop
git pull
```

### 2. Merge develop into main

```bash
git checkout main
git merge develop
```

### 3. Update version numbers

```bash
# Edit app/pyproject.toml: set version = "X.Y.Z"
# Edit app/build/installer.iss: set MyAppVersion "X.Y.Z"
git add app/pyproject.toml app/build/installer.iss
```

### 4. Update app/CHANGELOG.md

- Move [Unreleased] content to new version section `## [X.Y.Z] - YYYY-MM-DD`
- Add release date (ISO 8601 format)
- Update comparison links at bottom:
  ```
  [Unreleased]: https://github.com/UCBoulder/PHYS-2150/compare/vX.Y.Z...HEAD
  [X.Y.Z]: https://github.com/UCBoulder/PHYS-2150/compare/vPREVIOUS...vX.Y.Z
  ```
- Update version history summary table

### 5. Commit version changes and create tag

```bash
git add app/CHANGELOG.md
git commit -m "Release vX.Y.Z"
git tag -a vX.Y.Z -m "Version X.Y.Z - brief description"
git push origin main --tags
```

### 6. Create GitHub Release

Use standardized format — title: `PHYS 2150 vX.Y.Z`, body: highlights + CHANGELOG link:

```bash
gh release create vX.Y.Z --title "PHYS 2150 vX.Y.Z" --notes "$(cat <<'EOF'
## Highlights
- Bullet point summary of key changes (3-5 bullets)
- Focus on what matters to users, not implementation details
- Group related changes into single bullets

See [CHANGELOG](app/CHANGELOG.md) for full details.
EOF
)"
```

### 7. Build and upload installer

**Important:** Build PyInstaller executable FIRST (to embed correct version metadata), THEN build the installer. Run from the `app/` directory:

```bash
cd app

# Step 1: Build PyInstaller executable (embeds version from pyproject.toml)
rm -rf dist/PHYS2150
uv run pyinstaller build/phys2150.spec

# Step 2: Build Inno Setup installer (uses version from installer.iss)
# If iscc is in PATH:
iscc build/installer.iss
# Or use full path:
# "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" build\installer.iss

# Step 3: Upload installer to GitHub Release
gh release upload vX.Y.Z "dist/PHYS2150-Setup.exe" --clobber
```

**Why this order matters:**
- PyInstaller embeds package metadata from `pyproject.toml` into the executable
- The launcher reads version via `importlib.metadata.version("phys2150")`
- If you only rebuild the installer without rebuilding PyInstaller, the launcher will show the old version
- Inno Setup just packages the PyInstaller output, so the executable must be built first

### 8. Merge release commit back to develop

```bash
git checkout develop
git merge main
git push origin develop
```

### 9. Commit uv.lock if changed

```bash
# Check if uv.lock was updated during the build
git status
git add app/uv.lock
git commit -m "Update uv.lock for vX.Y.Z"
git push origin develop
git checkout main
git merge develop
git push origin main
git checkout develop
```

## Version Display Checklist

Before finalizing a release, verify the version appears correctly in:

- [ ] Installer title window (from `installer.iss`)
- [ ] Launcher app bottom-left corner (from `pyproject.toml` via PyInstaller metadata)
- [ ] Windows "Add/Remove Programs" list (from `installer.iss`)
- [ ] GitHub Release page
- [ ] app/CHANGELOG.md

## Known Issue: Metadata Caching on Upgrade

**Problem:** When installing a new version over an existing installation, the launcher may display the old version number even though Windows shows the correct version in "Add/Remove Programs".

**Root Cause:** Python package metadata (`.dist-info` directories) from the old installation may not be fully replaced during upgrade, causing `importlib.metadata` to read stale version information.

**Solution:** If the launcher shows an incorrect version after installation:
1. Uninstall the application completely
2. Reinstall using the new installer
3. The version should now display correctly

**Prevention:** The installer has been updated (v3.3.1+) to force complete removal of all application files during uninstall, which should prevent this issue in future upgrades. Users upgrading from older versions may still experience this once.
