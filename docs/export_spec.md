# Barline: padrão de exportação e relatório (rascunho v0)

Status: proposta da Etapa 0. Ajuste o que não combinar com o seu fluxo antes de implementar a Etapa 4.

## 1. Pasta de saída

- Nome: `<pasta original>_Barline`, criada ao lado da pasta original.
- Se já existir, usar `<pasta original>_Barline_2`, `_3` e assim por diante. Nunca sobrescrever.
- Os arquivos originais não são abertos para escrita em nenhum momento.
- Conteúdo: os stems renomeados, mais `Barline_Report.txt` e `Barline_Report.json`.

## 2. Nome dos arquivos exportados

Padrão: `NN_Grupo_Nome.wav`

| Parte | Regra |
|---|---|
| `NN` | número de 2 dígitos, sequencial na pasta inteira, na ordem dos grupos e, dentro do grupo, na ordem alfabética do nome |
| `Grupo` | `Drums`, `Bass`, `Melodic`, `Atmosphere`, `Vocals` ou `Unclassified` |
| `Nome` | nome normalizado: palavras iniciais maiúsculas, sem acentos, sem espaços (juntas por `-`), só letras, números e `-` |

Ordem dos grupos: Drums, Bass, Melodic, Atmosphere, Vocals, Unclassified.

Exemplos (pasta do gabarito `01_limpo_en`):

```
01_Drums_Clap.wav
02_Drums_Hats.wav
03_Drums_Kick.wav
04_Bass_Bass.wav
05_Bass_Sub.wav
06_Melodic_Lead.wav
07_Melodic_Piano.wav
08_Melodic_Pluck.wav
09_Atmosphere_Fx-Riser.wav
10_Atmosphere_Pad.wav
11_Vocals_Vocal-Chops.wav
12_Vocals_Vocal-Main.wav
```

Regras de borda:

- Dois stems com o mesmo nome normalizado no mesmo grupo: sufixo `-2`, `-3` (`Kick`, `Kick-2`).
- Nome muito longo: cortar o `Nome` em 40 caracteres.
- `Unclassified` mantém o nome original normalizado, para você reconhecer o arquivo e editar.
- A extensão é sempre `.wav` e o formato do áudio é preservado (a única conversão do v0 é dual-mono para mono verdadeiro, e só quando você aceita).

## 3. Relatório

Dois arquivos com o mesmo conteúdo: `Barline_Report.txt` (para ler) e `Barline_Report.json` (para teste automático).

### 3.1 Estrutura do `.txt`

```
BARLINE: relatório de preparação de stems
Versão do app:   0.0.1
Data:            2026-12-07 14:32
Pasta original:  D:\Projetos\Musica\Stems
Pasta exportada: D:\Projetos\Musica\Stems_Barline
Mix de referência: usada (reference.wav) | não usada

RESUMO
  Stems analisados:   12
  Sem problemas:       9
  Com aviso:           2
  Com erro:            1
  Convertidos:         1 (dual-mono para mono)
  Não classificados:   1

STEMS
  Original            Exportado                  Grupo       Status
  Kick.wav            03_Drums_Kick.wav          Drums       OK
  Sub.wav             05_Bass_Sub.wav            Bass        Aviso: dual-mono (convertido)
  ...

PROBLEMAS
  [ERRO]  Pad.wav: duração 2,5 s; os outros stems têm 4,0 s.
          Por que importa: o engenheiro vai receber partes de tamanhos diferentes.
  [AVISO] Kick.wav: 1 240 amostras no fundo de escala (clipping).
  ...

DECISÕES
  Aceitas sem edição:   10 sugestões
  Editadas por você:     2 (Lead.wav: grupo Melodic para Vocals; ...)
  Mantidos como estão:   problemas que o app não corrige no v0
```

### 3.2 Severidade dos problemas

| Tipo | Severidade | O app corrige no v0? |
|---|---|---|
| `length_mismatch` | Erro | Não, só avisa |
| `sample_rate_mismatch` | Erro | Não, só avisa |
| `bit_depth_mismatch` | Aviso | Não, só avisa |
| `clipping` | Erro | Não, só avisa |
| `silent` | Erro | Não, só avisa |
| `empty_file` | Erro | Não, só avisa |
| `duplicate` | Aviso | Não, só avisa |
| `dual_mono` | Aviso | Sim: converte para mono verdadeiro quando você aceita |
| `misaligned_start` | Aviso | Não (correção automática fica para a v1); só quando há mix de referência |

Sem mix de referência, o único aviso de alinhamento possível é quando as durações diferem.

### 3.3 Estrutura do `.json`

```json
{
  "app_version": "0.0.1",
  "date": "2026-12-07T14:32:00",
  "source_folder": "D:\\Projetos\\Musica\\Stems",
  "output_folder": "D:\\Projetos\\Musica\\Stems_Barline",
  "reference_mix_used": true,
  "summary": { "analyzed": 12, "ok": 9, "warning": 2, "error": 1, "converted": 1, "unclassified": 1 },
  "stems": [
    {
      "original": "Kick.wav",
      "exported": "03_Drums_Kick.wav",
      "group": "Drums",
      "suggested_group": "Drums",
      "group_edited_by_user": false,
      "issues": [ { "type": "clipping", "severity": "error", "detail": { "clipped_samples": 1240 } } ],
      "converted": null
    }
  ]
}
```

Os tipos de problema usam exatamente os mesmos nomes do `gabarito.json` dos testes.

## 4. Regras de detecção (iguais às do verificador em Python)

As regras estão em `tools/verify_test_folders.py` e são a referência para o C++ da Etapa 1:

- Duração, taxa e bit depth comparados com o valor mais comum da pasta (duração com tolerância de 1 ms).
- Clipping: 8 ou mais amostras no fundo de escala.
- Duplicado: bytes de áudio idênticos. Dual-mono: estéreo com L e R idênticos.
- Alinhamento: correlação cruzada com a mix de referência; mais de 5 ms de atraso gera aviso.
  A correlação usa o máximo com sinal; usar o módulo confunde meia-onda de tom grave com atraso.
