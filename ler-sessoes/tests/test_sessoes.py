import subprocess
import sys
import unittest
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
SKILL_DIR = TEST_DIR.parent
CLI = SKILL_DIR / "scripts" / "sessoes.py"
FIXTURES = TEST_DIR / "fixtures" / "codex"

SESSAO_CHEIA = "11111111"


class Base(unittest.TestCase):
    def rodar(self, *args):
        return subprocess.run(
            [sys.executable, "-B", str(CLI), *args, "--raiz", str(FIXTURES)],
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=60,
        )

    def corpo(self, resultado):
        return resultado.stdout.splitlines()[1:]


class ListaTest(Base):
    def test_lista_traz_uma_linha_por_sessao(self):
        resultado = self.rodar("lista")
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        linhas = resultado.stdout.splitlines()
        self.assertEqual(len(linhas), 5)
        self.assertIn("ferramenta", linhas[0])
        self.assertIn("tokens", linhas[0])
        texto = resultado.stdout
        self.assertIn("11111111", texto)
        self.assertIn("modelo-x/high", texto)
        self.assertIn("100/20", texto)
        self.assertEqual(texto.count("22222222"), 2)
        self.assertIn("sem-fim", texto)

    def test_lista_sem_fim_e_sem_tokens(self):
        linhas = self.rodar("lista").stdout.splitlines()
        sessao = [l for l in linhas if l.startswith("33333333")][0]
        self.assertIn("sem-fim", sessao)
        self.assertIn("modelo-z/medium", sessao)
        self.assertIn("/root/worker_x", sessao)
        self.assertNotIn("0/0", sessao)

    def test_lista_desde(self):
        resultado = self.rodar("lista", "--desde", "2026-09-01")
        self.assertIn("11111111", resultado.stdout)
        self.assertNotIn("22222222", resultado.stdout)
        self.assertNotIn("33333333", resultado.stdout)

    def test_lista_data_invalida(self):
        resultado = self.rodar("lista", "--desde", "19/09/2026")
        self.assertEqual(resultado.returncode, 2)
        self.assertIn("data invalida", resultado.stderr)

    def test_lista_ferramenta_sem_leitor(self):
        resultado = self.rodar("lista", "--ferramenta", "outra")
        self.assertEqual(resultado.returncode, 2)
        self.assertIn("sem leitor", resultado.stderr)


class LinhaTest(Base):
    def test_linha_conta_e_ordena_os_eventos(self):
        linhas = self.corpo(self.rodar("linha", SESSAO_CHEIA))
        self.assertEqual(len(linhas), 12)
        self.assertEqual([l.split(" ")[0] for l in linhas], [str(i) for i in range(1, 13)])
        self.assertTrue(linhas[0].startswith("1 0m user Ajuste o parser principal."), linhas[0])
        self.assertTrue(linhas[1].startswith("2 0m 1s msg Vou verificar o arquivo. Segunda linha."), linhas[1])
        self.assertTrue(linhas[2].startswith("3 0m 1s think Planejando; Lendo o log"), linhas[2])
        self.assertTrue(linhas[3].startswith("4 0m 2s cmd rg -n parser src\\a.py"), linhas[3])
        self.assertTrue(linhas[4].startswith("5 0m !1 cmd Get-Content nao-existe.txt"), linhas[4])
        self.assertTrue(linhas[5].startswith("6 0m 1s edit +src\\b.py"), linhas[5])
        self.assertTrue(linhas[6].startswith("7 0m 1s tool srv.acao Titulo curto"), linhas[6])
        self.assertTrue(linhas[7].startswith("8 0m 1s !1 tool srv.acao"), linhas[7])
        self.assertTrue(linhas[8].startswith("9 0m agent started /root/worker"), linhas[8])
        self.assertTrue(linhas[9].startswith("10 0m 1s agent wait"), linhas[9])
        self.assertTrue(linhas[10].startswith("11 0m 1s compact"), linhas[10])
        self.assertTrue(linhas[11].startswith("12 2m 1s ? FutureWidget"), linhas[11])

    def test_linha_cabecalho_da_sessao(self):
        resultado = self.rodar("linha", SESSAO_CHEIA)
        cabecalho = resultado.stdout.splitlines()[0]
        self.assertIn("11111111", cabecalho)
        self.assertIn("modelo-x/high", cabecalho)
        self.assertIn("fim", cabecalho)
        self.assertIn("cwd=C:\\proj", cabecalho)

    def test_linha_tipo_filtra_cada_tipo(self):
        esperados = {"user": 1, "msg": 1, "think": 1, "cmd": 2, "edit": 1, "tool": 2, "agent": 2, "compact": 1, "?": 1}
        for tipo, esperado in esperados.items():
            resultado = self.rodar("linha", SESSAO_CHEIA, "--tipo", tipo)
            self.assertEqual(len(self.corpo(resultado)), esperado, tipo)

    def test_linha_tipo_aceita_lista(self):
        linhas = self.corpo(self.rodar("linha", SESSAO_CHEIA, "--tipo", "cmd,edit"))
        self.assertEqual([l.split(" ")[0] for l in linhas], ["4", "5", "6"])

    def test_linha_falhas_so_exit_e_erro_de_ferramenta(self):
        linhas = self.corpo(self.rodar("linha", SESSAO_CHEIA, "--falhas"))
        self.assertEqual([l.split(" ")[0] for l in linhas], ["5", "8"])

    def test_linha_grep_procura_no_conteudo_completo(self):
        linhas = self.corpo(self.rodar("linha", SESSAO_CHEIA, "--grep", "AGULHA", "--largura", "20"))
        self.assertEqual(len(linhas), 1)
        self.assertTrue(linhas[0].startswith("4 "), linhas[0])
        self.assertNotIn("AGULHA", linhas[0])
        self.assertIn("…", linhas[0])

    def test_linha_de_ate(self):
        linhas = self.corpo(self.rodar("linha", SESSAO_CHEIA, "--de", "4", "--ate", "6"))
        self.assertEqual([l.split(" ")[0] for l in linhas], ["4", "5", "6"])

    def test_linha_tres_eventos_por_pagina(self):
        todas = self.corpo(self.rodar("linha", SESSAO_CHEIA))
        faixa = self.corpo(self.rodar("linha", SESSAO_CHEIA, "--de", "3", "--ate", "5"))
        self.assertEqual(faixa, todas[2:5])

    def test_prefixo_curto(self):
        linhas = self.corpo(self.rodar("linha", "3333"))
        self.assertEqual(linhas, ["1 0m think Pensando sem fim."])

    def test_prefixo_ambiguo_lista_candidatos(self):
        resultado = self.rodar("linha", "22222222")
        self.assertEqual(resultado.returncode, 2)
        self.assertIn("ambiguo", resultado.stderr)
        self.assertIn("22222222-aaa", resultado.stderr)
        self.assertIn("22222222-bbb", resultado.stderr)

    def test_sessao_inexistente(self):
        resultado = self.rodar("linha", "99999999")
        self.assertEqual(resultado.returncode, 2)
        self.assertIn("nao encontrada", resultado.stderr)


