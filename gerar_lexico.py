"""
gerar_lexico.py
---------------
Gera o arquivo `palavras.txt`, o léxico usado pelo autocomplete da Parte I.

A Parte I precisa de um conjunto grande de palavras para que o autocomplete
tenha o que completar -- a interface de exemplo do enunciado menciona 2500
palavras cadastradas. Em vez de inventar uma lista, o léxico é extraído do
vocabulário real dos documentos da Parte II, depois do pré-processamento. Isso
tem duas vantagens: são palavras em contexto técnico, e o mesmo vocabulário
serve às duas partes do trabalho.

Os artigos, porém, também trazem nomes próprios (turing), siglas (abnt),
termos em inglês (computer, programming) e pedaços como "aplicá", de
"aplicá-lo". Como o léxico é uma lista de palavras do português, como as do
exemplo do enunciado, só ficam as que o dicionário de português (Brasil) do
Microsoft Word reconhece. Os estrangeirismos que esse dicionário registra,
como software, download e marketing, continuam no léxico. Regerar o léxico
exige Windows com o Word; sem eles, o script para e não mexe no
`palavras.txt` do repositório.

As palavras vão para um documento do Word com o texto marcado como português
(Brasil), e ficam as que o corretor não sublinha. Marcar o texto é o que fixa
o idioma: o dicionário passado ao `Application.CheckSpelling` não muda a
resposta -- até o de inglês aceita "computação" --, que passaria a depender do
idioma padrão da instalação do Word.

As oito palavras usadas como exemplo na seção 2.2 do enunciado são acrescidas
explicitamente, para que a consulta de demonstração funcione mesmo que alguma
delas não apareça no corpus.

Uso:
    python gerar_lexico.py [pasta_dos_documentos]
"""

import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

from estatisticas import formatar_numero
from mecanismo import MecanismoBusca
from trie import normalizar

# Palavras da seção 2.2 do enunciado.
EXEMPLO_ENUNCIADO = [
    "computador",
    "computação",
    "computacional",
    "compilador",
    "complexidade",
    "programação",
    "processador",
    "processamento",
]

TAMANHO_MINIMO = 3
DESTINO = Path(__file__).parent / "palavras.txt"

# Consulta o corretor ortográfico de português (Brasil) do Word: lê as
# candidatas do primeiro arquivo e grava as aceitas no segundo. As palavras vão
# para documentos de 500 linhas, uma por parágrafo, com o texto marcado como
# português (Brasil) -- idioma 1046 -- e sem a detecção automática de idioma,
# que poderia remarcar "computer" como inglês. Ficam as que o corretor não
# aponta em `SpellingErrors`. Os lotes mantêm cada documento pequeno, longe do
# limite de erros a partir do qual o Word para de verificar.
SCRIPT_DO_CORRETOR = r"""
$ErrorActionPreference = 'Stop'
$palavras = @([IO.File]::ReadAllLines($args[0], [Text.Encoding]::UTF8) | Where-Object { $_ })
$aceitas = New-Object 'System.Collections.Generic.List[string]'
$word = New-Object -ComObject Word.Application
try {
  $word.Visible = $false
  $word.DisplayAlerts = 0
  for ($inicio = 0; $inicio -lt $palavras.Count; $inicio += 500) {
    $fim = [Math]::Min($inicio + 499, $palavras.Count - 1)
    $lote = @($palavras[$inicio..$fim])
    $documento = $word.Documents.Add()
    $documento.Content.Text = ($lote -join "`r")
    $documento.Content.LanguageID = 1046
    $documento.Content.NoProofing = $false
    $documento.Content.LanguageDetected = $true
    $apontadas = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
    foreach ($erro in $documento.SpellingErrors) { [void]$apontadas.Add($erro.Text) }
    foreach ($palavra in $lote) { if (-not $apontadas.Contains($palavra)) { $aceitas.Add($palavra) } }
    $documento.Close(0)
  }
  [IO.File]::WriteAllLines($args[1], $aceitas.ToArray(), (New-Object Text.UTF8Encoding($false)))
} finally {
  $word.Quit()
}
"""


