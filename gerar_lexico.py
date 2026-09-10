"""
gerar_lexico.py
---------------
Gera o arquivo `palavras.txt`, o léxico usado pelo autocomplete da Parte I.

A Parte I precisa de um conjunto grande de palavras para que o autocomplete
tenha o que completar -- a interface de exemplo do enunciado menciona 2500
palavras cadastradas. Em vez de inventar uma lista, o léxico é extraído do
vocabulário real dos documentos da Parte II, depois do pré-processamento. Isso
tem duas vantagens: são palavras portuguesas de verdade, em contexto técnico,
e o mesmo vocabulário serve às duas partes do trabalho.

As oito palavras usadas como exemplo na seção 2.2 do enunciado são acrescidas
explicitamente, para que a consulta de demonstração funcione mesmo que alguma
delas não apareça no corpus.

Uso:
    python gerar_lexico.py [pasta_dos_documentos]
"""

import sys
from pathlib import Path

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
    vocabulario.update(EXEMPLO_ENUNCIADO)

    # Ordena pela forma normalizada para que acentuadas fiquem junto das suas
    # equivalentes sem acento, e não relegadas ao fim da tabela Unicode.
    palavras = sorted(vocabulario, key=lambda p: (normalizar(p), p))

    cabecalho = (
        "# Lexico da Parte I - sistema de autocomplete\n"
        "#\n"
        "# Vocabulario extraido dos documentos de 'documentos/' apos o\n"
        "# pre-processamento (minusculas, remocao de pontuacao, tokenizacao e\n"
        "# remocao de stopwords), acrescido das palavras usadas como exemplo no\n"
        "# enunciado. Uma palavra por linha; linhas com # sao comentarios.\n"
        "#\n"
        f"# Total: {len(palavras)} palavras\n"
        "#\n"
        "# Regerar com:  python gerar_lexico.py\n\n"
    )
    DESTINO.write_text(cabecalho + "\n".join(palavras) + "\n", encoding="utf-8")

    print(f"{len(palavras):,} palavras gravadas em '{DESTINO.name}'")
    print(f"Origem: {documentos} documento(s) de '{pasta}/'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
