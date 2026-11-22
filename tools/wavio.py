"""Leitura e escrita mínimas de WAV (PCM 16/24/32 bits e float 32).

Só depende de numpy. Existe para o Barline ter um "oráculo" independente do código C++:
os scripts de teste geram e conferem arquivos sem usar o JUCE.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np

WAVE_FORMAT_PCM = 1
WAVE_FORMAT_FLOAT = 3
WAVE_FORMAT_EXTENSIBLE = 0xFFFE


@dataclass
class WavHeader:
    sample_rate: int
    bit_depth: int
    channels: int
    frames: int
    is_float: bool

    @property
    def duration_s(self) -> float:
        return self.frames / self.sample_rate if self.sample_rate else 0.0


@dataclass
class Wav(WavHeader):
    raw: bytes = b""  # bytes do chunk 'data', exatamente como estão no arquivo

    def samples(self) -> np.ndarray:
        """Amostras em float64, formato (frames, canais), faixa nominal [-1, 1)."""
        n = self.frames * self.channels
        if n == 0:
            return np.zeros((0, self.channels), dtype=np.float64)
        if self.is_float:
            a = np.frombuffer(self.raw, dtype="<f4", count=n).astype(np.float64)
        elif self.bit_depth == 16:
            a = np.frombuffer(self.raw, dtype="<i2", count=n).astype(np.float64) / 32768.0
        elif self.bit_depth == 24:
            b = np.frombuffer(self.raw, dtype=np.uint8, count=n * 3).reshape(-1, 3)
            v = (
                b[:, 0].astype(np.int32)
                | (b[:, 1].astype(np.int32) << 8)
                | (b[:, 2].astype(np.int32) << 16)
            )
            v = np.where(v & 0x800000, v - 0x1000000, v)
            a = v.astype(np.float64) / 8388608.0
        elif self.bit_depth == 32:
            a = np.frombuffer(self.raw, dtype="<i4", count=n).astype(np.float64) / 2147483648.0
        else:
            raise ValueError(f"bit depth não suportado: {self.bit_depth}")
        return a.reshape(self.frames, self.channels)

    def full_scale_count(self) -> int:
        """Quantas amostras estão no fundo de escala (candidatas a clipping)."""
        a = np.abs(self.samples())
        if a.size == 0:
            return 0
        if self.is_float:
            return int(np.count_nonzero(a >= 1.0))
        top = (2 ** (self.bit_depth - 1) - 1) / 2 ** (self.bit_depth - 1)
        return int(np.count_nonzero(a >= top - 1e-12))


def _iter_chunks(f) -> Iterator[tuple[bytes, int, int]]:
    """Gera (id, tamanho, posição do conteúdo) para cada chunk do RIFF/WAVE."""
    head = f.read(12)
    if len(head) < 12 or head[:4] != b"RIFF" or head[8:12] != b"WAVE":
        raise ValueError("não é um arquivo WAV (RIFF/WAVE)")
    while True:
        hdr = f.read(8)
        if len(hdr) < 8:
            return
        cid, size = hdr[:4], struct.unpack("<I", hdr[4:])[0]
        pos = f.tell()
        yield cid, size, pos
        f.seek(pos + size + (size & 1))


def _parse_fmt(f, size: int) -> tuple[int, int, int, int]:
    data = f.read(size)
    tag, channels, sample_rate, _byte_rate, _block, bits = struct.unpack("<HHIIHH", data[:16])
    if tag == WAVE_FORMAT_EXTENSIBLE and size >= 26:
        tag = struct.unpack("<H", data[24:26])[0]
    return tag, channels, sample_rate, bits


def read_header(path: Path | str) -> WavHeader:
    """Lê só o cabeçalho (rápido, não carrega o áudio)."""
    fmt = None
    data_size = None
    with open(path, "rb") as f:
        for cid, size, pos in _iter_chunks(f):
            if cid == b"fmt ":
                f.seek(pos)
                fmt = _parse_fmt(f, size)
            elif cid == b"data":
                data_size = size
                break
    if fmt is None or data_size is None:
        raise ValueError("WAV sem chunk 'fmt ' ou 'data'")
    tag, channels, sample_rate, bits = fmt
    frame_bytes = channels * (bits // 8)
    frames = data_size // frame_bytes if frame_bytes else 0
    return WavHeader(sample_rate, bits, channels, frames, tag == WAVE_FORMAT_FLOAT)


def read_wav(path: Path | str) -> Wav:
    fmt = None
    raw = None
    with open(path, "rb") as f:
        for cid, size, pos in _iter_chunks(f):
            if cid == b"fmt ":
                f.seek(pos)
                fmt = _parse_fmt(f, size)
            elif cid == b"data":
                f.seek(pos)
                raw = f.read(size)
                break
    if fmt is None or raw is None:
        raise ValueError("WAV sem chunk 'fmt ' ou 'data'")
    tag, channels, sample_rate, bits = fmt
    frame_bytes = channels * (bits // 8)
    frames = len(raw) // frame_bytes if frame_bytes else 0
    return Wav(sample_rate, bits, channels, frames, tag == WAVE_FORMAT_FLOAT, raw)


def write_wav(
    path: Path | str,
    data: np.ndarray,
    sample_rate: int,
    bit_depth: int = 24,
    is_float: bool = False,
) -> None:
    """Grava WAV. `data` em float, formato (frames,) ou (frames, canais).

    Valores fora de [-1, 1] são cortados no fundo de escala nos formatos inteiros.
    """
    x = np.asarray(data, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    frames, channels = x.shape

    if is_float:
        tag, bits = WAVE_FORMAT_FLOAT, 32
        payload = np.ascontiguousarray(x, dtype="<f4").tobytes()
    elif bit_depth == 16:
        tag, bits = WAVE_FORMAT_PCM, 16
        payload = np.clip(np.rint(x * 32767), -32768, 32767).astype("<i2").tobytes()
    elif bit_depth == 24:
        tag, bits = WAVE_FORMAT_PCM, 24
        q = np.clip(np.rint(x * 8388607), -8388608, 8388607).astype("<i4")
        payload = np.ascontiguousarray(q).view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
    else:
        raise ValueError(f"bit depth não suportado para escrita: {bit_depth}")

    block_align = channels * bits // 8
    fmt_chunk = struct.pack(
        "<4sIHHIIHH", b"fmt ", 16, tag, channels, sample_rate,
        sample_rate * block_align, block_align, bits,
    )
    fact_chunk = struct.pack("<4sII", b"fact", 4, frames) if tag == WAVE_FORMAT_FLOAT else b""
    pad = b"\x00" if len(payload) & 1 else b""
    data_chunk = struct.pack("<4sI", b"data", len(payload)) + payload + pad
    body = b"WAVE" + fmt_chunk + fact_chunk + data_chunk
    with open(path, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", len(body)) + body)
