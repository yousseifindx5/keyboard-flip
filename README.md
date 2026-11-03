# Keyboard Flip

**Typed in the wrong keyboard language? Fix it in one keystroke.**

Select the text, press a shortcut, and Keyboard Flip converts it in place, like `hello` → `اثممخ` and back again. It is not a translator: it re-types the same key presses on another keyboard layout.

Free, open source, and runs fully offline. Windows 10 / 11.

<!-- Add a screenshot: put an image in docs/screenshot.png and uncomment the next line -->
<!-- ![Keyboard Flip](docs/screenshot.png) -->

## Download

1. Go to the [latest release](../../releases/latest).
2. Download **KeyboardFlip_Setup.exe** and run it.

If Windows shows *"Windows protected your PC"*, click **More info**, then **Run anyway**. The app is new and not code-signed yet, and all of the source is here for you to read.

## How it works

1. Select the text you typed in the wrong language. (Nothing selected? It converts the last word.)
2. Press your shortcut.
3. The text is replaced where it was, and your clipboard is restored.

Converted by mistake? Press the undo shortcut.

## Features

- **6 languages:** Arabic, English, German, French, Spanish, Russian
- **Keyboard layouts:** choose the layout you type on (for example English US/UK, Arabic 101/102, Spanish Spain/Latin America)
- **Up to 10 shortcuts:** one per direction, each with its own key combination
- **Both ways:** one shortcut that detects the direction (between languages with different alphabets)
- **Convert last word** when nothing is selected
- **Undo** the last conversion
- **Excluded programs:** never convert inside apps you choose
- **System tray app**, optional start with Windows, light and dark themes, English and Arabic interface
- **Private:** no internet access, no telemetry

### Default shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl` + `Alt` + `L` | English → Arabic |
| `Ctrl` + `Alt` + `K` | Arabic → English |
| `Ctrl` + `Alt` + `Z` | Undo last conversion |

You can change all of them inside the app.

## Run from source

Requires Windows and Python 3.10 or newer.

```bat
pip install -r requirements.txt
python main.py
```

Or double-click `run_dev.bat`.

## Build the installer

Double-click **`build.bat`**. It installs the build tools, builds `KeyboardFlip.exe` with PyInstaller, and creates the installer with Inno Setup (it installs Inno Setup with `winget` if needed).

The result is `installer_output\KeyboardFlip_Setup.exe`. The installer also creates the uninstaller (Settings → Apps → Keyboard Flip).

Leftovers from old script versions can be removed with `Remove_Old_Versions.bat`.

## Project structure

```
main.py                 entry point (tray icon, single instance)
keyboardflip/
  engine.py             shortcut → copy → convert → paste
  layouts.py            keyboard layouts and conversion logic
  winapi.py             Windows API: hotkeys, clipboard, key sending
  ui.py                 window (CustomTkinter)
  config.py, i18n.py    settings and interface texts
  log.py                writes errors to error.log
tests/                  unit tests for the conversion logic
assets/                 logo (icon.png, icon.ico)
website/                landing page (deployed on Vercel)
build.bat, installer.iss
```

To add or fix a keyboard layout, see `keyboardflip/layouts.py`.

## Good to know

- Programs running as **Administrator** ignore Keyboard Flip unless you run it as Administrator too.
- Only text on the clipboard is restored afterwards; copied images or files are not.
- The Arabic letters `لا` can be typed with one key or two, so Arabic → English picks the reading that looks most like English. It can be wrong on rare words.
- Settings are stored in `%APPDATA%\KeyboardFlip\config.json`. Errors are logged to `error.log` in the same folder.

## Contributing

Ideas, bug reports, and pull requests are welcome. Please open an [issue](../../issues) first for bigger changes.

Before sending a pull request, run the tests (they don't need Windows):

```bash
python -m unittest discover -s tests -v
```

If Keyboard Flip saves you time, a ⭐ on the repo is the nicest thank you.

## License

Keyboard Flip is free and open source, released under the [MIT License](LICENSE).

You are free to use, study, share, and modify it.
