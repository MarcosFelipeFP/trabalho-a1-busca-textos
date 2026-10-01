"""
main.py
-------
Ponto de entrada do trabalho. Reúne as duas partes em um único programa:

    Parte I  -- autocomplete com Trie sobre um léxico de palavras
    Parte II -- mecanismo de busca sobre os arquivos .txt de uma pasta

Uso:
    python main.py                      menu principal, escolhe a parte
    python main.py --parte 1            vai direto para o autocomplete
    python main.py --parte 2            vai direto para a busca em documentos
    python main.py --pasta meus_txt     usa outra pasta de documentos
    python main.py --sem-stemming       desliga o RSLP, para comparação
"""

import argparse
import sys
import textwrap
from pathlib import Path

from estatisticas import Cronometro, formatar_duracao
from mecanismo import MecanismoBusca
from trie import Trie

RAIZ = Path(__file__).resolve().parent

LARGURA = 60

# A busca por prefixo devolve TODAS as palavras que começam com o prefixo
# (seção 2.3 do enunciado). Como um prefixo de uma letra alcança mais de mil
# delas, a lista é exibida em páginas destes tamanhos, sem cortar nada.
PALAVRAS_POR_PAGINA = 40
TERMOS_POR_PAGINA = 10

# Usadas quando não há léxico nem corpus: são as palavras da seção 2.2 do
# enunciado, o suficiente para o programa demonstrar o autocomplete.
PALAVRAS_EXEMPLO = [
    "computador", "computação", "computacional", "compilador",
    "complexidade", "programação", "processador", "processamento",
]


# ==========================================================================
#  APRESENTAÇÃO
# ==========================================================================

def configurar_saida():
    """
    Garante saída em UTF-8 no terminal.

    Necessário porque o console do Windows ainda pode operar em uma página de
    código legada (cp1252), na qual imprimir "computação" levantaria
    UnicodeEncodeError. `errors="replace"` evita que um caractere exótico
    derrube o programa inteiro.
    """
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass        # fluxo redirecionado ou sem suporte: segue como está


def cabecalho(titulo):
    """Imprime um título entre linhas de '=', no estilo dos exemplos do enunciado."""
    print()
    print("=" * LARGURA)
    print(titulo.center(LARGURA))
    print("=" * LARGURA)


def secao(titulo):
    """Separador leve para blocos dentro de uma tela."""
    print(f"\n{titulo}")
    print("-" * LARGURA)


def perguntar(mensagem):
    """
    Lê uma linha do usuário, tratando Ctrl+C e fim de entrada como saída limpa.

    Devolve None quando o usuário encerra, para que o laço de menu saiba parar
    sem estourar exceção na cara de quem está usando o programa.
    """
    try:
        return input(mensagem).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def exibir_em_paginas(itens, exibir_item, por_pagina, unidade):
    """
    Exibe todos os `itens`, `por_pagina` de cada vez.

    Enter mostra a página seguinte; qualquer outra resposta encerra a lista.
    A consulta já foi feita e cronometrada antes: a paginação é apenas
    apresentação, e por isso não entra no tempo informado ao usuário.
    """
    total = len(itens)
    for inicio in range(0, total, por_pagina):
        for item in itens[inicio:inicio + por_pagina]:
            exibir_item(item)

        exibidos = min(inicio + por_pagina, total)
        if exibidos < total:
            resposta = perguntar(f"  -- {exibidos} de {total} {unidade}. "
                                 f"Enter mostra mais; 0 encerra a lista: ")
            if resposta != "":
                return


def informar_tempo(segundos, rotulo="Tempo da consulta"):
    """
    Exibe o custo da consulta -- item 7 das estatísticas obrigatórias (3.9).

    Mostrar o tempo a cada consulta, e não só no relatório, é o que permite ao
    usuário perceber na prática a diferença de custo entre uma busca exata
    (O(1) no hash) e uma busca por sequência (O(n) sobre todo o corpus).
    """
    print(f"\n{rotulo}: {formatar_duracao(segundos)}")


