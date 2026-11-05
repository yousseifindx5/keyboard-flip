"""Keyboard layout tables and text conversion (pure Python, no Windows needed).

Every layout is described by the character produced by each physical key,
in two layers (normal / shift).  Converting text from layout A to layout B
means: find the key that produced each character in A, then output what the
same key produces in B.

Position order (48 slots; the last one is the extra ISO key):
  row0  ` 1 2 3 4 5 6 7 8 9 0 - =          (13)
  row1  q w e r t y u i o p [ ] \\          (13)
  row2  a s d f g h j k l ; '              (11)
  row3  z x c v b n m , . /                (10)
  extra the ISO "102nd" key                 (1)
"""
import math
import re
from functools import lru_cache

SLOTS = 48


class LayoutUnavailable(Exception):
    pass


# --------------------------------------------------------------------------
# Static tables for the three base layouts (always available, no Windows API)
# --------------------------------------------------------------------------
EN_US_N = ("` 1 2 3 4 5 6 7 8 9 0 - = "
           "q w e r t y u i o p [ ] \\ "
           "a s d f g h j k l ; ' "
           "z x c v b n m , . /").split(" ")
EN_US_S = ("~ ! @ # $ % ^ & * ( ) _ + "
           "Q W E R T Y U I O P { } | "
           "A S D F G H J K L : \" "
           "Z X C V B N M < > ?").split(" ")

# Arabic (101).  Diacritics are written as escapes so they stay readable:
# \u0651 shadda  \u064E fatha  \u064B fathatan  \u064F damma  \u064C dammatan
# \u0650 kasra   \u064D kasratan  \u0652 sukun  \u0640 tatweel
AR_101_N = ("ذ 1 2 3 4 5 6 7 8 9 0 - = "
            "ض ص ث ق ف غ ع ه خ ح ج د \\ "
            "ش س ي ب ل ا ت ن م ك ط "
            "ئ ء ؤ ر \u0644\u0627 ى ة و ز ظ").split(" ")
AR_101_S = ("\u0651 ! @ # $ % ^ & * ( ) _ + "
            "\u064E \u064B \u064F \u064C \u0644\u0625 \u0625 \u2018 \u00F7 \u00D7 \u061B < > | "
            "\u0650 \u064D ] [ \u0644\u0623 \u0623 \u0640 \u060C / : \" "
            "~ \u0652 } { \u0644\u0622 \u0622 \u2019 , . \u061F").split(" ")

# Russian (standard PC layout, ЙЦУКЕН)
RU_N = ("ё 1 2 3 4 5 6 7 8 9 0 - = "
        "й ц у к е н г ш щ з х ъ \\ "
        "ф ы в а п р о л д ж э "
        "я ч с м и т ь б ю .").split(" ")
RU_S = ("Ё ! \" № ; % : ? * ( ) _ + "
        "Й Ц У К Е Н Г Ш Щ З Х Ъ / "
        "Ф Ы В А П Р О Л Д Ж Э "
        "Я Ч С М И Т Ь Б Ю ,").split(" ")

def _t(text):
    """Space-separated tokens; the placeholder ∅ means 'this key types nothing'."""
    return ["" if t == "∅" else t for t in text.split(" ")]


# German (QWERTZ) - includes the ISO "<>" key as the 48th slot
DE_N = _t("^ 1 2 3 4 5 6 7 8 9 0 ß ´ "
          "q w e r t z u i o p ü + # "
          "a s d f g h j k l ö ä "
          "y x c v b n m , . - <")
DE_S = _t("° ! \" § $ % & / ( ) = ? ` "
          "Q W E R T Z U I O P Ü * ' "
          "A S D F G H J K L Ö Ä "
          "Y X C V B N M ; : _ >")

# French (AZERTY)
FR_N = _t("² & é \" ' ( - è _ ç à ) = "
          "a z e r t y u i o p ^ $ * "
          "q s d f g h j k l m ù "
          "w x c v b n , ; : ! <")
FR_S = _t("∅ 1 2 3 4 5 6 7 8 9 0 ° + "
          "A Z E R T Y U I O P ¨ £ µ "
          "Q S D F G H J K L M % "
          "W X C V B N ? . / § >")

# Spanish (Spain)
ES_N = _t("º 1 2 3 4 5 6 7 8 9 0 ' ¡ "
          "q w e r t y u i o p ` + ç "
          "a s d f g h j k l ñ ´ "
          "z x c v b n m , . - <")
