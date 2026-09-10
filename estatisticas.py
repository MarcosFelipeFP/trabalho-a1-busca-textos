"""
estatisticas.py
---------------
Medição de tempo e coleta das métricas exigidas na seção 3.9 do enunciado.

O objetivo declarado no enunciado é "relacionar a atividade aos conceitos de
análise de complexidade estudados na Unidade 1": as medições servem para
confrontar o custo assintótico previsto no papel com o tempo real observado.

--------------------------------------------------------------------------
Qual relógio usar
--------------------------------------------------------------------------
`time.perf_counter()` é o contador de maior resolução disponível e, ao
contrário de `time.time()`, é monotônico -- não anda para trás se o relógio do
sistema for ajustado durante a medição. É a função indicada para medir
INTERVALOS, que é exatamente o caso aqui. `time.time()` serviria para carimbar
uma data, não para cronometrar.

Uma ressalva metodológica que vale para todas as medições deste trabalho:
consultas isoladas duram poucos microssegundos, na mesma ordem de grandeza do
ruído do escalonador do sistema operacional. Por isso o `benchmark.py` repete
cada operação muitas vezes e reporta a MEDIANA, bem menos sensível a picos
esporádicos do que a média.
"""

import time

__all__ = ["Cronometro", "formatar_duracao", "Estatisticas"]


class Cronometro:
    """
    Cronômetro de uso como gerenciador de contexto.

        with Cronometro() as c:
            construir_indice()
        print(c.ms)

    O tempo fica disponível em `decorrido` (segundos) e `ms` (milissegundos)
    assim que o bloco termina.
    """

    __slots__ = ("inicio", "decorrido")

    def __init__(self):
        self.inicio = None
        self.decorrido = 0.0

    def __enter__(self):
        self.inicio = time.perf_counter()
        return self

    def __exit__(self, *_excecao):
        self.decorrido = time.perf_counter() - self.inicio
        return False        # não engole exceções ocorridas dentro do bloco

    @property
    def ms(self):
        """Tempo decorrido em milissegundos."""
        return self.decorrido * 1000.0

    def __repr__(self):
        return f"Cronometro({formatar_duracao(self.decorrido)})"


def formatar_duracao(segundos):
    """
    Formata uma duração escolhendo a unidade legível.

    Um índice leva centenas de milissegundos para ser construído; uma consulta
    leva microssegundos. Exibir tudo na mesma unidade produziria ou "0.000 s"
    ou "812000.000 us" -- nenhum dos dois ajuda a ler o resultado.
    """
    if segundos >= 1.0:
        return f"{segundos:.3f} s"
    if segundos >= 1e-3:
        return f"{segundos * 1e3:.3f} ms"
    return f"{segundos * 1e6:.1f} us"


class Estatisticas:
    """
    Reúne as sete métricas obrigatórias da seção 3.9 do enunciado.

        1. documentos processados
        2. total de palavras após a tokenização
        3. termos distintos
        4. palavras armazenadas na Trie
        5. tempo de construção da Trie
        6. tempo de construção do índice invertido
        7. tempo de cada consulta realizada

    O item 7 é acumulado em `consultas`, um histórico que também alimenta o
    resumo por tipo de consulta exibido no menu de estatísticas.
    """

    def __init__(self):
        self.documentos = 0
        self.total_palavras = 0          # tokens após a tokenização
        self.total_palavras_brutas = 0   # tokens antes da remoção de stopwords
        self.termos_distintos = 0
        self.palavras_na_trie = 0
        self.nos_na_trie = 0
        self.nos_na_trie_comprimida = 0
        self.postagens = 0

        self.tempo_leitura = 0.0
        self.tempo_preprocessamento = 0.0
        self.tempo_trie = 0.0
        self.tempo_indice = 0.0

        self.consultas = []              # lista de (tipo, texto, resultados, segundos)

    # -------------------------------------------------------------- consultas

    def registrar_consulta(self, tipo, texto, resultados, segundos):
        """Guarda o custo de uma consulta -- item 7 da seção 3.9."""
        self.consultas.append((tipo, texto, resultados, segundos))

    def ultima_consulta(self):
        """Devolve a consulta mais recente, ou None se nenhuma foi feita."""
        return self.consultas[-1] if self.consultas else None

    def resumo_por_tipo(self):
        """
        Agrega o histórico por tipo de consulta.

        Devolve {tipo: (quantidade, tempo_total, tempo_medio)}. Serve para
        mostrar, com números do próprio uso, que a busca exata (uma consulta de
        hash) custa consistentemente menos que a busca por prefixo (que ainda
        precisa varrer a subárvore da Trie).
        """
        agregado = {}
        for tipo, _texto, _resultados, segundos in self.consultas:
            quantidade, total = agregado.get(tipo, (0, 0.0))
            agregado[tipo] = (quantidade + 1, total + segundos)

        return {
            tipo: (quantidade, total, total / quantidade)
            for tipo, (quantidade, total) in agregado.items()
        }

    # ----------------------------------------------------------------- resumos

    def tempo_total_construcao(self):
        """Soma das quatro fases de construção do sistema."""
        return (
            self.tempo_leitura
            + self.tempo_preprocessamento
            + self.tempo_trie
            + self.tempo_indice
        )

    def taxa_reducao_stopwords(self):
        """Fração de tokens eliminada pela remoção de stopwords."""
        if not self.total_palavras_brutas:
            return 0.0
        removidos = self.total_palavras_brutas - self.total_palavras
        return removidos / self.total_palavras_brutas

    def economia_trie_comprimida(self):
        """Fração de nós economizada pela Trie comprimida em relação à tradicional."""
        if not self.nos_na_trie:
            return 0.0
        return 1.0 - (self.nos_na_trie_comprimida / self.nos_na_trie)
