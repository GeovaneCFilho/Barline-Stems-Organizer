#!/usr/bin/env python3
"""Gera pastas de stems sintéticas com erros plantados e o gabarito (gabarito.json).

Uso:
    python tools/make_test_folders.py [--out test_data/synthetic] [--seed 1]

Cada pasta tem 12 stems (WAV 24 bits, 44,1 kHz, 4 s) e uma mix de referência em
reference/mix.wav, calculada a partir dos stems corretos. Os erros plantados e o grupo
esperado de cada arquivo ficam no gabarito.json, que os testes automáticos das Etapas 1 e 2
usam como verdade.

A saída é determinística: a mesma semente gera exatamente os mesmos arquivos.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import zlib
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wavio import write_wav  # noqa: E402

SR = 44100
DUR = 4.0
BITS = 24
BEAT = 0.5  # 120 bpm
TAXONOMY = ["Drums", "Bass", "Melodic", "Atmosphere", "Vocals"]


# ---------------------------------------------------------------- sinais sintéticos
def _place(out: np.ndarray, start: int, seg: np.ndarray) -> None:
    n = len(out)
    if start >= n:
        return
    end = min(n, start + len(seg))
    out[start:end] += seg[: end - start]


def _env_ar(t: np.ndarray, attack: float, decay: float) -> np.ndarray:
    return np.minimum(1.0, t / max(attack, 1e-6)) * np.exp(-t * decay)


def g_kick(sr, dur, rng):
    out = np.zeros(int(sr * dur))
    L = int(0.4 * sr)
    t = np.arange(L) / sr
    seg = np.sin(2 * np.pi * np.cumsum(45 + 120 * np.exp(-t * 40)) / sr) * np.exp(-t * 7)
    for b in range(int(dur / BEAT) + 1):
        _place(out, int(b * BEAT * sr), seg)
    return out[:, None]


def g_clap(sr, dur, rng):
    out = np.zeros(int(sr * dur))
    L = int(0.25 * sr)
    t = np.arange(L) / sr
    for k in range(int(dur) + 1):
        _place(out, int((0.5 + k) * sr), rng.standard_normal(L) * np.exp(-t * 18))
    return out[:, None]


def g_hats(sr, dur, rng):
    out = np.zeros(int(sr * dur))
    L = int(0.08 * sr)
    t = np.arange(L) / sr
    for k in range(int(dur / 0.25) + 1):
        _place(out, int(k * 0.25 * sr), np.diff(rng.standard_normal(L + 1)) * np.exp(-t * 60))
    return out[:, None]


def g_sub(sr, dur, rng):
    out = np.zeros(int(sr * dur))
    L = int(1.0 * sr)
    t = np.arange(L) / sr
    seg = np.sin(2 * np.pi * 55 * t) * _env_ar(t, 0.02, 1.2)
    for k in range(int(dur) + 1):
        _place(out, int(k * sr), seg)
    return out[:, None]


def g_bass(sr, dur, rng):
    out = np.zeros(int(sr * dur))
    L = int(0.5 * sr)
    t = np.arange(L) / sr
    for i, f0 in enumerate([55.0, 55.0, 65.4, 49.0] * 4):
        w = 2 * np.pi * f0 * t
        seg = sum(np.sin(k * w) / k for k in range(1, 7)) * _env_ar(t, 0.005, 3.0)
        _place(out, int(i * BEAT * sr), seg)
    return out[:, None]


def g_piano(sr, dur, rng):
    n = int(sr * dur)
    out = np.zeros((n, 2))
    L = int(2.0 * sr)
    t = np.arange(L) / sr
    seg = sum(
        np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * 2 * f * t)
        for f in (261.6, 329.6, 392.0)
    ) * _env_ar(t, 0.003, 1.5)
    delay = int(0.0003 * sr)
    for k in range(int(dur / 2.0) + 1):
        _place(out[:, 0], int(k * 2.0 * sr), seg)
        _place(out[:, 1], int(k * 2.0 * sr) + delay, seg)
    return out


def g_pluck(sr, dur, rng):
    out = np.zeros(int(sr * dur))
    L = int(0.25 * sr)
    t = np.arange(L) / sr
    for i, f in enumerate([523.3, 659.3, 784.0, 659.3] * 8):
        seg = (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(4 * np.pi * f * t)) * _env_ar(t, 0.002, 14)
        _place(out, int(i * 0.25 * sr), seg)
    return out[:, None]


def g_lead(sr, dur, rng):
    out = np.zeros(int(sr * dur))
    L = int(1.0 * sr)
    t = np.arange(L) / sr
    vib = 1 + 0.01 * np.sin(2 * np.pi * 5 * t)
    for k, f in enumerate([880.0, 988.0, 1047.0, 988.0, 880.0]):
        seg = np.sin(2 * np.pi * f * t * vib) * _env_ar(t, 0.01, 1.0)
        _place(out, int(k * sr), seg)
    return out[:, None]


def g_pad(sr, dur, rng):
    n = int(sr * dur)
    t = np.arange(n) / sr
    out = np.zeros((n, 2))
    for ch, det in enumerate((0.5, -0.5)):
        for f in (130.8, 164.8, 196.0):
            out[:, ch] += np.sin(2 * np.pi * (f + det) * t) + 0.3 * np.sin(2 * np.pi * (f * 2 - det) * t)
    return out * np.minimum(1.0, t / 1.5)[:, None]


def g_fx(sr, dur, rng):
    n = int(sr * dur)
    ramp = (np.arange(n) / n) ** 2
    return rng.standard_normal((n, 2)) * ramp[:, None]


def g_vocal_main(sr, dur, rng):
    out = np.zeros(int(sr * dur))
    L = int(0.8 * sr)
    t = np.arange(L) / sr
    for k, f0 in enumerate([220.0, 247.0, 262.0, 247.0, 220.0]):
        seg = sum(np.sin(2 * np.pi * f0 * h * t) / h for h in range(1, 9)) * _env_ar(t, 0.03, 1.5)
        _place(out, int((0.2 + k * 0.9) * sr), seg)
    return out[:, None]


def g_vocal_chops(sr, dur, rng):
    out = np.zeros(int(sr * dur))
    L = int(0.125 * sr)
    t = np.arange(L) / sr
    for k, f0 in enumerate([330.0, 392.0, 440.0, 349.0] * 4):
        seg = sum(np.sin(2 * np.pi * f0 * h * t) / h for h in range(1, 7)) * _env_ar(t, 0.004, 12)
        _place(out, int(k * BEAT * sr), seg)
    return out[:, None]


# key: (nome EN, nome PT-BR, grupo, gerador)
STEMS = {
    "kick": ("Kick", "Bumbo", "Drums", g_kick),
    "clap": ("Clap", "Palma", "Drums", g_clap),
    "hats": ("Hats", "Chimbal", "Drums", g_hats),
    "sub": ("Sub", "Sub", "Bass", g_sub),
    "bass": ("Bass", "Baixo", "Bass", g_bass),
    "piano": ("Piano", "Piano", "Melodic", g_piano),
    "pluck": ("Pluck", "Pluck", "Melodic", g_pluck),
    "lead": ("Lead", "Lead", "Melodic", g_lead),
    "pad": ("Pad", "Pad", "Atmosphere", g_pad),
    "fx": ("FX Riser", "Subida FX", "Atmosphere", g_fx),
    "vocal": ("Vocal Main", "Voz Principal", "Vocals", g_vocal_main),
    "chops": ("Vocal Chops", "Chops Vocais", "Vocals", g_vocal_chops),
}

# Nomes bagunçados para testar o classificador. grupo None = deve cair em "Unclassified".
MESSY = {
    "kick": ("Mixer 03 - Kick (2).wav", "Drums"),
    "clap": ("Insert 7 Clap_final.wav", "Drums"),
    "hats": ("Audio_Hat_Open v2.wav", "Drums"),
    "sub": ("sub808.wav", "Bass"),
    "bass": ("BASSLINE_dry_01.wav", "Bass"),
    "piano": ("keys - chords.wav", "Melodic"),
    "pluck": ("Pluck 12.wav", "Melodic"),
    "lead": ("SYNTH 1.wav", None),
    "pad": ("pad_warm_(3).wav", "Atmosphere"),
    "fx": ("sample 04.wav", None),
    "vocal": ("Vox_Lead_DRY.wav", "Vocals"),  # armadilha: contém "Lead"
    "chops": ("Chops VOCAIS 2.wav", "Vocals"),
}


def render(key: str, sr: int, dur: float, peak: float = 0.6) -> np.ndarray:
    """Renderiza um stem de forma determinística; pico normalizado em `peak`."""
    rng = np.random.default_rng(zlib.crc32(key.encode()))
    x = STEMS[key][3](sr, dur, rng)
    return x * (peak / np.max(np.abs(x)))


# ---------------------------------------------------------------- pacote e mutações
@dataclass
class Item:
    key: str
    filename: str
    group: str  # grupo esperado ("Unclassified" quando ambíguo)
    data: np.ndarray
    sr: int = SR
    bits: int = BITS


def clean_items(names: str) -> dict[str, Item]:
    items: dict[str, Item] = {}
    for key, (en, pt, group, _gen) in STEMS.items():
        if names == "messy":
            filename, g = MESSY[key]
            group = g or "Unclassified"
        else:
            filename = (pt if names == "pt" else en) + ".wav"
        items[key] = Item(key, filename, group, render(key, SR, DUR))
    return items


def reference_mix(items: dict[str, Item]) -> np.ndarray:
    n = int(SR * DUR)
    mix = np.zeros((n, 2))
    for it in items.values():
        d = it.data
        mix += d if d.shape[1] == 2 else np.repeat(d, 2, axis=1)
    return mix * (0.8 / np.max(np.abs(mix)))


def apply(items: dict[str, Item], issues: list[dict], op: str, key: str, *args) -> None:
    it = items[key]
    if op == "length_mismatch":
        (cut_s,) = args
        it.data = render(key, it.sr, DUR - cut_s)
        issues.append({"file": it.filename, "type": op, "detail": {"short_by_s": cut_s}})
    elif op == "sample_rate_mismatch":
        (sr,) = args
        it.data, it.sr = render(key, sr, DUR), sr
        issues.append({"file": it.filename, "type": op, "detail": {"sample_rate": sr}})
    elif op == "bit_depth_mismatch":
        (bits,) = args
        it.bits = bits
        issues.append({"file": it.filename, "type": op, "detail": {"bit_depth": bits}})
    elif op == "clipping":
        (gain,) = args
        it.data = it.data * gain
        over = int(np.count_nonzero(np.abs(it.data) >= 1.0))
        issues.append({"file": it.filename, "type": op, "detail": {"min_clipped_samples": over}})
    elif op == "dual_mono":
        it.data = np.repeat(it.data[:, :1], 2, axis=1)
        issues.append({"file": it.filename, "type": op, "detail": {}})
    elif op == "silent":
        it.data = np.zeros_like(it.data)
        issues.append({"file": it.filename, "type": op, "detail": {}})
    elif op == "empty_file":
        it.data = np.zeros((0, it.data.shape[1]))
        issues.append({"file": it.filename, "type": op, "detail": {}})
    elif op == "misaligned_start":
        (offset_s,) = args
        shift = int(offset_s * it.sr)
        it.data = np.concatenate([np.zeros((shift, it.data.shape[1])), it.data[:-shift]])
        issues.append({"file": it.filename, "type": op, "detail": {"offset_ms": int(offset_s * 1000)}})
    elif op == "duplicate":
        (copy_name,) = args
        twin = deepcopy(it)
        twin.key, twin.filename = key + "_copy", copy_name
        items[twin.key] = twin
        for a, b in ((it, twin), (twin, it)):
            issues.append({"file": a.filename, "type": op, "detail": {"duplicate_of": b.filename}})
    else:
        raise ValueError(op)


FOLDERS = [
    dict(name="01_limpo_en", names="en", decoy=True, ops=[]),
    dict(name="02_limpo_ptbr", names="pt", ops=[]),
    dict(name="03_tamanho_diferente", names="en", ops=[("length_mismatch", "pad", 1.5)]),
    dict(name="04_taxa_diferente", names="en", ops=[("sample_rate_mismatch", "lead", 48000)]),
    dict(name="05_bit_depth_diferente", names="en", ops=[("bit_depth_mismatch", "bass", 16)]),
    dict(name="06_clipping", names="en", ops=[("clipping", "kick", 4.0)]),
    dict(name="07_duplicado", names="en", ops=[("duplicate", "pluck", "Pluck copy.wav")]),
    dict(name="08_dual_mono", names="en", ops=[("dual_mono", "sub")]),
    dict(name="09_vazios", names="en", ops=[("silent", "fx"), ("empty_file", "chops")]),
    dict(name="10_desalinhado", names="en", ops=[("misaligned_start", "piano", 0.25)]),
    dict(
        name="11_combinado", names="en",
        ops=[
            ("clipping", "kick", 4.0), ("length_mismatch", "pad", 1.5), ("dual_mono", "bass"),
            ("duplicate", "pluck", "Pluck copy.wav"), ("sample_rate_mismatch", "lead", 48000),
        ],
    ),
    dict(name="12_nomes_confusos", names="messy", ops=[]),
]


def build_folder(root: Path, spec: dict) -> dict:
    folder = root / spec["name"]
    if folder.exists():
        shutil.rmtree(folder)
    (folder / "reference").mkdir(parents=True)

    items = clean_items(spec["names"])
    if spec.get("decoy"):  # perto do fundo de escala, mas sem clipping: não pode ser acusado
        items["hats"].data = render("hats", SR, DUR, peak=0.99)
    write_wav(folder / "reference" / "mix.wav", reference_mix(items), SR, BITS)

    issues: list[dict] = []
    for op, key, *args in spec["ops"]:
        apply(items, issues, op, key, *args)

    files = {}
    for it in sorted(items.values(), key=lambda i: i.filename):
        write_wav(folder / it.filename, it.data, it.sr, it.bits)
        files[it.filename] = {
            "group": it.group,
            "format": {
                "sample_rate": it.sr, "bit_depth": it.bits,
                "channels": int(it.data.shape[1]), "frames": int(it.data.shape[0]),
            },
        }

    out = {
        "reference_mix": "reference/mix.wav",
        "files": files,
        "issues": sorted(issues, key=lambda i: (i["file"], i["type"])),
    }
    if spec.get("decoy"):
        out["decoys"] = [{"file": "Hats.wav", "note": "pico de cerca de -0,09 dBFS, sem clipping"}]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="test_data/synthetic", help="pasta de saída")
    args = ap.parse_args()

    root = Path(args.out)
    root.mkdir(parents=True, exist_ok=True)

    gabarito = {
        "version": 1,
        "generated_with": {"sample_rate": SR, "duration_s": DUR, "base_bit_depth": BITS},
        "taxonomy": TAXONOMY,
        "issue_types": [
            "length_mismatch", "sample_rate_mismatch", "bit_depth_mismatch", "clipping",
            "silent", "empty_file", "duplicate", "dual_mono", "misaligned_start",
        ],
        "folders": {},
    }
    for spec in FOLDERS:
        gabarito["folders"][spec["name"]] = build_folder(root, spec)
        n = len(gabarito["folders"][spec["name"]]["issues"])
        print(f"{spec['name']:28s} {n} erro(s) plantado(s)")

    (root / "gabarito.json").write_text(
        json.dumps(gabarito, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\nOK: {len(FOLDERS)} pastas e gabarito.json em {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
