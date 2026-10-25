# -*- coding: utf-8 -*-
"""
Validação dos valores das características técnicas do JSON do requerimento
contra as tabelas do CCT.

Estratégia (n-upla de colunas preservada):
1. As tabelas do CCT são lidas pela geometria do PDF; células mescladas
   (retornadas como None) são replicadas nas linhas/colunas cobertas.
2. Cada célula (do CCT e do JSON) é um conjunto de valores normalizados.
3. Uma linha do JSON está conforme se existir UMA linha do CCT em que, em todas
   as colunas, os valores do JSON sejam subconjunto dos valores da célula do CCT.
   Assim, o mesmo conteúdo do CCT pode ser distribuído em linhas diferentes no
   JSON (produto cartesiano das células), sem misturar valores de linhas distintas.
4. Se nenhuma linha do CCT cobre a linha do JSON, são reportados (coluna, valor)
   ausentes na linha do CCT mais próxima.
"""

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Pattern, Set, Tuple

import pymupdf as fitz

from core.const import EQUIVALENCIAS_CCT_FILENAME, UTILS_DIR
from core.log_print import log_info
from core.utils import carregar_json_com_fallback

# Chaves de coluna reconhecidas como "de características técnicas"; usadas para
# identificar tabelas relevantes do CCT (a tabela de modelos, por exemplo, é ignorada).
CHAVES_CARACTERISTICAS = {"faixa", "potencia", "eirp", "emissao", "tecnologia", "modulacao"}
VALORES_VAZIOS = {"", "-", "n/a", "na", "nao aplicavel"}
# Aplicadas ao texto já sem acentos e em minúsculas.
SUBSTITUICOES_TEXTO = (
    (r"(?<=\d)\s*(?:mhz|khz|ghz|dbm|w/kg|w)\b", ""),
    (r"(\d)[\s-]+(qam|psk)", r"\1\2"),
)

Atomo = FrozenSet[str]


def _sem_acentos(texto: Any, minusculas: bool = True) -> str:
    """Remove acentos/cedilhas (ü→u, ç→c); por padrão também converte para minúsculas."""
    decomposto = unicodedata.normalize("NFKD", str(texto if texto is not None else ""))
    resultado = "".join(c for c in decomposto if unicodedata.category(c) != "Mn")
    return resultado.lower() if minusculas else resultado


def _padrao_termo(termo: str) -> str:
    """Regex de um termo normalizado, tolerando qualquer espaçamento entre as palavras."""
    return re.escape(termo).replace(r"\ ", r"\s+")


@lru_cache(maxsize=1)
def _carregar_equivalencias() -> Tuple[Optional[Pattern[str]], Dict[str, str]]:
    """
    Carrega o dicionário de nomenclaturas equivalentes (utils/equivalencias_cct.json).
    Retorna a regex que localiza qualquer termo do dicionário (comparação sem acentos e sem
    diferenciar maiúsculas/minúsculas) e o mapa termo normalizado → identificador do grupo.
    """
    caminho = Path(__file__).parent.parent / UTILS_DIR / EQUIVALENCIAS_CCT_FILENAME
    dados = carregar_json_com_fallback(str(caminho))
    grupos = dados.get("equivalencias", []) if isinstance(dados, dict) else []
    termo_para_grupo: Dict[str, str] = {}
    for grupo in grupos:
        termos = [
            " ".join(_sem_acentos(termo).split())
            for termo in grupo if isinstance(termo, str)
        ]
        termos = [termo for termo in termos if termo]
        for termo in termos:
            termo_para_grupo.setdefault(termo, termos[0])
    if not termo_para_grupo:
        return None, {}
    # Termos mais longos primeiro, para que "salto em frequencia" prevaleça sobre termos menores.
    alternativas = "|".join(
        _padrao_termo(termo) for termo in sorted(termo_para_grupo, key=len, reverse=True)
    )
    return re.compile(rf"(?<![a-z0-9])(?:{alternativas})(?![a-z0-9])"), termo_para_grupo


def chave_coluna(cabecalho: Any) -> str:
    """Converte cabeçalhos equivalentes (JSON x CCT) em uma chave comum de coluna."""
    texto = _sem_acentos(re.sub(r"\([^)]*\)", " ", str(cabecalho or "")))
    letras = re.sub(r"[^a-z0-9]", "", texto)
    if "eirp" in letras:
        return "eirp"
    if "potencia" in letras:
        return "potencia"
    if "frequenc" in letras:
        return "faixa"
    if "designac" in letras:
        return "emissao"
    if "tecnolog" in letras or "espalhament" in letras:
        # Colunas de técnica de espalhamento (DSSS/OFDM) equivalem à de tecnologia no requerimento.
        return "tecnologia"
    if "modulac" in letras:
        return "modulacao"
    if letras.startswith("sar"):
        return "sarcabeca" if "cabeca" in letras else "sarcorpo"
    return letras


