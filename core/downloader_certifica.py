import os
import re
import time
from playwright.sync_api import sync_playwright
from core.log_print import log_info, log_erro
from core.const import (
    CHROME_PATH, CHROME_ARGS, CERTIFICA_URL, CERTIFICA_TEXTO_LOGIN_OK,
    CERTIFICA_INTERVALO_MONITORAMENTO, CERTIFICA_DIV_POR_TIPO,
    CERTIFICA_SELETOR_CONTADOR, CERTIFICA_TIMEOUT_CONTADOR,
    CERTIFICA_ID_DIV_LISTA, CERTIFICA_CAMPOS_REQUERIMENTO,
    CERTIFICA_INDICE_PRIMEIRA_COLUNA, CERTIFICA_TIMEOUT_PAGINA,
    CERTIFICA_ABA_FABRICANTE, CERTIFICA_ABA_SOLICITANTE, CERTIFICA_ABA_PRODUTO,
    CERTIFICA_ABA_ESPECIFICACOES, CERTIFICA_ABA_LABORATORIO, CERTIFICA_ABA_CERTIFICADO,
    CERTIFICA_ROTULO_INICIO_OCD, CERTIFICA_CABECALHO_MODELOS,
    CERTIFICA_CABECALHO_FREQUENCIAS, CERTIFICA_CAMPOS_LABORATORIO,
    CERTIFICA_JS_LER_ABA, CERTIFICA_TIPOS_ANEXO_BAIXAR, CERTIFICA_ABA_ANEXOS,
    CERTIFICA_TEXTO_ANEXO_DESATIVADO, CERTIFICA_TIMEOUT_DOWNLOAD,
    CERTIFICA_JS_LER_ANEXOS, CARACTERES_INVALIDOS, SEPARADOR_LINHA,
    CERTIFICA_ABA_INFO_ADICIONAIS, FRASES
)
from core.utils import (
    get_profile_dir, criar_pasta_se_nao_existir, carregar_json, salvar_json,
    requerimento_ja_baixado, marcar_requerimento_em_progresso,
    obter_requerimentos_pendentes,
    marcar_requerimento_concluido, marcar_requerimento_com_erro,
)


def pagina_contem_texto(page, texto):
    """Verifica se o texto aparece na página ou em algum de seus frames."""
    for frame in page.frames:
        try:
            if texto in frame.inner_text("body", timeout=2000):
                return True
        except Exception:
            # Frame em navegação/recarga: tenta novamente no próximo ciclo
            continue
    return False


def aguardar_login_certifica(page):
    """Monitora a página até que o texto de login concluído seja exibido."""
    log_info(f"Aguardando login do usuário (monitorando '{CERTIFICA_TEXTO_LOGIN_OK}')...")
    while not pagina_contem_texto(page, CERTIFICA_TEXTO_LOGIN_OK):
        time.sleep(CERTIFICA_INTERVALO_MONITORAMENTO)
    log_info("Login identificado.")


def abrir_lista_certifica(page, tipo):
    """Clica no link da div correspondente ao tipo escolhido e aguarda a página carregar."""
    div_id = CERTIFICA_DIV_POR_TIPO[tipo]
    log_info(f"Abrindo lista do tipo {tipo}...")
    # O onclick (OsAjax) está no <a> dentro da div; clicar no centro da div pode errar o link
    page.click(f"#{div_id} a")
    page.wait_for_load_state("load")
    page.wait_for_load_state("networkidle")
    log_info("Página carregada.")


def obter_total_registros(page):
    """Lê o contador de registros ("NNNN registros") da página e retorna NNNN como inteiro."""
    contador = page.wait_for_selector(CERTIFICA_SELETOR_CONTADOR, timeout=CERTIFICA_TIMEOUT_CONTADOR)
    texto = contador.inner_text()
    # Em listas paginadas o texto é "1 a 50 de 780 registros": o total é o último número
    numeros = re.findall(r"\d+", texto)
    if not numeros:
        raise ValueError(f"Contador de registros em formato inesperado: '{texto}'")
    return int(numeros[-1])


