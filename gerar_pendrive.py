"""
gerar_pendrive.py
-----------------
Prepara a pasta que vai para o pendrive ou para o Google Drive: a interface
inteira em UM arquivo .html e um LEIA-ME.

--------------------------------------------------------------------------
Por que um arquivo só
--------------------------------------------------------------------------
Pasta se desfaz com facilidade: alguém copia só um arquivo para a área de
trabalho, o antivírus da sala bloqueia um script, o Drive baixa metade. Um
arquivo único não tem como chegar incompleto. O HTML, o CSS, as fontes, os
algoritmos e os 24 documentos ficam dentro dele -- sem internet, sem Python,
sem instalação.

Esse arquivo é gerado pelo Vite em `interface/dist/index.html` (ver
`interface/vite.config.ts`). Este script só o copia com um nome legível e
escreve as instruções ao lado.

Uso:
    python gerar_pendrive.py                  grava em pendrive/
    python gerar_pendrive.py --destino E:/    grava direto no pendrive
"""

import argparse
import shutil
import sys
from pathlib import Path

__all__ = ["main"]

RAIZ = Path(__file__).parent
INTERFACE = RAIZ / "interface" / "dist" / "index.html"
NOME_SAIDA = "Busca em textos - Trabalho A1.html"

LEIAME = """\
BUSCA EM TEXTOS - Trabalho Prático A1
Trie, índice invertido e Knuth-Morris-Pratt
Universidade Veiga de Almeida

COMO ABRIR
----------
Clique duas vezes em "{arquivo}".

Não precisa de internet, de Python nem de instalar nada: a página abre no
navegador (Chrome, Edge ou Firefox) já com os 24 documentos e os algoritmos
dentro dela. Se veio do Google Drive, baixe o arquivo antes: o Drive não
executa páginas HTML na pré-visualização.

COMO USAR
---------
Digite na caixa e aperte Enter. Enquanto você digita, a Trie sugere palavras;
os resultados vêm do índice invertido, com as palavras encontradas realçadas.
As abas Palavra, Prefixo e Sequência trocam a modalidade de busca, e clicar
num resultado abre o texto inteiro.
"""


def main():
    analisador = argparse.ArgumentParser(
        description="Copia a interface de um arquivo só para o pendrive.")
    analisador.add_argument("--destino", default="pendrive",
                            help="pasta onde gravar (padrão: pendrive/)")
    argumentos = analisador.parse_args()

    if not INTERFACE.is_file():
        print("[erro] interface/dist/index.html não existe. Compile a interface antes:")
        print("         cd interface")
        print("         npm install")
        print("         npm run build")
        return 1

    destino = Path(argumentos.destino)
    destino.mkdir(parents=True, exist_ok=True)

    arquivo = destino / NOME_SAIDA
    shutil.copyfile(INTERFACE, arquivo)
    leiame = destino / "LEIA-ME.txt"
    # CRLF para o Bloco de Notas do Windows abrir com as quebras certas.
    leiame.write_text(LEIAME.format(arquivo=NOME_SAIDA), encoding="utf-8", newline="\r\n")

    print(f"Pronto ({arquivo.stat().st_size / 1024 / 1024:.1f} MB):")
    print(f"  {arquivo}")
    print(f"  {leiame}")
    print("\nCopie os dois para o pendrive ou para o Drive. Dois cliques no .html")
    print("abrem a apresentação em qualquer computador, sem internet e sem Python.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