def _variantes_numericas(token: str) -> Set[str]:
    """Gera as leituras possíveis de um número (vírgula/ponto decimal ou separador de milhar)."""
    leituras = {token.replace(",", ".")}
    if re.fullmatch(r"[1-9]\d{0,2}(?:[.,]\d{3})+", token):
        leituras.add(re.sub(r"[.,]", "", token))
    variantes = set()
    for leitura in leituras:
        try:
            variantes.add(format(Decimal(leitura).normalize(), "f"))
        except InvalidOperation:
            variantes.add(leitura)
    return variantes


def extrair_valores(valor: Any) -> List[Tuple[str, Atomo]]:
    """
    Divide o valor de uma célula em valores individuais: (texto para exibição, átomo).
    O átomo é o conjunto das leituras normalizadas do valor, usado na comparação.
    """
    bruto = str(valor if valor is not None else "").strip()
    sem_acento = _sem_acentos(bruto).strip()
    if sem_acento in VALORES_VAZIOS or re.fullmatch(r"-+", sem_acento):
        return []
    # Intervalos numéricos "2400 – 2483,5" ou "5.925-7.125" viram dois números.
    texto = re.sub(r"(?<=\d)\s*[-–—]\s*(?=\d)", " ", bruto)
    texto = _sem_acentos(texto)
    # Equivalências de nomenclatura, unidades coladas ao número e modulações ("16 QAM" = "16-QAM").
    for padrao, substituicao in SUBSTITUICOES_TEXTO:
        texto = re.sub(padrao, substituicao, texto)
    original = _sem_acentos(bruto, minusculas=False)
    # Termos do dicionário de equivalências viram marcadores "@n" (um por ocorrência), que
    # representam o grupo inteiro; o trecho original é guardado para exibição.
    padrao_dicionario, termo_para_grupo = _carregar_equivalencias()
    trechos: List[str] = []
    if padrao_dicionario:
        def _marcar(correspondencia: "re.Match[str]") -> str:
            trechos.append(correspondencia.group(0))
            return f" @{len(trechos) - 1} "
        texto = padrao_dicionario.sub(_marcar, texto)
    valores = []
    for token in re.split(r"[\s;/()\[\]]+|(?<=[a-z])-", texto):
        token = token.strip(".,:")
        if not token or token == "-":
            continue
        if re.fullmatch(r"@\d+", token):
            trecho = trechos[int(token[1:])]
            atomo = frozenset({"grupo:" + termo_para_grupo[" ".join(trecho.split())]})
            exibicao_busca = _padrao_termo(" ".join(trecho.split()))
        elif re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?", token):
            atomo = frozenset(_variantes_numericas(token))
            exibicao_busca = re.escape(token)
        else:
            atomo = frozenset({token})
            exibicao_busca = re.escape(token)
        # Recupera a grafia original (maiúsculas) quando o token consta literalmente no valor.
        achado = re.search(exibicao_busca, original, re.IGNORECASE)
        valores.append((achado.group(0) if achado else token, atomo))
    return valores


def extrair_atomos(valor: Any) -> List[Atomo]:
    """Átomos normalizados dos valores de uma célula."""
    return [atomo for _, atomo in extrair_valores(valor)]


class LinhaCCT:
    """Linha lógica de uma tabela do CCT, já com as células mescladas replicadas."""

    def __init__(self, chaves: List[str], celulas: List[str]):
        self.por_chave: Dict[str, Set[str]] = {}
        self.todos: Set[str] = set()
        for chave, celula in zip(chaves, celulas):
            for atomo in extrair_atomos(celula):
                self.por_chave.setdefault(chave, set()).update(atomo)
                self.todos.update(atomo)
            self.por_chave.setdefault(chave, set())


def extrair_tabelas_pdf(caminho: Path) -> List[List[List[Optional[str]]]]:
    """Extrai todas as tabelas do PDF (células mescladas aparecem como None)."""
    tabelas = []
    with fitz.open(caminho) as pdf:
        for pagina in pdf:
            for tabela in pagina.find_tables().tables:
                tabelas.append(tabela.extract())
    return tabelas


