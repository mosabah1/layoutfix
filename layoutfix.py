# -*- coding: utf-8 -*-
"""
layoutfix - اصلاح النص المكتوب بلغة لوحة مفاتيح خاطئة.

تكتب "ptsh fdj" وتقصد "مرحبا بك"؟ حدد النص واضغط الاختصار، او لا تحدد شيئا
واضغط الاختصار فيتحول السطر الحالي. الاتجاه يُكتشف تلقائيا (عربي <-> انجليزي).

التشغيل:
    layoutfix.exe                     # يعمل بالخلفية مع ايقونة بشريط المهام
    layoutfix.exe --autostart [off]   # شغّل/اوقف العمل مع بدء ويندوز
    layoutfix.exe --settings          # اطبع مسار ملف الاعدادات
    layoutfix.exe --debug             # شغّل مع سجل تشخيص
    layoutfix.exe --check             # افحص ان كل شي يعمل
    layoutfix.exe --convert "ptsh fdj"
    layoutfix.exe --selftest

من المصدر: ضع pythonw layoutfix.py مكان layoutfix.exe.
"""

import configparser
import ctypes
import os
import sys
import time
import winreg
from ctypes import wintypes

APP_NAME = "layoutfix"
VERSION = "1.0.0"

# ---------------------------------------------------------------- الاعدادات --
# هذه قيم افتراضية فقط. ما يُقرأ فعلا هو ملف الاعدادات، ويُنشأ عند اول تشغيل:
#   %APPDATA%\layoutfix\settings.ini
# او بجانب البرنامج اذا وُجد هناك ملف بنفس الاسم (وضع محمول - USB مثلا).

HOTKEY = "ctrl+alt+l"            # اختصار التحويل
HOTKEY_ALT = "ctrl+alt+shift+l"  # نفس التحويل لكن يفكك "لا" الى g+h (مثل light)
SWITCH_LAYOUT = True       # بدّل لغة الادخال بعد التحويل لتكمل كتابة بشكل صحيح
FALLBACK_LINE = True       # اذا لم يكن هناك نص محدد، حوّل السطر الحالي
NOTIFY = True              # اظهر رسالة تشرح السبب عند الفشل بدل صوت مبهم
EMPTY_GRACE = 0.7          # مهلة انتظار النص بعد ان تُلمس الحافظة (ثانية)
UNTOUCHED_GRACE = 0.4      # مهلة الحكم بأن البرنامج لم يستجب لـ Ctrl+C اصلا
DEBUG = False              # اكتب سجل تشخيص في layoutfix.log (شغّل بـ --debug)

BOOLS = ("switch_layout", "fallback_line", "notify", "debug")
FLOATS = ("empty_grace", "untouched_grace")
TEXTS = ("hotkey", "hotkey_alt")


def is_frozen():
    """هل نعمل كملف exe مبني بـ PyInstaller؟"""
    return getattr(sys, "frozen", False)


def app_path():
    """مسار الملف القابل للتنفيذ (او السكربت عند التشغيل من المصدر)."""
    if is_frozen():
        return os.path.abspath(sys.executable)
    return os.path.abspath(__file__)


def app_dir():
    return os.path.dirname(app_path())


def settings_path():
    """
    بجانب البرنامج اذا وُجد ملف هناك (وضع محمول)، والا في %APPDATA%.
    نفضّل %APPDATA% لان البرنامج قد يكون في مجلد غير قابل للكتابة.
    """
    portable = os.path.join(app_dir(), "settings.ini")
    if os.path.isfile(portable):
        return portable
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_NAME, "settings.ini")


def log_path():
    path = settings_path()
    return os.path.join(os.path.dirname(path), "layoutfix.log")


DEFAULT_INI = """\
; اعدادات layoutfix - احفظ الملف ثم اعد تشغيل الاداة ليسري التغيير
; settings for layoutfix - save, then restart the tool to apply

[layoutfix]
; الاختصار الرئيسي. امثلة: ctrl+alt+l  /  ctrl+shift+space  /  pause  /  f9
hotkey = ctrl+alt+l

; نفس التحويل لكن يفكك "لا" الى g+h - للكلمات مثل light و right
hotkey_alt = ctrl+alt+shift+l

; بدّل لغة الادخال بعد التحويل لتكمل الكتابة بشكل صحيح
switch_layout = true

; اذا لم يكن هناك نص محدد، حوّل السطر من بدايته حتى المؤشر
fallback_line = true

; اظهر رسالة تشرح السبب عند الفشل بدل صوت مبهم
notify = true

; اكتب سجل تشخيص في layoutfix.log بجانب هذا الملف
debug = false
"""


