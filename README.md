# Wine Game Installer

A simple graphical tool to install Windows games on **Steam Deck** (and any Linux desktop with KDE) using Wine — without needing to touch the terminal.

Designed for installing games from repacks (FitGirl, DODI, etc.) or any standard Windows installer `.exe`, with automatic dependency setup and optional Steam shortcut creation with GE-Proton.

---

## Why is this useful?

Installing Windows games on Steam Deck via Wine normally requires running several terminal commands, knowing which Wine runner to use, manually creating a Wine prefix, installing C++ runtimes, and configuring Steam shortcuts by hand.

This tool wraps all of that into a single graphical interface — useful especially in Desktop Mode where typing long commands without a physical keyboard is painful.

---

## Requirements

- Steam Deck (SteamOS) or any Linux with KDE
- [Lutris](https://lutris.net/) (Flatpak) installed with at least one Wine runner downloaded
- Python 3 (pre-installed on SteamOS)
- Internet connection (for GE-Proton download if not already installed)

---

## Installation

```bash
git clone https://github.com/your-username/wine-game-installer /tmp/wine-game-installer
xdg-open /tmp/wine-game-installer
```

Then double-click `install.sh` in the file manager → click **Execute**.

This will:
- Copy the app to `~/Applications/`
- Add a shortcut in the KDE application menu under **Games**

Launch it from: **Applications menu → Games → Wine Game Installer**

---

## How to use

1. **Select your installer** — click Browse and pick the setup `.exe` (FitGirl repack or any Windows installer)
2. **Enter a slug** — a short folder name for the game, e.g. `clair-obscur-33`
3. **Copy the install path** — when the installer window opens, paste the suggested path (`C:\Program Files\slug`) as the destination directory
4. **Click Install** — the app sets everything up and launches the installer
5. **Complete the installation** in the installer window that opens
6. **Add a Steam shortcut** (optional) — once installation is done, browse to the game `.exe` and click Add to Steam

---

## What the script does, in order

1. Creates a dedicated Wine prefix at `~/Games/<slug>/`
2. Initializes the prefix with `wineboot`
3. Installs **vcrun2022** (Microsoft Visual C++ Runtime) into the prefix via winetricks
4. Launches the installer `.exe` and waits for it to finish
5. Once the installer closes, shows the Steam shortcut section
6. If "Add to Steam" is selected:
   - Checks if the latest **GE-Proton** is installed — downloads and installs it automatically if not
   - Adds the game shortcut to Steam with GE-Proton set as the compatibility tool
7. Displays a completion message

---

## Notes

- The Wine runner used for installation is `wine-staging` from Lutris runners. The game itself runs via GE-Proton through Steam.
- vcrun2022 covers all Microsoft Visual C++ runtimes from 2015 to 2022 — this resolves the majority of C++ runtime errors on launch.
- The suggested install path (`C:\Program Files\slug`) is a recommendation — you can install wherever you want, just remember the path when selecting the game `.exe` afterward.
- After adding a Steam shortcut, **restart Steam** for the shortcut to appear.

---

## License

MIT
