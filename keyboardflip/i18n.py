"""Interface strings (English / Arabic)."""

UI_LANGUAGES = {"en": "English", "ar": "العربية"}

_STRINGS = {
    "en": {
        "tab_rules": "Conversions",
        "tab_keyboards": "Keyboards",
        "tab_settings": "Settings",
        "tab_about": "About",
        "sub_rules": "Choose what converts into what, and set a shortcut for each conversion.",
        "sub_keyboards": "Pick the languages you use and the keyboard layout you type on.",
        "sub_settings": "Behavior, shortcuts and appearance.",
        "add_rule": "+  Add conversion",
        "rules_count": "{n} of {m}",
        "both_ways": "Both ways",
        "same_alphabet": "Same alphabet",
        "change": "Change",
        "no_rules_title": "No conversions yet",
        "no_rules_desc": "Add your first conversion to start fixing text in one keystroke.",
        "press_shortcut": "Press the new shortcut",
        "esc_cancel": "Press Esc to cancel",
        "need_modifier": "Use Ctrl, Alt or Shift together with a key.",
        "hotkey_dup": "That shortcut is already used by another conversion.",
        "max_rules": "Maximum is {n} conversions.",
        "layout": "Layout",
        "single_layout": "Only one layout",
        "need_two_langs": "At least two languages must stay enabled.",
        "layout_unavailable": "That layout isn't available on this PC.",
        "status_on": "Conversions",
        "st_active": "{n} shortcut(s) active",
        "st_paused": "Paused",
        "st_failed": "Already used by another program: {keys}",
        "sec_general": "General",
        "sec_shortcuts": "Shortcuts",
        "sec_excluded": "Excluded programs",
        "sec_appearance": "Appearance",
        "settings_enabled": "Enable conversions",
        "settings_enabled_d": "Turn every shortcut on or off at once",
        "settings_autostart": "Start with Windows",
        "settings_autostart_d": "Launch quietly in the tray when you sign in",
        "settings_notify": "Show a notification",
        "settings_notify_d": "A small message after each conversion",
        "settings_lastword": "Convert the last word",
        "settings_lastword_d": "When nothing is selected, convert the word before the cursor",
        "undo_title": "Undo last conversion",
        "undo_desc": "Sends Ctrl+Z to the program you converted in, within 30 seconds",
        "excluded_title": "Never convert inside these programs",
        "excluded_hint": "You can add any program you like: type its name (for example chrome.exe) "
                         "and press Add, or press Pick app and click on that program within 3 seconds.",
        "excluded_ph": "program.exe",
        "add": "Add",
        "pick_app": "Pick app",
        "pick_wait": "Click the app… {n}",
        "pick_self": "Click on the other program first",
        "no_excluded": "No programs excluded",
        "settings_ui_lang": "Interface language",
        "settings_theme": "Theme",
        "about_text": "Fix text typed with the wrong keyboard language in one keystroke.\n"
                      "Works in any program and runs quietly from the system tray.",
        "open_folder": "Open settings folder",
        "converted": "{a} → {b}",
        "nothing": "Nothing to convert",
        "admin_app": "Can't reach this program. Run Keyboard Flip as administrator",
        "unchanged": "No change",
        "layout_missing": "Keyboard layout unavailable",
        "nothing_to_undo": "Nothing to undo",
        "undone": "Undone",
        "tray_open": "Open",
        "tray_enabled": "Enabled",
        "tray_quit": "Quit",
        "still_running": "Keyboard Flip is still running in the system tray",
    },
    "ar": {
        "tab_rules": "التحويلات",
        "tab_keyboards": "الكيبوردات",
        "tab_settings": "الإعدادات",
        "tab_about": "عن البرنامج",
        "sub_rules": "اختار هيتحوّل من إيه لإيه، وحدّد اختصار لكل تحويلة.",
        "sub_keyboards": "اختار اللغات اللي بتستخدمها ونوع الكيبورد اللي بتكتب عليه.",
        "sub_settings": "طريقة التشغيل والاختصارات والمظهر.",
        "add_rule": "+  إضافة تحويلة",
        "rules_count": "{n} من {m}",
        "both_ways": "الاتجاهين",
        "same_alphabet": "نفس الحروف",
        "change": "تغيير",
        "no_rules_title": "مفيش تحويلات لسه",
        "no_rules_desc": "أضف أول تحويلة وابدأ تصلّح الكلام بضغطة واحدة.",
        "press_shortcut": "اضغط على الاختصار الجديد",
        "esc_cancel": "اضغط Esc للإلغاء",
        "need_modifier": "استخدم Ctrl أو Alt أو Shift مع حرف.",
        "hotkey_dup": "الاختصار ده مستخدم في تحويلة تانية.",
        "max_rules": "أقصى عدد للتحويلات {n}.",
        "layout": "النوع",
        "single_layout": "نوع واحد فقط",
        "need_two_langs": "لازم لغتين على الأقل تفضل مفعّلة.",
        "layout_unavailable": "النوع ده مش متاح على الجهاز.",
        "status_on": "التحويلات",
        "st_active": "{n} اختصار شغّال",
        "st_paused": "متوقف",
        "st_failed": "مستخدم في برنامج تاني: {keys}",
        "sec_general": "عام",
        "sec_shortcuts": "الاختصارات",
        "sec_excluded": "البرامج المستثناة",
        "sec_appearance": "المظهر",
        "settings_enabled": "تفعيل التحويلات",
        "settings_enabled_d": "شغّل أو أوقف كل الاختصارات مرة واحدة",
        "settings_autostart": "التشغيل مع ويندوز",
        "settings_autostart_d": "يشتغل بهدوء في شريط المهام أول ما تفتح الجهاز",
        "settings_notify": "إظهار إشعار",
        "settings_notify_d": "رسالة صغيرة بعد كل تحويل",
        "settings_lastword": "تحويل آخر كلمة",
        "settings_lastword_d": "لو مفيش نص متحدد، حوّل الكلمة اللي قبل المؤشر",
        "undo_title": "التراجع عن آخر تحويل",
        "undo_desc": "بيبعت Ctrl+Z للبرنامج اللي حوّلت فيه، خلال 30 ثانية",
        "excluded_title": "لا تحوّل داخل البرامج دي",
        "excluded_hint": "تقدر تضيف أي برنامج بنفسك: اكتب اسمه (مثلًا chrome.exe) واضغط إضافة، "
                         "أو اضغط «اختيار برنامج» واضغط على البرنامج خلال 3 ثواني.",
        "excluded_ph": "program.exe",
        "add": "إضافة",
        "pick_app": "اختيار برنامج",
        "pick_wait": "اضغط على البرنامج… {n}",
        "pick_self": "اضغط على البرنامج التاني الأول",
        "no_excluded": "مفيش برامج مستثناة",
        "settings_ui_lang": "لغة الواجهة",
        "settings_theme": "المظهر",
        "about_text": "صلّح النص المكتوب بلغة الكيبورد الغلط بضغطة واحدة.\n"
                      "شغّال في أي برنامج وبيفضل هادي في شريط المهام.",
        "open_folder": "فتح مجلد الإعدادات",
        "converted": "{a} ← {b}",
        "nothing": "مفيش حاجة تتحوّل",
        "admin_app": "مش قادر أوصل للبرنامج ده. شغّل Keyboard Flip كمسؤول",
        "unchanged": "مفيش تغيير",
        "layout_missing": "نوع الكيبورد غير متاح",
        "nothing_to_undo": "مفيش حاجة للتراجع عنها",
        "undone": "تم التراجع",
        "tray_open": "فتح",
        "tray_enabled": "مفعّل",
        "tray_quit": "خروج",
        "still_running": "البرنامج لسه شغّال في شريط المهام",
    },
}

_LANG_NAMES = {
    "en": {"en": "English", "ar": "Arabic", "de": "German", "fr": "French",
           "es": "Spanish", "ru": "Russian"},
    "ar": {"en": "الإنجليزية", "ar": "العربية", "de": "الألمانية", "fr": "الفرنسية",
           "es": "الإسبانية", "ru": "الروسية"},
}

_lang = "en"


def set_language(code):
    global _lang
    _lang = code if code in _STRINGS else "en"


def get_language():
    return _lang


def tr(key):
    return _STRINGS[_lang].get(key) or _STRINGS["en"].get(key, key)


def lang_name(code):
    return _LANG_NAMES[_lang][code]
