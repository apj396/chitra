"""
chitra_paths.py — where the specification documents live.

Drishti and Disha assemble their system prompts by reading the L0 wrapper and
their scaffold out of CHITRA-v1_1-Agent-Prompt-Scaffolds.md at runtime, rather
than having the prompt pasted into the source. That is deliberate: a prompt
copied into code drifts from the specification the first time either changes.

The cost of that decision is that the code needs to find the documents, and
the path is machine-specific. This resolves it in one place instead of four,
and fails with an instruction rather than a traceback.

Search order:
  1. CHITRA_SPEC_DIR environment variable, if set
  2. ./specs next to the code
  3. ../specs
  4. the code directory itself
  5. /mnt/user-data/uploads (the authoring container)
"""

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

CANDIDATES = [
    os.environ.get("CHITRA_SPEC_DIR"),
    os.path.join(HERE, "specs"),
    os.path.join(os.path.dirname(HERE), "specs"),
    HERE,
    "/mnt/user-data/uploads",
]

# Which document each consumer needs, for the error message.
NEEDED_BY = {
    "CHITRA-v1_1-Agent-Prompt-Scaffolds.md":
        "Drishti and Disha, for the L0 wrapper and agent scaffolds",
    "CHITRA-v1_2-Tool-Integration-Handoff-Compliance.md":
        "audit_field_paths.py, for the artifact schemas",
    "CHITRA-v1_2_1-Extended-Handoff-Schemas.md":
        "reconcile_vocabulary.py, for the F.12 matrix",
}


def spec_dir():
    """First candidate that actually CONTAINS a specification document.

    Not the first that exists. The code directory always exists, so an
    existence test always returned it, and every consumer then looked for
    specs in a folder that has none. That is how a stale registry got written:
    reconcile_vocabulary crashed on the missing document, the caller used ';'
    instead of '&&', and a previous run's output was copied over the top.
    """
    for c in CANDIDATES:
        if not c or not os.path.isdir(c):
            continue
        try:
            entries = {_key(e) for e in os.listdir(c)}
        except OSError:
            continue
        if any(_key(k) in entries for k in NEEDED_BY):
            return c
    for c in CANDIDATES:
        if c and os.path.isdir(c):
            return c
    return HERE


def _key(name):
    """Compare filenames ignoring separator style and case.

    The documents are versioned as v1.1, v1.2.1 and so on. Some copies arrive
    with the dots converted to underscores, because several upload and export
    paths sanitise dots in filenames. CHITRA-v1.1-Agent-Prompt-Scaffolds.md and
    CHITRA-v1_1-Agent-Prompt-Scaffolds.md are the same document and both are
    correct names for it, so matching strips separators rather than demanding
    one style. Renaming the file would be the wrong fix.
    """
    return re.sub(r"[._\-\s]", "", name.lower())


def spec_file(filename, required=True):
    """Absolute path to a specification document.

    Raises FileNotFoundError with an instruction, not a bare path, because the
    person hitting this is setting the project up rather than debugging it.
    """
    wanted = _key(filename)
    for c in CANDIDATES:
        if not c or not os.path.isdir(c):
            continue
        p = os.path.join(c, filename)
        if os.path.isfile(p):
            return p
        for entry in os.listdir(c):
            if _key(entry) == wanted:
                return os.path.join(c, entry)
    if not required:
        return None
    looked = "\n".join(
        f"    {c}" + ("" if os.path.isdir(c) else "   (does not exist)")
        for c in CANDIDATES if c)
    raise FileNotFoundError(
        f"\n\nCannot find the specification document:\n    {filename}\n"
        f"\nNeeded by: {NEEDED_BY.get(filename, 'the CHITRA runtime')}\n"
        f"\nLooked in:\n{looked}\n"
        f"\nTo fix it, create a 'specs' folder beside the code and copy the\n"
        f"CHITRA specification documents into it:\n"
        f"    mkdir specs\n"
        f"    copy \"<wherever your CHITRA .md files are>\\{filename}\" specs\\\n"
        f"\nOr point CHITRA_SPEC_DIR at the folder that already holds them:\n"
        f"    set CHITRA_SPEC_DIR=C:\\path\\to\\your\\chitra\\specs\n")


def check_specs(filenames):
    """Return the list of documents that are missing. Does not raise."""
    return [f for f in filenames if spec_file(f, required=False) is None]
