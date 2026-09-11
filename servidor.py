"""
servidor.py
-----------
Interface web para experimentar as duas partes do trabalho no navegador.

O terminal já expõe tudo pelo `main.py`; este módulo existe para outro tipo de
uso: ver a Trie responder enquanto se digita, comparar lado a lado o custo de
uma consulta indexada e o de uma varredura com KMP, e mostrar o sistema
funcionando para quem não vai abrir um terminal.

Nada muda no núcleo. O servidor apenas embrulha `MecanismoBusca` e `Trie` em
respostas JSON -- as mesmas chamadas que a linha de comando faz, os mesmos
tempos medidos pelo mesmo cronômetro.

Uso:
    python servidor.py                  sobe em http://localhost:8000 e abre o navegador
    python servidor.py --porta 9000     escolhe outra porta
    python servidor.py --pasta meus_txt usa outra pasta de documentos
    python servidor.py --sem-stemming   desliga o RSLP, para comparação
    python servidor.py --sem-navegador  não abre o navegador sozinho

Usa apenas `http.server` da biblioteca padrão: nenhum framework web, nenhuma
dependência para instalar, coerente com a restrição do enunciado.
"""

import argparse
import json
import mimetypes
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from estatisticas import Cronometro, formatar_duracao
from main import carregar_lexico, configurar_saida
from mecanismo import MecanismoBusca
from trie import Trie

__all__ = ["Aplicacao", "criar_servidor", "main"]

RAIZ_WEB = Path(__file__).parent / "web"

# Limites de resposta. Existem para a interface: devolver os milhares de termos
# que começam com "a" não ajudaria ninguém a ler a tela, e o custo de
# serializar isso em JSON esconderia justamente o tempo que se quer medir.
LIMITE_PREFIXO = 60
LIMITE_CONTEXTOS = 4

# Rotas que exigem o parâmetro `q`. Ficam reunidas aqui para que um caminho
# inexistente possa ser recusado como 404 antes de reclamar do parâmetro.
ROTAS_DE_CONSULTA = frozenset({
    "/api/parte1/prefixo",
    "/api/parte1/palavra",
    "/api/parte2/palavra",
    "/api/parte2/prefixo",
    "/api/parte2/sequencia",
})


# ==========================================================================
#  ESTADO COMPARTILHADO
# ==========================================================================

