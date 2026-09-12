"""
gerar_pendrive.py
-----------------
Empacota a interface inteira em UM arquivo .html, para levar no pendrive e
abrir com dois cliques em qualquer computador.

--------------------------------------------------------------------------
Por que um arquivo só
--------------------------------------------------------------------------
Copiar a pasta `web/` já funciona: ela é autossuficiente e abre sem servidor.
Mas pasta se desfaz com facilidade -- alguém copia só o `index.html` para a
área de trabalho, o antivírus da sala bloqueia um dos scripts, o arquivo vai
por e-mail e chega sozinho -- e aí a apresentação começa com uma tela em
branco.

Um arquivo único não tem como chegar incompleto. O HTML, o CSS, os algoritmos
e o corpus inteiro ficam dentro dele: cerca de 1 MB, sem rede, sem Python, sem
instalação. Serve para o pendrive, para o anexo de e-mail e para o computador
da sala que ninguém viu antes.

--------------------------------------------------------------------------
O que entra
--------------------------------------------------------------------------
    web/index.html        o esqueleto da página
    web/estilo.css        vira <style>
    web/dados/*.js        corpus, léxico e stopwords
    web/algoritmos/*.js   Trie, RSLP, KMP, índice invertido
    web/interface/*.js    a interface

A ordem dos <script> do `index.html` é preservada exatamente: cada arquivo
registra o que o seguinte usa.

Uso:
    python gerar_pendrive.py                  gera em pendrive/
    python gerar_pendrive.py --destino E:/    grava direto no pendrive
"""

import argparse
import re
import sys
from pathlib import Path

__all__ = ["montar", "main"]

RAIZ = Path(__file__).parent
WEB = RAIZ / "web"

NOME_SAIDA = "Bancada - Trabalho A1.html"

PADRAO_CSS = re.compile(r'[ \t]*<link rel="stylesheet" href="([^"]+)">\s*\n')
PADRAO_JS = re.compile(r'[ \t]*<script src="([^"]+)"></script>\s*\n')

LEIAME = """\
BANCADA - Trabalho Prático A1
Processamento e busca de textos (Trie, índice invertido e Knuth-Morris-Pratt)
Universidade Veiga de Almeida

COMO ABRIR
----------
Clique duas vezes em "{arquivo}".

É só isso. Não precisa de internet, de Python, nem de instalar nada. A página
abre no navegador padrão do computador e já vem com os 24 documentos, o léxico
e os algoritmos dentro dela.

Se o computador perguntar com qual programa abrir, escolha o navegador
(Chrome, Edge ou Firefox).

O QUE DÁ PARA FAZER
-------------------
  1  Autocomplete      busca por prefixo na Trie, com a árvore desenhada
  2  Busca             as três modalidades da Parte II, incluindo o KMP
                       passo a passo sobre a fita de caracteres
  3  Laboratório       os sete experimentos de análise de complexidade,
                       rodando na hora, na máquina em que a página abriu
  4  Métricas          os números da seção 3.9 do enunciado
  5  Documentos        o corpus, com as ocorrências destacadas

Atalhos: 1 a 5 trocam de tela, "/" vai para a busca, "T" alterna claro e
escuro, "P" aumenta o texto para projeção, "?" lista tudo.

A régua no rodapé guarda o custo de cada consulta da sessão em escala
logarítmica. É onde a diferença entre a busca indexada (microssegundos) e a
varredura com KMP (milissegundos) aparece como distância na tela.

A VERSÃO COMPLETA
-----------------
Este arquivo é a interface. O trabalho completo -- os módulos Python, os
testes automatizados e o relatório -- está em:

    {repositorio}
"""

REPOSITORIO = "https://github.com/MarcosFelipeFP/trabalho-a1-busca-textos"


def ler(caminho):
    """Lê um arquivo de `web/`, recusando caminhos que escapem da pasta."""
    alvo = (WEB / caminho).resolve()
    if WEB.resolve() not in alvo.parents:
        raise SystemExit(f"[erro] caminho fora de web/: {caminho}")
    if not alvo.is_file():
        raise SystemExit(f"[erro] arquivo nao encontrado: {caminho}")
    return alvo.read_text(encoding="utf-8")


def proteger(codigo):
    """
    Neutraliza qualquer `</script` que apareça dentro do JavaScript embutido.

    O analisador de HTML fecha o bloco no primeiro `</script` que encontra, sem
    olhar se ele está dentro de uma string -- e o corpus é texto da Wikipédia
    sobre Computação, onde marcações podem aparecer citadas. A barra invertida
    não muda o valor da string em JavaScript e some para o HTML.
    """
    return codigo.replace("</script", "<\\/script")


def montar():
    """Devolve o HTML único, com tudo embutido, e a lista do que entrou."""
    pagina = ler("index.html")
    embutidos = []

    def trocar_css(achado):
        caminho = achado.group(1)
        embutidos.append(caminho)
        return f"<style>\n{ler(caminho)}\n</style>\n"

    def trocar_js(achado):
        caminho = achado.group(1)
        embutidos.append(caminho)
        return (f"<!-- {caminho} -->\n<script>\n"
                f"{proteger(ler(caminho))}\n</script>\n")

    pagina = PADRAO_CSS.sub(trocar_css, pagina)
    pagina = PADRAO_JS.sub(trocar_js, pagina)

    sobraram = re.findall(r'<(?:script src|link rel="stylesheet")', pagina)
    if sobraram:
        raise SystemExit(
            "[erro] sobrou referencia externa na pagina; o arquivo unico nao "
            "funcionaria fora da pasta web/."
        )

    return pagina, embutidos


def main():
    analisador = argparse.ArgumentParser(
        description="Gera a versão de um arquivo só, para levar no pendrive.")
    analisador.add_argument("--destino", default="pendrive",
                            help="pasta onde gravar (padrão: pendrive/)")
    argumentos = analisador.parse_args()

    if not WEB.is_dir():
        print("[erro] pasta 'web/' nao encontrada ao lado de gerar_pendrive.py.")
        return 1

    print("Embutindo a interface em um arquivo so...\n")
    pagina, embutidos = montar()

    destino = Path(argumentos.destino)
    destino.mkdir(parents=True, exist_ok=True)

    arquivo = destino / NOME_SAIDA
    arquivo.write_text(pagina, encoding="utf-8", newline="\n")

    leiame = destino / "LEIA-ME.txt"
    leiame.write_text(
        LEIAME.format(arquivo=NOME_SAIDA, repositorio=REPOSITORIO),
        encoding="utf-8", newline="\r\n")   # CRLF: o Bloco de Notas do Windows

    for caminho in embutidos:
        tamanho = len(ler(caminho).encode("utf-8"))
        print(f"  {caminho:<30} {tamanho / 1024:8.1f} KB")

    tamanho = arquivo.stat().st_size
    print(f"\n  {'TOTAL':<30} {tamanho / 1024:8.1f} KB")
    print(f"\nPronto:\n  {arquivo}\n  {leiame}")
    print("\nCopie os dois para o pendrive. Dois cliques no .html abrem a")
    print("apresentacao em qualquer computador, sem internet e sem Python.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