ES_S = _t("ª ! \" · $ % & / ( ) = ? ¿ "
          "Q W E R T Y U I O P ^ * Ç "
          "A S D F G H J K L Ñ ¨ "
          "Z X C V B N M ; : _ >")

STATIC = {
    "en-US": (EN_US_N, EN_US_S),
    "ar-101": (AR_101_N, AR_101_S),
    "ru": (RU_N, RU_S),
    "de-DE": (DE_N, DE_S),
    "fr-FR": (FR_N, FR_S),
    "es-ES": (ES_N, ES_S),
}

# layout id -> (display name, Windows KLID, language code)
# Layouts without a static table are read from Windows itself at runtime.
LAYOUT_INFO = {
    "en-US": ("English (US)", "00000409", "en"),
    "en-GB": ("English (UK)", "00000809", "en"),
    "ar-101": ("Arabic (101)", "00000401", "ar"),
    "ar-102": ("Arabic (102)", "00010401", "ar"),
    "ar-102az": ("Arabic (102) AZERTY", "00020401", "ar"),
    "ru": ("Russian", "00000419", "ru"),
    "de-DE": ("German (QWERTZ)", "00000407", "de"),
    "fr-FR": ("French (AZERTY)", "0000040C", "fr"),
    "es-ES": ("Spanish (Spain)", "0000040A", "es"),
    "es-LA": ("Spanish (Latin America)", "0000080A", "es"),
    # Added in 1.1: these have no static table, Windows itself tells us what each key types.
    "tr": ("Turkish (Q)", "0000041F", "tr"),
    "uk": ("Ukrainian", "00000422", "uk"),
    "fa": ("Persian", "00000429", "fa"),
    "hi": ("Hindi (Devanagari INSCRIPT)", "00000439", "hi"),
    "ur": ("Urdu", "00000420", "ur"),
    "it": ("Italian", "00000410", "it"),
    "pt-PT": ("Portuguese (Portugal)", "00000816", "pt"),
    "pt-BR": ("Portuguese (Brazil ABNT2)", "00010416", "pt"),
    "el": ("Greek", "00000408", "el"),
}

LANGUAGES = {
    "en": {"script": "latin", "layouts": ["en-US", "en-GB"]},
    "ar": {"script": "arabic", "layouts": ["ar-101", "ar-102", "ar-102az"]},
    "de": {"script": "latin", "layouts": ["de-DE"]},
    "fr": {"script": "latin", "layouts": ["fr-FR"]},
    "es": {"script": "latin", "layouts": ["es-ES", "es-LA"]},
    "ru": {"script": "cyrillic", "layouts": ["ru"]},
    "tr": {"script": "latin", "layouts": ["tr"]},
    "uk": {"script": "cyrillic", "layouts": ["uk"]},
    "fa": {"script": "arabic", "layouts": ["fa"]},
    "hi": {"script": "devanagari", "layouts": ["hi"]},
    "ur": {"script": "arabic", "layouts": ["ur"]},
    "it": {"script": "latin", "layouts": ["it"]},
    "pt": {"script": "latin", "layouts": ["pt-PT", "pt-BR"]},
    "el": {"script": "greek", "layouts": ["el"]},
}

DEFAULT_LAYOUTS = {"en": "en-US", "ar": "ar-101", "de": "de-DE", "fr": "fr-FR",
                   "es": "es-ES", "ru": "ru", "tr": "tr", "uk": "uk", "fa": "fa",
                   "hi": "hi", "ur": "ur", "it": "it", "pt": "pt-PT", "el": "el"}

# The languages that are switched on for a fresh install (the others are opt-in).
DEFAULT_LANGUAGES = ["en", "ar", "de", "fr", "es", "ru"]

# Right-to-left scripts: the caret moves the other way when selecting a word.
RTL_SCRIPTS = frozenset({"arabic"})


def _pad(tokens):
    tokens = list(tokens)
    return tokens + [""] * (SLOTS - len(tokens))


@lru_cache(maxsize=None)
def get_layout(layout_id):
    if layout_id not in LAYOUT_INFO:
        raise LayoutUnavailable(layout_id)
    name, klid, lang = LAYOUT_INFO[layout_id]
    if layout_id in STATIC:
        normal, shift = STATIC[layout_id]
    else:
        from . import winapi
        data = winapi.read_layout(klid)
        if not data:
            raise LayoutUnavailable(layout_id)
        normal, shift = data
    return {
        "id": layout_id,
        "name": name,
        "script": LANGUAGES[lang]["script"],
        "normal": _pad(normal),
        "shift": _pad(shift),
    }