def escrita_latina(palavra):
    """
    Só letras do alfabeto latino, com ou sem acento. Uma palavra em outra
    escrita, como o grego "κρυπτός" da etimologia de criptografia, não seria
    barrada pelo corretor do Word, que não aponta o que não verifica.
    """
    return all(unicodedata.name(letra, "").startswith("LATIN") for letra in palavra)


def palavras_do_portugues(palavras):
    """
    As palavras que o dicionário de português (Brasil) do Word reconhece.

    O Word é chamado pelo PowerShell, uma vez para a lista inteira, e verifica
    as palavras em lotes (ver `SCRIPT_DO_CORRETOR`). Levanta OSError ou
    CalledProcessError quando não há PowerShell ou Word.
    """
    with tempfile.TemporaryDirectory() as pasta:
        entrada = Path(pasta) / "candidatas.txt"
        saida = Path(pasta) / "aceitas.txt"
        script = Path(pasta) / "corretor.ps1"
        entrada.write_text("\n".join(palavras), encoding="utf-8")
        script.write_text(SCRIPT_DO_CORRETOR, encoding="utf-8-sig")
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-File", str(script), str(entrada), str(saida)],
                       check=True, capture_output=True)
        return set(saida.read_text(encoding="utf-8").split())


def main():
    pasta = sys.argv[1] if len(sys.argv) > 1 else "documentos"

    # `guardar_conteudo=False`: aqui só interessa o vocabulário, e manter o
    # texto bruto dos documentos em memória seria desperdício.
    mecanismo = MecanismoBusca(pasta, guardar_conteudo=False)
    documentos = mecanismo.construir()

    if not documentos:
        print(f"Nenhum arquivo .txt encontrado em '{pasta}/'.")
        print("Rode antes: python preparar_corpus.py")
        return 1

    vocabulario = {p for p in mecanismo.vocabulario
                   if len(p) >= TAMANHO_MINIMO and escrita_latina(p)}
    try:
        portuguesas = palavras_do_portugues(sorted(vocabulario))
    except (OSError, subprocess.CalledProcessError):
        print("Não foi possível consultar o dicionário de português do Word.")
        print(f"O filtro exige Windows com o Microsoft Word; '{DESTINO.name}' ficou como estava.")
        return 1
    fora = len(vocabulario - portuguesas)
    vocabulario &= portuguesas
    vocabulario.update(EXEMPLO_ENUNCIADO)

    # Ordena pela forma normalizada para que acentuadas fiquem junto das suas
    # equivalentes sem acento, e não relegadas ao fim da tabela Unicode.
    palavras = sorted(vocabulario, key=lambda p: (normalizar(p), p))

    cabecalho = (
        "# Lexico da Parte I - sistema de autocomplete\n"
        "#\n"
        "# Vocabulario extraido dos documentos de 'documentos/' apos o\n"
        "# pre-processamento (minusculas, remocao de pontuacao, tokenizacao e\n"
        "# remocao de stopwords), so com as palavras que o dicionario de\n"
        "# portugues (Brasil) do Microsoft Word reconhece, acrescido das palavras\n"
        "# usadas como exemplo no enunciado. Ficam de fora os nomes proprios, as\n"
        "# siglas e os termos em ingles que o dicionario nao registra; os\n"
        "# estrangeirismos que ele registra, como software, ficam. Uma palavra\n"
        "# por linha; linhas com # sao comentarios.\n"
        "#\n"
        f"# Total: {len(palavras)} palavras\n"
        "#\n"
        "# Regerar com:  python gerar_lexico.py\n\n"
    )
    DESTINO.write_text(cabecalho + "\n".join(palavras) + "\n", encoding="utf-8")

    print(f"{formatar_numero(len(palavras))} palavras gravadas em '{DESTINO.name}'")
    print(f"{formatar_numero(fora)} que o dicionário de português não reconhece ficaram de fora")
    print(f"Origem: {documentos} documento(s) de '{pasta}/'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