class Aplicacao:
    """
    Reúne as estruturas das duas partes, construídas uma única vez.

    O custo de indexar o corpus é pago na subida do servidor, não a cada
    consulta -- é exatamente essa a proposta do índice invertido, e repetir a
    construção por requisição inverteria o resultado de todas as medições.

    Cada requisição chega em uma thread própria, então a Trie da Parte I é
    protegida por um lock: consultar é leitura e roda em paralelo sem problema,
    mas inserir uma palavra nova altera a estrutura e precisa ser exclusivo.
    """

    def __init__(self, pasta="documentos", lexico="palavras.txt", usar_stemming=True):
        self.caminho_lexico = lexico
        self.pasta = pasta

        # --- Parte I: Trie do léxico, a mesma que `main.py --parte 1` monta ---
        palavras = carregar_lexico(lexico)
        self.trie = Trie()
        with Cronometro() as relogio:
            for palavra in palavras:
                self.trie.inserir(palavra)
        self.tempo_trie = relogio.decorrido
        self.trava = threading.Lock()

        # --- Parte II: mecanismo de busca sobre a pasta de documentos ---
        self.mecanismo = MecanismoBusca(pasta, usar_stemming=usar_stemming)
        self.documentos = self.mecanismo.construir()

    # ------------------------------------------------------------ estado

    def estado(self):
        """Números que a interface mostra no cabeçalho, antes de qualquer consulta."""
        e = self.mecanismo.estatisticas
        return {
            "parte1": {
                "lexico": Path(self.caminho_lexico).name,
                "palavras": len(self.trie),
                "nos": self.trie.total_nos(),
                "altura": self.trie.altura(),
                "tempo_construcao": self.tempo_trie,
            },
            "parte2": {
                "pasta": str(Path(self.pasta).resolve()),
                "documentos": e.documentos,
                "palavras": e.total_palavras,
                "palavras_brutas": e.total_palavras_brutas,
                "termos": e.termos_distintos,
                "radicais": self.mecanismo.indice.total_termos(),
                "postagens": e.postagens,
                "stemming": self.mecanismo.preprocessador.usar_stemming,
                "tempo_construcao": e.tempo_total_construcao(),
            },
        }

    # ------------------------------------------------------------ Parte I

    def autocompletar(self, prefixo, limite=LIMITE_PREFIXO):
        """
        Parte I, seção 2.3: as palavras do léxico que começam com o prefixo.

        A cronometragem cerca apenas as duas operações da Trie -- descer o
        prefixo e varrer a subárvore --, sem incluir a montagem do JSON.
        """
        with Cronometro() as relogio:
            palavras = self.trie.buscar_prefixo(prefixo, limite=limite)
            total = self.trie.contar_prefixo(prefixo)
        return {
            "prefixo": prefixo,
            "palavras": palavras,
            "total": total,
            "truncado": total > len(palavras),
            "tempo": relogio.decorrido,
        }

    def buscar_no_lexico(self, palavra):
        """Parte I, seção 2.3: a palavra existe no léxico? Custo O(m)."""
        with Cronometro() as relogio:
            existe = self.trie.buscar(palavra)
            formas = sorted(self.trie.formas_de(palavra))
            abaixo = self.trie.contar_prefixo(palavra)
        return {
            "palavra": palavra,
            "existe": existe,
            "formas": formas,
            "continuacoes": max(0, abaixo - (1 if existe else 0)),
            "tempo": relogio.decorrido,
        }

    def inserir_no_lexico(self, palavra):
        """
        Parte I, seção 2.4: insere uma palavra em tempo de execução.

        Vale só para a sessão do servidor; `palavras.txt` não é reescrito. Quem
        quiser gravar um léxico novo roda `python gerar_lexico.py`.
        """
        with self.trava:
            with Cronometro() as relogio:
                nova = self.trie.inserir(palavra)
            return {
                "palavra": palavra.strip(),
                "nova": nova,
                "palavras": len(self.trie),
                "nos": self.trie.total_nos(),
                "tempo": relogio.decorrido,
            }


# ==========================================================================
#  ROTAS
# ==========================================================================