def layout_available(layout_id):
    try:
        get_layout(layout_id)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------
# Conversion
# --------------------------------------------------------------------------
def build_map(src, dst, symbols=False):
    """char/token in `src` layout -> char/token on the same key of `dst`.

    Typing from a non-Latin layout rarely produces plain ASCII punctuation on
    purpose, so by default ASCII is left alone. With symbols=True, ASCII symbols
    are also converted when the same key is a *letter* on `dst`
    (e.g. Shift+D on the Arabic layout types "]", which really is a capital D).
    """
    table = {}
    latin_src = src["script"] == "latin"
    for layer in ("normal", "shift"):  # normal layer wins on conflicts
        for i, s in enumerate(src[layer]):
            d = dst[layer][i]
            if not s or not d or s in table:
                continue
            if not latin_src and s.isascii() and not (symbols and d.isalpha()):
                continue
            table[s] = d
    return table


@lru_cache(maxsize=None)
def get_table(src_id, dst_id, symbols=False):
    return build_map(get_layout(src_id), get_layout(dst_id), symbols)


def convert_text(text, table, skip_multi=frozenset()):
    """Replace every char/token via `table`. Positions in `skip_multi` may not
    start a multi-character token (used to read a lam-alef as two keys)."""
    if not table:
        return text
    maxlen = max(len(k) for k in table)  # e.g. 2 for the Arabic lam-alef keys
    out = []
    i, n = 0, len(text)
    while i < n:
        for size in range(min(maxlen, n - i), 0, -1):
            if size > 1 and i in skip_multi:
                continue
            chunk = text[i:i + size]
            if chunk in table:
                out.append(table[chunk])
                i += size
                break
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


# --------------------------------------------------------------------------
# Lam-alef ambiguity.  On Arabic keyboards the key `b` types "لا", but the two
# keys `g` + `h` type exactly the same text.  When converting Arabic -> English
# we try both readings of every word and keep the one that looks most like
# English (rough letter-pair frequencies, % of all pairs).
# --------------------------------------------------------------------------
_PAIRS = dict(
    (p.split(":")[0], float(p.split(":")[1])) for p in (
        "th:3.88 he:3.68 in:2.28 er:2.17 an:2.14 re:1.75 on:1.72 at:1.4 en:1.38 nd:1.35 "
        "ti:1.28 es:1.28 or:1.27 te:1.2 of:1.17 ed:1.17 is:1.13 it:1.12 al:1.09 ar:1.07 "
        "st:1.05 to:1.04 nt:1.04 ng:0.95 se:0.93 ha:0.93 as:0.87 ou:0.87 io:0.83 le:0.83 "
        "ve:0.83 co:0.79 me:0.79 de:0.76 hi:0.76 ri:0.73 ro:0.73 ic:0.7 ne:0.69 ea:0.69 "
        "ra:0.69 ce:0.65 li:0.62 ch:0.6 ll:0.58 be:0.58 ma:0.57 si:0.55 om:0.55 ur:0.54 "
        "ca:0.54 el:0.53 ta:0.53 la:0.51 ns:0.51 di:0.5 fo:0.5 ho:0.5 pe:0.49 ec:0.48 "
        "pr:0.47 no:0.46 ct:0.46 us:0.46 ac:0.45 ot:0.45 il:0.44 tr:0.44 ly:0.43 nc:0.43 "
        "et:0.42 ut:0.41 ss:0.41 so:0.4 rs:0.4 un:0.4 lo:0.39 wa:0.39 ge:0.38 ie:0.38 "
        "wh:0.38 ee:0.37 wi:0.37 em:0.36 ad:0.36 ol:0.36 rt:0.35 po:0.35 we:0.34 na:0.34 "
        "ul:0.33 ni:0.33 ts:0.33 mo:0.32 ow:0.32 pa:0.31 im:0.31 mi:0.3 ai:0.3 sh:0.3 "
        "ir:0.29 su:0.29 id:0.28 os:0.28 iv:0.28 ia:0.27 am:0.27 fi:0.26 ab:0.25 bo:0.22 "
        "ag:0.22 ig:0.22 ht:0.2 gh:0.18 gl:0.15 ob:0.17 ba:0.2 bi:0.15 bl:0.16 bu:0.2 "
        "by:0.15 ug:0.15 ub:0.08 og:0.1 ew:0.2 ey:0.2 ay:0.2 ok:0.1 ke:0.3 ki:0.2 "
        "ld:0.3 rd:0.3 rn:0.2 ry:0.3 sa:0.25 sp:0.2 sc:0.2 lt:0.2 ft:0.2 pl:0.2 ap:0.2 "
        "ef:0.2 fe:0.3 gr:0.25 gi:0.15 ga:0.2 go:0.2 gu:0.1 oo:0.4 mp:0.2 pt:0.15 "
        "um:0.1 up:0.1 vi:0.15 wo:0.2 yo:0.15 oc:0.2 od:0.2 ff:0.15 rg:0.1 rk:0.1 nk:0.1 "
        "tu:0.15 tw:0.1 sw:0.05 ye:0.15 ls:0.1 ru:0.2 rc:0.1 rm:0.1 ev:0.3 ex:0.2 ep:0.15"
    ).split()
)
_TRIPLES = {"igh": 3.0, "ugh": 3.0, "ght": 3.0, "ough": 3.0}  # only reachable through "gh"
# Common English words spelled with "gh" - reading these as g+h is almost always right.
_GH_WORDS = set((
    "high higher highest right rights light lights night nights might mighty fight sight tight "
    "bright brighter tonight slight flight fright delight tonight weigh weight height eight eighty "
    "eighteen neighbor neighbour though through throughout thought thoughts enough tough rough "
    "bought brought caught taught daughter naughty ought fought sought straight ghost ghosts "
    "ghetto ghz laugh laughter laughing cough dough plough slaughter sigh thigh nigh knight "
    "knights highway almighty lightning frightened enlighten overnight copyright playwright "
    "wright wrights lighter lightest righteous slaughter doughnut although throughout "
).split())