def load_settings():
    """يقرأ ملف الاعدادات وينشئه بالقيم الافتراضية عند اول تشغيل."""
    path = settings_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.isfile(path):
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(DEFAULT_INI)
            return path
    except OSError:
        return path                      # نكمل بالقيم الافتراضية

    parser = configparser.ConfigParser(inline_comment_prefixes=(";",))
    try:
        parser.read(path, encoding="utf-8")
    except (configparser.Error, OSError):
        return path
    if not parser.has_section(APP_NAME):
        return path

    g = globals()
    for key in TEXTS:
        if parser.has_option(APP_NAME, key):
            value = parser.get(APP_NAME, key).strip()
            if value:
                g[key.upper()] = value
    for key in BOOLS:
        if parser.has_option(APP_NAME, key):
            try:
                g[key.upper()] = parser.getboolean(APP_NAME, key)
            except ValueError:
                pass
    for key in FLOATS:
        if parser.has_option(APP_NAME, key):
            try:
                g[key.upper()] = parser.getfloat(APP_NAME, key)
            except ValueError:
                pass
    return path


def _log(msg):
    if not DEBUG:
        return
    try:
        path = log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("%s  %s\n" % (time.strftime("%H:%M:%S"), msg))
    except Exception:
        pass

# ------------------------------------------------- جدول لوحة المفاتيح العربية
# المفتاح: الحرف الذي يظهر على تخطيط US. القيمة: ما يظهر على تخطيط Arabic 101.

EN_TO_AR = {
    "`": "ذ", "~": "ّ",
    "q": "ض", "w": "ص", "e": "ث", "r": "ق", "t": "ف", "y": "غ",
    "u": "ع", "i": "ه", "o": "خ", "p": "ح", "[": "ج", "]": "د",
    "Q": "َ", "W": "ً", "E": "ُ", "R": "ٌ", "T": "لإ", "Y": "إ",
    "U": "‘", "I": "÷", "O": "×", "P": "؛", "{": "<", "}": ">",
    "a": "ش", "s": "س", "d": "ي", "f": "ب", "g": "ل", "h": "ا",
    "j": "ت", "k": "ن", "l": "م", ";": "ك", "'": "ط",
    "A": "ِ", "S": "ٍ", "D": "]", "F": "[", "G": "لأ", "H": "أ",
    "J": "ـ", "K": "،", "L": "/",
    "z": "ئ", "x": "ء", "c": "ؤ", "v": "ر", "b": "لا", "n": "ى",
    "m": "ة", ",": "و", ".": "ز", "/": "ظ",
    "Z": "~", "X": "ْ", "C": "}", "V": "{", "B": "لآ", "N": "آ",
    "M": "’", "<": ",", ">": ".", "?": "؟",
    "(": ")", ")": "(",          # الاقواس معكوسة في التخطيط العربي
}

AR_TO_EN = {}
for _k, _v in EN_TO_AR.items():
    AR_TO_EN.setdefault(_v, _k)
for _i, _d in enumerate("٠١٢٣٤٥٦٧٨٩"):
    AR_TO_EN[_d] = str(_i)

# المفاتيح متعددة الحروف (لا، لأ، لإ، لآ) يجب فحصها قبل الحرف المفرد
_MULTI = sorted((k for k in AR_TO_EN if len(k) > 1), key=len, reverse=True)
_MULTI_LEN = max((len(k) for k in _MULTI), default=1)


def _is_arabic(ch):
    o = ord(ch)
    return 0x0600 <= o <= 0x06FF or 0x0750 <= o <= 0x077F or 0xFB50 <= o <= 0xFEFF


def _is_latin(ch):
    return ("a" <= ch <= "z") or ("A" <= ch <= "Z")


def detect_direction(text):
    """يرجع 'ar2en' اذا كان النص عربيا، و'en2ar' اذا كان لاتينيا."""
    ar = sum(1 for c in text if _is_arabic(c))
    la = sum(1 for c in text if _is_latin(c))
    return "ar2en" if ar > la else "en2ar"


def en_to_ar(text):
    return "".join(EN_TO_AR.get(c, c) for c in text)


def ar_to_en(text, split_ligatures=False):
    """
    split_ligatures: "لا" غامضة - تنتج من مفتاح b ومن تتابع g+h معا.
    الافتراضي يفضّل b لانه اكثر شيوعا بكثير في الانجليزية من التتابع gh.
    مرّر True للتفسير الثاني (light، right، through).
    """
    out = []
    i = 0
    n = len(text)
    while i < n:
        hit = None
        if not split_ligatures:
            for size in range(min(_MULTI_LEN, n - i), 1, -1):
                chunk = text[i:i + size]
                if chunk in AR_TO_EN:
                    hit = (chunk, AR_TO_EN[chunk])
                    break
        if hit:
            out.append(hit[1])
            i += len(hit[0])
        else:
            out.append(AR_TO_EN.get(text[i], text[i]))
            i += 1
    return "".join(out)