def _preencher_mescladas(linhas: List[List[Optional[str]]]) -> List[List[str]]:
    """Replica o valor de células mescladas: do que está acima; na falta, do que está à esquerda."""
    resultado: List[List[str]] = []
    for i, linha in enumerate(linhas):
        nova = []
        for j, celula in enumerate(linha):
            if celula is None:
                if i > 0 and j < len(resultado[i - 1]):
                    celula = resultado[i - 1][j]
                elif j > 0:
                    celula = nova[j - 1]
                else:
                    celula = ""
            nova.append(celula)
        resultado.append(nova)
    return resultado


def linhas_cct_de_tabelas(tabelas: List[List[List[Optional[str]]]]) -> List[LinhaCCT]:
    """Seleciona as tabelas de características do CCT e devolve suas linhas de dados."""
    linhas_cct: List[LinhaCCT] = []
    chaves_anteriores: Optional[List[str]] = None
    for tabela in tabelas:
        if not tabela:
            continue
        chaves = [chave_coluna(c) for c in tabela[0]]
        if len(CHAVES_CARACTERISTICAS & set(chaves)) >= 2:
            dados = tabela[1:]
            chaves_anteriores = chaves
        elif chaves_anteriores and len(tabela[0]) == len(chaves_anteriores):
            # Tabela continuada em outra página sem repetir o cabeçalho.
            chaves, dados = chaves_anteriores, tabela
        else:
            chaves_anteriores = None
            continue
        for celulas in _preencher_mescladas(dados):
            linhas_cct.append(LinhaCCT(chaves, celulas))
    return linhas_cct


def _valores_ausentes(registro: Dict[str, Any], linha: LinhaCCT) -> List[Tuple[str, str]]:
    """Valores do registro do JSON ausentes na linha do CCT, como (título da coluna, valor)."""
    ausentes = []
    for cabecalho, valor in registro.items():
        chave = chave_coluna(cabecalho)
        alvo = linha.por_chave.get(chave)
        for exibicao, atomo in extrair_valores(valor):
            # O valor só vale na coluna equivalente do CCT; sem coluna equivalente na tabela
            # (cabeçalho não reconhecido), aceita-se em qualquer coluna da mesma linha.
            referencia = alvo if alvo is not None else linha.todos
            if not atomo & referencia:
                ausentes.append((str(cabecalho), exibicao))
    return ausentes


def _valores_em_outras_linhas(
    registro: Dict[str, Any],
    faltantes: List[Tuple[str, str]],
    linhas_cct: List[LinhaCCT],
) -> List[Tuple[str, str]]:
    """
    Dentre os valores faltantes, os que constam na coluna equivalente de alguma outra linha
    do CCT (o valor existe no CCT, mas não combinado com os demais valores da linha do JSON).
    """
    pares = set(faltantes)
    encontrados = []
    for cabecalho, valor in registro.items():
        chave = chave_coluna(cabecalho)
        for exibicao, atomo in extrair_valores(valor):
            if (str(cabecalho), exibicao) in pares and any(
                atomo & (linha.por_chave.get(chave) or set()) for linha in linhas_cct
            ):
                encontrados.append((str(cabecalho), exibicao))
    return encontrados


def _descrever_linha(registro: Dict[str, Any]) -> str:
    """Resume a linha do JSON no formato [valor][valor], omitindo vazios e '-'."""
    valores = [str(v).strip() for v in registro.values() if extrair_atomos(v)]
    return "".join(f"[{v}]" for v in valores)


def validar_caracteristicas_no_cct(
    produtos: List[Tuple[str, List[Dict[str, Any]]]],
    linhas_cct: List[LinhaCCT],
) -> List[Dict[str, Any]]:
    """
    Verifica se cada linha de características do JSON está coberta por alguma linha do CCT.

    Uma linha do JSON está conforme se existir uma linha do CCT cujas células contenham, coluna
    a coluna, todos os valores dela (a mesma linha do CCT pode cobrir várias linhas do JSON,
    pois as combinações das células podem estar distribuídas de outra forma). Caso contrário,
    retorna {"produto", "linha", "faltantes": [(coluna, valor)]}, com os valores ausentes
    na linha do CCT mais próxima (a que deixa menos valores ausentes).
    """
    pendencias = []
    total = 0
    for nome, lista in produtos:
        for registro in lista:
            if not isinstance(registro, dict) or not any(extrair_atomos(v) for v in registro.values()):
                continue
            total += 1
            melhor = min(
                (_valores_ausentes(registro, linha) for linha in linhas_cct),
                key=len,
                default=[],
            )
            if melhor:
                pendencias.append({
                    "produto": nome,
                    "linha": _descrever_linha(registro),
                    "faltantes": melhor,
                    "em_outra_linha": _valores_em_outras_linhas(registro, melhor, linhas_cct),
                })
    log_info(f"Características no CCT: {len(pendencias)} linha(s) com pendência em {total}")
    return pendencias
