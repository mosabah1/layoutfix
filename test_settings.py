# -*- coding: utf-8 -*-
"""
يختبر قراءة ملف الاعدادات.

الخطأ الذي وقع في 1.0.0: محررات ويندوز تحفظ UTF-8 مع BOM، وقراءة الملف
بـ utf-8 العادي تجعل configparser يفشل بـ MissingSectionHeaderError. وكان
الكود يبتلع الخطأ ويعود للقيم الافتراضية بصمت - فيغيّر المستخدم الاختصار
ولا يحدث شيء ولا يعرف لماذا.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import layoutfix as lf

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print("  %-46s %s%s" % (name, "OK" if ok else "فشل", detail))


SAMPLE = """\
; تعليق في الاول
[layoutfix]
hotkey = ctrl+alt+9
switch_layout = false
empty_grace = 0.3
"""

DEFAULTS = (("HOTKEY", "ctrl+alt+l"), ("HOTKEY_ALT", "ctrl+alt+shift+l"),
            ("SWITCH_LAYOUT", True), ("EMPTY_GRACE", 0.7))


def load_from(raw_bytes):
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "settings.ini")
    with open(path, "wb") as fh:
        fh.write(raw_bytes)
    lf.settings_path = lambda: path
    for name, value in DEFAULTS:
        setattr(lf, name, value)
    lf.load_settings()
    return dict(hotkey=lf.HOTKEY, hotkey_alt=lf.HOTKEY_ALT,
                switch=lf.SWITCH_LAYOUT, grace=lf.EMPTY_GRACE,
                error=lf.SETTINGS_ERROR)


print("1) ملف بـ UTF-8 بلا BOM\n")
r = load_from(SAMPLE.encode("utf-8"))
check("قرأ الاختصار", r["hotkey"] == "ctrl+alt+9", "  -> %r" % r["hotkey"])
check("قرأ قيمة منطقية", r["switch"] is False, "  -> %r" % r["switch"])
check("قرأ رقما عشريا", r["grace"] == 0.3, "  -> %r" % r["grace"])
check("بلا اخطاء", not r["error"])

print("\n2) ملف بـ UTF-8 مع BOM - هذا ما تكتبه محررات ويندوز\n")
r = load_from(b"\xef\xbb\xbf" + SAMPLE.encode("utf-8"))
check("قرأ الاختصار رغم BOM", r["hotkey"] == "ctrl+alt+9",
      "  -> %r" % r["hotkey"])
check("قرأ البقية رغم BOM", r["switch"] is False and r["grace"] == 0.3)
check("بلا اخطاء", not r["error"], "  -> %r" % r["error"])

print("\n3) ملف تالف - يجب ان يشرح السبب لا ان يصمت\n")
r = load_from("هذا ليس ملف اعدادات اصلا\n".encode("utf-8"))
check("عاد للقيم الافتراضية", r["hotkey"] == "ctrl+alt+l")
check("وسجّل سببا مفهوما", bool(r["error"]),
      "\n      %s" % (r["error"] or "").splitlines()[0])

print("\n4) قسم باسم خاطئ - نفس المطلوب\n")
r = load_from("[wrongname]\nhotkey = ctrl+alt+9\n".encode("utf-8"))
check("عاد للقيم الافتراضية", r["hotkey"] == "ctrl+alt+l")
check("وسجّل سببا مفهوما", bool(r["error"]), "\n      %s" % r["error"])

print("\n5) تفريغ مفتاح اختياري يجب ان يعطّله لا ان يُهمَل\n")
r = load_from("[layoutfix]\nhotkey_alt =\n".encode("utf-8"))
check("تفريغ hotkey_alt يعطّل الاختصار الثاني", r["hotkey_alt"] == "",
      "  -> %r" % r["hotkey_alt"])
r = load_from("[layoutfix]\nhotkey =\n".encode("utf-8"))
check("لكن الاختصار الرئيسي يبقى على الافتراضي",
      r["hotkey"] == "ctrl+alt+l", "  -> %r" % r["hotkey"])

print("\nالنتيجة:", "كل الاختبارات ناجحة" if all(results) else "فيه فشل")
sys.exit(0 if all(results) else 1)
