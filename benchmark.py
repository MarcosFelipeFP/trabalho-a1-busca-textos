"""
benchmark.py
------------
Experimentos que sustentam com medições a análise de complexidade do relatório.

O enunciado pede, na seção 3.9, que as medições de tempo sejam usadas para
"relacionar a atividade aos conceitos de análise de complexidade estudados na
Unidade 1". Este script faz exatamente isso: para cada estrutura, confronta o
custo assintótico previsto no papel com o comportamento observado.

Metodologia:
  * o relógio é `time.perf_counter()`, monotônico e de alta resolução;
  * cada medição é repetida e o script reporta a MEDIANA, não a média, porque
    uma única interrupção do escalonador do sistema operacional distorce a
    média mas quase não afeta a mediana;
  * operações da ordem de microssegundos são executadas em LOTES dentro da
    região cronometrada, e o total é dividido no fim. Sem isso, o que se
    mediria seria majoritariamente o custo de chamar o próprio relógio, e não
    o da operação sob teste;
  * as estruturas são construídas uma vez e reaproveitadas entre repetições,
    para medir a consulta e não a construção.

Uso:
    python benchmark.py
    python benchmark.py --pasta outra_pasta
"""

import argparse
import random
import statistics
import sys
import time

from indice_invertido import TabelaHash
from kmp import buscar_ingenuo, buscar_kmp
from mecanismo import MecanismoBusca
from trie import Trie, TrieComprimida, distancia_edicao, normalizar

LARGURA = 74
REPETICOES = 25


# ==========================================================================
#  APOIO
# ==========================================================================

def titulo(texto):
    print()
    print("=" * LARGURA)
    print(f"  {texto}")
    print("=" * LARGURA)


def subtitulo(texto):
    print(f"\n{texto}")
    print("-" * LARGURA)


def medir(funcao, repeticoes=REPETICOES, lotes=1):
    """
    Cronometra `funcao` e devolve a mediana do custo de UMA execução, em segundos.

    Duas proteções contra ruído de medição, ambas necessárias quando a operação
    medida dura microssegundos:

      * `lotes` -- a função é executada `lotes` vezes DENTRO da região
        cronometrada, e o total é dividido no fim. Isso empurra o intervalo
        medido para a casa dos milissegundos, muito acima da resolução e do
        custo de chamada do próprio relógio. Sem isso, medir uma consulta de
        4 us significa medir majoritariamente o overhead de `perf_counter`.

      * `repeticoes` + mediana -- uma interrupção do escalonador do sistema
        operacional durante uma das medições distorce a média, mas quase não
        afeta a mediana.
    """
    tempos = []
    for _ in range(repeticoes):
        inicio = time.perf_counter()
        for _ in range(lotes):
            funcao()
        tempos.append((time.perf_counter() - inicio) / lotes)
    return statistics.median(tempos)


def us(segundos):
    """Formata segundos como microssegundos."""
    return f"{segundos * 1e6:>10.2f} us"


# ==========================================================================
#  EXPERIMENTO 1 - TRIE CONTRA BUSCA SEQUENCIAL
# ==========================================================================