# ==========================================================================
#  PARTE I - AUTOCOMPLETE COM TRIE
# ==========================================================================

def carregar_lexico(caminho):
    """
    Lê o arquivo de palavras, ignorando comentários e linhas em branco.

    Se o arquivo não existir, cai nas palavras de exemplo do enunciado, de modo
    que a Parte I roda mesmo em uma cópia do projeto sem o corpus baixado.
    """
    arquivo = Path(caminho)
    if not arquivo.exists():
        print(f"[aviso] '{arquivo.name}' não encontrado; usando as palavras de exemplo.")
        print("        Para gerar o léxico completo: python gerar_lexico.py")
        return list(PALAVRAS_EXEMPLO)

    palavras = []
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#"):
            palavras.append(linha)
    return palavras or list(PALAVRAS_EXEMPLO)


def autocomplete_buscar(trie):
    """
    Opção 1: informa se a palavra completa existe (seção 2.3, item 2).

    O laço mantém a consulta ativa: depois de cada resposta o programa pergunta
    a próxima palavra, e só volta ao menu quando o usuário responde vazio. São
    as "sucessivas consultas" do item 4 sem obrigar a reescolher a opção.
    """
    while True:
        palavra = perguntar("Digite a palavra (Enter volta ao menu): ")
        if not palavra:
            return

        with Cronometro() as relogio:
            existe = trie.buscar(palavra)

        if existe:
            formas = sorted(trie.formas_de(palavra))
            print(f"\nA palavra '{palavra}' EXISTE na Trie.")
            if formas != [palavra]:
                print(f"Grafias registradas: {', '.join(formas)}")
        else:
            print(f"\nA palavra '{palavra}' NÃO está na Trie.")
            sugestoes = trie.buscar_prefixo(palavra, limite=5)
            if sugestoes:
                print(f"Começam assim: {', '.join(sugestoes)}")
            # Fora do cronômetro: a busca aproximada é um serviço a mais,
            # e não o custo O(m) da busca exata que o enunciado pede.
            parecidas = [p for p, distancia, _ in trie.buscar_aproximado(palavra)
                         if distancia > 0]
            if parecidas:
                print(f"Você quis dizer: {', '.join(parecidas)}?")
        informar_tempo(relogio.decorrido)


def autocomplete_prefixo(trie):
    """Opção 2: todas as palavras que começam com o prefixo (item 3)."""
    while True:
        prefixo = perguntar("Digite o prefixo (Enter volta ao menu): ")
        if not prefixo:
            return

        with Cronometro() as relogio:
            encontradas = trie.buscar_prefixo(prefixo)

        if not encontradas:
            print(f"\nNenhuma palavra começa com '{prefixo}'.")
        else:
            print("\nPalavras encontradas:")
            exibir_em_paginas(encontradas, lambda palavra: print(f"  {palavra}"),
                              PALAVRAS_POR_PAGINA, "palavras")
        informar_tempo(relogio.decorrido)


def autocomplete_inserir(trie):
    """Opção 3: inserção de novas palavras durante a execução (item 5)."""
    while True:
        palavra = perguntar("Digite a nova palavra (Enter volta ao menu): ")
        if not palavra:
            return

        with Cronometro() as relogio:
            nova = trie.inserir(palavra)

        if nova:
            print(f"\n'{palavra}' inserida. Total agora: {len(trie):,} palavras.")
        else:
            print(f"\n'{palavra}' já estava cadastrada.")
        informar_tempo(relogio.decorrido, "Tempo da inserção")