class MostraTest(Base):
    def test_mostra_evento_inteiro(self):
        resultado = self.rodar("mostra", SESSAO_CHEIA, "4")
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn("evento 4 cmd", resultado.stdout)
        self.assertIn("comando: rg -n parser src\\a.py", resultado.stdout)
        self.assertIn("cwd: C:/proj", resultado.stdout)
        self.assertIn("exit: 0", resultado.stdout)
        self.assertIn("duração: 2.50s", resultado.stdout)
        self.assertIn("AGULHA", resultado.stdout)

    def test_mostra_corta_o_meio(self):
        resultado = self.rodar("mostra", SESSAO_CHEIA, "4", "--max-bytes", "200")
        self.assertIn("INICIO", resultado.stdout)
        self.assertIn("FIM", resultado.stdout)
        self.assertIn("bytes cortados do meio", resultado.stdout)
        self.assertNotIn("AGULHA", resultado.stdout)

    def test_mostra_edicao_traz_diff(self):
        resultado = self.rodar("mostra", SESSAO_CHEIA, "6")
        self.assertIn("+ src\\b.py", resultado.stdout)
        self.assertIn("print('novo')", resultado.stdout)

    def test_mostra_tipo_desconhecido_nao_derruba(self):
        resultado = self.rodar("mostra", SESSAO_CHEIA, "12")
        self.assertEqual(resultado.returncode, 0)
        self.assertIn("FutureWidget", resultado.stdout)

    def test_mostra_evento_inexistente(self):
        resultado = self.rodar("mostra", SESSAO_CHEIA, "99")
        self.assertEqual(resultado.returncode, 2)
        self.assertIn("evento 99 inexistente", resultado.stderr)


class FonteTest(unittest.TestCase):
    def test_cli_nao_tem_nomes_do_codex(self):
        texto = (SKILL_DIR / "scripts" / "sessoes.py").read_text(encoding="utf-8")
        proibidos = [
            "session_meta",
            "payload",
            "item_completed",
            "parent_thread_id",
            "agent_path",
            "agent_nickname",
            "turn_context",
            "token_count",
            "task_complete",
            "response_item",
            "CommandExecution",
            "FileChange",
            "AgentMessage",
            "UserMessage",
            "Reasoning",
            "McpToolCall",
            "CollabAgentToolCall",
            "SubAgentActivity",
            "ContextCompaction",
            "aggregated_output",
            "exit_code",
            "duration_ms",
            "summary_text",
            "started_at_ms",
            "completed_at_ms",
            "parsed_cmd",
            "cli_version",
            "thread_source",
            "session_id",
            "base_instructions",
            "world_state",
            "token_usage_record",
            "rollout-",
            "jsonl",
        ]
        for nome in proibidos:
            self.assertNotIn(nome, texto, nome)

    def test_cli_so_cita_o_leitor_no_registro(self):
        texto = (SKILL_DIR / "scripts" / "sessoes.py").read_text(encoding="utf-8")
        self.assertEqual(texto.count("codex"), 2, "import e LEITORES")


if __name__ == "__main__":
    unittest.main()