def experimento_trie_vs_sequencial(vocabulario):
    """
    Compara a busca por prefixo na Trie com a varredura de uma lista.

    Previsão teórica:
        Trie        O(m + p)  -- p = nós abaixo do prefixo, ou seja, o custo
                                 acompanha a QUANTIDADE DE RESULTADOS
        sequencial  O(V * m)  -- custo proporcional ao TAMANHO DO VOCABULÁRIO

    A distinção é o ponto do experimento. Não se espera que o tempo da Trie
    fique parado: ele cresce, porque vocabulários maiores produzem mais
    respostas para o mesmo prefixo. O que se espera é que ele acompanhe os
    resultados devolvidos, e não o tamanho da coleção -- por isso o segundo
    quadro repete a medição com o número de resultados FIXADO por `limite`,
    onde aí sim o tempo da Trie deve estabilizar.
    """
    titulo("EXPERIMENTO 1 - Busca por prefixo: Trie contra varredura sequencial")

    prefixos = ["comp", "prog", "algor", "dad", "red", "seg", "inte", "proc"]
    print(f"\nPrefixos testados: {', '.join(prefixos)}")
    print(f"Mediana de {REPETICOES} repetições por medição.")

    base = sorted(vocabulario)
    fracoes = (0.125, 0.25, 0.5, 1.0)

    subtitulo("(a) Todos os resultados: o custo da Trie acompanha o que ela devolve")
    print(f"  {'vocabulário':>12}{'resultados':>12}{'Trie':>15}"
          f"{'lista':>15}{'ganho':>10}")
    print("  " + "-" * (LARGURA - 4))

    for fracao in fracoes:
        amostra = base[: max(1, int(len(base) * fracao))]
        trie = Trie(amostra)
        lista = list(amostra)
        encontrados = sum(len(trie.buscar_prefixo(p)) for p in prefixos)

        def com_trie():
            for prefixo in prefixos:
                trie.buscar_prefixo(prefixo)

        def com_lista():
            # Busca sequencial: testa todas as palavras, uma por uma.
            for prefixo in prefixos:
                chave = normalizar(prefixo)
                [p for p in lista if normalizar(p).startswith(chave)]

        tempo_trie = medir(com_trie, lotes=200)
        tempo_lista = medir(com_lista)
        ganho = tempo_lista / tempo_trie if tempo_trie else 0

        print(f"  {len(amostra):>12,}{encontrados:>12,}{us(tempo_trie):>15}"
              f"{us(tempo_lista):>15}{ganho:>9.0f}x")

    print("\n  As duas colunas de tempo crescem, mas por motivos diferentes: a")
    print("  da lista cresce porque há mais palavras para varrer; a da Trie,")
    print("  porque há mais palavras para DEVOLVER. O quadro (b) separa os dois")
    print("  efeitos.")

    subtitulo("(b) Resultados limitados a 10 por prefixo: p fica constante")
    print(f"  {'vocabulário':>12}{'resultados':>12}{'Trie':>15}"
          f"{'lista':>15}{'ganho':>10}")
    print("  " + "-" * (LARGURA - 4))

    for fracao in fracoes:
        amostra = base[: max(1, int(len(base) * fracao))]
        trie = Trie(amostra)
        lista = list(amostra)
        encontrados = sum(len(trie.buscar_prefixo(p, limite=10)) for p in prefixos)

        def com_trie_limitada():
            for prefixo in prefixos:
                trie.buscar_prefixo(prefixo, limite=10)

        def com_lista_limitada():
            for prefixo in prefixos:
                chave = normalizar(prefixo)
                achados = []
                for palavra in lista:
                    if normalizar(palavra).startswith(chave):
                        achados.append(palavra)
                        if len(achados) >= 10:
                            break

        tempo_trie = medir(com_trie_limitada, lotes=500)
        tempo_lista = medir(com_lista_limitada)
        ganho = tempo_lista / tempo_trie if tempo_trie else 0

        print(f"  {len(amostra):>12,}{encontrados:>12,}{us(tempo_trie):>15}"
              f"{us(tempo_lista):>15}{ganho:>9.0f}x")

    print("\n  A comparação decisiva está entre a segunda e a terceira linha: o")
    print("  vocabulário DOBRA, o número de resultados fica igual, e o tempo da")
    print("  Trie não se move -- enquanto o da lista dobra junto com V. É a")
    print("  demonstração controlada de que o custo da Trie é O(m + p) e o da")
    print("  varredura é O(V * m). Nas demais linhas o tempo da Trie sobe, mas")
    print("  acompanhando a coluna de resultados, não a de vocabulário.")


# ==========================================================================
#  EXPERIMENTO 2 - AUTOCOMPLETE TOP-K: VARREDURA CONTRA BUSCA BEST-FIRST
# ==========================================================================

