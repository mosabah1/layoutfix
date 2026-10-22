# layoutfix

**[العربية](README.ar.md)** · English

Fix text typed with the wrong keyboard layout. One shortcut, converted in place.

```
hgsghl ugd;l     →   السلام عليكم
اثممخ            →   hello
```

You type fast, you look up, and the language was wrong. Instead of deleting the
whole line and retyping it, press **Ctrl+Alt+L**.

---

## Install

1. Download `layoutfix.exe` from the [latest release](../../releases/latest).
2. Put it anywhere you like and double-click it.
3. A tray icon appears near the clock. That's it — no installer, no Python.

To have it start with Windows: right-click the tray icon → **تشغيل مع ويندوز**.

### Windows will warn you the first time

The executable is not code-signed (a certificate costs a few hundred dollars a
year), so Windows SmartScreen shows **"Windows protected your PC"**. Click
**More info → Run anyway**.

Some antivirus engines may also flag it. That is expected for this kind of
tool — it sends keystrokes and reads the clipboard, which is exactly what a
keylogger does. The difference is in what it *doesn't* do; see
[Is it safe?](#is-it-safe) below. If you'd rather not trust a binary, the
source is here and [building it yourself](#build-from-source) takes one command.

---

## Use

| Situation | What to press |
|---|---|
| Text is selected | **Ctrl+Alt+L** — converts the selection |
| Nothing selected | **Ctrl+Alt+L** — converts the current line up to the caret |
| English word containing `gh` (light, right, through) | **Ctrl+Alt+Shift+L** — see [the one ambiguity](#the-one-ambiguity) |

The direction is detected automatically: Arabic text becomes English and
English text becomes Arabic. After converting, the keyboard input language is
switched to match, so you can keep typing without thinking about it.

Works in anything that supports Ctrl+C / Ctrl+V — browsers, Word, WhatsApp,
Telegram, VS Code.

---

## Settings

Right-click the tray icon → **فتح ملف الاعدادات**, or edit:

```
%APPDATA%\layoutfix\settings.ini
```

| Key | Default | Meaning |
|---|---|---|
| `hotkey` | `ctrl+alt+l` | The main shortcut |
| `hotkey_alt` | `ctrl+alt+shift+l` | Same, but splits `لا` into `g`+`h` |
| `switch_layout` | `true` | Switch input language after converting |
| `fallback_line` | `true` | Convert the current line when nothing is selected |
| `notify` | `true` | Explain failures in a notification instead of a beep |
| `debug` | `false` | Write `layoutfix.log` next to the settings file |

Save the file and restart the tool to apply.

**Portable mode:** put a `settings.ini` next to `layoutfix.exe` and it is used
instead, so the tool can live on a USB stick with its configuration.

---

## Is it safe?

Fair question for a tool that types for you. What it actually does:

- **It does not hook the keyboard.** There is no `WH_KEYBOARD_LL` hook, no
  keystroke buffer, nothing recording what you type. It registers two global
  hotkeys with `RegisterHotKey` and sleeps until one of them is pressed.
- **It reads text only when you press the shortcut**, by sending Ctrl+C to the
  focused window — the same copy you would do yourself.
- **It writes nothing to disk** unless you set `debug = true` yourself, and then
  only to a local log file you can read and delete.
- **It makes no network connections.** There is no update check, no telemetry,
  nothing to send anywhere.
- **Your clipboard is restored** after every conversion, including on failure.

The whole thing is one readable Python file with no third-party dependencies —
standard library and the Windows API, nothing else. Read it in an afternoon.

---

## The one ambiguity

`لا` is produced by two different keystrokes: the `b` key (which types it as a
single ligature) and the sequence `g` then `h` (ل + ا). On screen they are
identical, so the original keystrokes cannot be recovered with certainty.

The default resolves it to `b`, because the letter `b` is roughly twenty times
more frequent in English than the `gh` bigram. So `مهلاف` becomes `libt`.
For those words press **Ctrl+Alt+Shift+L** instead and you get `light`.

This is not a bug, and it is not fixable without a dictionary.

---

## Troubleshooting

The tool explains failures in a notification naming the program it was acting on:

| Message | Meaning |
|---|---|
| لم أتمكن من قراءة النص | The program didn't respond to Ctrl+C, or it runs elevated |
| لا شيء للتحويل | Text was read but converting doesn't change it (digits, symbols) |
| الحافظة مشغولة | Another program is holding the clipboard |

For more detail, set `debug = true` in the settings file and restart. The log
lands next to the settings file and records the target program, how many
characters were copied, and whether Windows blocked the input.

**If the target program runs as Administrator and layoutfix doesn't**, Windows
blocks all synthetic input to it (UIPI). Run layoutfix as Administrator too.

---

## Build from source

Needs Python 3.9+ on Windows. No third-party packages to run it; PyInstaller
and Pillow only to build the executable and its icon.

```bat
pip install pyinstaller pillow
build.cmd
```

The result is `dist\layoutfix.exe`. Or just run it directly:

```bat
pythonw layoutfix.py
```

### Tests

```bat
python layoutfix.py --selftest      ; the layout map, both directions
python test_clipboard_race.py       ; capturing the selection
python layoutfix.py --check         ; hotkey, tray icon, clipboard, Win32 structs
```

`test_clipboard_race.py` covers the hardest part of this tool — reading the
selected text. Three real bugs lived there, all of them now regression-tested:

1. **The modifier keys are still held down.** The hotkey fires while your
   fingers are still on `Ctrl+Alt`, so the target receives `Ctrl+Alt+C`. A
   synthetic keyup does not clear the physical key state — you have to wait for
   the user to actually let go (`GetAsyncKeyState`).
2. **Scan code zero.** Chrome and Electron apps ignore synthetic key events that
   arrive without a scan code, so they are filled in from `MapVirtualKeyW`, with
   `KEYEVENTF_EXTENDEDKEY` for `Home`/`End`.
3. **`GetClipboardSequenceNumber` alone is not enough.** It increments on
   `EmptyClipboard` — *before* the application writes the text — so you read an
   empty clipboard and give up. Worse, you can read the user's *previous*
   clipboard content and mistake it for the selection. A sentinel string written
   before Ctrl+C removes both failures: if the sentinel is still there, nothing
   was copied, and stale content cannot come back because it was overwritten.

---

## Layout map

Based on the standard Windows **Arabic 101** layout against **US QWERTY**.
Covers letters, Shift diacritics, Arabic punctuation (`،` `؛` `؟`), the mirrored
parentheses, and Arabic-Indic digits (`٠١٢٣` → `0123`).

Adding another layout is mostly a matter of adding a table like `EN_TO_AR`;
pull requests welcome.

---

## License

MIT — see [LICENSE](LICENSE).
