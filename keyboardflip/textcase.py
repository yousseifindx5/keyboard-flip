"""Letter-case helpers (pure Python, no Windows needed).

One shortcut walks through three states, one step per press:
    lower / mixed  ->  UPPER CASE  ->  Sentence case  ->  lower case  ->  UPPER CASE ...
"""

_SENTENCE_END = ".!?؟…\n\r"  # . ! ? Arabic question mark, ellipsis, line breaks


def sentence_case(text):
    """First letter of every sentence in capitals, everything else in lower case."""
    out, capitalize = [], True
    for ch in text.lower():
        if capitalize and ch.isalpha():
            out.append(ch.upper())
            capitalize = False
            continue
        out.append(ch)
        if ch in _SENTENCE_END:
            capitalize = True
        elif ch.isalnum():  # a digit or a letter without a capital form starts the sentence
            capitalize = False
    return "".join(out)


def cycle_case(text):
    """Return (new_text, state) where state is 'upper', 'sentence' or 'lower'.

    The next state is worked out from the text itself, so no memory is needed
    between presses. A state that would not change anything (for example the
    single letter "A", which is both upper and sentence case) is skipped.
    """
    names = ("upper", "sentence", "lower")
    states = (text.upper(), sentence_case(text), text.lower())
    current = 2  # anything else (mixed case) behaves like lower case: go to UPPER next
    for i, candidate in enumerate(states):
        if candidate == text:
            current = i
            break
    for step in (1, 2, 3):
        index = (current + step) % 3
        if states[index] != text:
            return states[index], names[index]
    return text, names[current]
