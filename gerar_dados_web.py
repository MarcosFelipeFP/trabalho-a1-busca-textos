"""
gerar_dados_web.py
------------------
Empacota o corpus, o léxico e as stopwords em JSON para a interface do
navegador, que roda sem servidor -- inclusive a partir de um pendrive.

--------------------------------------------------------------------------
Por que os dados precisam ser empacotados
--------------------------------------------------------------------------
Uma página aberta pelo protocolo `file://` não tem origem própria, e por isso
os navegadores recusam qualquer `fetch` para arquivos vizinhos: ler
`documentos/algoritmos.txt` do disco, do jeito que o servidor faz, é bloqueado
antes de sair.

A saída é levar os dados para dentro da página. Este script grava três
arquivos JSON em `interface/src/dados/`; na compilação da interface
(`npm run build`), o Vite os embute no mesmo `.html` que carrega os
algoritmos, e a página abre com dois cliques em qualquer computador.

--------------------------------------------------------------------------
Nenhum nome de arquivo entra no código
--------------------------------------------------------------------------
A exigência da seção 3.2 do enunciado continua valendo: a lista de documentos
é descoberta varrendo a pasta, exatamente como `MecanismoBusca.listar_arquivos`
faz. Soltar um `.txt` novo em `documentos/`, rodar este script e recompilar a
interface basta para que ele apareça no navegador.

Uso:
    python gerar_dados_web.py                  regenera interface/src/dados/
    python gerar_dados_web.py --pasta outra    usa outra pasta de documentos
"""

import argparse
import json
import sys
from pathlib import Path

from main import carregar_lexico, configurar_saida
from preparar_corpus import ARTIGOS
from preprocessamento import carregar_stopwords

__all__ = ["gerar", "escrever_json"]

RAIZ = Path(__file__).parent
DESTINO = RAIZ / "interface" / "src" / "dados"


def escrever_json(caminho, valor):
    """
    Grava `valor` como JSON compacto e devolve o tamanho do arquivo em bytes.

    `ensure_ascii=False` mantém "computação" legível dentro do arquivo, e a
    ausência de espaços entre os separadores tira quase 10% do tamanho do
    corpus -- que vai inteiro para dentro da página.
    """
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(valor, ensure_ascii=False, separators=(",", ":")),
                       encoding="utf-8", newline="\n")
    return caminho.stat().st_size


def gerar(pasta="documentos", lexico="palavras.txt"):
    """Regenera os três arquivos de `interface/src/dados/` e devolve o que saiu."""
    pasta_documentos = Path(pasta)
    arquivos = sorted(pasta_documentos.glob("*.txt")) if pasta_documentos.is_dir() else []

    if not arquivos:
        raise SystemExit(
            f"[erro] nenhum .txt encontrado em '{pasta_documentos}/'.\n"
            f"       Rode `python preparar_corpus.py` para baixar a base de exemplo."
        )

    # O título exibido na interface é o do artigo da Wikipédia, quando o arquivo
    # veio de `preparar_corpus.py`; um .txt novo solto na pasta usa o próprio
    # nome, sem sublinhados. A lista de arquivos continua vindo da varredura.
    titulos = {f"{nome}.txt": titulo for titulo, nome in ARTIGOS}
    documentos = [
        {"nome": arquivo.name,
         "titulo": titulos.get(arquivo.name, arquivo.stem.replace("_", " ").capitalize()),
         "bytes": arquivo.stat().st_size,
         "texto": arquivo.read_text(encoding="utf-8", errors="replace")}
        for arquivo in arquivos
    ]
    palavras = carregar_lexico(lexico)
    stopwords = sorted(carregar_stopwords())

    return [
        (escrever_json(DESTINO / "corpus.json", documentos),
         DESTINO / "corpus.json", f"{len(documentos)} documentos"),
        (escrever_json(DESTINO / "lexico.json", palavras),
         DESTINO / "lexico.json", f"{len(palavras)} palavras"),
        (escrever_json(DESTINO / "stopwords.json", stopwords),
         DESTINO / "stopwords.json", f"{len(stopwords)} stopwords"),
    ]


def main():
    configurar_saida()
    analisador = argparse.ArgumentParser(
        description="Empacota corpus, léxico e stopwords para a interface offline.",
    )
    analisador.add_argument("--pasta", default="documentos",
                            help="pasta com os arquivos .txt (padrão: documentos)")
    analisador.add_argument("--lexico", default="palavras.txt",
                            help="arquivo de palavras da Parte I (padrão: palavras.txt)")
    argumentos = analisador.parse_args()

    print("Empacotando os dados para a interface...\n")
    total = 0
    for tamanho, caminho, conteudo in gerar(argumentos.pasta, argumentos.lexico):
        total += tamanho
        relativo = caminho.relative_to(RAIZ).as_posix()
        print(f"  {relativo:<28} {tamanho / 1024:8.1f} KB   {conteudo}")

    print(f"\n  {'total':<28} {total / 1024:8.1f} KB")
    print("\nPronto. Recompile a interface para embutir os dados novos:")
    print("  cd interface && npm run build")
    return 0


if __name__ == "__main__":
    sys.exit(main())