class Manipulador(BaseHTTPRequestHandler):
    """
    Atende a duas coisas: os arquivos estáticos de `web/` e as rotas `/api/`.

    As rotas devolvem exatamente os dicionários que `MecanismoBusca` já produz
    para o terminal. A interface é uma segunda apresentação dos mesmos dados,
    não uma segunda implementação.
    """

    protocol_version = "HTTP/1.1"
    server_version = "BuscaTextos/1.0"
    aplicacao = None
    silencioso = False

    # ------------------------------------------------------------- resposta

    def _enviar(self, codigo, corpo, tipo):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _json(self, dados, codigo=200):
        # ensure_ascii=False para não transformar "computação" em escapes \u.
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self._enviar(codigo, corpo, "application/json; charset=utf-8")

    def _erro(self, codigo, mensagem):
        self._json({"erro": mensagem}, codigo=codigo)

    def _arquivo(self, caminho_relativo):
        """
        Serve um arquivo de `web/`, recusando qualquer caminho que escape da
        pasta -- sem isso, um pedido por `../../palavras.txt` sairia do lugar
        previsto.
        """
        raiz = RAIZ_WEB.resolve()
        alvo = (raiz / caminho_relativo.lstrip("/")).resolve()

        if raiz != alvo and raiz not in alvo.parents:
            return self._erro(403, "caminho fora da pasta web/")
        if not alvo.is_file():
            return self._erro(404, f"arquivo nao encontrado: {caminho_relativo}")

        tipo, _ = mimetypes.guess_type(alvo.name)
        tipo = tipo or "application/octet-stream"
        if tipo.startswith("text/") or tipo.endswith("javascript"):
            tipo += "; charset=utf-8"
        self._enviar(200, alvo.read_bytes(), tipo)

    # -------------------------------------------------------------- verbos

    def do_GET(self):
        endereco = urlparse(self.path)
        rota = unquote(endereco.path)
        parametros = parse_qs(endereco.query)

        if rota.startswith("/api/"):
            return self._api(rota, parametros)
        if rota == "/":
            return self._arquivo("index.html")
        return self._arquivo(rota)

    def do_POST(self):
        rota = unquote(urlparse(self.path).path)
        if rota != "/api/parte1/inserir":
            return self._erro(404, f"rota desconhecida: {rota}")

        try:
            tamanho = int(self.headers.get("Content-Length", 0))
            corpo = json.loads(self.rfile.read(tamanho) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._erro(400, "corpo da requisicao nao e JSON valido")

        palavra = str(corpo.get("palavra", "")).strip()
        if not palavra:
            return self._erro(400, "informe a palavra a inserir")
        self._json(self.aplicacao.inserir_no_lexico(palavra))

    # ----------------------------------------------------------------- api

    def _api(self, rota, parametros):
        aplicacao = self.aplicacao
        consulta = (parametros.get("q") or [""])[0].strip()
        limite = self._inteiro(parametros.get("limite"), LIMITE_PREFIXO)

        if rota == "/api/estado":
            return self._json(aplicacao.estado())

        if rota == "/api/estatisticas":
            return self._json(resumir_estatisticas(aplicacao.mecanismo))

        if rota == "/api/parte2/documentos":
            return self._json({"documentos": aplicacao.mecanismo.resumo_documentos()})

        if rota == "/api/parte2/documento":
            nome = (parametros.get("nome") or [""])[0]
            texto = aplicacao.mecanismo.conteudo.get(nome)
            if texto is None:
                return self._erro(404, f"documento nao indexado: {nome}")
            return self._json({"documento": nome, "texto": texto})

        # Daqui para baixo, todas as rotas dependem de uma consulta não vazia.
        # A rota é conferida antes: um caminho inexistente é 404, não 400 por
        # falta de parâmetro em algo que nem existe.
        if rota not in ROTAS_DE_CONSULTA:
            return self._erro(404, f"rota desconhecida: {rota}")
        if not consulta:
            return self._erro(400, "informe a consulta no parametro 'q'")

        if rota == "/api/parte1/prefixo":
            return self._json(aplicacao.autocompletar(consulta, limite=limite))

        if rota == "/api/parte1/palavra":
            return self._json(aplicacao.buscar_no_lexico(consulta))

        if rota == "/api/parte2/palavra":
            return self._json(aplicacao.mecanismo.buscar_palavra(consulta))

        if rota == "/api/parte2/prefixo":
            return self._json(aplicacao.mecanismo.buscar_prefixo(consulta, limite=limite))

        if rota == "/api/parte2/sequencia":
            return self._json(aplicacao.mecanismo.buscar_sequencia(
                consulta, max_contextos=LIMITE_CONTEXTOS))

        return self._erro(404, f"rota desconhecida: {rota}")

    @staticmethod
    def _inteiro(valores, padrao):
        """Lê um inteiro da query string, caindo no padrão quando vier lixo."""
        try:
            return max(1, min(500, int(valores[0])))
        except (TypeError, ValueError, IndexError):
            return padrao

    # ------------------------------------------------------------------ log

    def log_message(self, formato, *argumentos):
        """
        Uma linha por requisição, sem o timestamp verboso do padrão.

        As consultas de autocomplete chegam a cada tecla digitada; o log
        original do `BaseHTTPRequestHandler` encheria o terminal em segundos.
        """
        if not self.silencioso:
            sys.stderr.write(f"  {formato % argumentos}\n")


def resumir_estatisticas(mecanismo):
    """
    As mesmas sete métricas obrigatórias da seção 3.9 que o terminal imprime,
    em JSON e com os tempos já formatados para exibição.
    """
    e = mecanismo.estatisticas
    return {
        "corpus": {
            "documentos": e.documentos,
            "palavras": e.total_palavras,
            "palavras_brutas": e.total_palavras_brutas,
            "reducao_stopwords": e.taxa_reducao_stopwords(),
            "termos": e.termos_distintos,
            "palavras_na_trie": e.palavras_na_trie,
            "radicais": mecanismo.indice.total_termos(),
            "postagens": e.postagens,
        },
        "memoria": {
            "nos_trie": e.nos_na_trie,
            "nos_trie_comprimida": e.nos_na_trie_comprimida,
            "economia": e.economia_trie_comprimida(),
        },
        "construcao": {
            "leitura": formatar_duracao(e.tempo_leitura),
            "preprocessamento": formatar_duracao(e.tempo_preprocessamento),
            "trie": formatar_duracao(e.tempo_trie),
            "indice": formatar_duracao(e.tempo_indice),
            "total": formatar_duracao(e.tempo_total_construcao()),
        },
        "preprocessamento": {
            str(chave): str(valor)
            for chave, valor in mecanismo.preprocessador.descrever().items()
        },
        "consultas": {
            "total": len(e.consultas),
            "por_tipo": {
                tipo: {
                    "quantidade": quantidade,
                    "total": formatar_duracao(total),
                    "media": formatar_duracao(media),
                }
                for tipo, (quantidade, total, media) in sorted(e.resumo_por_tipo().items())
            },
            "ultimas": [
                {"tipo": tipo, "texto": texto, "resultados": resultados,
                 "tempo": formatar_duracao(segundos)}
                for tipo, texto, resultados, segundos in e.consultas[-8:]
            ],
        },
        "hash": mecanismo.indice.espelhar_em_tabela_hash().estatisticas(),
    }


# ==========================================================================
#  INICIALIZAÇÃO
# ==========================================================================

def criar_servidor(aplicacao, porta=8000, silencioso=False):
    """Monta o servidor com a aplicação já construída presa ao manipulador."""
    manipulador = type("ManipuladorLigado", (Manipulador,), {
        "aplicacao": aplicacao,
        "silencioso": silencioso,
    })
    servidor = ThreadingHTTPServer(("127.0.0.1", porta), manipulador)
    servidor.daemon_threads = True
    return servidor


def analisar_argumentos():
    analisador = argparse.ArgumentParser(
        description="Interface web do trabalho de processamento e busca de textos.",
    )
    analisador.add_argument("--porta", type=int, default=8000,
                            help="porta do servidor (padrão: 8000)")
    analisador.add_argument("--pasta", default="documentos",
                            help="pasta com os arquivos .txt (padrão: documentos)")
    analisador.add_argument("--lexico", default="palavras.txt",
                            help="arquivo de palavras da Parte I (padrão: palavras.txt)")
    analisador.add_argument("--sem-stemming", action="store_true",
                            help="desliga o stemmer RSLP, para comparação")
    analisador.add_argument("--sem-navegador", action="store_true",
                            help="não abre o navegador automaticamente")
    analisador.add_argument("--silencioso", action="store_true",
                            help="não registra as requisições no terminal")
    return analisador.parse_args()


def main():
    configurar_saida()
    argumentos = analisar_argumentos()

    if not RAIZ_WEB.is_dir():
        print(f"[erro] pasta '{RAIZ_WEB.name}/' não encontrada ao lado de servidor.py.")
        return 1

    print("Construindo as estruturas...")
    aplicacao = Aplicacao(
        pasta=argumentos.pasta,
        lexico=argumentos.lexico,
        usar_stemming=not argumentos.sem_stemming,
    )

    estado = aplicacao.estado()
    print(f"  Parte I  : {estado['parte1']['palavras']:,} palavras na Trie "
          f"({formatar_duracao(estado['parte1']['tempo_construcao'])})")
    if aplicacao.documentos:
        print(f"  Parte II : {estado['parte2']['documentos']} documentos, "
              f"{estado['parte2']['termos']:,} termos distintos "
              f"({formatar_duracao(estado['parte2']['tempo_construcao'])})")
    else:
        print(f"  Parte II : nenhum .txt em '{argumentos.pasta}/'. "
              f"A busca em documentos fica vazia.")

    endereco = f"http://localhost:{argumentos.porta}"
    try:
        servidor = criar_servidor(aplicacao, argumentos.porta, argumentos.silencioso)
    except OSError as falha:
        print(f"\n[erro] não foi possível ocupar a porta {argumentos.porta}: {falha}")
        print("       Escolha outra com --porta 8001.")
        return 1

    print(f"\nServidor no ar em {endereco}")
    print("Ctrl+C encerra.\n")

    if not argumentos.sem_navegador:
        threading.Timer(0.5, lambda: webbrowser.open(endereco)).start()

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando o servidor.")
    finally:
        servidor.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
