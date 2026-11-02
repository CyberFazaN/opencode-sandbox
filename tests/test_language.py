"""D-013: active documents and messages are English.

Lightweight on purpose: letters outside ASCII and frequent German, French and Spanish function
words are reported; in Python files only comments and strings are read for words."""
import io
import re
import tokenize
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# A maintainer's untracked local instructions (AGENTS.md, .gitignore) are not part of the tree.
LOCAL_DOCS = {"AGENTS.local.md"}
# Intentional non-English letters: a test fixture file name.
ALLOWED = {"tests/test_gitflow_roundtrip.py": {"ü"}, "tests/integration/test_10_lifecycle.py": {"ü"}}
FOREIGN = {"und", "nicht", "oder", "wird", "werden", "für", "auch", "sind", "dass", "wenn", "keine", "bitte", "eine",
           "ist", "das", "der", "avec", "pour", "dans", "sont", "les", "une", "est", "para", "los", "las", "una", "que"}


def active_files():
    files = sorted(p for p in ROOT.glob("*.md") if p.name not in LOCAL_DOCS) + [ROOT / "pyproject.toml"]
    files += sorted((ROOT / "docs").glob("*.md"))
    files += sorted((ROOT / "docs" / "engineering").rglob("*.md"))
    files += sorted(p for p in (ROOT / ".github").rglob("*") if p.is_file())
    for top in ("src", "tests"):
        files += sorted(p for p in (ROOT / top).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    return [p for p in files if p != Path(__file__).resolve()]  # this file quotes foreign samples


def prose(path, text):
    """The text in which words are checked: everything, or a Python file's comments and strings."""
    if path.suffix != ".py":
        return text
    parts = []
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type in (tokenize.COMMENT, tokenize.STRING) or tok.type == getattr(tokenize, "FSTRING_MIDDLE", -1):
            parts.append(tok.string)
    return "\n".join(parts)


def problems(text, words_text=None, allowed=frozenset()):
    found = []
    for word in re.findall(r"\w+", text):
        letters = "".join(ch for ch in word if not ch.isascii() and unicodedata.category(ch).startswith("L"))
        if letters and word not in allowed and letters not in allowed:
            found.append(word)
    found += [w for w in re.findall(r"\b[a-zßäöüàâçéèêëîïôûùÿñ]+\b", text if words_text is None else words_text) if w in FOREIGN]
    return found


def test_the_check_detects_other_languages():
    assert problems("Die Datei wird nicht gelöscht") == ["gelöscht", "wird", "nicht"]
    assert problems("Удалить окружение") == ["Удалить", "окружение"]
    assert problems("Le fichier est supprimé pour toujours") == ["supprimé", "est", "pour"]
    assert problems("Delete the environment — it is gone (≈ 2 GB, → next)") == []


def test_active_documents_and_messages_are_english():
    bad = {}
    for path in active_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # binary asset
        rel = path.relative_to(ROOT).as_posix()
        found = problems(text, prose(path, text), ALLOWED.get(rel, frozenset()))
        if found:
            bad[rel] = sorted(set(found))
    assert bad == {}