def obter_requerimentos_certifica(page):
    """
    Lê a tabela de requerimentos da lista exibida e retorna uma lista de dicts.
    Usa as colunas de índice 2 a 9 (a partir de 0) e o href do link da primeira delas.
    """
    container = page.wait_for_selector(f"#{CERTIFICA_ID_DIV_LISTA}", timeout=CERTIFICA_TIMEOUT_CONTADOR)
    inicio = CERTIFICA_INDICE_PRIMEIRA_COLUNA
    fim = inicio + len(CERTIFICA_CAMPOS_REQUERIMENTO)
    requerimentos = []
    for linha in container.query_selector_all("tr"):
        # Linhas de cabeçalho usam <th> e não possuem <td>
        colunas = linha.query_selector_all("td")
        if len(colunas) < fim:
            continue

        valores = [coluna.inner_text().strip() for coluna in colunas[inicio:fim]]
        requerimento = dict(zip(CERTIFICA_CAMPOS_REQUERIMENTO, valores))

        link = colunas[inicio].query_selector("a")
        # A propriedade href retorna a URL absoluta, utilizável diretamente em page.goto
        requerimento["link"] = link.evaluate("a => a.href") if link else None
        requerimentos.append(requerimento)
    return requerimentos


def ler_requerimentos_do_tipo(page, tipo):
    """Abre a lista do tipo (1 ou 2) e retorna seus requerimentos (lista vazia se não houver)."""
    abrir_lista_certifica(page, tipo)
    total = obter_total_registros(page)
    log_info(f"{total} registros encontrados.")
    if total == 0:
        log_info("Não há requerimentos a analisar.")
        return []
    requerimentos = obter_requerimentos_certifica(page)
    log_info(f"{len(requerimentos)} requerimentos lidos da tabela.")
    return requerimentos


def pares_para_dict(pares):
    """Converte pares [rótulo, valor] em dict, removendo ':' final e ignorando rótulos vazios/repetidos."""
    dados = {}
    for rotulo, valor in pares:
        rotulo = rotulo.rstrip(":").strip()
        if rotulo and rotulo not in dados:
            dados[rotulo] = valor
    return dados


def tabela_por_cabecalho(aba, texto_cabecalho):
    """Retorna a primeira tabela da aba cujo cabeçalho contém o texto, convertida em lista de dicts."""
    for linhas in aba["tabelas"]:
        if not linhas or not any(texto_cabecalho in celula for celula in linhas[0]):
            continue
        cabecalho = linhas[0]
        registros = [dict(zip(cabecalho, linha)) for linha in linhas[1:] if len(linha) == len(cabecalho)]
        # Descarta linhas totalmente vazias (modelos de linha da página)
        return [r for r in registros if any(v for v in r.values())]
    return []


def ler_aba_certifica(page, sufixo):
    """Lê uma aba da página de análise; retorna {"pares": [...], "tabelas": [...]} (vazio se ausente)."""
    aba = page.evaluate(CERTIFICA_JS_LER_ABA, sufixo)
    if aba is None:
        log_erro(f"Aba '{sufixo}' não encontrada na página do requerimento.")
        return {"pares": [], "tabelas": [], "registros": []}
    return aba


