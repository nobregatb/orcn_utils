import math
import re
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


# --- BASE DE REGRAS UNIFICADAS EXAUSTIVA (ATO 14.448 + MODIFICADORES) ---

BASE_REGRAS_UNIFICADAS = [
    # 1. Baixa Frequência / Portadoras Originais
    {
        "faixa": (26.96, 27.28),
        "atos_validos": {"ato14448"},
        "descricao": "Baixa Frequência / Faixa Cidadão"
    },
    {
        "faixa": (49.82, 49.90),
        "atos_validos": {"ato14448"},
        "descricao": "Controles e Brinquedos"
    },
    {
        "faixa": (40.66, 40.70),
        "atos_validos": {"ato14448"},
        "descricao": "Faixa 40.66-40.70 MHz"
    },

    # 2. Microfones sem Fio e Sistemas Específicos (Tabela XV e Ajustes)
    {
        "faixa": (43.7, 47.0),
        "atos_validos": {"ato14448"},
        "descricao": "Microfones e Sistemas Específicos"
    },
    {
        "faixa": (48.7, 50.0),
        "atos_validos": {"ato14448"},
        "descricao": "Microfones e Sistemas Específicos"
    },
    {
        "faixa": (54.0, 72.0),
        "atos_validos": {"ato14448"},
        "limite_eirp_mw": 50.0,
        "descricao": "Microfones sem fio"
    },
    {
        "faixa": (72.0, 73.0),
        "atos_validos": {"ato14448"},
        "descricao": "Controle / Telecomando / Microfones"
    },
    {
        "faixa": (74.6, 74.8),
        "atos_validos": {"ato14448"},
        "descricao": "Controle / Telecomando"
    },
    {
        "faixa": (75.2, 76.0),
        "atos_validos": {"ato14448"},
        "descricao": "Controle / Telecomando"
    },
    {
        "faixa": (76.0, 88.0),
        "atos_validos": {"ato14448"},
        "descricao": "Microfones sem fio"
    },
    {
        "faixa": (88.0, 108.0),
        "atos_validos": {"ato14448"},
        "descricao": "Sistemas de Radiodifusão / Restritos"
    },
    {
        "faixa": (174.0, 216.0),
        "atos_validos": {"ato14448"},
        "descricao": "Microfones sem fio"
    },
    {
        "faixa": (225.0, 270.0),
        "atos_validos": {"ato14448"},
        "ambiente_exigido": "indoor",
        "descricao": "Uso restrito em ambientes internos"
    },
    {
        "faixa": (470.0, 608.0),
        "atos_validos": {"ato14448"},
        "descricao": "Microfones sem fio UHF"
    },
    {
        "faixa": (614.0, 806.0),  # Redação dada pelo Ato 14448
        "atos_validos": {"ato14448"},
        "descricao": "Microfones sem fio (Faixa ampliada)"
    },
    {
        "faixa": (864.0, 868.0),
        "atos_validos": {"ato14448"},
        "descricao": "Sistemas de Curta Distância"
    },

    # 3. Telemedição de Características de Material (Item 8)
    {
        "faixa": (890.0, 907.5),
        "atos_validos": {"ato14448"},
        "vedacoes": ["voz", "mensagem"],
        "descricao": "Telemedição de material (Veda voz e mensagens)[cite: 1]"
    },
    {
        "faixa": (915.0, 940.0),
        "atos_validos": {"ato14448"},
        "vedacoes": ["voz", "mensagem"],
        "descricao": "Telemedição de material (Veda voz e mensagens)[cite: 1]"
    },

    # 4. Tecnologia de Espalhamento Espectral e Modulação Digital (Tabela I / Item 9.1.1)
    {
        "faixa": (902.0, 907.5),
        "atos_validos": {"ato14448"},
        "potencia_conduzida_max_dbm": 30.0,
        "descricao": "Espalhamento Espectral / ISM 902-907.5 MHz"
    },
    {
        "faixa": (915.0, 928.0),
        "atos_validos": {"ato14448"},
        "potencia_conduzida_max_dbm": 30.0,
        "descricao": "Espalhamento Espectral / ISM 915-928 MHz"
    },
    {
        "faixa": (2400.0, 2483.5),
        "atos_validos": {"ato14448"},
        "potencia_conduzida_max_dbm": 30.0,
        "descricao": "Industrial, Científica e Médica - 2.4 GHz"
    },
    {
        "faixa": (5725.0, 5875.0),
        "atos_validos": {"ato14448"},
        "potencia_conduzida_max_dbm": 30.0,
        "descricao": "Industrial, Científica e Médica - 5.8 GHz"
    },
    {
        "faixa": (24000.0, 24250.0),
        "atos_validos": {"ato14448"},
        "descricao": "Radiação Restrita - 24 GHz"
    },

    # 5. WLAN / Wi-Fi 5 GHz (Item 11.1.3 e Ato 14158)
    {
        "faixa": (5150.0, 5250.0),
        "atos_validos": {"ato14448", "ato423", "ato4776"},
        "ambiente_exigido": "indoor",
        "potencia_conduzida_max_dbm": 24.0,  # 250 mW[cite: 1]
        "descricao": "WLAN / Wi-Fi 5 GHz (Exclusivo Indoor)"
    },
    {
        "faixa": (5250.0, 5350.0),
        "atos_validos": {"ato14448", "ato14158"},
        "potencia_conduzida_max_dbm": 24.0,  # 250 mW[cite: 1]
        "descricao": "WLAN 5.25-5.35 GHz (Ato 14158)"
    },
    {
        "faixa": (5470.0, 5725.0),
        "atos_validos": {"ato14448", "ato4776"},
        "descricao": "WLAN com DFS (Ato 4776)"
    },

    # 6. Comunicação Veicular ITS (Ato 4776 / Ato 2506)
    {
        "faixa": (5855.0, 5925.0),
        "atos_validos": {"ato14448", "ato4776", "ato2506"},
        "eirp_max_dbm": 23.0,
        "descricao": "Comunicação Veicular ITS (Ato 4776)"
    },

    # 7. Faixa de 6 GHz Não Licenciada / Wi-Fi 6E-7 (Ato 423)
    {
        "faixa": (5925.0, 7125.0),
        "atos_validos": {"ato14448", "ato423"},
        "descricao": "Faixa de 6 GHz Não Licenciada / Wi-Fi 6E-7 (Ato 423)"
    },

    # 8. Ultra Larga Banda (UWB) e Imagens Médicas (Ato 423 / Tabela XIV)
    {
        "faixa": (3100.0, 3300.0),
        "atos_validos": {"ato14448", "ato423"},
        "eirp_pico_max_dbm": 0.0,
        "descricao": "UWB / Imagens Médicas (Ato 423)[cite: 1]"
    },
    {
        "faixa": (3700.0, 10600.0),
        "atos_validos": {"ato14448", "ato423"},
        "eirp_pico_max_dbm": 0.0,
        "descricao": "UWB / Imagens Médicas (Ato 423)[cite: 1]"
    },

    # 9. Sistemas Multigigabit sem Fio (57-71 GHz - Ato 4776)
    {
        "faixa": (57000.0, 71000.0),
        "atos_validos": {"ato14448", "ato4776"},
        "vedacoes": ["satelite"],
        "eirp_media_max_dbm": 40.0,  #[cite: 1]
        "eirp_pico_max_dbm": 43.0,   #[cite: 1]
        "descricao": "Sistema Multigigabit sem Fio 57-71 GHz (Vedado em satélites)[cite: 1]"
    },

    # 10. Radares e Nível Probing Radar (76-81 GHz - Ato 423 / Ato 14158)
    {
        "faixa": (76000.0, 81000.0),
        "atos_validos": {"ato14448", "ato423", "ato14158"},
        "descricao": "Radares / LPR / Radar Veicular (76-81 GHz)"
    },

    # 11. Sistemas de Alta Frequência / Ondas Milimétricas (Ato 14158)
    {
        "faixa": (116000.0, 123000.0),
        "atos_validos": {"ato14448", "ato14158"},
        "descricao": "Sistemas de Alta Frequência 116-123 GHz"
    },
    {
        "faixa": (174800.0, 182000.0),
        "atos_validos": {"ato14448", "ato14158"},
        "descricao": "Sistemas de Alta Frequência 174.8-182 GHz"
    },
    {
        "faixa": (185000.0, 190000.0),
        "atos_validos": {"ato14448", "ato14158"},
        "descricao": "Sistemas de Alta Frequência 185-190 GHz"
    },
    {
        "faixa": (244000.0, 246000.0),
        "atos_validos": {"ato14448", "ato14158"},
        "descricao": "Sistemas de Alta Frequência 244-246 GHz"
    }
]


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
            next(
                (r for r in BASE_REGRAS_UNIFICADAS if r["faixa"][0] <= freq <= r["faixa"][1]),
                None
            )
            for freq in frequencias
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
                regra_encontrada = next(
                    (
                        r for r in BASE_REGRAS_UNIFICADAS
                        if r["faixa"][0] <= frequencia <= r["faixa"][1]
                    ),
                    None
                )
                if regra_encontrada and not normas_ativas.intersection(regra_encontrada["atos_validos"]):
                    raise ValueError(
                        f"VIOLAÇÃO DE ESCOPO: A frequência informada exige referência aos atos "
                        f"{regra_encontrada['atos_validos']}, mas o contexto fornecido continha: "
                        f"{normas_ativas} (frequência: {frequencia} MHz)."
                    )
        return self