import math
import json
import re
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator

# --- FUNÇÕES DE CONVERSÃO E PARSING DE POTÊNCIA ---

def parse_valor_numerico(val_str: Optional[str]) -> Optional[float]:
    """Converte número brasileiro (ponto de milhar e vírgula decimal) para float."""
    if not val_str or not val_str.strip():
        return None
    try:
        limpo = val_str.strip().replace(".", "").replace(",", ".")
        return float(limpo)
    except ValueError:
        return None


def parse_frequencias_mhz(faixa: str) -> List[float]:
    """Extrai um valor ou os dois extremos informados e converte GHz para MHz."""
    encontrados = list(re.finditer(
        r"(?P<valor>\d[\d.,]*)(?:\s*(?P<unidade>GHz|MHz))?",
        faixa,
        flags=re.IGNORECASE
    ))
    if not encontrados or len(encontrados) > 2:
        raise ValueError("Nenhum valor numérico encontrado.")

    unidade_padrao = "GHz" if "GHZ" in faixa.upper() else "MHz"
    valores = []
    for encontrado in encontrados:
        valor = float(encontrado.group("valor").replace(".", "").replace(",", "."))
        unidade = encontrado.group("unidade") or unidade_padrao
        if unidade.upper() == "GHZ":
            valor *= 1000.0
        valores.append(valor)
    return valores


def parse_frequencia_mhz(faixa: str) -> float:
    """Extrai a frequência inicial de uma faixa e converte GHz para MHz."""
    return parse_frequencias_mhz(faixa)[0]


def watts_to_dbm(watts: float) -> float:
    """Converte Potência de Watts para dBm: P(dBm) = 10 * log10(P(W) * 1000)"""
    if watts <= 0:
        return float('-inf')
    return 10 * math.log10(watts * 1000.0)


# --- REGRAS DE FAIXA CARREGADAS DE JSON ---

_ARQUIVO_FAIXAS = Path(__file__).resolve().parent.parent / "utils" / "faixas.json"
with _ARQUIVO_FAIXAS.open(encoding="utf-8") as arquivo:
    BASE_REGRAS_UNIFICADAS = json.load(arquivo)

for _regra in BASE_REGRAS_UNIFICADAS:
    _regra["faixa"] = tuple(_regra["faixa"])
    _regra["atos_validos"] = set(_regra["atos_validos"])


def obter_regras_frequencia(frequencia: float) -> List[dict]:
    """Retorna todas as regras que contêm a frequência, incluindo sobreposições."""
    return [
        regra for regra in BASE_REGRAS_UNIFICADAS
        if regra["faixa"][0] <= frequencia <= regra["faixa"][1]
    ]


def obter_regra_frequencia(frequencia: float) -> Optional[dict]:
    """Retorna a regra mais específica para validar restrições da frequência."""
    regras_aplicaveis = obter_regras_frequencia(frequencia)
    if not regras_aplicaveis:
        return None
    return min(regras_aplicaveis, key=lambda regra: regra["faixa"][1] - regra["faixa"][0])


# --- MODELO DE VALIDAÇÃO PYDANTIC ---