def convert(text, direction=None, split_ligatures=False):
    """يحول النص الى التخطيط البديل. الاتجاه يُكتشف تلقائيا ان لم يُحدد."""
    if not text:
        return text, None
    direction = direction or detect_direction(text)
    if direction == "ar2en":
        return ar_to_en(text, split_ligatures), "ar2en"
    return en_to_ar(text), "en2ar"


# ==========================================================  Win32 plumbing ==

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
ULONG_PTR = ctypes.c_size_t

WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_COMMAND = 0x0111
WM_HOTKEY = 0x0312
WM_INPUTLANGCHANGEREQUEST = 0x0050
WM_RBUTTONUP = 0x0205
WM_LBUTTONDBLCLK = 0x0203
WM_TRAY = 0x8001          # WM_APP + 1

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 1, 2, 4, 8, 0x4000
HOTKEY_ID = 0xA711
HOTKEY_ALT_ID = 0xA712

VK_SHIFT, VK_CTRL, VK_ALT = 0x10, 0x11, 0x12
VK_LWIN, VK_RWIN = 0x5B, 0x5C
VK_HOME, VK_END = 0x24, 0x23
VK_C, VK_V = 0x43, 0x56

VK_NAMES = {
    "ctrl": MOD_CONTROL, "control": MOD_CONTROL,
    "alt": MOD_ALT, "shift": MOD_SHIFT, "win": MOD_WIN,
}


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("style", wintypes.UINT),
                ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HICON)]


class GUID(ctypes.Structure):
    _fields_ = [("d1", wintypes.DWORD), ("d2", wintypes.WORD),
                ("d3", wintypes.WORD), ("d4", ctypes.c_byte * 8)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND),
                ("uID", wintypes.UINT), ("uFlags", wintypes.UINT),
                ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
                ("szTip", wintypes.WCHAR * 128), ("dwState", wintypes.DWORD),
                ("dwStateMask", wintypes.DWORD), ("szInfo", wintypes.WCHAR * 256),
                ("uVersion", wintypes.UINT), ("szInfoTitle", wintypes.WCHAR * 64),
                ("dwInfoFlags", wintypes.DWORD), ("guidItem", GUID),
                ("hBalloonIcon", wintypes.HICON)]


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.GetClipboardData.restype = ctypes.c_void_p
user32.SetClipboardData.argtypes = (wintypes.UINT, ctypes.c_void_p)
user32.SetClipboardData.restype = ctypes.c_void_p
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetKeyboardLayout.restype = ctypes.c_void_p
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetClipboardSequenceNumber.restype = wintypes.DWORD
user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
user32.MapVirtualKeyW.restype = wintypes.UINT
user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
user32.LoadIconW.argtypes = (wintypes.HINSTANCE, ctypes.c_void_p)
user32.LoadIconW.restype = wintypes.HICON
user32.CreatePopupMenu.restype = wintypes.HMENU
user32.DefWindowProcW.argtypes = (wintypes.HWND, wintypes.UINT,
                                  wintypes.WPARAM, wintypes.LPARAM)
user32.DefWindowProcW.restype = LRESULT
user32.CreateWindowExW.argtypes = (
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID)
user32.CreateWindowExW.restype = wintypes.HWND
kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = (
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD))
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND,
                                            ctypes.POINTER(wintypes.DWORD))
kernel32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
kernel32.GlobalAlloc.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = (ctypes.c_void_p,)
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = (ctypes.c_void_p,)


# ------------------------------------------------------------- ارسال مفاتيح --

def _send(*inputs):
    arr = (INPUT * len(inputs))(*inputs)
    n = user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))
    if n != len(inputs):
        _log("SendInput حُجب: ارسلنا %d من %d (err=%d)"
             % (n, len(inputs), ctypes.get_last_error()))
    return n


# مفاتيح ممتدة: لا بد من علامة KEYEVENTF_EXTENDEDKEY والا فُسّرت خطأ
EXTENDED_VKS = frozenset([0x21, 0x22, 0x23, 0x24,       # PgUp PgDn End Home
                          0x25, 0x26, 0x27, 0x28,       # الاسهم
                          0x2D, 0x2E, 0x5B, 0x5C])      # Ins Del Win


