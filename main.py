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
from pathlib import Path

from estatisticas import Cronometro, formatar_duracao
from mecanismo import MecanismoBusca
from trie import Trie

LARGURA = 60

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
            palavra = perguntar("Digite a palavra: ")
            if not palavra:
                continue
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
            informar_tempo(relogio.decorrido)

        elif opcao == "2":
            prefixo = perguntar("Digite o prefixo: ")
            if not prefixo:
                continue
            with Cronometro() as relogio:
                encontradas = trie.buscar_prefixo(prefixo, limite=40)
                total = trie.contar_prefixo(prefixo)

            if not encontradas:
                print(f"\nNenhuma palavra começa com '{prefixo}'.")
            else:
                print("\nPalavras encontradas:")
                for palavra in encontradas:
                    print(f"  {palavra}")
                if total > len(encontradas):
                    print(f"  ... e mais {total - len(encontradas)} "
                          f"(exibindo {len(encontradas)} de {total})")
            informar_tempo(relogio.decorrido)

        elif opcao == "3":
            palavra = perguntar("Digite a nova palavra: ")
            if not palavra:
                continue
            with Cronometro() as relogio:
                nova = trie.inserir(palavra)
            if nova:
                print(f"\n'{palavra}' inserida. Total agora: {len(trie):,} palavras.")
            else:
                print(f"\n'{palavra}' já estava cadastrada.")
            informar_tempo(relogio.decorrido, "Tempo da inserção")

        else:
            print("\nOpção inválida.")


# ==========================================================================
#  PARTE II - MECANISMO DE BUSCA EM DOCUMENTOS
# ==========================================================================

def mostrar_progresso(nome, posicao, total):
    """Callback de progresso da indexação."""
    print(f"  [{posicao:>2}/{total}] {nome}")


def exibir_busca_palavra(mecanismo):
    """Consulta por palavra exata (seção 3.7.1)."""
    palavra = perguntar("Digite a palavra: ")
    if not palavra:
        return

    resposta = mecanismo.buscar_palavra(palavra)
    documentos = resposta["documentos"]

    if not documentos:
        print(f"\n'{palavra}' não foi encontrada em nenhum documento.")
        informar_tempo(resposta["tempo"])
        return

    print(f"\nEncontrada em {len(documentos)} arquivo(s):")
    for documento, pontuacao in documentos:
        frequencia = resposta["frequencias"][documento]
        print(f"  - {documento:<42} {frequencia:>4} ocorrência(s)   BM25 {pontuacao:.3f}")

    # Mostra o ganho do stemming quando ele existe: é a demonstração concreta
    # de por que o item opcional da seção 3.3 foi implementado.
    exatos = len(resposta["exatos"])
    if exatos and exatos < len(documentos):
        print(f"\n  Sem stemming a forma exata '{resposta['termo']}' apareceria em "
              f"{exatos} arquivo(s).")
        print(f"  O radical '{resposta['radical']}' (RSLP) alcança {len(documentos)}, "
              f"reunindo as variantes da palavra.")

    informar_tempo(resposta["tempo"])


def exibir_busca_prefixo(mecanismo):
    """Consulta por prefixo: Trie seguida do índice invertido (seção 3.7.2)."""
    prefixo = perguntar("Digite o prefixo: ")
    if not prefixo:
        return

    resposta = mecanismo.buscar_prefixo(prefixo, limite=25)
    termos = resposta["termos"]

    if not termos:
        print(f"\nNenhum termo do vocabulário começa com '{prefixo}'.")
        informar_tempo(resposta["tempo"])
        return

    print("\nPalavras encontradas:")
    for termo in termos:
        documentos = resposta["por_termo"][termo]
        print(f"  {termo:<26} -> {len(documentos):>2} documento(s)")

    if resposta["truncado"]:
        print(f"  ... exibindo {len(termos)} de {resposta['total_disponivel']} termos")

    print(f"\nDocumentos que contêm algum desses termos: {len(resposta['documentos'])}")
    for documento, pontuacao in resposta["ranking"][:8]:
        print(f"  - {documento:<42} BM25 {pontuacao:.3f}")

    informar_tempo(resposta["tempo"])


def exibir_busca_sequencia(mecanismo):
    """Consulta por sequência de caracteres com KMP (seção 3.7.3, bônus)."""
    sequencia = perguntar("Digite a sequência: ")
    if not sequencia:
        return

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
    print(f"  Palavras após a tokenização         : {e.total_palavras:,}")
    print(f"  Palavras antes das stopwords        : {e.total_palavras_brutas:,} "
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
        print(f"Total de palavras: {e.total_palavras:,}")
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
        "--pasta", default="documentos",
        help="pasta com os arquivos .txt (padrão: documentos)",
    )
    analisador.add_argument(
        "--lexico", default="palavras.txt",
        help="arquivo de palavras da Parte I (padrão: palavras.txt)",
    )
    analisador.add_argument(
        "--sem-stemming", action="store_true",
        help="desliga o stemmer RSLP, para comparar o efeito da normalização",
    )
    return analisador.parse_args()


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