class FrequenciaItem(BaseModel):
    faixa_frequencias_tx: str = Field(..., alias="Faixa de Frequências Tx (MHz)")
    tecnologia: Optional[str] = Field(None, alias="Tecnologia")
    especificacoes_ambiente: Optional[str] = Field(None, description="Ex: indoor ou outdoor")
    
    # Campos de potência mapeados do JSON
    potencia_max_saida_w: Optional[str] = Field(None, alias="Potência Máxima de Saída (W)")
    potencia_media_eirp_dbm: Optional[str] = Field(None, alias="Potência Média E.I.R.P. (dBm)")
    potencia_pico_eirp_dbm: Optional[str] = Field(None, alias="Potência de Pico E.I.R.P. (dBm)")

    @model_validator(mode="after")
    def validar_regras_e_potencias(self) -> "FrequenciaItem":
        try:
            frequencias = parse_frequencias_mhz(self.faixa_frequencias_tx)
        except ValueError:
            raise ValueError(f"Formato inválido na propriedade 'Faixa de Frequências Tx (MHz)': '{self.faixa_frequencias_tx}'.")

        # Todos os valores declarados precisam estar em faixas previstas no ato.
        regras_encontradas = [
            obter_regra_frequencia(freq) for freq in frequencias
        ]

        for freq, regra in zip(frequencias, regras_encontradas):
            if regra is None:
                raise ValueError(
                    f"VIOLAÇÃO CRÍTICA: A frequência '{freq} MHz' não está "
                    "contemplada nas regras do Ato 14.448."
                )

        regra_encontrada = regras_encontradas[0]

        # 2. Validação de Restrições Ambientais e Vedações
        if regra_encontrada.get("ambiente_exigido") == "indoor":
            if self.especificacoes_ambiente and self.especificacoes_ambiente.lower() != "indoor":
                raise ValueError(f"Violação regulatória: A faixa {self.faixa_frequencias_tx} exige ambiente indoor[cite: 1].")

        if "vedacoes" in regra_encontrada:
            for vedado in regra_encontrada["vedacoes"]:
                if self.tecnologia and vedado in self.tecnologia.lower():
                    raise ValueError(f"Violação regulatória: Uso vedado para '{vedado}' nesta faixa.")

        # 3. Validação e Cálculo de Potência Conduzida (W -> dBm)
        val_pot_w = parse_valor_numerico(self.potencia_max_saida_w)
        if val_pot_w is not None and "potencia_conduzida_max_dbm" in regra_encontrada:
            pot_calc_dbm = watts_to_dbm(val_pot_w)
            limite_dbm = regra_encontrada["potencia_conduzida_max_dbm"]
            if pot_calc_dbm > limite_dbm + 0.01:
                raise ValueError(
                    f"Violação de Potência Conduzida: Calculado {pot_calc_dbm:.2f} dBm ({val_pot_w} W), "
                    f"excede o limite regulatório de {limite_dbm} dBm[cite: 1]."
                )

        # 4. Validação de Potência Média E.I.R.P. (dBm)
        val_media_dbm = parse_valor_numerico(self.potencia_media_eirp_dbm)
        if val_media_dbm is not None and "eirp_media_max_dbm" in regra_encontrada:
            limite_media_dbm = regra_encontrada["eirp_media_max_dbm"]
            if val_media_dbm > limite_media_dbm:
                raise ValueError(
                    f"Violação de EIRP Média: Informado {val_media_dbm} dBm, "
                    f"excede o limite regulatório de {limite_media_dbm} dBm[cite: 1]."
                )

        # 5. Validação de Potência de Pico E.I.R.P. (dBm)
        val_pico_dbm = parse_valor_numerico(self.potencia_pico_eirp_dbm)
        if val_pico_dbm is not None and "eirp_pico_max_dbm" in regra_encontrada:
            limite_pico_dbm = regra_encontrada["eirp_pico_max_dbm"]
            if val_pico_dbm > limite_pico_dbm:
                raise ValueError(
                    f"Violação de EIRP de Pico: Informado {val_pico_dbm} dBm, "
                    f"excede o limite regulatório de {limite_pico_dbm} dBm[cite: 1]."
                )

        return self


class HomologacaoProduto(BaseModel):
    normas_referencia: List[str] = Field(default_factory=lambda: ["ato14448"])
    frequencias: List[FrequenciaItem]

    @model_validator(mode="after")
    def validar_contexto_normativo(self) -> "HomologacaoProduto":
        normas_ativas = {n.lower().replace(" ", "").replace("_", "").replace("º", "") for n in self.normas_referencia}

        for item in self.frequencias:
            for frequencia in parse_frequencias_mhz(item.faixa_frequencias_tx):
                regras_aplicaveis = obter_regras_frequencia(frequencia)
                atos_validos = set().union(
                    *(regra["atos_validos"] for regra in regras_aplicaveis)
                )
                if regras_aplicaveis and not normas_ativas.intersection(atos_validos):
                    raise ValueError(
                        f"VIOLAÇÃO DE ESCOPO: A frequência informada exige referência aos atos "
                        f"{atos_validos}, mas o contexto fornecido continha: "
                        f"{normas_ativas} (frequência: {frequencia} MHz)."
                    )
        return self