def _k(vk, up=False):
    # Chrome وتطبيقات Electron تتجاهل احيانا الاحداث التي تصل بـ scan code صفر
    scan = user32.MapVirtualKeyW(vk, 0)                  # MAPVK_VK_TO_VSC
    flags = 0x0002 if up else 0                          # KEYEVENTF_KEYUP
    if vk in EXTENDED_VKS:
        flags |= 0x0001                                  # KEYEVENTF_EXTENDEDKEY
    i = INPUT(type=1)
    i.u.ki = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags,
                        time=0, dwExtraInfo=0)
    return i


def tap(vk, *mods):
    """
    نرسل كل ضغطة بمفردها مع فاصل زمني. الارسال دفعة واحدة بنفس الطابع الزمني
    تتجاهله برامج كثيرة (Electron، المتصفحات) لانها تعالج الادخال لا تزامنيا.
    """
    sent = 0
    for m in mods:
        sent += _send(_k(m))
        time.sleep(0.012)
    sent += _send(_k(vk))
    time.sleep(0.012)
    sent += _send(_k(vk, True))
    time.sleep(0.012)
    for m in reversed(mods):
        sent += _send(_k(m, True))
        time.sleep(0.008)
    return sent


MOD_KEYS = (VK_CTRL, VK_ALT, VK_SHIFT, VK_LWIN, VK_RWIN)


def held_modifiers():
    return [vk for vk in MOD_KEYS if user32.GetAsyncKeyState(vk) & 0x8000]


def release_modifiers(timeout=1.2):
    """
    ننتظر حتى ترفع يدك فعليا عن Ctrl+Alt قبل ارسال Ctrl+C.

    بدون هذا الانتظار، المفاتيح ما زالت مضغوطة فيزيائيا لحظة اطلاق الاختصار،
    فيستقبل البرنامج Ctrl+Alt+C لا Ctrl+C - وهذا هو سبب "لا شيء يحدث".
    ارسال keyup صناعي لا يغير حالة المفتاح الفيزيائي، فلا بد من الانتظار.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not held_modifiers():
            time.sleep(0.02)        # نترك البرنامج يستقر
            return True
        time.sleep(0.015)
    # ما زالت مضغوطة (او عالقة منطقيا) - نحررها صناعيا كحل اخير
    stuck = held_modifiers()
    if stuck:
        _send(*[_k(vk, True) for vk in stuck])
        time.sleep(0.04)
    return False


# ----------------------------------------------------------------- الحافظة --

def _open_clipboard(tries=10):
    for _ in range(tries):
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.02)
    return False


def clip_get():
    if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
        return ""
    if not _open_clipboard():
        return ""
    try:
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return ""
        p = kernel32.GlobalLock(h)
        if not p:
            return ""
        try:
            return ctypes.wstring_at(p)
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


def clip_set(text):
    if not _open_clipboard():
        return False
    try:
        user32.EmptyClipboard()
        if text is None:
            return True
        buf = ctypes.create_unicode_buffer(text)
        size = ctypes.sizeof(buf)
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
        if not h:
            return False
        p = kernel32.GlobalLock(h)
        ctypes.memmove(p, buf, size)
        kernel32.GlobalUnlock(h)
        return bool(user32.SetClipboardData(CF_UNICODETEXT, h))
    finally:
        user32.CloseClipboard()


# علامة فريدة لا يكتبها اي برنامج (محارف صفرية العرض)
SENTINEL = "​⁠layoutfix⁠​"


def copy_selection(timeout=1.5):
    """
    ينسخ النص المحدد. يرجع "" اذا لم ينسخ البرنامج شيئا.

    نضع علامة فريدة في الحافظة قبل Ctrl+C، فيصبح لكل حالة توقيع واضح:
      - العلامة اختفت وجاء نص  -> هذا هو النص المحدد
      - العلامة باقية           -> البرنامج لم ينسخ شيئا (لا تحديد)
      - الحافظة فُرّغت ولا نص    -> لا تحديد، لان EmptyClipboard يسبق الكتابة

    الاهم: بما اننا محونا المحتوى السابق، يستحيل ان نرجع نصا قديما من
    حافظتك ونحسبه النص المحدد - وهذا ما كان يحدث عند تزاحم برنامجين عليها.
    """
    started = time.time()
    if not clip_set(SENTINEL):
        _log("تعذر وضع العلامة - برنامج آخر يمسك الحافظة")
    seq0 = user32.GetClipboardSequenceNumber()
    tap(VK_C, VK_CTRL)

    touched_at = None
    while time.time() - started < timeout:
        time.sleep(0.025)
        now = time.time()
        got = clip_get()
        if got and got != SENTINEL:
            return got
        if user32.GetClipboardSequenceNumber() != seq0:
            # لُمست الحافظة لكن لا نص بعد - قد يكون النص في الطريق
            if touched_at is None:
                touched_at = now
            elif now - touched_at > EMPTY_GRACE:
                _log("فُرّغت الحافظة ولم يصل نص خلال %.0f ملّي - لا تحديد"
                     % (EMPTY_GRACE * 1000))
                return ""
        elif now - started > UNTOUCHED_GRACE:
            _log("العلامة ما زالت موجودة - البرنامج لم يستجب لـ Ctrl+C")
            return ""
    _log("انتهت المهلة (%.1f ثانية) بلا نص" % timeout)
    return ""


# --------------------------------------------------------- تبديل لغة الادخال --

def foreground_app():
    """اسم البرنامج الذي يعمل في المقدمة - يساعد في معرفة سبب الفشل."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return "?"
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    name = "?"
    h = kernel32.OpenProcess(0x1000, False, pid.value)   # QUERY_LIMITED_INFO
    if h:
        buf = ctypes.create_unicode_buffer(512)
        size = wintypes.DWORD(512)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            name = buf.value.rsplit("\\", 1)[-1]
        kernel32.CloseHandle(h)
    title = ctypes.create_unicode_buffer(120)
    user32.GetWindowTextW(hwnd, title, 120)
    return "%s (%s)" % (name, title.value[:40]) if title.value else name


