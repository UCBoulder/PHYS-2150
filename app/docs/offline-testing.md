# Testing PHYS 2150 Measurement Suite (Offline Mode)

This guide is for UI testing without lab hardware. In the lab, students use the installed launcher application—no command line needed.

## Prerequisites

Install the `uv` package manager:

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Mac/Linux (Terminal):**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Close and reopen your terminal after installation.

## Setup

1. Download the latest release ZIP from: https://github.com/UCBoulder/PHYS-2150/releases

2. Unzip the downloaded file

3. Open a terminal and navigate to the unzipped folder:

   **Windows (PowerShell):**
   ```powershell
   cd ~\Downloads\PHYS-2150-X.Y.Z   # adjust path as needed
   ```

   **Mac/Linux:**
   ```bash
   cd ~/Downloads/PHYS-2150-X.Y.Z   # adjust path as needed
   ```

4. Install dependencies:
   ```bash
   uv sync
   ```

## Running the Launcher

```bash
uv run python launcher.py
```

This opens the same launcher interface students use in the lab.

**Important:** Before clicking EQE or I-V, press **Ctrl+Shift+D** (or **Cmd+Shift+D** on Mac) to enable offline mode. You'll see a confirmation that offline mode is enabled. Then click the app button to launch.

## Running Apps Directly (Alternative)

You can also run apps directly from the command line with offline mode:

```bash
uv run python -m eqe --offline    # EQE Measurement
uv run python -m jv --offline     # I-V Measurement
```

## Keyboard Shortcuts

All shortcuts use **Ctrl+Shift** on Windows/Linux or **Cmd+Shift** on Mac.

### Launcher Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl/Cmd+Shift+D | Toggle offline mode (enable before launching EQE or I-V!) |
| Ctrl/Cmd+Shift+T | Toggle terminal window visibility |
| Ctrl/Cmd+Shift+C | Toggle dark/light theme |
| E | Launch EQE app |
| I | Launch I-V app |

### In-App Shortcuts (EQE & I-V)

| Shortcut | Action | Description |
|----------|--------|-------------|
| Ctrl/Cmd+Shift+T | Toggle Console | Shows application logs and debug messages |
| Ctrl/Cmd+Shift+D | Toggle Debug Mode | Captures Python `print()` statements to the console |
| Ctrl/Cmd+Shift+E | Toggle Analysis Panel | Staff-only panel for advanced analysis |
| Ctrl/Cmd+Shift+L | Toggle Log Viewer | Opens full session log in a modal window |
| Ctrl/Cmd+Shift+C | Toggle Theme | Switch between dark and light mode |

## Notes

- Use `--theme light` flag for light mode when running apps directly