def experimento_autocomplete(mecanismo):
    """
    Compara as duas formas de responder "as k melhores palavras deste prefixo".

    Previsão teórica:
        varredura    O(m + p)             -- visita a subárvore inteira do
                                            prefixo para depois escolher as k
        best-first   O(m + k·h·σ·log(...)) -- não depende de p

    A grandeza observada é o NÚMERO DE NÓS VISITADOS, e não o tempo. Tempo em
    microssegundos oscila com o escalonador; nós visitados é determinístico e
    é exatamente a quantidade que a análise assintótica prevê. O tempo aparece
    ao lado como confirmação.

    A previsão que interessa é qualitativa: conforme o prefixo encurta, p
    explode e a coluna da varredura acompanha, enquanto a do best-first fica
    praticamente parada -- ela só depende de k, que é fixo.
    """
    titulo("EXPERIMENTO 2 - Autocomplete top-k: varredura contra best-first")

    trie = mecanismo.trie
    k = 10
    prefixos = ["computac", "comput", "compu", "comp", "com", "co", "c"]

    print(f"\n  As {k} palavras mais frequentes do corpus que começam com cada")
    print("  prefixo, obtidas de duas formas sobre a MESMA Trie.")
    print(f"  Mediana de {REPETICOES} repetições por medição.")

    subtitulo("(a) Trabalho realizado para devolver as mesmas k palavras")
    print(f"  {'prefixo':>10}{'palavras':>11}{'nós (varredura)':>18}"
          f"{'nós (best-first)':>18}{'economia':>11}")
    print("  " + "-" * (LARGURA - 4))

    for prefixo in prefixos:
        disponiveis = trie.contar_prefixo(prefixo)

        # Varredura: para escolher as k melhores é preciso ver todas, então a
        # coleta vai sem limite -- é esse o custo que o best-first evita.
        trie.buscar_prefixo(prefixo)
        nos_varredura = trie.nos_visitados

        trie.sugerir(prefixo, limite=k)
        nos_best_first = trie.nos_visitados

        economia = (1 - nos_best_first / nos_varredura) if nos_varredura else 0.0
        print(f"  {prefixo:>10}{disponiveis:>11,}{nos_varredura:>18,}"
              f"{nos_best_first:>18,}{economia:>10.1%}")

    subtitulo("(b) Tempo das duas estratégias")
    print(f"  {'prefixo':>10}{'palavras':>11}{'varredura':>16}"
          f"{'best-first':>16}{'ganho':>10}")
    print("  " + "-" * (LARGURA - 4))

    for prefixo in prefixos:
        disponiveis = trie.contar_prefixo(prefixo)

        def com_varredura():
            # Ordenar por frequência exige a lista inteira antes de cortar.
            palavras = trie.buscar_prefixo(prefixo)
            ordenadas = sorted(palavras,
                               key=lambda p: -mecanismo.frequencia.get(p, 0))
            return ordenadas[:k]

        def com_best_first():
            return trie.sugerir(prefixo, limite=k)

        tempo_varredura = medir(com_varredura, lotes=20)
        tempo_best = medir(com_best_first, lotes=20)
        ganho = tempo_varredura / tempo_best if tempo_best else 0

        print(f"  {prefixo:>10}{disponiveis:>11,}{us(tempo_varredura):>16}"
              f"{us(tempo_best):>16}{ganho:>9.1f}x")

    subtitulo("(c) O que cada estratégia devolve para 'comp'")
    alfabeticas = trie.buscar_prefixo("comp", limite=5)
    relevantes = trie.sugerir("comp", limite=5)

    print(f"  {'ordem alfabética':<30}{'por frequência no corpus':<30}")
    print("  " + "-" * (LARGURA - 4))
    for posicao in range(5):
        esquerda = alfabeticas[posicao] if posicao < len(alfabeticas) else ""
        if posicao < len(relevantes):
            palavra, peso = relevantes[posicao]
            direita = f"{palavra} ({peso}x)"
        else:
            direita = ""
        print(f"  {esquerda:<30}{direita:<30}")

    print("\n  A tabela (a) é a demonstração: o prefixo encurta, a subárvore")
    print("  cresce em ordens de grandeza e a varredura cresce junto, enquanto")
    print("  o best-first mal se mexe -- ele para assim que as k palavras saem,")
    print("  e a poda por `melhor_peso` garante que nenhuma subárvore descartada")
    print("  poderia conter algo melhor. A tabela (c) mostra por que isso vale a")
    print("  pena: a coluna da direita é a que um usuário reconheceria como")
    print("  autocomplete.")