def notify(title, msg, beep=0x30):
    """رسالة منبثقة من ايقونة شريط المهام، مع صوت كاحتياط."""
    _log("%s - %s" % (title, msg))
    user32.MessageBeep(beep)
    if not (NOTIFY and _nid is not None):
        return
    _nid.uFlags = 0x10                     # NIF_INFO فقط
    _nid.szInfoTitle = title[:62]
    _nid.szInfo = msg[:250]
    _nid.dwInfoFlags = 0x01                # NIIF_INFO
    shell32.Shell_NotifyIconW(1, ctypes.byref(_nid))      # NIM_MODIFY
    _nid.uFlags = 0x01 | 0x02 | 0x04       # ارجع الاعدادات المعتادة


def switch_input_language(primary):
    """primary: 0x01 عربي، 0x09 انجليزي."""
    count = user32.GetKeyboardLayoutList(0, None)
    if count <= 0:
        return
    arr = (ctypes.c_void_p * count)()
    user32.GetKeyboardLayoutList(count, arr)
    for hkl in arr:
        if hkl and ((hkl & 0xFFFF) & 0x3FF) == primary:
            hwnd = user32.GetForegroundWindow()
            if hwnd:
                user32.PostMessageW(hwnd, WM_INPUTLANGCHANGEREQUEST, 0,
                                    ctypes.c_void_p(hkl))
            return


# ------------------------------------------------------------- الفعل الرئيسي --

def do_fix(split_ligatures=False):
    app = foreground_app()
    _log("--- الاختصار في: %s" % app)

    if not release_modifiers():
        _log("انتهى وقت انتظار رفع المفاتيح - اكملنا على اي حال")

    saved = clip_get()
    try:
        _do_fix_inner(saved, split_ligatures, app)
    finally:
        # نعيد حافظتك مهما حدث - والا بقيت فيها علامتنا او النص المحوّل
        if clip_get() != saved:
            clip_set(saved)


def _do_fix_inner(saved, split_ligatures, app):
    text = copy_selection()
    used_line = False
    if not text and FALLBACK_LINE:
        tap(VK_HOME, VK_SHIFT)          # حدد من بداية السطر الى المؤشر
        time.sleep(0.06)
        text = copy_selection()
        used_line = bool(text)

    if not text.strip():
        notify("لم أتمكن من قراءة النص",
               "%s لم يستجب لـ Ctrl+C. حدّد النص يدوياً ثم أعد المحاولة. "
               "إذا كان البرنامج يعمل كمسؤول (Administrator) فويندوز يحجب "
               "الإرسال إليه." % app)
        return

    _log("نُسخ %d حرف%s: %r" % (len(text), " (سطر)" if used_line else "",
                                 text[:60]))

    fixed, direction = convert(text, split_ligatures=split_ligatures)
    if fixed == text:
        if used_line:
            tap(VK_END)                 # الغِ التحديد
        notify("لا شيء للتحويل",
               "النص المقروء لا يتغير بالتحويل: %r" % text[:40], beep=0x40)
        return

    if not clip_set(fixed):
        notify("الحافظة مشغولة",
               "برنامج آخر يمسك الحافظة الآن. أعد المحاولة بعد لحظة.")
        return

    time.sleep(0.04)
    tap(VK_V, VK_CTRL)
    time.sleep(0.22)
    _log("لُصق (%s): %r" % (direction, fixed[:60]))

    if SWITCH_LAYOUT:
        switch_input_language(0x01 if direction == "en2ar" else 0x09)


