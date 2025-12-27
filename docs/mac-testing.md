# Testing PHYS 2150 Measurement Suite App on Mac (Offline Mode)

This guide is for UI testing on Mac. In the lab, students will use the installed launcher application—no command line needed.

## Prerequisites

Install the `uv` package manager by opening Terminal and running:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Close and reopen Terminal after installation.

## Setup

1. Download the latest release ZIP from: https://github.com/UCBoulder/PHYS-2150/releases

2. Unzip the downloaded file

3. Open Terminal and navigate to the unzipped folder:
   ```bash
   cd ~/Downloads/PHYS-2150-X.Y.Z   # adjust path as needed
   ```

4. Install dependencies and activate the environment:
   ```bash
   uv sync
   source .venv/bin/activate
   ```

## Running the Launcher

```bash
python launcher.py
```

This opens the same launcher interface students will use in the lab.

**Important:** Before clicking EQE or I-V, press **Ctrl+Shift+D** (or **Cmd+Shift+D** on Mac) to enable offline mode. You'll see a confirmation that offline mode is enabled. Then click the app button to launch.

## Running Apps Directly (Alternative)

You can also run apps directly from the command line with offline mode:

```bash
python -m eqe --offline    # EQE Measurement
python -m jv --offline     # I-V Measurement
```

## Keyboard Shortcuts

All shortcuts work with either **Ctrl+Shift** or **Cmd+Shift** on Mac.

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

- If you close Terminal and return later, navigate to the folder and run `source .venv/bin/activate` again
- Use `--theme light` flag for light mode when running apps directly
