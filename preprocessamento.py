"""
preprocessamento.py
-------------------
Etapas de preparação do texto exigidas na seção 3.3 do enunciado, implementadas
como funções separadas e encadeáveis para que o pipeline fique explícito:

    1. conversão para minúsculas
    2. remoção de pontuação
    3. tokenização
    4. remoção de stopwords
    5. (opcional) stemming com o algoritmo RSLP

Só a biblioteca padrão é usada: `re` para expressões regulares e `pathlib` para
leitura de arquivos, ambos explicitamente permitidos pelo enunciado. O
tratamento de acentos vem de `trie.normalizar`, que usa `unicodedata`.

--------------------------------------------------------------------------
Por que o token guarda a forma acentuada
--------------------------------------------------------------------------
A tokenização preserva os acentos ("computação" continua "computação"). Quem
normaliza é a Trie, ao montar a chave, e o stemmer, no último passo. Manter a
forma original até o fim é o que permite ao autocomplete devolver a palavra
escrita corretamente, em vez de uma versão descaracterizada.
"""

import re
from pathlib import Path

from stemmer_rslp import RSLP
from trie import normalizar

__all__ = [
    "para_minusculas",
    "remover_pontuacao",
    "tokenizar",
    "remover_stopwords",
    "carregar_stopwords",
    "Preprocessador",
]

# Um "token" é uma sequência maximal de letras. A classe [^\W\d_] significa
# "caractere de palavra que não seja dígito nem sublinhado", ou seja, apenas
# letras -- incluindo as acentuadas do português, porque o módulo `re` do
# Python trabalha em Unicode por padrão.
PADRAO_TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)

# Tudo que for pontuação (categoria Unicode P*) ou símbolo (S*) vira espaço.
# Espaço, e não string vazia, para que "banco-de-dados" produza três tokens em
# vez de um amálgama "bancodedados".
PADRAO_PONTUACAO = re.compile(r"[^\w\s]|_", re.UNICODE)

CAMINHO_STOPWORDS_PADRAO = Path(__file__).parent / "stopwords.txt"


def para_minusculas(texto):
    """Etapa 1: caixa baixa. Complexidade O(n) no tamanho do texto."""
    return texto.lower()


def remover_pontuacao(texto):
    """
    Etapa 2: troca pontuação e símbolos por espaço.

    Complexidade O(n). Observação: esta etapa aparece separada porque o
    enunciado a lista explicitamente; a tokenização por expressão regular da
    etapa 3 já daria conta sozinha, mas manter as duas deixa o pipeline
    rastreável passo a passo.
    """
    return PADRAO_PONTUACAO.sub(" ", texto)


def tokenizar(texto):
    """
    Etapa 3: quebra o texto em palavras.

    Números e sequências alfanuméricas são descartados: o vocabulário do
    mecanismo de busca é de palavras, e "1998" ou "x86" não têm prefixo
    linguístico útil para o autocomplete.

    Complexidade O(n).
    """
    return PADRAO_TOKEN.findall(texto)


def remover_stopwords(tokens, stopwords, tamanho_minimo=2):
    """
    Etapa 4: descarta palavras vazias e tokens curtos demais.

    A comparação é feita sobre a forma normalizada (minúscula e sem acento),
    de modo que a lista de stopwords pode ser escrita sem acentuação.

    Complexidade O(t), com t = número de tokens: cada teste é uma consulta a
    conjunto hash, O(1) em média.
    """
    return [
        token
        for token in tokens
        if len(token) >= tamanho_minimo and normalizar(token) not in stopwords
    ]


def carregar_stopwords(caminho=None):
    """
    Lê a lista de stopwords do arquivo, ignorando linhas em branco e
    comentários iniciados por '#'.

    Devolve um `set` de formas normalizadas -- conjunto, e não lista, porque a
    remoção de stopwords consulta essa estrutura uma vez por token do corpus:
    O(1) médio contra O(n) da busca sequencial.
    """
    arquivo = Path(caminho) if caminho else CAMINHO_STOPWORDS_PADRAO
    if not arquivo.exists():
        return set()

    stopwords = set()
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        stopwords.add(normalizar(linha))
    return stopwords


class Preprocessador:
    """
    Encapsula o pipeline completo e a configuração usada em todo o sistema.

    Manter uma única instância compartilhada garante que documentos e consultas
    passem exatamente pelo mesmo tratamento -- se a indexação remover stopwords
    e a consulta não, os dois lados deixam de se encontrar.
    """

    def __init__(self, stopwords=None, usar_stemming=True, tamanho_minimo=2):
        self.stopwords = stopwords if stopwords is not None else carregar_stopwords()
        self.usar_stemming = usar_stemming
        self.tamanho_minimo = tamanho_minimo
        self.stemmer = RSLP()

    def processar(self, texto):
        """
        Aplica as etapas 1 a 4 e devolve a lista de tokens que vão para o
        vocabulário, preservando a acentuação original.

        Complexidade O(n + t): uma varredura do texto mais uma dos tokens.
        """
        _brutos, filtrados = self.processar_detalhado(texto)
        return filtrados

    def processar_detalhado(self, texto):
        """
        Como `processar`, mas devolve também os tokens ANTES da remoção de
        stopwords, na forma `(brutos, filtrados)`.

        Existe para evitar trabalho duplicado na indexação: as estatísticas
        obrigatórias da seção 3.9 pedem tanto o total bruto quanto o total após
        a filtragem, e obter os dois com duas chamadas separadas significaria
        tokenizar o documento inteiro duas vezes.
        """
        texto = para_minusculas(texto)
        texto = remover_pontuacao(texto)
        brutos = tokenizar(texto)
        filtrados = remover_stopwords(brutos, self.stopwords, self.tamanho_minimo)
        return brutos, filtrados

    def radicalizar(self, token):
        """
        Etapa 5: devolve o radical do token quando o stemming está ligado;
        caso contrário devolve apenas a forma normalizada.

        É este método que define a CHAVE do índice invertido, e ele precisa ser
        o mesmo na indexação e na consulta.
        """
        if self.usar_stemming:
            return self.stemmer.radicalizar(token)
        return normalizar(token)

    def processar_consulta(self, texto):
        """
        Passa o texto digitado pelo usuário pelo mesmo pipeline dos documentos.

        Diferença importante: aqui as stopwords NÃO são descartadas por
        tamanho mínimo de forma silenciosa; se a consulta inteira for filtrada,
        devolve-se lista vazia e a interface avisa o usuário.
        """
        texto = para_minusculas(texto)
        texto = remover_pontuacao(texto)
        return tokenizar(texto)

    def termos_da_consulta(self, texto):
        """
        Separa a consulta em termos pesquisáveis e palavras ignoradas.

        Devolve `(termos, ignorados)`. Uma consulta com várias palavras precisa
        descartar as stopwords do mesmo jeito que a indexação descartou: em
        "estrutura de dados", o "de" não está no índice, e exigir que os
        documentos contenham TODOS os termos zeraria qualquer resultado. As
        ignoradas voltam para a interface poder dizer o que ficou de fora.
        """
        brutos = self.processar_consulta(texto)
        termos = remover_stopwords(brutos, self.stopwords, self.tamanho_minimo)
        mantidos = set(termos)
        ignorados = [token for token in brutos if token not in mantidos]
        return termos, ignorados

    def descrever(self):
        """Resumo da configuração, exibido nas estatísticas do sistema."""
        return {
            "stopwords carregadas": len(self.stopwords),
            "stemming": "RSLP (Orengo & Huyck, 2001)" if self.usar_stemming else "desligado",
            "tamanho minimo do token": self.tamanho_minimo,
        }
