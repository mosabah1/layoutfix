# -*- coding: utf-8 -*-
"""
اختبارات التقاط النص من الحافظة - تحاكي ما تفعله البرامج الحقيقية.

تغطي خطأين وقعا فعلا:
  1. رقم تسلسل الحافظة يرتفع عند EmptyClipboard، اي قبل كتابة النص.
     الاكتفاء بتغيّر الرقم يقرأ حافظة فارغة ويستسلم. (ظهر في Chrome)
  2. قراءة محتوى الحافظة القديم وحسبانه النص المنسوخ عند تزاحم
     برنامجين على الحافظة. العلامة الفريدة تمنع هذا.
"""
import os
import sys
import threading
import time
import ctypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import layoutfix as lf

user32 = lf.user32
results = []

lf.tap = lambda *a, **k: 0        # نعطل ارسال المفاتيح: نختبر منطق الانتظار


def check(name, ok, detail=""):
    results.append(ok)
    print("  %-44s %s%s" % (name, "OK" if ok else "فشل", detail))


def app_copies(delay_empty, delay_set, text, hold=False):
    """يحاكي برنامجا ينسخ: يفرّغ الحافظة ثم يكتب النص بعد فترة."""
    time.sleep(delay_empty)
    if hold:
        # يمسك الحافظة مفتوحة طوال الفترة (اسوأ حالة)
        if lf._open_clipboard(50):
            user32.EmptyClipboard()
            time.sleep(delay_set)
            buf = ctypes.create_unicode_buffer(text)
            h = lf.kernel32.GlobalAlloc(0x2000, ctypes.sizeof(buf))
            p = lf.kernel32.GlobalLock(h)
            ctypes.memmove(p, buf, ctypes.sizeof(buf))
            lf.kernel32.GlobalUnlock(h)
            user32.SetClipboardData(13, h)
            user32.CloseClipboard()
    else:
        lf.clip_set("")               # يفرّغ: الرقم يرتفع والحافظة فارغة
        time.sleep(delay_set)
        lf.clip_set(text)


def race_case(name, hold, delay_set):
    lf.clip_set("محتوى قديم")
    t = threading.Thread(target=app_copies,
                         args=(0.10, delay_set, "نجح النسخ", hold))
    t.start()
    got = lf.copy_selection()
    t.join()
    check(name, got == "نجح النسخ", "  -> %r" % got)


print("1) سباق الحافظة: البرنامج يفرّغ ثم يكتب النص متأخرا\n")
race_case("كتابة بعد 250 ملّي", False, 0.25)
race_case("كتابة بعد 600 ملّي", False, 0.60)
race_case("حافظة ممسوكة مفتوحة 300 ملّي", True, 0.30)

print("\n2) لا تحديد: يجب ان ترجع فارغة، لا المحتوى القديم\n")
lf.clip_set("محتوى قديم لا علاقة له بالتحديد")
t0 = time.time()
got = lf.copy_selection()
elapsed = time.time() - t0
check("لا يرجّع المحتوى القديم", got == "", "  -> %r" % got)
check("ويحكم بسرعة (اقل من 0.9 ثانية)", elapsed < 0.9,
      "  -> %.2f ثانية" % elapsed)

print("\n3) العلامة لا تتسرب الى النص المقروء\n")
lf.clip_set("محتوى قديم")
t = threading.Thread(target=app_copies, args=(0.10, 0.2, "نص حقيقي", False))
t.start()
got = lf.copy_selection()
t.join()
check("النص المرجَّع خال من العلامة", lf.SENTINEL not in got, "  -> %r" % got)

lf.clip_set("")
print("\nالنتيجة:", "كل الاختبارات ناجحة" if all(results) else "فيه فشل")
sys.exit(0 if all(results) else 1)