def executar_parte1(caminho_lexico):
    """Menu do sistema de autocomplete (seções 2.2 a 2.4 do enunciado)."""
    palavras = carregar_lexico(caminho_lexico)

    trie = Trie()
    with Cronometro() as relogio:
        for palavra in palavras:
            trie.inserir(palavra)
    tempo_construcao = relogio.decorrido

    print(f"\nTrie construída em {formatar_duracao(tempo_construcao)} "
          f"({trie.total_nos():,} nós, altura {trie.altura()}).")

    while True:
        cabecalho("AUTOCOMPLETE COM TRIE")
        print(f"Palavras cadastradas: {len(trie):,}")
        print()
        print("1 - Buscar palavra")
        print("2 - Buscar por prefixo")
        print("3 - Inserir nova palavra")
        print("4 - Sair")
        print()

        opcao = perguntar("Escolha uma opção: ")
        if opcao is None or opcao == "4":
            print("\nEncerrando o autocomplete.")
            return

        if opcao == "1":
            autocomplete_buscar(trie)
        elif opcao == "2":
            autocomplete_prefixo(trie)
        elif opcao == "3":
            autocomplete_inserir(trie)
        else:
            print("\nOpção inválida.")


# ==========================================================================
#  PARTE II - MECANISMO DE BUSCA EM DOCUMENTOS
# ==========================================================================

def mostrar_progresso(nome, posicao, total):
    """Callback de progresso da indexação."""
    print(f"  [{posicao:>2}/{total}] {nome}")


def exibir_busca_palavra(mecanismo):
    """
    Consulta por palavra exata (seção 3.7.1), em laço.

    Depois de cada resposta o programa pede a próxima palavra; o Enter vazio
    volta ao menu. Assim dá para comparar consultas seguidas -- "algoritmo",
    depois "algoritmos" -- sem reescolher a opção a cada vez.
    """
    while True:
        palavra = perguntar("Digite a palavra (Enter volta ao menu): ")
        if not palavra:
            return
        _mostrar_busca_palavra(mecanismo, palavra)


def _mostrar_busca_palavra(mecanismo, palavra):
    """Executa uma consulta por palavra e imprime o resultado."""
    resposta = mecanismo.buscar_palavra(palavra)
    documentos = resposta["documentos"]
    termos = resposta["termos"]

    if resposta["ignorados"]:
        print(f"\n  Ignoradas (stopwords): {', '.join(resposta['ignorados'])}")

    if not documentos:
        print(f"\n'{palavra}' não foi encontrada em nenhum documento.")
        mostrar_correcao(resposta)
        informar_tempo(resposta["tempo"])
        return

    if len(termos) > 1:
        print("\nTermos da consulta:")
        for termo in termos:
            print(f"  {termo['termo']:<20} radical '{termo['radical']}' "
                  f"-> {termo['documentos']} arquivo(s)")
        print(f"\nArquivos com todos os termos: {len(resposta['todos'])} "
              f"(com algum deles: {len(documentos)})")
    else:
        print(f"\nEncontrada em {len(documentos)} arquivo(s):")

    for documento, pontuacao in documentos:
        frequencia = resposta["frequencias"][documento]
        marca = ""
        if len(termos) > 1:
            marca = f"   [{resposta['cobertura'][documento]}/{len(termos)} termos]"
        print(f"  - {documento:<42} {frequencia:>4} ocorrência(s)   "
              f"BM25 {pontuacao:.3f}{marca}")

    # Mostra o ganho do stemming quando ele existe: é a demonstração concreta
    # de por que o item opcional da seção 3.3 foi implementado.
    if len(termos) == 1:
        exatos = termos[0]["exatos"]
        if exatos and exatos < len(documentos):
            print(f"\n  Sem stemming a forma exata '{resposta['termo']}' apareceria em "
                  f"{exatos} arquivo(s).")
            print(f"  O radical '{resposta['radical']}' (RSLP) alcança {len(documentos)}, "
                  f"reunindo as variantes da palavra.")

    mostrar_correcao(resposta)
    informar_tempo(resposta["tempo"])


def mostrar_correcao(resposta):
    """
    O "você quis dizer?": sugestões por distância de edição para os termos que
    não levaram a documento nenhum, buscadas na Trie do vocabulário.
    """
    for termo, sugestoes in resposta["aproximadas"].items():
        if sugestoes:
            lista = ", ".join(
                f"{palavra} ({distancia} {'edições' if distancia > 1 else 'edição'})"
                for palavra, distancia, _peso in sugestoes[:3])
            print(f"\n  Nada para '{termo}'. Parecidas: {lista}")
    if resposta["correcao"]:
        print(f"  Você quis dizer: {resposta['correcao']}?")