# -------------------------------------------------------- النافذة والايقونة --

_wndproc_ref = None
_nid = None


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def autostart_command():
    """الامر الذي يُسجَّل للاقلاع. عند التشغيل من المصدر نمرر السكربت."""
    exe = app_path()
    if is_frozen():
        return '"%s"' % exe
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.isfile(pyw):
        pyw = sys.executable
    return '"%s" "%s"' % (pyw, exe)


def autostart_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(value)
    except OSError:
        return False


def set_autostart(enable):
    """يضيف او يزيل الاداة من برامج بدء التشغيل. لا يحتاج صلاحيات مسؤول."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            if enable:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ,
                                  autostart_command())
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError as exc:
        _log("تعذر تعديل الاقلاع التلقائي: %s" % exc)
        return False


def open_settings_file():
    """يفتح ملف الاعدادات في المحرر الافتراضي."""
    path = load_settings()           # ينشئه ان لم يكن موجودا
    try:
        os.startfile(path)           # noqa: S606 - ويندوز فقط
    except OSError:
        user32.MessageBoxW(None, "ملف الاعدادات:\n%s" % path, APP_NAME, 0x40)


def parse_hotkey(spec):
    parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
    mods = MOD_NOREPEAT
    vk = None
    for p in parts:
        if p in VK_NAMES:
            mods |= VK_NAMES[p]
        elif len(p) == 1:
            vk = ord(p.upper())
        elif p.startswith("f") and p[1:].isdigit():
            vk = 0x70 + int(p[1:]) - 1
        elif p in ("space",):
            vk = 0x20
        elif p in ("pause", "break"):
            vk = 0x13
        elif p in ("insert", "ins"):
            vk = 0x2D
    if vk is None:
        raise SystemExit("اختصار غير صالح: %s" % spec)
    return mods, vk


MF_SEPARATOR = 0x0800
MF_CHECKED = 0x0008

ID_FIX, ID_QUIT, ID_FIX_ALT = 1, 2, 3
ID_AUTOSTART, ID_SETTINGS, ID_ABOUT = 4, 5, 6


def show_menu(hwnd):
    menu = user32.CreatePopupMenu()
    user32.AppendMenuW(menu, 0, ID_FIX, "حوّل الآن  (%s)" % HOTKEY.upper())
    user32.AppendMenuW(menu, 0, ID_FIX_ALT,
                       "حوّل مع تفكيك لا  (%s)" % HOTKEY_ALT.upper())
    user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
    user32.AppendMenuW(menu, MF_CHECKED if autostart_enabled() else 0,
                       ID_AUTOSTART, "تشغيل مع ويندوز")
    user32.AppendMenuW(menu, 0, ID_SETTINGS, "فتح ملف الاعدادات")
    user32.AppendMenuW(menu, 0, ID_ABOUT, "عن الاداة")
    user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
    user32.AppendMenuW(menu, 0, ID_QUIT, "ايقاف الاداة")

    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    user32.SetForegroundWindow(hwnd)
    cmd = user32.TrackPopupMenu(menu, 0x0100 | 0x0002, pt.x, pt.y, 0, hwnd, None)
    user32.DestroyMenu(menu)

    if cmd == ID_FIX:
        do_fix()
    elif cmd == ID_FIX_ALT:
        do_fix(split_ligatures=True)
    elif cmd == ID_AUTOSTART:
        wanted = not autostart_enabled()
        if set_autostart(wanted):
            notify(APP_NAME,
                   "ستعمل الاداة تلقائيا مع ويندوز." if wanted
                   else "لن تعمل الاداة تلقائيا مع ويندوز.", beep=0x40)
        else:
            notify(APP_NAME, "تعذر تعديل بدء التشغيل.")
    elif cmd == ID_SETTINGS:
        open_settings_file()
    elif cmd == ID_ABOUT:
        user32.MessageBoxW(
            None,
            "%s %s\n\n"
            "يحوّل النص المكتوب بلغة لوحة مفاتيح خاطئة (عربي <-> انجليزي).\n\n"
            "التحويل      : %s\n"
            "تفكيك لا     : %s\n"
            "الاعدادات    : %s\n\n"
            "رخصة MIT - الكود مفتوح المصدر."
            % (APP_NAME, VERSION, HOTKEY.upper(), HOTKEY_ALT.upper(),
               settings_path()),
            "عن %s" % APP_NAME, 0x40)
    elif cmd == ID_QUIT:
        user32.DestroyWindow(hwnd)


def wndproc(hwnd, msg, wparam, lparam):
    if msg == WM_TRAY:
        low = lparam & 0xFFFF
        if low in (WM_RBUTTONUP, WM_LBUTTONDBLCLK):
            show_menu(hwnd)
        return 0
    if msg in (WM_CLOSE, WM_DESTROY):
        if _nid is not None:
            shell32.Shell_NotifyIconW(2, ctypes.byref(_nid))   # NIM_DELETE
        user32.PostQuitMessage(0)
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def run_daemon(check_only=False):
    global _wndproc_ref, _nid

    # نسخة واحدة فقط
    mutex = kernel32.CreateMutexW(None, True, "layoutfix_single_instance")
    if ctypes.get_last_error() == 183:        # ERROR_ALREADY_EXISTS
        if check_only:
            print("الاداة تعمل بالفعل (نسخة واحدة فقط مسموحة).")
        return

    hinst = kernel32.GetModuleHandleW(None)
    _wndproc_ref = WNDPROC(wndproc)
    cls = WNDCLASSEXW()
    cls.cbSize = ctypes.sizeof(WNDCLASSEXW)
    cls.lpfnWndProc = _wndproc_ref
    cls.hInstance = hinst
    cls.lpszClassName = "LayoutFixWnd"
    if not user32.RegisterClassExW(ctypes.byref(cls)):
        raise ctypes.WinError(ctypes.get_last_error())

    hwnd = user32.CreateWindowExW(0, "LayoutFixWnd", "layoutfix", 0,
                                  0, 0, 0, 0, None, None, hinst, None)
    if not hwnd:
        raise ctypes.WinError(ctypes.get_last_error())

    mods, vk = parse_hotkey(HOTKEY)
    if not user32.RegisterHotKey(hwnd, HOTKEY_ID, mods, vk):
        user32.MessageBoxW(
            None,
            "تعذر تسجيل الاختصار %s - ربما يستخدمه برنامج آخر.\n"
            "غيّر قيمة HOTKEY في اعلى الملف layoutfix.py." % HOTKEY.upper(),
            "layoutfix", 0x10)
        return
    if HOTKEY_ALT:
        amods, avk = parse_hotkey(HOTKEY_ALT)
        user32.RegisterHotKey(hwnd, HOTKEY_ALT_ID, amods, avk)

    _nid = NOTIFYICONDATAW()
    _nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    _nid.hWnd = hwnd
    _nid.uID = 1
    _nid.uFlags = 0x01 | 0x02 | 0x04          # MESSAGE | ICON | TIP
    _nid.uCallbackMessage = WM_TRAY
    _nid.hIcon = user32.LoadIconW(None, 32516)      # IDI_INFORMATION
    _nid.szTip = "layoutfix - %s لتصحيح لغة النص" % HOTKEY.upper()
    if not shell32.Shell_NotifyIconW(0, ctypes.byref(_nid)):       # NIM_ADD
        print("تحذير: تعذر اضافة الايقونة لشريط المهام (الاداة تعمل بدونها).")

    if check_only:
        print("حجم INPUT:", ctypes.sizeof(INPUT), "(المتوقع 40 على 64-بت)")
        saved = clip_get()
        probe = "layoutfix-clipboard-probe"
        clip_set(probe)
        got = clip_get()
        clip_set(saved)
        print("الحافظة:", "OK" if got == probe else "فشل (%r)" % got)
        print("النافذة والاختصار والايقونة: OK (%s)" % HOTKEY.upper())
        print("البرنامج في المقدمة:", foreground_app())
        print("مفاتيح مضغوطة الآن:", held_modifiers() or "لا شيء")
        notify("layoutfix جاهزة", "هذه رسالة تجريبية - الاختصار %s"
               % HOTKEY.upper(), beep=0x40)
        time.sleep(0.6)
        shell32.Shell_NotifyIconW(2, ctypes.byref(_nid))            # NIM_DELETE
        user32.UnregisterHotKey(hwnd, HOTKEY_ID)
        user32.UnregisterHotKey(hwnd, HOTKEY_ALT_ID)
        user32.DestroyWindow(hwnd)
        return

    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        if msg.message == WM_HOTKEY and msg.wParam in (HOTKEY_ID, HOTKEY_ALT_ID):
            try:
                do_fix(split_ligatures=msg.wParam == HOTKEY_ALT_ID)
            except Exception:
                user32.MessageBeep(0x10)
            continue
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

    user32.UnregisterHotKey(hwnd, HOTKEY_ID)
    user32.UnregisterHotKey(hwnd, HOTKEY_ALT_ID)


# ------------------------------------------------------------------ الاختبار --

def selftest():
    ok = True

    # 1) كل مفتاح يرجع لنفسه
    for en, ar in EN_TO_AR.items():
        if AR_TO_EN.get(ar) != en:
            continue                     # قيمة مكررة، يفوز اول مفتاح
        back = ar_to_en(ar)
        if back != en:
            print("فشل الرجوع للمفتاح: %r -> %r -> %r" % (en, ar, back))
            ok = False

    # 2) ذهاب وعودة لجمل كاملة
    samples = ["hello world", "Hello, World!", "light through night",
               "ljvhl 123", "tfatfatfa", "a-b_c/d"]
    print("ذهاب وعودة (انجليزي -> عربي -> انجليزي):")
    for s in samples:
        ar = en_to_ar(s)
        plain = ar_to_en(ar)
        split = ar_to_en(ar, split_ligatures=True)
        if plain == s:
            mark, note = "OK  ", ""
        elif split == s:
            mark, note = "OK  ", "  (بـ HOTKEY_ALT: %r)" % split
        else:
            mark, note = "فشل", "  -> %r / %r" % (plain, split)
            ok = False
        print("  %s %-22r -> %-26r%s" % (mark, s, ar, note))

    # 3) الحالات الواقعية: نص عربي مكتوب بتخطيط انجليزي والعكس
    print("\nالحالة الواقعية (ما يظهر على الشاشة -> ما بعد الاختصار):")
    real = ["hglsghl ugd;l", "lvpfh", "hello", "ljv", "Shdk hglwfhp"]
    for s in real:
        garbled = s if detect_direction(s) == "ar2en" else s
        out, direction = convert(garbled)
        print("  %-16r %s -> %r" % (garbled, direction, out))
        # نتأكد ان التحويل مرتين يرجعنا للاصل
        rt = convert(out)[0]
        if rt != garbled and convert(out, split_ligatures=True)[0] != garbled:
            print("      تنبيه: التحويل مرتين لا يرجع للاصل (%r)" % rt)

    print("\nالنتيجة:", "ناجح" if ok else "فيه اخطاء")
    return 0 if ok else 1


def attach_console():
    """
    الـ exe مبني بلا نافذة console (والا ومضت عند كل اقلاع). لكن عند
    استدعائه بوسائط من طرفية نرتبط بطرفية المستدعي ليظهر الاخراج هناك.
    """
    if not is_frozen():
        return
    if sys.stdout is not None and sys.stderr is not None:
        return          # الاخراج موجَّه الى ملف او انبوب بالفعل - لا نلمسه
    try:
        if kernel32.AttachConsole(-1):          # ATTACH_PARENT_PROCESS
            sys.stdout = open("CONOUT$", "w", encoding="utf-8",
                              errors="replace", buffering=1)
            sys.stderr = open("CONOUT$", "w", encoding="utf-8",
                              errors="replace", buffering=1)
    except Exception:
        pass


def main():
    args = sys.argv[1:]
    if args:
        attach_console()

    # التحويل النصي لا يحتاج اعدادات ولا نافذة
    if args and args[0] in ("--convert", "-c", "--convert-alt"):
        text = " ".join(args[1:])
        out, direction = convert(text, split_ligatures=args[0] == "--convert-alt")
        print(out)
        print("(%s)" % direction, file=sys.stderr)
        return 0
    if args and args[0] == "--selftest":
        return selftest()
    if args and args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if args and args[0] in ("-v", "--version"):
        print("%s %s" % (APP_NAME, VERSION))
        return 0

    path = load_settings()

    if args and args[0] == "--autostart":
        on = len(args) < 2 or args[1] not in ("off", "0", "false")
        ok = set_autostart(on)
        print("الاقلاع التلقائي: %s%s"
              % ("مفعّل" if on else "متوقف", "" if ok else "  (فشل)"))
        return 0 if ok else 1
    if args and args[0] == "--settings":
        print(path)
        return 0
    if args and args[0] == "--debug":
        globals()["DEBUG"] = True
        _log("=== بدأ التشغيل بوضع التشخيص (%s %s) ===" % (APP_NAME, VERSION))
    if args and args[0] == "--check":
        print("ملف الاعدادات:", path)
        run_daemon(check_only=True)
        return 0

    run_daemon()
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
