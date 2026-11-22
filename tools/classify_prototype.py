#!/usr/bin/env python3
"""Protótipo em Python das regras do dicionário, medido contra o gabarito.

Uso:
    python tools/classify_prototype.py [--dir test_data/synthetic]

Não é o classificador final (esse é C++ na Etapa 2): serve para validar as regras de
data/name_dictionary.json antes de implementar, e para medir a meta de 80% de acerto.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

DICT = json.loads((Path(__file__).resolve().parent.parent / "data" / "name_dictionary.json").read_text(encoding="utf-8"))
TERMS = {t: g for g, spec in DICT["groups"].items() for t in spec["terms"]}
NORM = DICT["normalization"]
PRIORITY = DICT["matching_rules"]["priority_when_several"]
DROP = set(NORM["generic_prefixes"]) | set(NORM["version_suffixes"])


def tokens(filename: str) -> list[str]:
    s = re.sub(r"\.wav$", "", filename, flags=re.I)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[_\-.()\[\]]", " ", s)
    s = re.sub(r"(?<=[a-z])(?=[0-9])|(?<=[0-9])(?=[a-z])", " ", s)
    out = []
    for tok in s.split():
        if tok in TERMS:
            out.append(tok)
        elif tok in DROP or re.fullmatch(NORM["number_like_tokens_regex"], tok):
            continue
        else:
            out.append(tok)
    return out


def classify(filename: str) -> str:
    toks = tokens(filename)
    found, i = set(), 0
    while i < len(toks):
        pair = " ".join(toks[i:i + 2])
        if len(toks[i:i + 2]) == 2 and pair in TERMS:
            found.add(TERMS[pair]); i += 2
        else:
            if toks[i] in TERMS:
                found.add(TERMS[toks[i]])
            i += 1
    for g in PRIORITY:
        if g in found:
            return g
    return "Unclassified"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default="test_data/synthetic")
    args = ap.parse_args()
    gab = json.loads((Path(args.dir) / "gabarito.json").read_text(encoding="utf-8"))

    total = right = 0
    for folder, spec in gab["folders"].items():
        for name, meta in spec["files"].items():
            got, want = classify(name), meta["group"]
            total += 1
            right += got == want
            if got != want:
                print(f"ERRO  {folder}/{name}: esperado {want}, deu {got}")
    print(f"\nAcerto: {right}/{total} = {100 * right / total:.1f}%")
    return 0 if right == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
