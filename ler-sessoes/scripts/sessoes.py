"""CLI que resume sessoes de agentes locais para outro agente ler."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path

_DIRETORIO = Path(__file__).resolve().parent
if str(_DIRETORIO) not in sys.path:
    sys.path.insert(0, str(_DIRETORIO))

import _codex
from _modelo import Evento, Sessao

# Cada leitor expoe FERRAMENTA, RAIZ_PADRAO, ler_sessoes(raiz, desde) e carregar_eventos(sessao).
LEITORES = {leitor.FERRAMENTA: leitor for leitor in (_codex,)}


def _erro(mensagem: str):
    sys.stderr.write("sessoes: %s\n" % mensagem)
    raise SystemExit(2)


def _preparar_saida() -> None:
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", errors="replace")


def _data(texto: str) -> date:
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError:
        _erro("data invalida (use AAAA-MM-DD): %s" % texto)


def _carregar(ferramenta: str | None, raiz: str | None, desde: date | None = None) -> list[Sessao]:
    if ferramenta is not None and ferramenta not in LEITORES:
        _erro("ferramenta sem leitor: %s" % ferramenta)
    pasta_dada = Path(raiz).expanduser() if raiz else None
    if pasta_dada is not None and not pasta_dada.exists():
        _erro("raiz inexistente: %s" % pasta_dada)
    sessoes: list[Sessao] = []
    for nome, leitor in LEITORES.items():
        if ferramenta is not None and nome != ferramenta:
            continue
        pasta = pasta_dada or leitor.RAIZ_PADRAO
        if pasta.exists():
            sessoes.extend(leitor.ler_sessoes(pasta, desde=desde))
    return sessoes


def _carregar_eventos(sessao: Sessao) -> None:
    LEITORES[sessao.ferramenta].carregar_eventos(sessao)


def _curto(identificador: str) -> str:
    return identificador[:8]


def _hora(instante: datetime | None) -> str:
    if instante is None:
        return ""
    return instante.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _dur(segundos: float) -> str:
    total = max(0, int(segundos))
    if total < 60:
        return "%ds" % total
    if total < 3600:
        return "%dm%02ds" % (total // 60, total % 60)
    return "%dh%02dm" % (total // 3600, total % 3600 // 60)


def _minuto(instante: datetime | None, inicio: datetime | None) -> str | None:
    if instante is None or inicio is None:
        return None
    return "%dm" % max(0, int((instante - inicio).total_seconds() // 60))


def _modelo_esforco(sessao: Sessao) -> str:
    return "/".join(x for x in (sessao.modelo, sessao.esforco) if x)


def _tokens(sessao: Sessao) -> str:
    if sessao.tokens_entrada is None and sessao.tokens_saida is None:
        return "-"
    entrada = str(sessao.tokens_entrada) if sessao.tokens_entrada is not None else "-"
    saida = str(sessao.tokens_saida) if sessao.tokens_saida is not None else "-"
    return "%s/%s" % (entrada, saida)


def _duracao(sessao: Sessao) -> str:
    if sessao.duracao_s is None or sessao.duracao_s < 1:
        return "-"
    return _dur(sessao.duracao_s)


def _resolver(id_ou_prefixo: str, raiz: str | None) -> Sessao:
    prefixo = id_ou_prefixo.lower()
    achadas = [s for s in _carregar(None, raiz) if s.id.lower().startswith(prefixo)]
    if not achadas:
        _erro("sessao nao encontrada: %s" % id_ou_prefixo)
    if len(achadas) > 1:
        sys.stderr.write("sessoes: prefixo ambiguo: %s\n" % id_ou_prefixo)
        for sessao in achadas:
            sys.stderr.write("  %s %s %s\n" % (sessao.id[:12], sessao.ferramenta, _modelo_esforco(sessao) or "-"))
        raise SystemExit(2)
    return achadas[0]


def _relativizar(texto: str, cwd: str | None) -> str:
    if not cwd or not texto:
        return texto
    partes = re.split(r"[\\/]+", cwd.strip())
    partes = [p for p in partes if p]
    if not partes:
        return texto
    padrao = re.compile(r"[\\/]+".join(re.escape(p) for p in partes) + r"[\\/]+", re.IGNORECASE)
    return padrao.sub("", texto)


def _linha_evento(evento: Evento, sessao: Sessao, largura: int) -> str:
    partes = [str(evento.n)]
    minuto = _minuto(evento.instante, sessao.inicio)
    if minuto:
        partes.append(minuto)
    if evento.duracao_s is not None and evento.duracao_s >= 1:
        partes.append(_dur(evento.duracao_s))
    if evento.exit is not None and evento.exit != 0:
        partes.append("!%d" % evento.exit)
    partes.append(evento.tipo)
    texto = _uma_linha(_relativizar(evento.texto, sessao.cwd))
    if not texto:
        return " ".join(partes)
    if largura and largura > 0 and len(texto) > largura:
        texto = texto[: largura - 1] + "…"
    partes.append(texto)
    return " ".join(partes)


def _uma_linha(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


def _cortar_bytes(texto: str, max_bytes: int) -> str:
    dados = texto.encode("utf-8")
    if max_bytes <= 0 or len(dados) <= max_bytes:
        return texto
    metade = max(1, max_bytes // 2)
    cabeca = _aparar_inicio(dados[:metade])
    rabo = _aparar_fim(dados[-metade:])
    cortados = len(dados) - len(cabeca) - len(rabo)
    aviso = "\n[... %d bytes cortados do meio ...]\n" % cortados
    return cabeca.decode("utf-8", errors="replace") + aviso + rabo.decode("utf-8", errors="replace")


def _aparar_inicio(pedaco: bytes) -> bytes:
    while pedaco and (pedaco[-1] & 0xC0) == 0x80:
        pedaco = pedaco[:-1]
    if pedaco and (pedaco[-1] & 0xC0) == 0xC0:
        pedaco = pedaco[:-1]
    return pedaco


def _aparar_fim(pedaco: bytes) -> bytes:
    while pedaco and (pedaco[0] & 0xC0) == 0x80:
        pedaco = pedaco[1:]
    return pedaco


def _cabecalho(sessao: Sessao) -> str:
    partes = ["#", _curto(sessao.id), sessao.ferramenta]
    modelo = _modelo_esforco(sessao)
    if modelo:
        partes.append(modelo)
    hora = _hora(sessao.inicio)
    if hora:
        partes.append(hora)
    if sessao.duracao_s is not None and sessao.duracao_s >= 1:
        partes.append(_dur(sessao.duracao_s))
    partes.append(sessao.termino)
    if sessao.nome:
        partes.append(sessao.nome)
    if sessao.cwd:
        partes.append("cwd=" + sessao.cwd)
    return " ".join(partes)


def _passa(evento: Evento, tipos: set[str] | None, args, padrao: re.Pattern | None) -> bool:
    if tipos is not None and evento.tipo not in tipos:
        return False
    if args.falhas and (evento.exit is None or evento.exit == 0):
        return False
    if padrao is not None and not padrao.search(evento.detalhe):
        return False
    if args.de is not None and evento.n < args.de:
        return False
    if args.ate is not None and evento.n > args.ate:
        return False
    return True


def cmd_lista(args) -> int:
    desde = _data(args.desde) if args.desde else None
    sessoes = _carregar(args.ferramenta, args.raiz, desde)
    sessoes.sort(key=lambda s: s.inicio.timestamp() if s.inicio else 0.0, reverse=True)
    cabecalho = ("id", "ferramenta", "modelo/esforço", "início", "duração", "tokens", "término", "pai", "nome")
    linhas = [_colunas_lista(s) for s in sessoes]
    larguras = []
    for indice, titulo in enumerate(cabecalho):
        largura = len(titulo)
        for linha in linhas:
            largura = max(largura, len(linha[indice]))
        larguras.append(largura)
    sys.stdout.write(_juntar(cabecalho, larguras) + "\n")
    for linha in linhas:
        sys.stdout.write(_juntar(linha, larguras) + "\n")
    return 0


def _colunas_lista(sessao: Sessao) -> tuple[str, ...]:
    return (
        _curto(sessao.id),
        sessao.ferramenta,
        _modelo_esforco(sessao) or "-",
        _hora(sessao.inicio) or "-",
        _duracao(sessao),
        _tokens(sessao),
        sessao.termino,
        _curto(sessao.pai) if sessao.pai else "-",
        sessao.nome or "-",
    )


def _juntar(colunas, larguras) -> str:
    return " ".join(valor.ljust(largura) for valor, largura in zip(colunas, larguras)).rstrip()


def cmd_linha(args) -> int:
    sessao = _resolver(args.id, args.raiz)
    _carregar_eventos(sessao)
    tipos = None
    if args.tipo:
        tipos = {t.strip() for t in args.tipo.split(",") if t.strip()}
        if not tipos:
            _erro("--tipo vazio")
    padrao = None
    if args.grep:
        try:
            padrao = re.compile(args.grep)
        except re.error as erro:
            _erro("regex invalida: %s" % erro)
    sys.stdout.write(_cabecalho(sessao) + "\n")
    for evento in sessao.eventos:
        if _passa(evento, tipos, args, padrao):
            sys.stdout.write(_linha_evento(evento, sessao, args.largura) + "\n")
    return 0


def cmd_mostra(args) -> int:
    sessao = _resolver(args.id, args.raiz)
    _carregar_eventos(sessao)
    escolhido = None
    for evento in sessao.eventos:
        if evento.n == args.n:
            escolhido = evento
            break
    if escolhido is None:
        _erro("evento %d inexistente em %s (total %d)" % (args.n, _curto(sessao.id), len(sessao.eventos)))
    cabecalho = "# %s evento %d %s %s" % (
        _curto(sessao.id),
        escolhido.n,
        escolhido.tipo,
        _hora(escolhido.instante),
    )
    sys.stdout.write(cabecalho.rstrip() + "\n")
    detalhe = _relativizar(escolhido.detalhe, sessao.cwd)
    sys.stdout.write(_cortar_bytes(detalhe, args.max_bytes) + "\n")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="sessoes.py",
        description="Resume sessoes de agentes locais para outro agente ler.",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    lista = sub.add_parser("lista", help="lista as sessoes")
    lista.add_argument("--ferramenta", help="so as sessoes deste leitor")
    lista.add_argument("--desde", help="inclui sessoes a partir de AAAA-MM-DD")
    lista.add_argument("--raiz", help="pasta dos logs")
    lista.set_defaults(fn=cmd_lista)

    linha = sub.add_parser("linha", help="mostra os eventos de uma sessao")
    linha.add_argument("id", help="id ou prefixo unico")
    linha.add_argument("--tipo", help="filtra por tipos separados por virgula")
    linha.add_argument("--falhas", action="store_true", help="so exit diferente de zero e erro de ferramenta")
    linha.add_argument("--grep", help="procura regex no conteudo completo")
    linha.add_argument("--de", type=int, help="primeiro n")
    linha.add_argument("--ate", type=int, help="ultimo n")
    linha.add_argument("--largura", type=int, default=160, help="limite de caracteres do texto")
    linha.add_argument("--raiz", help="pasta dos logs")
    linha.set_defaults(fn=cmd_linha)

    mostra = sub.add_parser("mostra", help="mostra um evento inteiro")
    mostra.add_argument("id", help="id ou prefixo unico")
    mostra.add_argument("n", type=int, help="numero do evento")
    mostra.add_argument("--max-bytes", type=int, default=4000, help="limite de bytes da saida")
    mostra.add_argument("--raiz", help="pasta dos logs")
    mostra.set_defaults(fn=cmd_mostra)

    args = parser.parse_args(argv)
    _preparar_saida()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
