"""Thin Windows API layer built on ctypes.

The module can be imported on any OS (so the pure-Python parts can be tested),
but the functions only do real work on Windows.
"""
import ctypes
import os
import sys
import threading
import time
from ctypes import wintypes

IS_WIN = sys.platform == "win32"

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
WM_HOTKEY, WM_QUIT, WM_USER = 0x0312, 0x0012, 0x0400
CF_UNICODETEXT, GMEM_MOVEABLE = 13, 0x0002

VK_LSHIFT, VK_LCTRL = 0xA0, 0xA2
VK_C, VK_V, VK_Z = 0x43, 0x56, 0x5A
VK_LEFT, VK_RIGHT = 0x25, 0x27
MODIFIER_VKS = (0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C)
MENU_TRIGGER_VKS = (0xA4, 0xA5, 0x5B, 0x5C)  # Alt / Win tap would open a menu
EXTENDED_VKS = {0x25, 0x26, 0x27, 0x28, 0x21, 0x22, 0x23, 0x24, 0x2D, 0x2E,
                0x5B, 0x5C, 0xA3, 0xA5}

# --------------------------------------------------------------------------
# Hotkey names <-> virtual-key codes  (pure Python)
# --------------------------------------------------------------------------
_NAMED = {
    "space": 0x20, "tab": 0x09, "enter": 0x0D, "backspace": 0x08,
    "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
}
_OEM = {0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-", 0xBE: ".", 0xBF: "/",
        0xC0: "`", 0xDB: "[", 0xDC: "\\", 0xDD: "]", 0xDE: "'"}
_OEM_REV = {v: k for k, v in _OEM.items()}
_NAMED_REV = {v: k for k, v in _NAMED.items()}


def name_to_vk(name):
    name = name.strip()
    if len(name) == 1:
        c = name.upper()
        if "A" <= c <= "Z" or "0" <= c <= "9":
            return ord(c)
        return _OEM_REV.get(name)
    low = name.lower()
    if low.startswith("f") and low[1:].isdigit() and 1 <= int(low[1:]) <= 24:
        return 0x70 + int(low[1:]) - 1
    return _NAMED.get(low)


def vk_to_name(vk):
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        return chr(vk)
    if 0x70 <= vk <= 0x87:
        return "F%d" % (vk - 0x70 + 1)
    if vk in _NAMED_REV:
        return _NAMED_REV[vk]
    return _OEM.get(vk)


def parse_hotkey(text):
    """'ctrl+alt+L' -> (modifier_mask, vk) or None."""
    mods, vk = 0, None
    for part in (p.strip() for p in text.split("+")):
        low = part.lower()
        if not part:
            continue
        if low in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif low == "alt":
            mods |= MOD_ALT
        elif low == "shift":
            mods |= MOD_SHIFT
        elif low in ("win", "windows", "super"):
            mods |= MOD_WIN
        else:
            if vk is not None:
                return None
            vk = name_to_vk(part)
            if vk is None:
                return None
    if vk is None:
        return None
    return mods, vk


def normalize_hotkey(text):
    """Canonical form, so duplicates can be detected. '' if invalid."""
    parsed = parse_hotkey(text)
    if not parsed:
        return ""
    mods, vk = parsed
    parts = []
    if mods & MOD_CONTROL:
        parts.append("ctrl")
    if mods & MOD_ALT:
        parts.append("alt")
    if mods & MOD_SHIFT:
        parts.append("shift")
    if mods & MOD_WIN:
        parts.append("win")
    parts.append(vk_to_name(vk))
    return "+".join(parts)


# --------------------------------------------------------------------------
# ctypes structures
# --------------------------------------------------------------------------
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_void_p)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_void_p)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