# ==========================================================================
#  EXPERIMENTO 3 - TRIE TRADICIONAL CONTRA COMPRIMIDA
# ==========================================================================

def experimento_trie_comprimida(vocabulario):
    """
    Mede a economia de memória da Trie comprimida (PATRICIA).

    Responde com números à questão conceitual 6 do enunciado: a Trie
    tradicional gasta um nó por caractere, mesmo em cadeias sem bifurcação; a
    comprimida colapsa cada cadeia dessas em um nó só.
    """
    titulo("EXPERIMENTO 3 - Trie tradicional contra Trie comprimida (PATRICIA)")

    palavras = sorted(vocabulario)

    inicio = time.perf_counter()
    trie = Trie(palavras)
    tempo_trie = time.perf_counter() - inicio

    inicio = time.perf_counter()
    comprimida = TrieComprimida(palavras)
    tempo_comprimida = time.perf_counter() - inicio

    caracteres = sum(len(normalizar(p)) for p in palavras)

    subtitulo("Memória")
    print(f"  Palavras distintas                 : {len(trie):,}")
    print(f"  Caracteres totais (limite superior): {caracteres:,}")
    print(f"  Nós na Trie tradicional            : {trie.total_nos():,}")
    print(f"  Nós na Trie comprimida             : {comprimida.total_nos():,}")
    economia = 1 - comprimida.total_nos() / trie.total_nos()
    print(f"  Economia de nós                    : {economia * 100:.1f}%")

    subtitulo("Construção")
    print(f"  Trie tradicional : {tempo_trie * 1000:>8.2f} ms")
    print(f"  Trie comprimida  : {tempo_comprimida * 1000:>8.2f} ms")

    subtitulo("Consulta por prefixo (mediana de 25 repetições)")
    prefixos = ["comp", "prog", "algor", "dad", "red"]

    tempo_a = medir(lambda: [trie.buscar_prefixo(p) for p in prefixos], lotes=200)
    tempo_b = medir(lambda: [comprimida.buscar_prefixo(p) for p in prefixos], lotes=200)
    print(f"  Trie tradicional : {us(tempo_a)}")
    print(f"  Trie comprimida  : {us(tempo_b)}")

    iguais = all(trie.buscar_prefixo(p) == comprimida.buscar_prefixo(p)
                 for p in prefixos + ["a", "z", "xyz", ""])
    print(f"\n  Resultados idênticos nas duas estruturas: {iguais}")
    print("  A compressão muda o consumo de memória, não a linguagem reconhecida.")


# ==========================================================================
#  EXPERIMENTO 4 - KMP CONTRA BUSCA INGÊNUA
# ==========================================================================