def _english_score(word):
    word = word.lower()
    score = 0.0
    for i in range(len(word) - 1):
        a, b = word[i], word[i + 1]
        if a.isalpha() and b.isalpha() and a.isascii() and b.isascii():
            score += math.log(max(_PAIRS.get(a + b, 0.0), 0.01) / 100.0)
    for tri, bonus in _TRIPLES.items():
        if tri in word:
            score += bonus
    stem = re.sub(r"[^a-z]", "", word)
    if stem in _GH_WORDS or (stem.endswith("s") and stem[:-1] in _GH_WORDS):
        score += 8.0
    return score


def convert_between(text, src_id, dst_id):
    """Convert `text` typed on layout `src_id` into what the same keys give on `dst_id`."""
    src = get_layout(src_id)
    get_layout(dst_id)  # raises LayoutUnavailable early
    if src["script"] == "latin":
        return convert_text(text, get_table(src_id, dst_id))

    plain = get_table(src_id, dst_id)
    with_symbols = get_table(src_id, dst_id, True)
    english_target = LAYOUT_INFO[dst_id][2] == "en"
    out = []
    for piece in re.split(r"(\s+)", text):
        if not piece or piece.isspace():
            out.append(piece)
            continue
        # Symbols like "/" or "]" are only converted inside words that also contain
        # letters of the source alphabet, so "2026/11/03" and "[x]" stay untouched.
        table = with_symbols if any(not c.isascii() for c in piece) else plain
        multi = [k for k in table if len(k) > 1]
        if not (multi and src["script"] == "arabic" and english_target):
            out.append(convert_text(piece, table))
            continue
        spots = [i for i in range(len(piece)) if any(piece.startswith(k, i) for k in multi)]
        if not spots or len(spots) > 8:
            out.append(convert_text(piece, table))
            continue
        best = None
        for mask in range(1 << len(spots)):  # mask 0 = read as one lam-alef key
            skip = frozenset(p for j, p in enumerate(spots) if (mask >> j) & 1)
            candidate = convert_text(piece, table, skip)
            score = _english_score(candidate)
            if best is None or score > best[0]:
                best = (score, candidate)
        out.append(best[1])
    return "".join(out)


def script_counts(text):
    ar = sum(1 for c in text if "\u0600" <= c <= "\u06FF" or "\u0750" <= c <= "\u077F")
    cy = sum(1 for c in text if "\u0400" <= c <= "\u04FF")
    hi = sum(1 for c in text if "\u0900" <= c <= "\u097F")
    el = sum(1 for c in text if "\u0370" <= c <= "\u03FF" or "\u1F00" <= c <= "\u1FFF")
    la = sum(1 for c in text if c.isalpha() and c.isascii())
    return {"arabic": ar, "cyrillic": cy, "devanagari": hi, "greek": el, "latin": la}