def exibir_busca_prefixo(mecanismo):
    """
    Consulta por prefixo (seção 3.7.2): a Trie recupera os termos do
    vocabulário e, para cada um, o índice invertido informa os documentos em
    que ele aparece -- a integração "Trie -> termos; índice/hash -> documentos"
    pedida no enunciado.

    Em laço, como as demais consultas: o Enter vazio volta ao menu.
    """
    while True:
        prefixo = perguntar("Digite o prefixo (Enter volta ao menu): ")
        if not prefixo:
            return
        _mostrar_busca_prefixo(mecanismo, prefixo)


def _mostrar_busca_prefixo(mecanismo, prefixo):
    """Executa uma consulta por prefixo e imprime o resultado."""
    resposta = mecanismo.buscar_prefixo(prefixo, limite=None)
    termos = resposta["termos"]

    if not termos:
        print(f"\nNenhum termo do vocabulário começa com '{prefixo}'.")
        informar_tempo(resposta["tempo"])
        return

    def exibir_termo(termo):
        documentos = resposta["por_termo"][termo]
        print(f"  {termo:<26} -> {len(documentos):>2} documento(s)")
        # Os nomes quebram em linhas de até 72 colunas, sem partir nenhum nome.
        for linha in textwrap.wrap(", ".join(documentos), width=66,
                                   break_long_words=False, break_on_hyphens=False):
            print(f"      {linha}")

    print("\nPalavras encontradas:")
    exibir_em_paginas(termos, exibir_termo, TERMOS_POR_PAGINA, "termos")

    # A lista acima é a alfabética que o enunciado pede. Esta é a que um
    # autocomplete usaria: as mais frequentes no corpus primeiro, recuperadas
    # pela busca best-first da Trie, sem varrer a subárvore do prefixo.
    if resposta["sugestoes"]:
        print("\nMais relevantes (por frequência no corpus):")
        for posicao, (palavra, ocorrencias) in enumerate(resposta["sugestoes"][:5], 1):
            print(f"  {posicao}. {palavra:<26} {ocorrencias:>5} ocorrência(s)")

    ranking = resposta["ranking"]
    print(f"\nDocumentos que contêm algum desses termos: {len(resposta['documentos'])}")
    if len(ranking) > 8:
        print("Os 8 mais relevantes pelo BM25:")
    for documento, pontuacao in ranking[:8]:
        print(f"  - {documento:<42} BM25 {pontuacao:.3f}")

    informar_tempo(resposta["tempo"])


def exibir_busca_sequencia(mecanismo):
    """
    Consulta por sequência de caracteres com KMP (seção 3.7.3, bônus), em laço:
    o Enter vazio volta ao menu.
    """
    while True:
        sequencia = perguntar("Digite a sequência (Enter volta ao menu): ")
        if not sequencia:
            return
        _mostrar_busca_sequencia(mecanismo, sequencia)


def _mostrar_busca_sequencia(mecanismo, sequencia):
    """Executa uma busca por sequência e imprime o resultado."""
    resposta = mecanismo.buscar_sequencia(sequencia)
    resultados = resposta["resultados"]

    if not resultados:
        print(f"\nA sequência '{sequencia}' não aparece em nenhum documento.")
    else:
        print(f"\n{resposta['total_ocorrencias']} ocorrência(s) em "
              f"{len(resultados)} arquivo(s):")
        for item in resultados:
            print(f"\n  {item['documento']} ({item['ocorrencias']} ocorrência(s))")
            for trecho in item["contextos"]:
                print(f"      {trecho}")

    print(f"\n  Comparações de caractere feitas pelo KMP: {resposta['comparacoes']:,}")
    informar_tempo(resposta["tempo"])


