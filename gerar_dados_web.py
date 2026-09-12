"""
gerar_dados_web.py
------------------
Empacota o corpus, o léxico e as stopwords em arquivos JavaScript para que a
interface do navegador funcione sem servidor nenhum -- basta abrir
`web/index.html` com dois cliques, inclusive a partir de um pendrive.

--------------------------------------------------------------------------
Por que os dados precisam virar JavaScript
--------------------------------------------------------------------------
Uma página aberta pelo protocolo `file://` não tem origem própria, e por isso
os navegadores recusam qualquer `fetch` para arquivos vizinhos: ler
`documentos/algoritmos.txt` do disco, do jeito que o servidor faz, é bloqueado
antes de sair. A exceção histórica é a tag `<script src="...">`, que continua
carregando arquivos da mesma pasta.

Daí a estratégia: o conteúdo que o servidor entregaria por HTTP é convertido
em atribuições JavaScript e carregado como script comum. Nada de build, nada
de empacotador -- só `json.dumps` escrevendo literais.

--------------------------------------------------------------------------
Nenhum nome de arquivo entra no código
--------------------------------------------------------------------------
A exigência da seção 3.2 do enunciado continua valendo: a lista de documentos
é descoberta varrendo a pasta, exatamente como `MecanismoBusca.listar_arquivos`
faz. Este script é o ponto em que a varredura acontece para a versão offline;
soltar um `.txt` novo em `documentos/` e rodá-lo de novo basta para que ele
apareça no navegador.

Uso:
    python gerar_dados_web.py                  regenera web/dados/
    python gerar_dados_web.py --pasta outra    usa outra pasta de documentos
"""

import argparse
import json
import sys
from pathlib import Path

from main import carregar_lexico, configurar_saida
from preprocessamento import carregar_stopwords

__all__ = ["gerar", "escrever_modulo"]

RAIZ = Path(__file__).parent
DESTINO = RAIZ / "web" / "dados"

CABECALHO = """\
/* ---------------------------------------------------------------------------
   {arquivo}
   GERADO POR `python gerar_dados_web.py` -- não edite à mão.

   {descricao}
   --------------------------------------------------------------------------- */

'use strict';

window.DADOS = window.DADOS || {{}};
"""


def escrever_modulo(caminho, descricao, atribuicoes):
    """
    Escreve um arquivo .js com uma ou mais atribuições em `window.DADOS`.

    `atribuicoes` é uma lista de pares (nome, valor); o valor é serializado com
    `json.dumps`, que já produz literais JavaScript válidos -- JSON é subconjunto
    da sintaxe de objeto da linguagem, e o escape de aspas, barras e quebras de
    linha vem pronto.
    """
    partes = [CABECALHO.format(arquivo=caminho.name, descricao=descricao)]
    for nome, valor in atribuicoes:
        # ensure_ascii=False preserva "computação" legível dentro do arquivo;
        # o <script> é carregado como UTF-8 pelo charset declarado na página.
        partes.append(f"\nwindow.DADOS.{nome} = {json.dumps(valor, ensure_ascii=False)};\n")

    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("".join(partes), encoding="utf-8", newline="\n")
    return caminho.stat().st_size


def gerar(pasta="documentos", lexico="palavras.txt"):
    """Regenera os três arquivos de `web/dados/` e devolve um resumo do que saiu."""
    pasta_documentos = Path(pasta)
    arquivos = sorted(pasta_documentos.glob("*.txt")) if pasta_documentos.is_dir() else []

    if not arquivos:
        raise SystemExit(
            f"[erro] nenhum .txt encontrado em '{pasta_documentos}/'.\n"
            f"       Rode `python preparar_corpus.py` para baixar a base de exemplo."
        )

    documentos = [
        {"nome": arquivo.name,
         "bytes": arquivo.stat().st_size,
         "texto": arquivo.read_text(encoding="utf-8", errors="replace")}
        for arquivo in arquivos
    ]

    palavras = carregar_lexico(lexico)
    stopwords = sorted(carregar_stopwords())

    resumo = [
        (escrever_modulo(
            DESTINO / "corpus.js",
            f"Conteúdo original dos {len(documentos)} arquivos de '{pasta_documentos}/'.\n"
            "   É o texto bruto, sem pré-processamento: o KMP da Parte II varre exatamente\n"
            "   estes caracteres, como faz sobre o arquivo em disco.",
            [("corpus", documentos)],
        ), DESTINO / "corpus.js", f"{len(documentos)} documentos"),

        (escrever_modulo(
            DESTINO / "lexico.js",
            f"Léxico da Parte I: as {len(palavras):,} palavras de '{lexico}',\n"
            "   já sem os comentários do arquivo original.".replace(",", "."),
            [("lexico", palavras)],
        ), DESTINO / "lexico.js", f"{len(palavras)} palavras"),

        (escrever_modulo(
            DESTINO / "stopwords.js",
            f"As {len(stopwords)} stopwords do português, na forma normalizada\n"
            "   (minúscula e sem acento) que o pré-processamento compara.",
            [("stopwords", stopwords)],
        ), DESTINO / "stopwords.js", f"{len(stopwords)} stopwords"),
    ]

    return resumo


def main():
    configurar_saida()
    analisador = argparse.ArgumentParser(
        description="Empacota corpus, léxico e stopwords em JavaScript para a versão offline.",
    )
    analisador.add_argument("--pasta", default="documentos",
                            help="pasta com os arquivos .txt (padrão: documentos)")
    analisador.add_argument("--lexico", default="palavras.txt",
                            help="arquivo de palavras da Parte I (padrão: palavras.txt)")
    argumentos = analisador.parse_args()

    print("Empacotando os dados para a versão offline...\n")
    total = 0
    for tamanho, caminho, conteudo in gerar(argumentos.pasta, argumentos.lexico):
        total += tamanho
        relativo = caminho.relative_to(RAIZ).as_posix()
        print(f"  {relativo:<24} {tamanho / 1024:8.1f} KB   {conteudo}")

    print(f"\n  {'total':<24} {total / 1024:8.1f} KB")
    print("\nPronto. `web/index.html` já abre sozinho, sem servidor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
