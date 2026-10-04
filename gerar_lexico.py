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
Microsoft Word reconhece. Por isso regerar o léxico exige Windows com o Word;
sem eles, o script para e não mexe no `palavras.txt` do repositório.

As oito palavras usadas como exemplo na seção 2.2 do enunciado são acrescidas
explicitamente, para que a consulta de demonstração funcione mesmo que alguma
delas não apareça no corpus.

Uso:
    python gerar_lexico.py [pasta_dos_documentos]
"""

import subprocess
import sys
import tempfile
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

# Consulta o corretor ortográfico de português (Brasil) do Word, palavra por
# palavra: lê as candidatas do primeiro arquivo e grava as aceitas no segundo.
SCRIPT_DO_CORRETOR = r"""
$ErrorActionPreference = 'Stop'
$palavras = [IO.File]::ReadAllLines($args[0], [Text.Encoding]::UTF8)
$word = New-Object -ComObject Word.Application
try {
  $word.Visible = $false
  $documento = $word.Documents.Add()
  $portugues = $word.Languages.Item(1046).Name
  $sem = [Type]::Missing
  $maiusculas = $false
  $aceitas = @($palavras | Where-Object {
    $word.CheckSpelling($_, [ref]$sem, [ref]$maiusculas, [ref]$portugues) })
  [IO.File]::WriteAllLines($args[1], [string[]]$aceitas, (New-Object Text.UTF8Encoding($false)))
  $documento.Close(0)
} finally {
  $word.Quit()
}
"""


def palavras_do_portugues(palavras):
    """
    As palavras que o dicionário de português (Brasil) do Word reconhece.

    O Word é chamado pelo PowerShell, uma vez para a lista inteira. Levanta
    OSError ou CalledProcessError quando não há PowerShell ou Word.
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

    vocabulario = {p for p in mecanismo.vocabulario if len(p) >= TAMANHO_MINIMO}
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
        "# portugues (Brasil) do Microsoft Word reconhece -- ficam de fora nomes\n"
        "# proprios, siglas e termos em ingles --, acrescido das palavras usadas\n"
        "# como exemplo no enunciado. Uma palavra por linha; linhas com # sao\n"
        "# comentarios.\n"
        "#\n"
        f"# Total: {len(palavras)} palavras\n"
        "#\n"
        "# Regerar com:  python gerar_lexico.py\n\n"
    )
    DESTINO.write_text(cabecalho + "\n".join(palavras) + "\n", encoding="utf-8")

    print(f"{formatar_numero(len(palavras))} palavras gravadas em '{DESTINO.name}'")
    print(f"{formatar_numero(fora)} fora do dicionário de português ficaram de fora")
    print(f"Origem: {documentos} documento(s) de '{pasta}/'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