if IS_WIN:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _P = ctypes.c_void_p
    U, D, B = wintypes.UINT, wintypes.DWORD, wintypes.BOOL

    def _sig(fn, argtypes, restype):
        fn.argtypes = argtypes
        fn.restype = restype

    _sig(user32.LoadKeyboardLayoutW, [wintypes.LPCWSTR, U], _P)
    _sig(user32.UnloadKeyboardLayout, [_P], B)
    _sig(user32.MapVirtualKeyExW, [U, U, _P], U)
    _sig(user32.MapVirtualKeyW, [U, U], U)
    _sig(user32.ToUnicodeEx, [U, U, ctypes.POINTER(ctypes.c_ubyte), wintypes.LPWSTR,
                              ctypes.c_int, U, _P], ctypes.c_int)
    _sig(user32.RegisterHotKey, [_P, ctypes.c_int, U, U], B)
    _sig(user32.UnregisterHotKey, [_P, ctypes.c_int], B)
    _sig(user32.GetMessageW, [ctypes.POINTER(wintypes.MSG), _P, U, U], ctypes.c_int)
    _sig(user32.PeekMessageW, [ctypes.POINTER(wintypes.MSG), _P, U, U, U], B)
    _sig(user32.PostThreadMessageW, [D, U, wintypes.WPARAM, wintypes.LPARAM], B)
    _sig(user32.OpenClipboard, [_P], B)
    _sig(user32.CloseClipboard, [], B)
    _sig(user32.EmptyClipboard, [], B)
    _sig(user32.GetClipboardData, [U], _P)
    _sig(user32.SetClipboardData, [U, _P], _P)
    _sig(user32.GetClipboardSequenceNumber, [], D)
    _sig(user32.SendInput, [U, ctypes.POINTER(INPUT), ctypes.c_int], U)
    _sig(user32.GetAsyncKeyState, [ctypes.c_int], ctypes.c_short)
    _sig(user32.GetForegroundWindow, [], _P)
    _sig(user32.GetWindowThreadProcessId, [_P, ctypes.POINTER(D)], D)
    _sig(user32.GetParent, [_P], _P)
    _sig(user32.GetWindowLongW, [_P, ctypes.c_int], ctypes.c_long)
    _sig(user32.SetWindowLongW, [_P, ctypes.c_int, ctypes.c_long], ctypes.c_long)

    _sig(kernel32.GlobalAlloc, [U, ctypes.c_size_t], _P)
    _sig(kernel32.GlobalLock, [_P], _P)
    _sig(kernel32.GlobalUnlock, [_P], B)
    _sig(kernel32.GlobalFree, [_P], _P)
    _sig(kernel32.GetCurrentThreadId, [], D)
    _sig(kernel32.OpenProcess, [D, B, D], _P)
    _sig(kernel32.QueryFullProcessImageNameW, [_P, D, wintypes.LPWSTR, ctypes.POINTER(D)], B)
    _sig(kernel32.CloseHandle, [_P], B)
    _sig(kernel32.CreateMutexW, [_P, B, wintypes.LPCWSTR], _P)
    _sig(kernel32.CreateEventW, [_P, B, B, wintypes.LPCWSTR], _P)
    _sig(kernel32.OpenEventW, [D, B, wintypes.LPCWSTR], _P)
    _sig(kernel32.SetEvent, [_P], B)
    _sig(kernel32.WaitForSingleObject, [_P, D], D)


# --------------------------------------------------------------------------
# Reading a Windows keyboard layout (used for layouts without a static table)
# --------------------------------------------------------------------------
# Scan codes in the same order as layouts.py: row0, row1(+backslash), row2, row3, ISO key
SCANCODES = (
    [0x29] + list(range(0x02, 0x0E)) +
    list(range(0x10, 0x1C)) + [0x2B] +
    list(range(0x1E, 0x29)) +
    list(range(0x2C, 0x36)) + [0x56]
)


def read_layout(klid):
    """Return (normal, shift) token lists for a Windows KLID, or None."""
    if not IS_WIN:
        return None
    hkl = user32.LoadKeyboardLayoutW(klid, 0x80)  # KLF_NOTELLSHELL, not activated
    if not hkl:
        return None
    try:
        layers = []
        for shifted in (False, True):
            state = (ctypes.c_ubyte * 256)()
            if shifted:
                state[0x10] = 0x80
                state[0xA0] = 0x80
            tokens = []
            for sc in SCANCODES:
                vk = user32.MapVirtualKeyExW(sc, 3, hkl)  # MAPVK_VSC_TO_VK_EX
                token = ""
                if vk:
                    buf = ctypes.create_unicode_buffer(8)
                    n = user32.ToUnicodeEx(vk, sc, state, buf, 8, 4, hkl)
                    if n > 0 and buf.value[:n] >= " ":
                        token = buf.value[:n]
                tokens.append(token)
            layers.append(tokens)
        return layers[0], layers[1]
    except Exception:
        return None
    finally:
        try:
            user32.UnloadKeyboardLayout(hkl)
        except Exception:
            pass


# --------------------------------------------------------------------------
# Global hotkeys (RegisterHotKey + message loop thread)
# --------------------------------------------------------------------------
class HotkeyListener:
    def __init__(self, on_hotkey):
        self.on_hotkey = on_hotkey
        self.failed = []
        self._thread = None
        self._tid = None

    def start(self, bindings):
        """bindings: list of (id, 'ctrl+alt+L')."""
        self.stop()
        self.failed = []
        if not IS_WIN or not bindings:
            return
        ready = threading.Event()

        def run():
            self._tid = kernel32.GetCurrentThreadId()
            msg = wintypes.MSG()
            user32.PeekMessageW(ctypes.byref(msg), None, WM_USER, WM_USER, 0)  # create queue
            registered = []
            for hid, text in bindings:
                parsed = parse_hotkey(text)
                if parsed and user32.RegisterHotKey(None, hid, parsed[0] | MOD_NOREPEAT, parsed[1]):
                    registered.append(hid)
                else:
                    self.failed.append(text)
            ready.set()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    try:
                        self.on_hotkey(int(msg.wParam))
                    except Exception:
                        pass
            for hid in registered:
                user32.UnregisterHotKey(None, hid)

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
        ready.wait(2)

    def stop(self):
        if self._thread and self._thread.is_alive() and IS_WIN:
            user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
            self._thread.join(1)
        self._thread = None


