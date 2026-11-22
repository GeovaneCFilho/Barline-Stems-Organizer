#!/usr/bin/env python3
"""Confere se os detectores de referência (em Python) encontram exatamente os erros do gabarito.

Uso:
    python tools/verify_test_folders.py [--dir test_data/synthetic]

Serve a dois propósitos:
  1. prova que o gerador plantou o que o gabarito diz (nem a mais, nem a menos);
  2. fixa as regras de detecção em código simples, que o C++ da Etapa 1 deve reproduzir.

Regras (as mesmas que o C++ deve seguir):
  - length_mismatch:      duração diferente da duração mais comum da pasta (tolerância de 1 ms)
  - sample_rate_mismatch: taxa de amostragem diferente da mais comum
  - bit_depth_mismatch:   bit depth/formato diferente do mais comum
  - clipping:             8 ou mais amostras no fundo de escala
  - silent:               arquivo com áudio, mas todas as amostras são zero
  - empty_file:           arquivo sem nenhuma amostra
  - duplicate:            mesmo conteúdo (bytes de áudio idênticos) em arquivos diferentes
  - dual_mono:            estéreo com canais L e R idênticos
  - misaligned_start:     pico da correlação cruzada com a mix de referência a mais de 5 ms
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wavio import Wav, read_wav  # noqa: E402

CLIP_MIN_SAMPLES = 8
DURATION_TOL_S = 0.001
MISALIGN_TOL_S = 0.005
MISALIGN_SEARCH_S = 1.0


def mono_sum(w: Wav) -> np.ndarray:
    return w.samples().mean(axis=1)


def best_lag(stem: np.ndarray, ref: np.ndarray, sr: int) -> int:
    """Atraso (em amostras) em que o stem melhor casa com a mix. Positivo = stem atrasado."""
    n = len(stem) + len(ref)
    corr = np.fft.irfft(np.fft.rfft(stem, n) * np.conj(np.fft.rfft(ref, n)), n)
    max_lag = int(MISALIGN_SEARCH_S * sr)
    window = np.concatenate([corr[:max_lag + 1], corr[-max_lag:]])
    lags = np.concatenate([np.arange(0, max_lag + 1), np.arange(-max_lag, 0)])
    # Máximo COM sinal: o módulo confundiria meia-onda de um tom grave (fase invertida) com atraso.
    return int(lags[int(np.argmax(window))])


def analyze(folder: Path, reference: Path | None) -> set[tuple[str, str]]:
    wavs = {p.name: read_wav(p) for p in sorted(folder.glob("*.wav"))}
    found: set[tuple[str, str]] = set()

    with_audio = {n: w for n, w in wavs.items() if w.frames > 0}
    for name, w in wavs.items():
        if w.frames == 0:
            found.add((name, "empty_file"))

    if with_audio:
        common_dur = Counter(round(w.duration_s, 3) for w in with_audio.values()).most_common(1)[0][0]
        common_sr = Counter(w.sample_rate for w in with_audio.values()).most_common(1)[0][0]
        common_fmt = Counter((w.bit_depth, w.is_float) for w in with_audio.values()).most_common(1)[0][0]
        for name, w in with_audio.items():
            if abs(w.duration_s - common_dur) > DURATION_TOL_S:
                found.add((name, "length_mismatch"))
            if w.sample_rate != common_sr:
                found.add((name, "sample_rate_mismatch"))
            if (w.bit_depth, w.is_float) != common_fmt:
                found.add((name, "bit_depth_mismatch"))

    silent = set()
    for name, w in with_audio.items():
        if not np.any(w.samples()):
            silent.add(name)
            found.add((name, "silent"))
        elif w.full_scale_count() >= CLIP_MIN_SAMPLES:
            found.add((name, "clipping"))

    groups: dict[str, list[str]] = defaultdict(list)
    for name, w in with_audio.items():
        if name not in silent:
            groups[hashlib.sha1(w.raw).hexdigest()].append(name)
    for names in groups.values():
        if len(names) > 1:
            found.update((n, "duplicate") for n in names)

    for name, w in with_audio.items():
        if name in silent or w.channels != 2:
            continue
        s = w.samples()
        if np.array_equal(s[:, 0], s[:, 1]):
            found.add((name, "dual_mono"))

    if reference is not None and reference.exists():
        ref = read_wav(reference)
        ref_m = mono_sum(ref)
        for name, w in with_audio.items():
            if name in silent or w.sample_rate != ref.sample_rate:
                continue
            lag = best_lag(mono_sum(w), ref_m, w.sample_rate)
            if abs(lag) / w.sample_rate > MISALIGN_TOL_S:
                found.add((name, "misaligned_start"))
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default="test_data/synthetic")
    args = ap.parse_args()
    root = Path(args.dir)

    gabarito = json.loads((root / "gabarito.json").read_text(encoding="utf-8"))
    failures = 0

    for fname, spec in gabarito["folders"].items():
        folder = root / fname
        problems: list[str] = []

        # 1. o formato de cada arquivo bate com o gabarito
        for name, meta in spec["files"].items():
            w = read_wav(folder / name)
            got = {"sample_rate": w.sample_rate, "bit_depth": w.bit_depth,
                   "channels": w.channels, "frames": w.frames}
            if got != meta["format"]:
                problems.append(f"formato de {name}: esperado {meta['format']}, lido {got}")
        extra = {p.name for p in folder.glob("*.wav")} - set(spec["files"])
        if extra:
            problems.append(f"arquivos fora do gabarito: {sorted(extra)}")

        # 2. os erros detectados são exatamente os plantados
        expected = {(i["file"], i["type"]) for i in spec["issues"]}
        detected = analyze(folder, folder / spec["reference_mix"])
        for item in sorted(expected - detected):
            problems.append(f"NÃO detectado: {item}")
        for item in sorted(detected - expected):
            problems.append(f"detectado a mais (falso positivo): {item}")

        status = "OK " if not problems else "FALHA"
        print(f"[{status}] {fname:28s} {len(expected)} erro(s) esperado(s)")
        for p in problems:
            print(f"         - {p}")
        failures += bool(problems)

    print(f"\n{len(gabarito['folders']) - failures}/{len(gabarito['folders'])} pastas conferem")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
