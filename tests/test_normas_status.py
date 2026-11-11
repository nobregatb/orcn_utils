import json
from datetime import date

import pytest

import core.normas_status as normas_status
from core.normas_status import _eh_ato, _normas_elegiveis, _pagina_indica_revogacao


def test_pagina_indica_revogacao_ignorando_caixa_acentos_e_espacos():
    html = "<p>ATO nº 123, de 1º de março de 2024 ( REVOGADO )</p>"

    assert _pagina_indica_revogacao("Ato nº 123, de 1º de marco de 2024", html)


def test_pagina_nao_indica_revogacao_quando_marcador_nao_vem_logo_apos_nome():
    html = "<p>Ato nº 123, de 1º de março de 2024 - vigente (REVOGADO)</p>"

    assert not _pagina_indica_revogacao("Ato nº 123, de 1º de marco de 2024", html)


def test_pagina_do_ato_943_com_dia_zero_a_esquerda_nao_e_falha_de_url():
    html = "<h1>Ato nº 943, de 08 de fevereiro de 2018</h1>"

    with pytest.raises(ValueError, match="nome do normativo não encontrado"):
        _pagina_indica_revogacao("Ato nº 943, de 8 de Fevereiro de 2018", html)


def test_pagina_da_resolucao_789_com_anatel_no_titulo_nao_e_falha_de_url():
    html = "<h1>Resolução Anatel nº 789, de 06 de julho de 2026</h1>"

    with pytest.raises(ValueError, match="nome do normativo não encontrado"):
        _pagina_indica_revogacao("Resolução nº 789, de 06 de julho de 2026", html)


def test_pagina_sem_nome_do_normativo_falha_sem_confirmar_revogacao():
    with pytest.raises(ValueError, match="nome do normativo não encontrado"):
        _pagina_indica_revogacao("Ato nº 123", "<p>Outro normativo (REVOGADO)</p>")


def test_tipo_do_status_revogado_depende_de_ser_ato():
    assert _eh_ato({"nome": "Ato nº 123"})
    assert not _eh_ato({"nome": "Resolução nº 123"})


def test_normas_com_url_sei_nao_sao_elegiveis_para_verificacao():
    normas = [
        {"id": "ato_sei", "url": "https://sei.anatel.gov.br/sei/documento", "status": "vigente"},
        {"id": "ato_site", "url": "https://informacoes.anatel.gov.br/ato", "status": "vigente"},
    ]

    assert [norma["id"] for norma in _normas_elegiveis(normas)] == ["ato_site"]


def test_verificacao_registra_progresso_e_resultado_por_normativo(tmp_path, monkeypatch, capsys):
    caminho_normas = tmp_path / "normas.json"
    caminho_normas.write_text(json.dumps([
        {"id": "ato123", "nome": "Ato nº 123", "url": "https://example.test/ato", "status": "vigente"},
        {"id": "resolucao456", "nome": "Resolução nº 456", "url": "https://example.test/resolucao", "status": "vigente"},
    ]), encoding="utf-8")
    monkeypatch.setitem(normas_status.JSON_FILES, "normas", str(caminho_normas))
    monkeypatch.setattr(
        normas_status,
        "_consultar_norma",
        lambda norma: norma["id"] == "ato123",
    )

    execucao = normas_status.iniciar_verificacao_semanal()
    normas_status.finalizar_verificacao_semanal(execucao)
    saida = capsys.readouterr().out

    assert "Verificação semanal de vigência iniciada: 0/2" in saida
    assert "Verificação de vigência [1/2]" in saida
    assert "Verificação de vigência [2/2]" in saida
    assert "ato123 - Ato nº 123: marcador de revogação encontrado." in saida
    assert "resolucao456 - Resolução nº 456: nenhum marcador de revogação encontrado." in saida


def test_salva_consultas_bem_sucedidas_mesmo_quando_outra_norma_falha(tmp_path, monkeypatch):
    caminho_normas = tmp_path / "normas.json"
    caminho_normas.write_text(json.dumps([
        {"id": "ato2220", "nome": "Ato nº 2220", "url": "https://example.test/ato", "status": "vigente"},
        {"id": "ato9999", "nome": "Ato nº 9999", "url": "https://example.test/falha", "status": "vigente"},
    ]), encoding="utf-8")
    monkeypatch.setitem(normas_status.JSON_FILES, "normas", str(caminho_normas))

    class ThreadConcluida:
        def join(self):
            pass

    execucao = (
        ThreadConcluida(),
        {"consultas": {"ato2220": True}, "falhas": {"ato9999": "timeout"}},
    )
    normas_status.finalizar_verificacao_semanal(execucao)
    documento = json.loads(caminho_normas.read_text(encoding="utf-8"))
    normas_salvas = documento["normas"]
    normas_por_id = {norma["id"]: norma for norma in normas_salvas}

    assert documento[normas_status.CAMPO_ULTIMA_VERIFICACAO] is None
    assert normas_por_id["ato2220"]["status"] == "revogado"
    assert normas_por_id["ato9999"]["status"] == "vigente"
    assert normas_por_id["ato9999"]["url"] == "https://example.test/falha"
    assert normas_status.CAMPO_ULTIMA_VERIFICACAO not in normas_por_id["ato9999"]


def test_data_global_nao_atualizada_quando_uma_consulta_falha(tmp_path, monkeypatch):
    caminho_normas = tmp_path / "normas.json"
    caminho_normas.write_text(json.dumps({
        normas_status.CAMPO_ULTIMA_VERIFICACAO: None,
        "normas": [
            {"id": "ato123", "nome": "Ato nº 123", "status": "vigente"},
            {"id": "res456", "nome": "Resolução nº 456", "status": "vigente"},
        ],
    }), encoding="utf-8")
    monkeypatch.setitem(normas_status.JSON_FILES, "normas", str(caminho_normas))

    class ThreadConcluida:
        def join(self):
            pass

    execucao = (
        ThreadConcluida(),
        {"consultas": {"ato123": False}, "falhas": {"res456": "timeout"}},
    )
    normas_status.finalizar_verificacao_semanal(execucao)
    documento = json.loads(caminho_normas.read_text(encoding="utf-8"))

    assert documento[normas_status.CAMPO_ULTIMA_VERIFICACAO] is None
    resolucao = next(n for n in documento["normas"] if n["id"] == "res456")
    assert resolucao["status"] == "vigente"


def test_url_malformada_preserva_status_e_data(tmp_path, monkeypatch):
    caminho_normas = tmp_path / "normas.json"
    caminho_normas.write_text(json.dumps({
        normas_status.CAMPO_ULTIMA_VERIFICACAO: None,
        "normas": [
            {"id": "res123", "nome": "Resolução nº 123", "url": "hhttps://example.test/123", "status": "vigente"},
        ],
    }), encoding="utf-8")
    monkeypatch.setitem(normas_status.JSON_FILES, "normas", str(caminho_normas))

    class ThreadConcluida:
        def join(self):
            pass

    execucao = (
        ThreadConcluida(),
        {"consultas": {}, "falhas": {"res123": "URL inválida"}},
    )
    normas_status.finalizar_verificacao_semanal(execucao)
    documento = json.loads(caminho_normas.read_text(encoding="utf-8"))

    assert documento[normas_status.CAMPO_ULTIMA_VERIFICACAO] is None
    assert documento["normas"][0]["status"] == "vigente"
    assert documento["normas"][0]["url"] == "hhttps://example.test/123"