def experimento_kmp(mecanismo):
    """
    Confronta KMP e força bruta em dois cenários.

    No pior caso construído, a diferença entre O(n+m) e O(n*m) fica explícita.
    Em texto natural a vantagem é modesta, porque falhas em texto real
    costumam ocorrer no primeiro ou segundo caractere -- e é justamente por
    isso que a busca ingênua sobrevive na prática apesar do pior caso ruim.
    """
    titulo("EXPERIMENTO 4 - Casamento de cadeias: KMP contra força bruta")

    subtitulo("Pior caso construído: texto 'aaa...a', padrão 'aaa...ab'")
    print(f"  {'n':>10}{'m':>6}{'KMP (comp.)':>16}{'ingênuo (comp.)':>18}{'razão':>10}")
    print("  " + "-" * (LARGURA - 4))
    for n in (2000, 4000, 8000, 16000):
        m = 60
        texto = "a" * n
        padrao = "a" * (m - 1) + "b"
        k = buscar_kmp(texto, padrao)
        i = buscar_ingenuo(texto, padrao)
        razao = i.comparacoes / k.comparacoes
        print(f"  {n:>10,}{m:>6}{k.comparacoes:>16,}{i.comparacoes:>18,}{razao:>9.1f}x")

    print("\n  As comparações do KMP crescem como 2n (linear); as do ingênuo")
    print("  crescem como n*m. Dobrar n dobra o KMP e dobra o ingênuo, mas a")
    print("  razão entre eles permanece próxima de m/2 -- o fator perdido.")

    subtitulo("Texto natural: corpus real do trabalho")
    corpus = "\n".join(mecanismo.conteudo.values()).lower()
    print(f"  Tamanho do corpus: {len(corpus):,} caracteres\n")
    print(f"  {'padrão':<28}{'ocorr.':>8}{'KMP':>14}{'ingênuo':>14}{'razão':>9}")
    print("  " + "-" * (LARGURA - 4))
    for padrao in ["rede neural", "chave pública", "algoritmo de busca",
                   "complexidade computacional", "aprendizado"]:
        k = buscar_kmp(corpus, padrao)
        i = buscar_ingenuo(corpus, padrao)
        razao = i.comparacoes / k.comparacoes if k.comparacoes else 0
        print(f"  {padrao:<28}{len(k.ocorrencias):>8}"
              f"{k.comparacoes:>14,}{i.comparacoes:>14,}{razao:>8.2f}x")

    print("\n  Em texto natural a vantagem encolhe: o alfabeto é grande e as")
    print("  falhas acontecem cedo, então a força bruta raramente atinge o seu")
    print("  pior caso. A garantia do KMP, porém, vale para QUALQUER entrada.")


# ==========================================================================
#  EXPERIMENTO 5 - TABELA HASH: COLISÕES NA PRÁTICA
# ==========================================================================

def experimento_hash(mecanismo):
    """
    Mede colisões e comprimento de cadeia da tabela hash própria sobre os
    termos reais do índice.

    Serve para transformar em número o que a seção 3.6 do enunciado pede para
    explicar: por que a busca é O(1) em média e o que são as colisões.
    """
    titulo("EXPERIMENTO 5 - Tabela hash: fator de carga e colisões")

    termos = list(mecanismo.indice.por_radical)
    print(f"\n  Termos indexados: {len(termos):,}\n")

    print(f"  {'capacidade':>12}{'carga':>10}{'colisões':>12}"
          f"{'maior cadeia':>15}{'cadeia média':>15}")
    print("  " + "-" * (LARGURA - 4))

    for capacidade in (512, 2048, 8192, 32768):
        # `CARGA_MAXIMA` alto desativa o redimensionamento automático, para que
        # o efeito do fator de carga escolhido fique visível.
        tabela = TabelaHash(capacidade=capacidade)
        tabela.CARGA_MAXIMA = 1e9
        for termo in termos:
            tabela.inserir(termo, None)

        e = tabela.estatisticas()
        print(f"  {e['capacidade']:>12,}{e['fator de carga']:>10.3f}"
              f"{e['colisoes']:>12,}{e['maior cadeia']:>15}"
              f"{e['cadeia media']:>15.3f}")

    print("\n  A cadeia média acompanha o fator de carga: é o α da análise")
    print("  clássica, e o custo médio da busca é O(1 + α). Com a tabela")
    print("  redimensionando para manter α abaixo de 0.75, o custo fica O(1).")

    subtitulo("Comparação com o dict do Python")
    tabela = TabelaHash(capacidade=1024)
    for termo in termos:
        tabela.inserir(termo, None)
    dicionario = {termo: None for termo in termos}
    amostra = random.sample(termos, min(2000, len(termos)))

    tempo_propria = medir(lambda: [tabela.buscar(t) for t in amostra], repeticoes=7)
    tempo_dict = medir(lambda: [dicionario.get(t) for t in amostra], repeticoes=7)

    print(f"  Tabela própria (Python puro) : {tempo_propria * 1000:>8.2f} ms")
    print(f"  dict nativo (C)              : {tempo_dict * 1000:>8.2f} ms")
    print(f"  Razão                        : {tempo_propria / tempo_dict:>8.1f}x")
    print("\n  Mesma complexidade assintótica, O(1) em média nos dois casos. A")
    print("  diferença é o fator constante: o dict é implementado em C e usa")
    print("  endereçamento aberto. É por isso que o sistema usa o dict e a")
    print("  tabela própria fica reservada à demonstração.")