def extrair_dados_requerimento_certifica(page):
    """
    Lê a página de análise do requerimento e retorna os blocos do JSON:
    ocd, lab, fabricante, solicitante, produto, modelos, frequencias e certificado.
    """
    aba_solicitante = ler_aba_certifica(page, CERTIFICA_ABA_SOLICITANTE)
    pares = aba_solicitante["pares"]
    rotulos = [rotulo for rotulo, _ in pares]
    # Antes do marcador: solicitante; depois: OCD
    corte = rotulos.index(CERTIFICA_ROTULO_INICIO_OCD) if CERTIFICA_ROTULO_INICIO_OCD in rotulos else len(pares)

    aba_produto = ler_aba_certifica(page, CERTIFICA_ABA_PRODUTO)
    aba_especificacoes = ler_aba_certifica(page, CERTIFICA_ABA_ESPECIFICACOES)
    aba_laboratorio = ler_aba_certifica(page, CERTIFICA_ABA_LABORATORIO)

    # Mesmo padrão do SCH: o nome do laboratório fica na chave "Nome" (primeiro registro da lista)
    lab = {}
    if aba_laboratorio["registros"]:
        lab = dict(zip(CERTIFICA_CAMPOS_LABORATORIO, aba_laboratorio["registros"][0]))

    return {
        "fabricante": pares_para_dict(ler_aba_certifica(page, CERTIFICA_ABA_FABRICANTE)["pares"]),
        "solicitante": pares_para_dict(pares[:corte]),
        "ocd": pares_para_dict(pares[corte + 1:]),
        "lab": lab,
        "produto": pares_para_dict(aba_produto["pares"]),
        "modelos": tabela_por_cabecalho(aba_produto, CERTIFICA_CABECALHO_MODELOS),
        "frequencias": tabela_por_cabecalho(aba_especificacoes, CERTIFICA_CABECALHO_FREQUENCIAS),
        "certificado": pares_para_dict(ler_aba_certifica(page, CERTIFICA_ABA_CERTIFICADO)["pares"]),
    }


def gravar_json_requerimento_certifica(requerimento, dados, pasta):
    """Grava (mesclando com o existente) o JSON do requerimento em <pasta>\\<nome sem '_'>.json."""
    caminho_json = os.path.join(pasta, f"{os.path.basename(pasta)[1:]}.json")
    conteudo = carregar_json(caminho_json) or {}
    conteudo["requerimento"] = {**conteudo.get("requerimento", {}), **requerimento}
    conteudo.update(dados)
    if not salvar_json(conteudo, caminho_json, indent=4):
        raise OSError(f"Não foi possível gravar {caminho_json}")
    log_info(f"JSON salvo: {caminho_json}")


def formatar_data_anexo(data_hora):
    """Converte 'dd/mm/aaaa hh:mm:ss' para 'aaaa.mm.dd HHhMMmSSs'; '0000.00.00' se a data for inválida."""
    match = re.search(r"(\d{2})/(\d{2})/(\d{4})(?:\s+(\d{2}):(\d{2}):(\d{2}))?", data_hora)
    if not match:
        return "0000.00.00"
    dia, mes, ano, hora, minuto, segundo = match.groups()
    data = f"{ano}.{mes}.{dia}"
    # Sem hora na página, mantém só a data
    return f"{data} {hora}h{minuto}m{segundo}s" if hora else data


def nome_arquivo_anexo(anexo):
    """Monta '[tipo][data][arquivo - descrição].pdf' com caracteres inválidos substituídos por '_'."""
    arquivo = os.path.splitext(anexo["arquivo"])[0]
    corpo = f"{arquivo} - {anexo['descricao']}" if anexo["descricao"] else arquivo
    nome = f"[{anexo['tipo']}][{formatar_data_anexo(anexo['data_hora'])}][{corpo}].pdf"
    return re.sub(CARACTERES_INVALIDOS, "_", nome)


def baixar_anexo_por_requisicao(page, link_id, destino):
    """
    Reproduz o __doPostBack do link via requisição HTTP com os cookies da sessão,
    sem acionar o download do navegador (que fechava o contexto). Retorna False se não aplicável.
    """
    alvo = page.evaluate(
        """id => {
            const link = document.getElementById(id);
            const m = link && (link.getAttribute('href') || '').match(/__doPostBack\\('([^']*)','([^']*)'\\)/);
            if (!m) return null;
            const form = link.closest('form') || document.forms[0];
            const campos = {};
            new FormData(form).forEach((v, k) => { if (typeof v === 'string') campos[k] = v; });
            campos['__EVENTTARGET'] = m[1];
            campos['__EVENTARGUMENT'] = m[2];
            return { acao: form.action || location.href, campos };
        }""",
        link_id,
    )
    if not alvo:
        return False
    resposta = page.context.request.post(
        alvo["acao"], form=alvo["campos"],         headers={"Referer": page.url},
                timeout=CERTIFICA_TIMEOUT_DOWNLOAD, ignore_https_errors=True,
            )
    conteudo = resposta.body()
    if not resposta.ok or "text/html" in resposta.headers.get("content-type", "") or not conteudo:
        return False
    with open(destino, "wb") as arquivo:
        arquivo.write(conteudo)
    return True


