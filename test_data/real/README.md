# Pastas reais de stems

Aqui ficam só os gabaritos (`*.gabarito.json`) das suas pastas reais. Os WAV reais ficam fora do repositório.

Como preencher:

1. Exporte uma pasta de stems do FL Studio (10 a 20 no total, de projetos diferentes).
2. Rode `python tools/scan_real_folder.py "<caminho da pasta>"`.
3. Abra o `.gabarito.json` gerado, preencha `group` de cada arquivo e liste em `issues` os erros reais que você encontrou ouvindo/conferindo.
4. Para plantar erros conhecidos em cópias de pastas boas (tamanho diferente, clipping, duplicado, dual-mono, arquivo vazio), faça a cópia, estrague a cópia e anote o erro no gabarito dela.

Tipos de erro aceitos: `length_mismatch`, `sample_rate_mismatch`, `bit_depth_mismatch`, `clipping`, `silent`, `empty_file`, `duplicate`, `dual_mono`, `misaligned_start`.
