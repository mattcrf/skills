"""Leitor somente leitura das sessoes gravadas pelo Codex."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import unquote

from _modelo import Evento, Sessao

FERRAMENTA = "codex"
RAIZ_PADRAO = Path.home() / ".codex" / "sessions"

_MAPA_TIPOS = {
    "UserMessage": "user",
    "AgentMessage": "msg",
    "Reasoning": "think",
    "CommandExecution": "cmd",
    "FileChange": "edit",
    "McpToolCall": "tool",
    "CollabAgentToolCall": "agent",
    "SubAgentActivity": "agent",
    "ContextCompaction": "compact",
}

_MARCAS_META = ('"session_meta"', '"turn_context"', '"token_count"', '"task_complete"')
_MARCAS_COMPLETO = ('"event_msg"', '"session_meta"', '"turn_context"')

_ID_NO_NOME = re.compile(
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$"
)

_CODIGOS_EDICAO = {"add": "+", "update": "~", "delete": "-"}


def ler_sessoes(raiz: Path, desde: date | None = None) -> list[Sessao]:
    sessoes: list[Sessao] = []
    for caminho in sorted(raiz.rglob("*.jsonl")):
        sessao = _ler_meta(caminho)
        if sessao is None:
            continue
        if desde is not None and sessao.inicio is not None:
            if sessao.inicio.astimezone().date() < desde:
                continue
        sessoes.append(sessao)
    return sorted(sessoes, key=lambda s: s.inicio.timestamp() if s.inicio else 0.0)


def carregar_eventos(sessao: Sessao) -> list[Evento]:
    eventos: list[Evento] = []
    if sessao.caminho is not None:
        try:
            for linha in _linhas(sessao.caminho):
                if not _interessa(linha, _MARCAS_COMPLETO):
                    continue
                registro = _registro(linha)
                if registro is None or registro.get("type") != "event_msg":
                    continue
                corpo = registro.get("payload")
                if not isinstance(corpo, dict) or corpo.get("type") != "item_completed":
                    continue
                item = corpo.get("item")
                if not isinstance(item, dict):
                    item = {}
                instante = _iso(registro.get("timestamp"))
                eventos.append(_evento(len(eventos) + 1, corpo, item, instante))
        except OSError:
            eventos = []
    sessao.eventos = eventos
    return eventos


def _ler_meta(caminho: Path) -> Sessao | None:
    sessao = Sessao(id=_id_do_nome(caminho), ferramenta=FERRAMENTA, caminho=caminho)
    tokens: tuple[int | None, int | None] | None = None
    primeiro: datetime | None = None
    ultimo: datetime | None = None
    achou_modelo = False
    achou_dados = False
    try:
        linhas = _linhas(caminho)
        for linha in linhas:
            if not _interessa(linha, _MARCAS_META):
                continue
            registro = _registro(linha)
            if registro is None:
                continue
            achou_dados = True
            instante = _iso(registro.get("timestamp"))
            if instante is not None:
                if primeiro is None:
                    primeiro = instante
                ultimo = instante
            tipo = registro.get("type")
            corpo = registro.get("payload")
            if not isinstance(corpo, dict):
                corpo = {}
            if tipo == "session_meta":
                _aplicar_meta(sessao, corpo)
            elif tipo == "turn_context":
                if not achou_modelo:
                    sessao.modelo = _texto(corpo.get("model"))
                    sessao.esforco = _texto(corpo.get("effort"))
                    achou_modelo = True
            elif tipo == "event_msg":
                sub = corpo.get("type")
                if sub == "token_count":
                    info = corpo.get("info")
                    total = info.get("total_token_usage") if isinstance(info, dict) else None
                    if isinstance(total, dict):
                        tokens = (
                            _inteiro(total.get("input_tokens")),
                            _inteiro(total.get("output_tokens")),
                        )
                elif sub == "task_complete":
                    sessao.termino = "fim"
    except OSError:
        return None
    if not achou_dados:
        return None
    if sessao.inicio is None:
        sessao.inicio = primeiro
    if sessao.inicio is not None and ultimo is not None:
        segundos = (ultimo - sessao.inicio).total_seconds()
        if segundos > 0:
            sessao.duracao_s = segundos
    if tokens is not None:
        sessao.tokens_entrada, sessao.tokens_saida = tokens
    return sessao


def _aplicar_meta(sessao: Sessao, corpo: dict) -> None:
    ident = _texto(corpo.get("id"))
    if ident:
        sessao.id = ident
    pai = _texto(corpo.get("parent_thread_id"))
    if pai:
        sessao.pai = pai
    nome = _texto(corpo.get("agent_path"))
    if nome:
        sessao.nome = nome
    cwd = _texto(corpo.get("cwd"))
    if cwd:
        sessao.cwd = cwd
    inicio = _iso(corpo.get("timestamp"))
    if inicio is not None:
        sessao.inicio = inicio


def _evento(n: int, corpo: dict, item: dict, instante: datetime | None) -> Evento:
    nome = _texto(item.get("type"))
    tipo = _MAPA_TIPOS.get(nome, "?")
    inicio = _de_ms(corpo.get("started_at_ms")) or instante
    duracao = _duracao(item, corpo)
    exit_code = _exit(item)
    if tipo == "?":
        texto = nome or "desconhecido"
        detalhe = _json(item)
    else:
        texto, detalhe = _conteudo(tipo, item)
    return Evento(
        n=n,
        instante=inicio,
        tipo=tipo,
        duracao_s=duracao,
        exit=exit_code,
        texto=texto,
        detalhe=detalhe,
    )


def _conteudo(tipo: str, item: dict) -> tuple[str, str]:
    if tipo in ("user", "msg"):
        return _conteudo_mensagem(item)
    if tipo == "think":
        return _conteudo_pensamento(item)
    if tipo == "cmd":
        return _conteudo_comando(item)
    if tipo == "edit":
        return _conteudo_edicao(item)
    if tipo == "tool":
        return _conteudo_ferramenta(item)
    if tipo == "agent":
        return _conteudo_agente(item)
    return "", ""


def _conteudo_mensagem(item: dict) -> tuple[str, str]:
    partes: list[str] = []
    conteudo = item.get("content")
    if isinstance(conteudo, list):
        for bloco in conteudo:
            if not isinstance(bloco, dict):
                continue
            classe = (_texto(bloco.get("type")) or "").lower()
            if classe in ("text", "input_text", "output_text"):
                partes.append(str(bloco.get("text") or ""))
            elif classe in ("local_image", "image"):
                partes.append("[imagem %s]" % (_texto(bloco.get("path")) or "?"))
            else:
                partes.append("[%s]" % (bloco.get("type") or "?"))
    detalhe = "\n".join(partes)
    return _uma_linha(detalhe), detalhe


def _conteudo_pensamento(item: dict) -> tuple[str, str]:
    resumo = [x for x in item.get("summary_text") or [] if isinstance(x, str)]
    if not resumo:
        bruto = item.get("raw_content")
        if isinstance(bruto, list):
            resumo = [x for x in bruto if isinstance(x, str)]
    detalhe = "\n".join(resumo)
    # O Codex escreve cada titulo do resumo em **negrito**; na linha ele so custa tokens.
    texto = "; ".join(_uma_linha(x.replace("**", "")) for x in resumo)
    return texto, detalhe


def _conteudo_comando(item: dict) -> tuple[str, str]:
    comando = _comando(item.get("command"))
    linhas: list[str] = []
    if comando:
        linhas.append("comando: " + comando)
    cwd = _caminho(item.get("cwd"))
    if cwd:
        linhas.append("cwd: " + cwd)
    codigo = _inteiro(item.get("exit_code"))
    if codigo is not None:
        linhas.append("exit: %d" % codigo)
    duracao = _duracao(item, {})
    if duracao is not None:
        linhas.append("duração: %.2fs" % duracao)
    linhas.append("saída:")
    linhas.append(_saida(item))
    return _uma_linha(comando), "\n".join(linhas)


def _conteudo_edicao(item: dict) -> tuple[str, str]:
    mudancas = item.get("changes")
    if not isinstance(mudancas, dict):
        mudancas = {}
    marcas: list[str] = []
    blocos: list[str] = []
    for caminho, mudanca in mudancas.items():
        classe = ""
        if isinstance(mudanca, dict):
            classe = _texto(mudanca.get("type")) or ""
        marca = _CODIGOS_EDICAO.get(classe, "?")
        marcas.append("%s%s" % (marca, caminho))
        blocos.append("%s %s" % (marca, caminho))
        if isinstance(mudanca, dict):
            diff = mudanca.get("unified_diff")
            conteudo = mudanca.get("content")
            if isinstance(diff, str) and diff:
                blocos.append(diff)
            elif isinstance(conteudo, str) and conteudo:
                blocos.append(conteudo)
    if not blocos:
        detalhe = _saida(item)
        return _uma_linha(detalhe), detalhe
    return _uma_linha(" ".join(marcas)), "\n".join(blocos)


def _conteudo_ferramenta(item: dict) -> tuple[str, str]:
    servidor = _texto(item.get("server")) or ""
    ferramenta = _texto(item.get("tool")) or ""
    nome = ".".join(x for x in (servidor, ferramenta) if x) or "ferramenta"
    argumentos = item.get("arguments")
    titulo = ""
    if isinstance(argumentos, dict):
        titulo = _texto(argumentos.get("title")) or ""
    texto = nome + (" " + titulo if titulo else "")
    linhas = ["ferramenta: " + nome]
    status = _texto(item.get("status"))
    if status:
        linhas.append("status: " + status)
    if argumentos is not None:
        linhas.append("argumentos: " + _json(argumentos))
    resultado = _texto_resultado(item.get("result"))
    if resultado:
        linhas.append("resultado:")
        linhas.append(resultado)
    return texto, "\n".join(linhas)


def _conteudo_agente(item: dict) -> tuple[str, str]:
    if item.get("type") == "SubAgentActivity":
        acao = _texto(item.get("kind")) or "atividade"
        caminho = _texto(item.get("agent_path")) or ""
        thread = _texto(item.get("agent_thread_id")) or ""
        texto = (acao + " " + caminho).strip()
        linhas = ["subagente: " + (caminho or "?")]
        linhas.append("ação: " + acao)
        if thread:
            linhas.append("thread: " + thread)
        return texto, "\n".join(linhas)
    acao = _texto(item.get("tool")) or "colaboração"
    destinos: list[str] = []
    for chave in ("receiver_agents", "agents_states"):
        valor = item.get(chave)
        if isinstance(valor, dict):
            destinos.extend(str(x) for x in valor)
        elif isinstance(valor, list):
            destinos.extend(str(x) for x in valor)
    texto = " ".join([acao] + destinos)
    return texto, _json(item)


def _saida(item: dict) -> str:
    agregada = item.get("aggregated_output")
    if isinstance(agregada, str) and agregada:
        return agregada
    partes = [x for x in (item.get("stdout"), item.get("stderr")) if isinstance(x, str) and x]
    if partes:
        return "\n".join(partes)
    formatado = item.get("formatted_output")
    return formatado if isinstance(formatado, str) else ""


def _comando(valor: object) -> str:
    if isinstance(valor, str):
        return valor
    if isinstance(valor, list) and valor:
        partes = [str(x) for x in valor]
        if len(partes) >= 3 and partes[1] in ("-Command", "-c", "/c", "/k", "-lc"):
            return " ".join(partes[2:])
        return " ".join(partes)
    return ""


def _caminho(valor: object) -> str | None:
    if not isinstance(valor, str) or not valor:
        return None
    if valor.startswith("file://"):
        resto = unquote(valor[7:])
        if len(resto) > 2 and resto[0] == "/" and resto[2] == ":":
            resto = resto[1:]
        return resto
    return valor


def _texto_resultado(resultado: object) -> str:
    if isinstance(resultado, str):
        return resultado
    if isinstance(resultado, dict):
        partes: list[str] = []
        conteudo = resultado.get("content")
        if isinstance(conteudo, list):
            for bloco in conteudo:
                if isinstance(bloco, dict):
                    if "text" in bloco:
                        partes.append(str(bloco.get("text") or ""))
                    else:
                        partes.append(_json(bloco))
        if not partes:
            partes.append(_json(resultado))
        return "\n".join(partes)
    if resultado is None:
        return ""
    return _json(resultado)


def _exit(item: dict) -> int | None:
    codigo = _inteiro(item.get("exit_code"))
    if codigo is not None:
        return codigo
    status = item.get("status")
    if isinstance(status, str) and status != "completed":
        return 1
    resultado = item.get("result")
    if isinstance(resultado, dict) and resultado.get("isError"):
        return 1
    return None


def _duracao(item: dict, corpo: dict) -> float | None:
    valor = item.get("duration")
    if isinstance(valor, dict):
        secs = valor.get("secs")
        nanos = valor.get("nanos")
        if _numero(secs):
            total = float(secs)
            if _numero(nanos):
                total += float(nanos) / 1e9
            return total
    inicio = corpo.get("started_at_ms")
    fim = corpo.get("completed_at_ms")
    if _numero(inicio) and _numero(fim):
        return (float(fim) - float(inicio)) / 1000.0
    return None


def _json(valor: object) -> str:
    try:
        return json.dumps(valor, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return str(valor)


def _uma_linha(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


def _linhas(caminho: Path):
    with caminho.open("r", encoding="utf-8", errors="replace") as arquivo:
        for linha in arquivo:
            yield linha


def _interessa(linha: str, marcas: tuple[str, ...]) -> bool:
    return any(marca in linha for marca in marcas)


def _registro(linha: str) -> dict | None:
    try:
        registro = json.loads(linha)
    except ValueError:
        return None
    return registro if isinstance(registro, dict) else None


def _iso(valor: object) -> datetime | None:
    if not isinstance(valor, str):
        return None
    texto = valor.strip()
    if texto.endswith("Z"):
        texto = texto[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(texto)
    except ValueError:
        return None


def _de_ms(valor: object) -> datetime | None:
    if not _numero(valor):
        return None
    return datetime.fromtimestamp(float(valor) / 1000.0, tz=timezone.utc)


def _numero(valor: object) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def _inteiro(valor: object) -> int | None:
    if isinstance(valor, bool) or not isinstance(valor, int):
        return None
    return valor


def _texto(valor: object) -> str | None:
    if isinstance(valor, str) and valor:
        return valor
    return None


def _id_do_nome(caminho: Path) -> str:
    casado = _ID_NO_NOME.search(caminho.stem)
    return casado.group(1).lower() if casado else caminho.stem