def baixar_anexo_por_clique(page, link_id, destino):
    """Alternativa: dispara o clique do link e salva o download do navegador."""
    with page.expect_download(timeout=CERTIFICA_TIMEOUT_DOWNLOAD) as download_info:
        page.evaluate("id => document.getElementById(id).click()", link_id)
    download_info.value.save_as(destino)


def baixar_anexos_certifica(page, pasta):
    """Baixa anexos para a pasta do requerimento, ignorando arquivos desativados."""
    anexos = page.evaluate(CERTIFICA_JS_LER_ANEXOS, [CERTIFICA_ABA_ANEXOS, CERTIFICA_TEXTO_ANEXO_DESATIVADO])
    if anexos is None:
        log_erro(f"Aba '{CERTIFICA_ABA_ANEXOS}' não encontrada na página do requerimento.")
        return 0, 1
    log_info(f"📎 {len(anexos)} anexo(s) listado(s) na aba Anexos")
    baixados = 0
    falhas = 0
    for anexo in anexos:
        if anexo["tipo"] not in CERTIFICA_TIPOS_ANEXO_BAIXAR:
            continue
        if anexo["desativado"]:
            continue
        destino = os.path.join(pasta, nome_arquivo_anexo(anexo))
        if os.path.exists(destino):
            log_info(f"⏭️ Arquivo já existe, pulando: {os.path.basename(destino)}")
            baixados += 1
            continue
        if page.is_closed():
            log_erro("A página do Certifica foi fechada; interrompendo download dos anexos.")
            return baixados, falhas + 1
        try:
            if not baixar_anexo_por_requisicao(page, anexo["link_id"], destino):
                baixar_anexo_por_clique(page, anexo["link_id"], destino)

            baixados += 1
            log_info(f"✅ Baixado: {os.path.basename(destino)}")
        except Exception as e:
            falhas += 1
            log_erro(f"Erro ao baixar anexo '{anexo['arquivo']}': {str(e)}")
    log_info(f"💾 Total de {baixados} PDF(s) salvos em: {pasta}")
    return baixados, falhas


def painel_aba_certifica(page, sufixo, rotulo):
    """Ativa a aba pelo rótulo e retorna o locator do seu painel."""
    page.locator("[role=tab]", has_text=rotulo).first.click()
    painel = page.locator(f'[id$="wttab_{sufixo}_block_wtContent"]')
    painel.locator('input[value="Editar"]').wait_for(state="visible", timeout=CERTIFICA_TIMEOUT_PAGINA)
    return painel


def editar_aba_certifica(painel):
    """Entra no modo de edição da aba e aguarda o postback terminar."""
    painel.locator('input[value="Editar"]').click()
    painel.locator('input[value="Salvar"]').wait_for(state="visible", timeout=CERTIFICA_TIMEOUT_PAGINA)


def salvar_aba_certifica(painel):
    """Clica em Salvar e aguarda a aba voltar ao modo leitura."""
    painel.locator('input[value="Salvar"]').click()
    painel.locator('input[value="Editar"]').wait_for(state="visible", timeout=CERTIFICA_TIMEOUT_PAGINA)


def cancelar_edicao_certifica(painel):
    """Sai do modo de edição sem salvar, se estiver nele."""
    try:
        cancelar = painel.locator('input[value="Cancelar Edição"]')
        if cancelar.count() and cancelar.first.is_visible():
            cancelar.first.click()
            painel.locator('input[value="Editar"]').wait_for(state="visible", timeout=CERTIFICA_TIMEOUT_PAGINA)
    except Exception:
        pass


