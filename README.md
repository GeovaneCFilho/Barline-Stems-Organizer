# Barline

Preparador de stems para Windows. Você solta a pasta de stems, o Barline diagnostica os problemas (tamanhos diferentes, clipping, duplicados, dual-mono, áudio faltando, desalinhamento), propõe grupo, cor e nome padronizado, e exporta uma pasta organizada com relatório. Os originais nunca são alterados.

Stack: C++20 + JUCE de ponta a ponta. Python só para ferramentas de teste.

Status: Etapa 0 (preparação). O app só abre uma janela vazia; o código do núcleo começa na Etapa 1.

## Compilar no Windows

Pré-requisitos: Visual Studio 2022 (carga de trabalho "Desenvolvimento para desktop com C++"), CMake 3.22+ e Git.

```powershell
cmake -S . -B build
cmake --build build --config Release --parallel
.\build\Barline_artefacts\Release\Barline.exe
```

Na primeira configuração o CMake baixa o JUCE (tag fixada em `BARLINE_JUCE_TAG`, hoje 8.0.15). Para trocar a versão: `cmake -S . -B build -DBARLINE_JUCE_TAG=<tag>`.

O workflow `.github/workflows/windows-build.yml` compila em um Windows limpo a cada push e guarda o `Barline.exe` como artefato. É a prova de que o build funciona fora da sua máquina.

## Pastas

| Pasta | Conteúdo |
|---|---|
| `Source/` | código do app (C++/JUCE) |
| `data/name_dictionary.json` | dicionário de nomes (inglês e português) para os 5 grupos, com as regras de normalização |
| `docs/export_spec.md` | padrão de nome da exportação e formato do relatório |
| `tools/` | geração e conferência de pastas de teste (Python) |
| `test_data/synthetic/` | pastas sintéticas geradas (não vão para o git) |
| `test_data/real/` | gabaritos das suas pastas reais (os WAV reais não vão para o git) |

## Pastas de teste

```powershell
pip install -r requirements-dev.txt

# 12 pastas sintéticas com erros plantados + gabarito.json (determinístico)
python tools/make_test_folders.py

# confere se os detectores de referência acham exatamente os erros do gabarito
python tools/verify_test_folders.py

# mede o dicionário de nomes contra o gabarito
python tools/classify_prototype.py

# cria o rascunho de gabarito de uma pasta REAL de stems, para você preencher
python tools/scan_real_folder.py "D:\Projetos\Musica\Stems"
```

Tipos de erro do gabarito: `length_mismatch`, `sample_rate_mismatch`, `bit_depth_mismatch`, `clipping`, `silent`, `empty_file`, `duplicate`, `dual_mono`, `misaligned_start`.

As regras de detecção do verificador em Python são a referência que o C++ da Etapa 1 deve reproduzir (ver `docs/export_spec.md`, seção 4).

## Primeiro commit

```powershell
git init
git add .
git commit -m "Etapa 0: esqueleto JUCE, ferramentas de teste e dicionário de nomes"
git branch -M main
git remote add origin https://github.com/<usuario>/barline.git
git push -u origin main
```
