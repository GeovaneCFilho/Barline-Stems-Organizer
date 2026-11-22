#!/usr/bin/env python3
"""Lista os WAV de uma pasta de stems reais e cria um rascunho de gabarito para você preencher.

Uso:
    python tools/scan_real_folder.py "D:/Projetos/MinhaMusica/Stems" [--out test_data/real]

Cria test_data/real/<nome-da-pasta>.gabarito.json com o formato de cada arquivo (lido do
cabeçalho) e dois campos para você preencher à mão depois de ouvir/conferir a pasta:
  - "group": o grupo certo do stem (Drums, Bass, Melodic, Atmosphere, Vocals ou Unclassified)
  - "issues": os erros reais da pasta, com os mesmos tipos do gabarito sintético
Também avisa de diferenças óbvias (duração, taxa, bit depth) para você não esquecer de anotar.

Nada é copiado nem alterado na pasta original; os WAV reais NÃO devem ir para o git.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wavio import read_header  # noqa: E402

GROUPS = ["Drums", "Bass", "Melodic", "Atmosphere", "Vocals", "Unclassified"]
ISSUE_TYPES = [
    "length_mismatch", "sample_rate_mismatch", "bit_depth_mismatch", "clipping",
    "silent", "empty_file", "duplicate", "dual_mono", "misaligned_start",
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", help="pasta com os stems (WAV)")
    ap.add_argument("--out", default="test_data/real", help="onde salvar o rascunho do gabarito")
    args = ap.parse_args()

    folder = Path(args.folder)
    wavs = sorted(folder.glob("*.wav"), key=lambda p: p.name.lower())
    if not wavs:
        print(f"Nenhum .wav em {folder}", file=sys.stderr)
        return 1

    files = {}
    for p in wavs:
        try:
            h = read_header(p)
        except Exception as e:  # arquivo corrompido também é informação útil
            files[p.name] = {"group": None, "unreadable": str(e)}
            continue
        files[p.name] = {
            "group": None,
            "format": {
                "sample_rate": h.sample_rate, "bit_depth": h.bit_depth,
                "channels": h.channels, "frames": h.frames,
                "duration_s": round(h.duration_s, 3), "float": h.is_float,
            },
        }

    ok = [f["format"] for f in files.values() if "format" in f]
    notes = []
    if ok:
        for label, key in (("duração (s)", "duration_s"), ("taxa de amostragem", "sample_rate"),
                           ("bit depth", "bit_depth"), ("canais", "channels")):
            values = Counter(f[key] for f in ok)
            if len(values) > 1:
                notes.append(f"{label} varia: {dict(values)}")

    out = {
        "source_folder_name": folder.name,
        "allowed_groups": GROUPS,
        "allowed_issue_types": ISSUE_TYPES,
        "files": files,
        "issues": [],
        "todo": "Preencha 'group' de cada arquivo e liste em 'issues' os erros reais "
                "(ex.: {\"file\": \"Kick.wav\", \"type\": \"clipping\", \"detail\": {}}).",
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{folder.name}.gabarito.json"
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"{len(wavs)} arquivo(s) em '{folder.name}'")
    for n in notes:
        print(f"  atenção: {n}")
    print(f"Rascunho salvo em {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
