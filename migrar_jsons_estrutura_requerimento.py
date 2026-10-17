"""Migra JSONs antigos de requerimentos para a estrutura de produtos."""

import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

PASTA_BASE = r"C:\Users\tbnobrega\OneDrive - ANATEL\Anatel\_ORCN\req_inbox"
APLICAR = True


def migrar_conteudo(dados: Any) -> Tuple[Optional[Dict[str, Any]], str]:
    """Converte as chaves antigas quando os dados necessários estão disponíveis."""
    if not isinstance(dados, dict):
        return None, "o conteúdo do JSON não é um objeto"

    frequencias_antigas = dados.get("frequencias")
    tem_frequencias = "frequencias" in dados
    caracteristicas = dados.get("caracteristicas_tecnicas")
    caracteristicas = caracteristicas if caracteristicas is not None else {}
    if not isinstance(caracteristicas, dict):
        return None, "'caracteristicas_tecnicas' não é um objeto"

    tem_subprodutos = "subprodutos" in caracteristicas
    produtos_antigos = caracteristicas.get("produtos", [])
    subprodutos_antigos = caracteristicas.get("subprodutos", [])

    if not tem_frequencias and not tem_subprodutos:
        return None, "já está atualizado"
    if tem_frequencias and not isinstance(frequencias_antigas, list):
        return None, "'frequencias' não é uma lista"
    if not isinstance(produtos_antigos, list):
        return None, "'produtos' não é uma lista"
    if not isinstance(subprodutos_antigos, list):
        return None, "'subprodutos' não é uma lista"

    produto = dados.get("produto")
    nome_principal = (
        str(produto.get("Produto") or "").strip()
        if isinstance(produto, dict) else ""
    )
    if tem_frequencias and not nome_principal:
        return None, "falta 'produto.Produto' para identificar o produto principal"

    migrado = copy.deepcopy(dados)
    caracteristicas_migradas = copy.deepcopy(caracteristicas)
    produtos = copy.deepcopy(produtos_antigos)

    if tem_subprodutos:
        for subproduto in subprodutos_antigos:
            if subproduto not in produtos:
                produtos.append(copy.deepcopy(subproduto))

    if tem_frequencias:
        produto_principal = next(
            (
                item for item in produtos
                if isinstance(item, dict) and item.get("nome") == nome_principal
            ),
            None,
        )
        if produto_principal is None:
            produtos.insert(0, {
                "nome": nome_principal,
                "caracteristicas": copy.deepcopy(frequencias_antigas),
            })
        else:
            caracteristicas_principais = produto_principal.get("caracteristicas", [])
            if not isinstance(caracteristicas_principais, list):
                return None, "as características do produto principal não são uma lista"
            for frequencia in frequencias_antigas:
                if frequencia not in caracteristicas_principais:
                    caracteristicas_principais.append(copy.deepcopy(frequencia))
            produto_principal["caracteristicas"] = caracteristicas_principais

    caracteristicas_migradas["produtos"] = produtos
    caracteristicas_migradas.pop("subprodutos", None)
    migrado["caracteristicas_tecnicas"] = caracteristicas_migradas
    migrado.pop("frequencias", None)
    return migrado, "migrado"


def arquivos_alvo(pasta: Path):
    """Lista JSONs sob qualquer subdiretório cujo nome comece com '_'."""
    for raiz, _, arquivos in os.walk(pasta):
        caminho_raiz = Path(raiz)
        relativo = caminho_raiz.relative_to(pasta)
        esta_em_pasta_alvo = any(parte.startswith("_") for parte in relativo.parts)
        if not esta_em_pasta_alvo:
            continue
        for nome in arquivos:
            if Path(nome).suffix.casefold() == ".json":
                yield caminho_raiz / nome


def salvar_json_atomico(caminho: Path, dados: Dict[str, Any]) -> None:
    """Grava o JSON por substituição atômica para evitar arquivos parciais."""
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=caminho.parent,
            prefix=f".{caminho.name}.",
            suffix=".tmp",
            delete=False,
        ) as arquivo:
            temporario = Path(arquivo.name)
            json.dump(dados, arquivo, ensure_ascii=False, indent=4)
            arquivo.write("\n")
        os.replace(temporario, caminho)
    finally:
        if temporario is not None and temporario.exists():
            temporario.unlink()


def processar_pasta(pasta: Path, aplicar: bool) -> int:
    """Analisa os JSONs-alvo, grava migrações se solicitado e retorna falhas."""
    migrados = 0
    ignorados = 0
    falhas = 0

    for caminho in arquivos_alvo(pasta):
        try:
            with caminho.open("r", encoding="utf-8-sig") as arquivo:
                original = json.load(arquivo)
            atualizado, motivo = migrar_conteudo(original)
            if atualizado is None:
                ignorados += 1
                if motivo != "já está atualizado":
                    print(f"IGNORADO: {caminho} ({motivo})")
                continue

            migrados += 1
            acao = "MIGRADO" if aplicar else "PRONTO"
            print(f"{acao}: {caminho}")
            if aplicar:
                salvar_json_atomico(caminho, atualizado)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError) as erro:
            falhas += 1
            print(f"ERRO: {caminho} ({erro})")

    modo = "gravados" if aplicar else "identificados para migração"
    print(
        f"Concluído: {migrados} {modo}, {ignorados} ignorado(s), "
        f"{falhas} falha(s)."
    )
    return falhas


def main() -> int:
    pasta = Path(PASTA_BASE).expanduser().resolve()
    if not pasta.is_dir():
        raise NotADirectoryError(f"A pasta não existe ou não é um diretório: {pasta}")
    return 1 if processar_pasta(pasta, APLICAR) else 0


if __name__ == "__main__":
    raise SystemExit(main())