def limpar_campo_aba_certifica(page, sufixo, rotulo_aba, seletor_campo, nome_campo):
    """Clica em Editar, limpa o campo se estiver preenchido e salva. Retorna False em caso de erro."""
    painel = None
    try:
        painel = painel_aba_certifica(page, sufixo, rotulo_aba)
        # O valor só é carregado no campo após entrar no modo de edição
        editar_aba_certifica(painel)
        campo = painel.locator(seletor_campo)
        campo.wait_for(state="visible", timeout=CERTIFICA_TIMEOUT_PAGINA)
        if not campo.input_value().strip():
            log_info(f"ℹ️ '{nome_campo}' já está vazio.")
            cancelar_edicao_certifica(painel)
            return True
        campo.fill("")
        salvar_aba_certifica(painel)
        log_info(f"✅ '{nome_campo}' limpo e salvo na aba '{rotulo_aba}'.")
        return True
    except Exception as e:
        log_erro(f"Falha ao limpar '{nome_campo}': {e}")
        if painel is not None:
            cancelar_edicao_certifica(painel)
        return False


def preencher_info_adicionais_certifica(page):
    """Marca 'Acompanhar o processo', preenche a justificativa, limpa a data de previsão e salva."""
    painel = None
    try:
        painel = painel_aba_certifica(page, CERTIFICA_ABA_INFO_ADICIONAIS, "Informações Adicionais")
        editar_aba_certifica(painel)
        painel.locator('input[type="checkbox"]').check()
        justificativa = painel.locator('textarea[id$="wtTextJustificativa"]')
        justificativa.wait_for(state="visible", timeout=CERTIFICA_TIMEOUT_PAGINA)
        page.wait_for_function(
            "el => !el.readOnly && !el.disabled",
            arg=justificativa.element_handle(),
            timeout=CERTIFICA_TIMEOUT_PAGINA,
        )
        justificativa.fill(FRASES["analise_simplificada"])
        data = painel.locator('input[id$="wtDataValidadeModelo2"]')
        if data.input_value().strip():
            data.fill("")
        salvar_aba_certifica(painel)
        log_info("✅ Aba 'Informações Adicionais' preenchida e salva.")
        return True
    except Exception as e:
        log_erro(f"Falha ao preencher 'Informações Adicionais': {e}")
        if painel is not None:
            cancelar_edicao_certifica(painel)
        return False


def ajustar_campos_certifica(page):
    """Limpa/preenche os campos exigidos nas abas. Retorna o número de falhas."""
    resultados = [
        limpar_campo_aba_certifica(
            page, CERTIFICA_ABA_ESPECIFICACOES, "Especificações",
            'textarea[id$="wtObsProduto"]', "Observações do Produto",
        ),
        preencher_info_adicionais_certifica(page),
        limpar_campo_aba_certifica(
            page, CERTIFICA_ABA_CERTIFICADO, "Certificado",
            'textarea[id$="AnaliseCertificadoCCT_wt45"]', "Especificações Complementares",
        ),
    ]
    return resultados.count(False)