def exibir_documentos(mecanismo):
    """Opção 4 do menu: lista os arquivos indexados."""
    linhas = mecanismo.resumo_documentos()
    if not linhas:
        print("\nNenhum documento indexado.")
        return

    secao(f"DOCUMENTOS INDEXADOS ({len(linhas)})")
    print(f"  {'arquivo':<44}{'KB':>8}{'tokens':>10}")
    for linha in linhas:
        print(f"  {linha['documento']:<44}"
              f"{linha['bytes'] / 1024:>8.1f}"
              f"{linha['tokens']:>10,}")


def exibir_estatisticas(mecanismo):
    """Opção 5 do menu: as sete métricas obrigatórias da seção 3.9."""
    e = mecanismo.estatisticas

    secao("ESTATÍSTICAS DO SISTEMA")
    print(f"  Documentos processados              : {e.documentos:,}")
    print(f"  Palavras após a tokenização         : {e.total_palavras_brutas:,}")
    print(f"  Palavras após remover stopwords     : {e.total_palavras:,} "
          f"(redução de {e.taxa_reducao_stopwords() * 100:.1f}%)")
    print(f"  Termos distintos (vocabulário)      : {e.termos_distintos:,}")
    print(f"  Palavras armazenadas na Trie        : {e.palavras_na_trie:,}")
    print(f"  Radicais no índice invertido        : {mecanismo.indice.total_termos():,}")
    print(f"  Postagens (pares termo-documento)   : {e.postagens:,}")

    secao("MEMÓRIA DAS ESTRUTURAS")
    print(f"  Nós na Trie tradicional             : {e.nos_na_trie:,}")
    print(f"  Nós na Trie comprimida (PATRICIA)   : {e.nos_na_trie_comprimida:,}")
    print(f"  Economia da compressão              : "
          f"{e.economia_trie_comprimida() * 100:.1f}%")

    secao("TEMPOS DE CONSTRUÇÃO")
    print(f"  Leitura dos arquivos                : {formatar_duracao(e.tempo_leitura)}")
    print(f"  Pré-processamento                   : {formatar_duracao(e.tempo_preprocessamento)}")
    print(f"  Construção da Trie                  : {formatar_duracao(e.tempo_trie)}")
    print(f"  Construção do índice invertido      : {formatar_duracao(e.tempo_indice)}")
    print(f"  Total                               : {formatar_duracao(e.tempo_total_construcao())}")

    secao("CONFIGURAÇÃO DO PRÉ-PROCESSAMENTO")
    for chave, valor in mecanismo.preprocessador.descrever().items():
        print(f"  {chave:<36}: {valor}")

    if e.consultas:
        secao(f"CONSULTAS REALIZADAS ({len(e.consultas)})")
        print(f"  {'tipo':<12}{'qtd':>6}{'tempo total':>16}{'tempo médio':>16}")
        for tipo, (quantidade, total, media) in sorted(e.resumo_por_tipo().items()):
            print(f"  {tipo:<12}{quantidade:>6}"
                  f"{formatar_duracao(total):>16}{formatar_duracao(media):>16}")

        print("\n  Últimas consultas:")
        for tipo, texto, resultados, segundos in e.consultas[-5:]:
            print(f"    {tipo:<10} '{texto[:26]:<26}' "
                  f"{resultados:>4} resultado(s)  {formatar_duracao(segundos)}")
    else:
        secao("CONSULTAS REALIZADAS")
        print("  Nenhuma consulta feita ainda nesta sessão.")