# --------------------------------------------------------------------------
# Clipboard
# --------------------------------------------------------------------------
def _open_clipboard(retries=15):
    for _ in range(retries):
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.005)
    return False


def clipboard_seq():
    return user32.GetClipboardSequenceNumber()


def get_clipboard_text():
    """Text on the clipboard, '' if there is none, None if it couldn't be opened."""
    if not _open_clipboard():
        return None
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def set_clipboard_text(text):
    data = (text + "\0").encode("utf-16-le")
    if not _open_clipboard():
        return False
    try:
        user32.EmptyClipboard()
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            return False
        ptr = kernel32.GlobalLock(handle)
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            return False
        return True
    finally:
        user32.CloseClipboard()


def wait_clipboard_change(seq, timeout):
    end = time.perf_counter() + timeout
    while time.perf_counter() < end:
        if clipboard_seq() != seq:
            return True
        time.sleep(0.003)
    return clipboard_seq() != seq


# --------------------------------------------------------------------------
# Sending keys
# --------------------------------------------------------------------------
def send_keys(events):
    """events: list of (vk, is_down) sent as one uninterrupted batch."""
    n = len(events)
    arr = (INPUT * n)()
    for i, (vk, down) in enumerate(events):
        arr[i].type = 1  # INPUT_KEYBOARD
        arr[i].u.ki.wVk = vk
        arr[i].u.ki.wScan = user32.MapVirtualKeyW(vk, 0)
        flags = 0 if down else 0x0002  # KEYEVENTF_KEYUP
        if vk in EXTENDED_VKS:
            flags |= 0x0001
        arr[i].u.ki.dwFlags = flags
    user32.SendInput(n, arr, ctypes.sizeof(INPUT))


def send_combo(*vks):
    send_keys([(v, True) for v in vks] + [(v, False) for v in reversed(vks)])


def release_modifiers():
    """Lift any modifier the user is still holding (they just pressed the hotkey)."""
    held = [vk for vk in MODIFIER_VKS if user32.GetAsyncKeyState(vk) & 0x8000]
    if not held:
        return
    if any(vk in MENU_TRIGGER_VKS for vk in held):
        send_keys([(0xE8, True), (0xE8, False)])  # mask key: stops Alt/Win opening a menu
    send_keys([(vk, False) for vk in held])


# --------------------------------------------------------------------------
# Misc helpers
# --------------------------------------------------------------------------
def foreground_process_name():
    if not IS_WIN:
        return ""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    handle = kernel32.OpenProcess(0x1000, False, pid.value)  # QUERY_LIMITED_INFORMATION
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(520)
        size = wintypes.DWORD(520)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value).lower()
    finally:
        kernel32.CloseHandle(handle)
    return ""


def set_no_activate(tk_window):
    """Make a Tk window show without stealing keyboard focus."""
    if not IS_WIN:
        return
    try:
        wid = tk_window.winfo_id()
        hwnd = user32.GetParent(wid) or wid
        style = user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
        user32.SetWindowLongW(hwnd, -20, style | 0x08000000 | 0x00000080)  # NOACTIVATE | TOOLWINDOW
    except Exception:
        pass


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "KeyboardFlip"


def autostart_command():
    if getattr(sys, "frozen", False):
        return '"%s" --minimized' % sys.executable
    pyw = sys.executable.replace("python.exe", "pythonw.exe")
    return '"%s" "%s" --minimized' % (pyw, os.path.abspath(sys.argv[0]))


def is_autostart():
    if not IS_WIN:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, RUN_NAME)
            return True
    except OSError:
        return False


def set_autostart(enabled):
    if not IS_WIN:
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(key, RUN_NAME)
            except FileNotFoundError:
                pass


# Single instance: a named mutex, plus a named event the 2nd copy uses to
# tell the 1st copy "show your window".
def acquire_single_instance():
    if not IS_WIN:
        return None, False
    handle = kernel32.CreateMutexW(None, False, "Local\\KeyboardFlipMutex")
    return handle, ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS


def create_show_event():
    return kernel32.CreateEventW(None, False, False, "Local\\KeyboardFlipShow") if IS_WIN else None


def signal_existing():
    if not IS_WIN:
        return
    ev = kernel32.OpenEventW(0x0002, False, "Local\\KeyboardFlipShow")  # EVENT_MODIFY_STATE
    if ev:
        kernel32.SetEvent(ev)
        kernel32.CloseHandle(ev)


def wait_event(handle, timeout_ms):
    return bool(handle) and kernel32.WaitForSingleObject(handle, timeout_ms) == 0