def processar_requerimento_certifica(page, requerimento):
    """Cria a pasta do requerimento, abre seu link, lê os dados, grava o JSON e baixa os anexos."""
    num_req = requerimento["num_req"]
    if num_req.count("/") != 1:
        log_erro(f"Número de requerimento inválido (esperado 'num/ano'): '{num_req}'")
        return
    if requerimento_ja_baixado(num_req):
        log_info(f"✅ Requerimento {num_req} já baixado, pulando.")
        return
    marcar_requerimento_em_progresso(num_req)
    pasta = criar_pasta_se_nao_existir(num_req)
    if not requerimento.get("link"):
        log_erro(f"Requerimento {num_req} sem link para a página de análise.")
        return
    log_info(f"Lendo dados do requerimento {num_req}...")
    page.goto(requerimento["link"], timeout=CERTIFICA_TIMEOUT_PAGINA)
    page.get_by_text("N° do Processo SEI:").wait_for(
        state="visible",
        timeout=CERTIFICA_TIMEOUT_PAGINA,
    )
    gravar_json_requerimento_certifica(
        requerimento,
        extrair_dados_requerimento_certifica(page),
        pasta,
    )
    baixados, falhas = baixar_anexos_certifica(page, pasta)
    falhas_campos = ajustar_campos_certifica(page)
    if falhas:
        marcar_requerimento_com_erro(num_req, f"Falha ao baixar {falhas} anexo(s)")
        log_info(f"⚠️ Requerimento {num_req} marcado com erro por falhas no processamento dos anexos")
    elif falhas_campos:
        marcar_requerimento_com_erro(num_req, f"Falha ao ajustar {falhas_campos} aba(s) do Certifica")
        log_info(f"⚠️ Requerimento {num_req} marcado com erro por falhas no preenchimento das abas")
    else:
        marcar_requerimento_concluido(num_req, baixados)
        if baixados:
            log_info(f"✅ Requerimento {num_req} marcado como concluído ({baixados} arquivos)")
        else:
            log_info(f"✅ Requerimento {num_req} marcado como concluído (0 novos arquivos; anexos já existiam)")


def baixar_documentos_certifica(obter_tipo):
    """
    Abre o Certifica, aguarda o login do usuário e pergunta o tipo de download.
    obter_tipo: função que interage com o usuário e retorna o tipo escolhido (ou None).
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                get_profile_dir(),
                headless=False,
                executable_path=CHROME_PATH,
                args=CHROME_ARGS,
                accept_downloads=True,
            )
            page = browser.new_page()
            page.goto(CERTIFICA_URL)

            aguardar_login_certifica(page)

            tipo = obter_tipo()
            if tipo is None:
                browser.close()
                return

            # "Todos" lê primeiro os retornos para estudo (1) e depois os em análise (2)
            tipos_a_ler = ["1", "2"] if tipo == "3" else [tipo]
            requerimentos = []
            for tipo_atual in tipos_a_ler:
                requerimentos.extend(ler_requerimentos_do_tipo(page, tipo_atual))
            log_info(f"Total de requerimentos lidos: {len(requerimentos)}.")

            log_info(SEPARADOR_LINHA)
            log_info("🤖 DOWNLOAD CERTIFICA - ANEXOS")
            log_info(SEPARADOR_LINHA)
            log_info(f"🔎 {len(requerimentos)} requerimentos encontrados nas listas")

            # Como no SCH, requerimentos já concluídos no download_status.json são pulados
            pendentes = set(obter_requerimentos_pendentes([r["num_req"] for r in requerimentos]))
            requerimentos = [r for r in requerimentos if r["num_req"] in pendentes]

            if requerimentos:
                log_info(f"⏳ {len(requerimentos)} requerimento(s) serão processados")

            # Para cada requerimento: cria a pasta (ou renomeia, como no SCH), lê a página e grava o JSON
            for indice, requerimento in enumerate(requerimentos, start=1):
                log_info(SEPARADOR_LINHA)
                log_info(f"▶️  Requerimento {indice}: {requerimento['num_req']}")
                log_info(SEPARADOR_LINHA)
                try:
                    processar_requerimento_certifica(page, requerimento)
                except Exception as e:
                    log_erro(f"Erro ao processar requerimento {requerimento.get('num_req')}: {str(e)[:100]}")
                    marcar_requerimento_com_erro(requerimento.get("num_req"), str(e)[:200])

            log_info(SEPARADOR_LINHA)
            log_info("✅ PROCESSAMENTO CONCLUÍDO!")
            log_info(SEPARADOR_LINHA)

            # Mantém o navegador aberto até o usuário confirmar
            log_info("Pressione ENTER para encerrar...")
            input()
            if not browser.is_closed():
                browser.close()
    except Exception as e:
        log_erro(f"Erro no download do Certifica: {str(e)}")