def executar_parte2(pasta, usar_stemming):
    """Menu do mecanismo de busca em documentos (seções 3.7 e 3.8)."""
    cabecalho("INDEXANDO DOCUMENTOS")
    print(f"Pasta: {Path(pasta).resolve()}\n")

    mecanismo = MecanismoBusca(pasta, usar_stemming=usar_stemming)
    total = mecanismo.construir(ao_progredir=mostrar_progresso)

    if total == 0:
        print(f"\nNenhum arquivo .txt encontrado em '{pasta}/'.")
        print("Para baixar o corpus de exemplo: python preparar_corpus.py")
        return

    e = mecanismo.estatisticas
    print(f"\nIndexação concluída em {formatar_duracao(e.tempo_total_construcao())}.")

    while True:
        cabecalho("SISTEMA DE BUSCA EM DOCUMENTOS")
        print(f"Documentos processados: {e.documentos:,}")
        print(f"Total de palavras: {e.total_palavras_brutas:,}")
        print(f"Termos distintos: {e.termos_distintos:,}")
        print()
        print("1 - Buscar palavra")
        print("2 - Buscar por prefixo")
        print("3 - Buscar sequência nos documentos (KMP)")
        print("4 - Listar documentos")
        print("5 - Exibir estatísticas")
        print("6 - Sair")
        print()

        opcao = perguntar("Escolha uma opção: ")
        if opcao is None or opcao == "6":
            print("\nEncerrando o mecanismo de busca.")
            return

        if opcao == "1":
            exibir_busca_palavra(mecanismo)
        elif opcao == "2":
            exibir_busca_prefixo(mecanismo)
        elif opcao == "3":
            exibir_busca_sequencia(mecanismo)
        elif opcao == "4":
            exibir_documentos(mecanismo)
        elif opcao == "5":
            exibir_estatisticas(mecanismo)
        else:
            print("\nOpção inválida.")


# ==========================================================================
#  MENU PRINCIPAL
# ==========================================================================

def menu_principal(argumentos):
    """Escolhe entre as duas partes do trabalho."""
    while True:
        cabecalho("PROCESSAMENTO E BUSCA DE TEXTOS")
        print("Trabalho Prático A1 - Análise e Otimização de Sistemas")
        print()
        print("1 - Parte I  : Autocomplete com Trie")
        print("2 - Parte II : Mecanismo de busca em documentos")
        print("3 - Sair")
        print()

        opcao = perguntar("Escolha uma opção: ")
        if opcao is None or opcao == "3":
            print("\nAté logo.")
            return

        if opcao == "1":
            executar_parte1(argumentos.lexico)
        elif opcao == "2":
            executar_parte2(argumentos.pasta, not argumentos.sem_stemming)
        else:
            print("\nOpção inválida.")


def analisar_argumentos():
    analisador = argparse.ArgumentParser(
        description="Trabalho Prático A1 - Processamento e Busca de Textos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    analisador.add_argument(
        "--parte", choices=["1", "2"],
        help="vai direto para a Parte I (autocomplete) ou II (busca em documentos)",
    )
    analisador.add_argument(
        "--pasta", default=None,
        help="pasta com os arquivos .txt (padrão: a pasta 'documentos' ao lado do main.py)",
    )
    analisador.add_argument(
        "--lexico", default=None,
        help="arquivo de palavras da Parte I (padrão: 'palavras.txt' ao lado do main.py)",
    )
    analisador.add_argument(
        "--sem-stemming", action="store_true",
        help="desliga o stemmer RSLP, para comparar o efeito da normalização",
    )

    argumentos = analisador.parse_args()

    # Os padrões seguem a pasta do main.py, e não o diretório de onde o comando
    # foi chamado: `python "C:\\...\\Trabalho A1\\main.py"` funciona de qualquer
    # lugar. Caminhos informados pelo usuário continuam relativos ao diretório
    # atual, como manda o costume de qualquer programa de linha de comando.
    if argumentos.pasta is None:
        argumentos.pasta = RAIZ / "documentos"
    if argumentos.lexico is None:
        argumentos.lexico = RAIZ / "palavras.txt"
    return argumentos


def main():
    configurar_saida()
    argumentos = analisar_argumentos()

    if argumentos.parte == "1":
        executar_parte1(argumentos.lexico)
    elif argumentos.parte == "2":
        executar_parte2(argumentos.pasta, not argumentos.sem_stemming)
    else:
        menu_principal(argumentos)
    return 0


if __name__ == "__main__":
    sys.exit(main())