# ==========================================================================
#  EXPERIMENTO 6 - ESCALABILIDADE DA INDEXAÇÃO
# ==========================================================================

def experimento_escalabilidade(pasta):
    """
    Verifica se o tempo de construção cresce linearmente com o corpus.

    Previsão: O(N) no total de tokens. Se a previsão valer, o tempo por mil
    tokens deve permanecer aproximadamente constante conforme o corpus cresce.
    """
    titulo("EXPERIMENTO 6 - Escalabilidade da indexação")

    completo = MecanismoBusca(pasta, guardar_conteudo=False)
    arquivos = completo.listar_arquivos()
    if len(arquivos) < 4:
        print("\n  Corpus pequeno demais para o experimento.")
        return

    print(f"\n  {'docs':>6}{'tokens':>12}{'trie (ms)':>12}{'índice (ms)':>14}"
          f"{'total (ms)':>13}{'us/1k tokens':>16}")
    print("  " + "-" * (LARGURA - 4))

    for quantidade in (len(arquivos) // 4, len(arquivos) // 2,
                       3 * len(arquivos) // 4, len(arquivos)):
        if quantidade < 1:
            continue

        mecanismo = MecanismoBusca(pasta, guardar_conteudo=False)
        # Restringe a varredura aos primeiros `quantidade` arquivos.
        mecanismo.listar_arquivos = lambda n=quantidade: arquivos[:n]
        mecanismo.construir()

        e = mecanismo.estatisticas
        total = e.tempo_total_construcao()
        por_mil = (total / e.total_palavras * 1000 * 1e6) if e.total_palavras else 0

        print(f"  {e.documentos:>6}{e.total_palavras:>12,}"
              f"{e.tempo_trie * 1000:>12.1f}{e.tempo_indice * 1000:>14.1f}"
              f"{total * 1000:>13.1f}{por_mil:>16.1f}")

    print("\n  A última coluna é o custo normalizado. Mantendo-se estável")
    print("  enquanto o corpus quadruplica, ela confirma o comportamento")
    print("  linear previsto: O(N) no total de tokens.")


# ==========================================================================
#  EXPERIMENTO 7 - RANQUEAMENTO: BM25 CONTRA TF-IDF
# ==========================================================================

def experimento_ranqueamento(mecanismo):
    """
    Compara as ordens produzidas por BM25 e TF-IDF para as mesmas consultas.

    A diferença aparece principalmente em documentos longos: sem normalização
    por tamanho, o TF-IDF tende a premiá-los apenas por acumularem mais
    ocorrências.
    """
    titulo("EXPERIMENTO 7 - Ranqueamento: BM25 contra TF-IDF")

    indice = mecanismo.indice
    print(f"\n  Tamanho médio dos documentos: {indice.tamanho_medio():.0f} tokens\n")

    for consulta in ["algoritmo", "rede", "dados", "segurança"]:
        radical = mecanismo.preprocessador.radicalizar(consulta)
        bm25 = indice.ranquear_bm25([radical])[:5]
        tfidf = indice.ranquear_tfidf([radical])[:5]
        if not bm25:
            continue

        subtitulo(f"Consulta: '{consulta}'  (radical '{radical}')")
        print(f"  {'#':>2}  {'BM25':<40}{'TF-IDF':<40}")
        for posicao in range(max(len(bm25), len(tfidf))):
            esquerda = f"{bm25[posicao][0]} ({bm25[posicao][1]:.2f})" if posicao < len(bm25) else ""
            direita = f"{tfidf[posicao][0]} ({tfidf[posicao][1]:.2f})" if posicao < len(tfidf) else ""
            print(f"  {posicao + 1:>2}  {esquerda:<40}{direita:<40}")

        tamanhos_bm25 = [indice.tamanho_documento[d] for d, _ in bm25]
        tamanhos_tfidf = [indice.tamanho_documento[d] for d, _ in tfidf]
        print(f"\n      tamanho médio do top-5  BM25: {sum(tamanhos_bm25) / len(tamanhos_bm25):>8,.0f} tokens")
        print(f"      tamanho médio do top-5 TFIDF: {sum(tamanhos_tfidf) / len(tamanhos_tfidf):>8,.0f} tokens")

        # Termo presente em TODOS os documentos: df = N, logo log10(N/df) = 0 e
        # o TF-IDF zera a consulta inteira, deixando a ordem sem significado. O
        # BM25 escapa disso pelo "+1" dentro do logaritmo do seu IDF.
        df = indice.frequencia_documental(radical)
        if df == len(indice.documentos):
            print(f"\n      ACHADO: '{radical}' ocorre nos {df} documentos (df = N).")
            print("      O TF-IDF zera todos os pesos -- log10(N/df) = log10(1) = 0 --")
            print("      e a ordem que ele exibe passa a ser apenas alfabética.")
            print("      O BM25 continua discriminando porque seu IDF é")
            print("      ln((N-df+0.5)/(df+0.5) + 1), que se mantém positivo.")


# ==========================================================================
#  EXPERIMENTO 8 - EFEITO DO STEMMING
# ==========================================================================

def experimento_stemming(mecanismo):
    """
    Mede o que o RSLP muda no índice e na cobertura das consultas.

    Duas grandezas interessam: quanto o vocabulário encolhe (menos chaves, menos
    memória) e quantos documentos a mais uma consulta alcança (mais recall).
    """
    titulo("EXPERIMENTO 8 - Efeito do stemming RSLP")

    indice = mecanismo.indice
    exatos = indice.total_termos(usar_radical=False)
    radicais = indice.total_termos(usar_radical=True)

    subtitulo("Compressão do vocabulário")
    print(f"  Formas distintas no texto : {exatos:,}")
    print(f"  Radicais distintos (RSLP) : {radicais:,}")
    print(f"  Redução                   : {(1 - radicais / exatos) * 100:.1f}%")
    print(f"  Formas por radical         : {exatos / radicais:.2f}")

    subtitulo("Cobertura das consultas")
    print(f"  {'consulta':<20}{'sem stemming':>16}{'com stemming':>16}{'ganho':>12}")
    print("  " + "-" * (LARGURA - 4))

    for consulta in ["algoritmo", "rede", "dado", "programa", "computador",
                     "sistema", "documento", "informação"]:
        resposta = mecanismo.buscar_palavra(consulta)
        sem = resposta["termos"][0]["exatos"] if resposta["termos"] else 0
        com = len(resposta["documentos"])
        ganho = f"+{com - sem}" if com > sem else "0"
        print(f"  {consulta:<20}{sem:>16}{com:>16}{ganho:>12}")

    print("\n  O ganho é o número de arquivos que a consulta só encontra porque")
    print("  o radical reúne singular, plural e formas derivadas da palavra.")


# ==========================================================================
#  EXPERIMENTO 9 - BUSCA APROXIMADA: TRIE CONTRA PALAVRA A PALAVRA
# ==========================================================================

def experimento_busca_aproximada(mecanismo):
    """
    Compara o "você quis dizer?" feito sobre a Trie com a comparação da consulta
    contra cada palavra do vocabulário, uma por uma.

    Previsão teórica:
        palavra a palavra   O(V · m · ℓ)  -- uma matriz m×ℓ por palavra
        Trie                O(n · m)      -- uma linha por nó visitado

    A grandeza observada é o número de CÉLULAS da matriz de programação
    dinâmica efetivamente calculadas, que não depende de relógio nem de
    máquina. A força bruta recebe o filtro óbvio -- palavras cujo tamanho
    difere da consulta em mais que o limite não podem estar dentro dele e nem
    são comparadas --, para a comparação ser justa. A Trie ganha mesmo assim,
    por dois motivos: palavras com prefixo comum dividem as mesmas linhas, e
    ramos cujo mínimo já passou do limite são podados inteiros.
    """
    titulo("EXPERIMENTO 9 - Busca aproximada: Trie contra palavra a palavra")

    trie = mecanismo.trie
    chaves = sorted({normalizar(palavra) for palavra in mecanismo.vocabulario})
    consultas = ["algortimo", "estrutra", "compilaodr", "neurl", "hahs"]

    print(f"\n  Vocabulário: {len(chaves):,} chaves, {trie.total_nos():,} nós na Trie.")
    print("  Distância máxima: 2 edições (1 para palavras de até 4 letras).")

    subtitulo("(a) Células da matriz calculadas por consulta")
    print(f"  {'consulta':<13}{'achadas':>8}{'nós visitados':>15}"
          f"{'células (Trie)':>16}{'palavra a palavra':>19}{'razão':>8}")
    print("  " + "-" * (LARGURA - 4))

    medidas = []
    for consulta in consultas:
        chave = normalizar(consulta)
        distancia = 1 if len(chave) <= 4 else 2

        achadas = trie.buscar_aproximado(consulta, distancia, limite=None)
        celulas_trie = trie.nos_visitados * len(chave)
        comparadas = [c for c in chaves if abs(len(c) - len(chave)) <= distancia]
        celulas_bruta = sum(len(c) * len(chave) for c in comparadas)

        # Confere que as duas vias concordam antes de comparar os custos.
        pela_forca = sum(1 for c in comparadas if distancia_edicao(c, chave) <= distancia)
        assert pela_forca == len(achadas), f"divergência em '{consulta}'"

        medidas.append((consulta, chave, distancia, comparadas))
        print(f"  {consulta:<13}{len(achadas):>8}{trie.nos_visitados:>15,}"
              f"{celulas_trie:>16,}{celulas_bruta:>19,}"
              f"{celulas_bruta / celulas_trie:>7.0f}x")

    subtitulo("(b) Tempo das duas estratégias")
    print(f"  {'consulta':<13}{'Trie':>16}{'palavra a palavra':>20}{'ganho':>10}")
    print("  " + "-" * (LARGURA - 4))

    for consulta, chave, distancia, comparadas in medidas:
        tempo_trie = medir(lambda: trie.buscar_aproximado(consulta, distancia, limite=None),
                           repeticoes=9)
        tempo_bruta = medir(
            lambda: [c for c in comparadas if distancia_edicao(c, chave) <= distancia],
            repeticoes=3)
        print(f"  {consulta:<13}{us(tempo_trie):>16}{us(tempo_bruta):>20}"
              f"{tempo_bruta / tempo_trie:>9.1f}x")

    print("\n  A coluna de nós visitados é a poda em ação: de mais de trinta mil")
    print("  nós, a busca abre poucos milhares -- os caminhos que ainda estão a até")
    print("  duas edições de algum prefixo da consulta. É por isso que o \"você")
    print("  quis dizer?\" cabe no tempo de uma consulta interativa.")


# ==========================================================================

def main():
    analisador = argparse.ArgumentParser(
        description="Experimentos de complexidade do Trabalho A1"
    )
    analisador.add_argument("--pasta", default="documentos",
                            help="pasta com os arquivos .txt")
    argumentos = analisador.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    random.seed(42)

    titulo("TRABALHO A1 - EXPERIMENTOS DE ANÁLISE DE COMPLEXIDADE")
    print("\n  Construindo o índice sobre o corpus...")

    mecanismo = MecanismoBusca(argumentos.pasta)
    if mecanismo.construir() == 0:
        print(f"\n  Nenhum .txt em '{argumentos.pasta}/'. "
              f"Rode antes: python preparar_corpus.py")
        return 1

    e = mecanismo.estatisticas
    print(f"  {e.documentos} documentos, {e.total_palavras:,} tokens, "
          f"{e.termos_distintos:,} termos distintos.")

    experimento_trie_vs_sequencial(mecanismo.vocabulario)
    experimento_autocomplete(mecanismo)
    experimento_trie_comprimida(mecanismo.vocabulario)
    experimento_kmp(mecanismo)
    experimento_hash(mecanismo)
    experimento_escalabilidade(argumentos.pasta)
    experimento_ranqueamento(mecanismo)
    experimento_stemming(mecanismo)
    experimento_busca_aproximada(mecanismo)

    titulo("FIM DOS EXPERIMENTOS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
