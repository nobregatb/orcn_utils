import os
from pathlib import Path
import sys, json
import time
import re
from openpyxl import load_workbook
from playwright.sync_api import sync_playwright
from datetime import datetime
from core.utils import carregar_log_downloads
from core.log_print import log_info, log_erro, log_erro_critico
from core.const import (
    BOTOES, CHROME_PATH, TBN_FILES_FOLDER, CHROME_PROFILE_DIR, 
    REQUERIMENTOS_DIR_INBOX, MOSAICO_BASE_URL, BOTOES_PDF, CHROME_ARGS,
    TIMEOUT_SESSAO_MFA, MAX_TENTATIVAS_BOTAO, MAX_TENTATIVAS_DOWNLOAD,
    EXCEL_SHEET_NAME, EXCEL_TABLE_NAME, STATUS_EM_ANALISE, STATUS_AUTOMATICO, 
    SEPARADOR_LINHA, MENSAGENS_STATUS, MENSAGENS_ERRO, CARACTERES_INVALIDOS, 
    FORMATO_NOME_ARQUIVO, CSS_SELECTORS, TAB_REQUERIMENTOS, TIPOS_DOCUMENTOS, FRASES
)
from core.utils import (
    is_bundled, get_files_folder, get_profile_dir, req_para_fullpath, 
    criar_pasta_se_nao_existir, carregar_json, salvar_json,
    requerimento_ja_baixado, marcar_requerimento_em_progresso,
    marcar_requerimento_concluido, marcar_requerimento_com_erro,
    obter_requerimentos_pendentes, limpar_log_downloads_se_completo, testar_radiacao_restrita
)


# Define FILES_FOLDER e PROFILE_DIR baseado no modo de execução
FILES_FOLDER = get_files_folder()
PROFILE_DIR = get_profile_dir()


def criar_json_dos_novos_requerimentos(rows):
    """Cria arquivos JSON para novos requerimentos"""
    for i, row in enumerate(rows, start=1):
        try:
            cols = row.query_selector_all("td") 
            dados = [col.inner_text().strip() for col in cols]
            # if dados[TAB_REQUERIMENTOS['status']] in STATUS_EM_ANALISE:
            if type(dados) == list and len(dados) > 0:
                # Cria um dicionário com os dados do requerimento usando TAB_REQUERIMENTOS
                requerimento_json = {}                
                for atributo, indice in TAB_REQUERIMENTOS.items():
                    if indice < len(dados):
                        valor = dados[indice]
                        # Se o valor contém '\n', cria um array de elementos
                        if '\n' in valor:
                            requerimento_json[atributo] = [item.strip() for item in valor.split('\n') if item.strip()]
                        else:
                            requerimento_json[atributo] = valor
                    else:
                        requerimento_json[atributo] = ""
                
                # Validação crítica dos dados do requerimento
                from core.utils import validar_dados_criticos
                validar_dados_criticos(
                    requerimento_json=requerimento_json,
                    nome_requerimento=requerimento_json.get('num_req', 'DESCONHECIDO'),
                    contexto="criação de JSON de novos requerimentos"
                )
                
                pasta = criar_pasta_se_nao_existir(requerimento_json['num_req'])
                nome_pasta = os.path.basename(pasta)
                dados_json = {}
                dados_json["requerimento"] = requerimento_json
                with open(os.path.join(pasta, f"{nome_pasta[1:]}.json"), "w", encoding="utf-8") as f:
                    json.dump(dados_json, f, ensure_ascii=False, indent=4)
        except Exception as e:
            log_erro(f"Erro ao ler linha {i}: {str(e)[:50]}")

    log_info(f"Total de requerimentos processados e arquivos JSON salvos!")


def wait_primefaces_ajax(page, timeout=5000):
    """Espera todas as requisições AJAX do PrimeFaces terminarem"""
    try:
        page.wait_for_function(
            """() => {
                if (typeof PrimeFaces === 'undefined') return true;
                if (!PrimeFaces.ajax) return true;
                if (!PrimeFaces.ajax.Queue) return true;
                return PrimeFaces.ajax.Queue.isEmpty();
            }""",
            timeout=timeout
        )
    except:
        pass
    time.sleep(0.3)


def primefaces_click(page, element, description="elemento"):
    """
    Clica em botões submit do PrimeFaces (type="submit").
    Esses botões precisam submeter o formulário via AJAX.
    """
    
    # Scroll até o elemento
    try:
        element.scroll_into_view_if_needed()
        time.sleep(0.3)
    except:
        pass
    
    # MÉTODO 1: Executa o onclick diretamente se existir
    try:
        onclick_executed = page.evaluate("""(button) => {
            const onclick = button.getAttribute('onclick');
            if (onclick) {
                try:
                    // Executa o código onclick
                    eval(onclick);
                    return true;
                } catch (e) {
                    console.error('Erro ao executar onclick:', e);
                    return false;
                }
            }
            return false;
        }""", element)
        
        if onclick_executed:
            log_info("✅ Onclick executado diretamente")
            time.sleep(1)
            return True
    except Exception as e:
        X = 1#log_erro(f"Onclick falhou: {str(e)[:50]}")
    
    # MÉTODO 2: Submit via PrimeFaces.ajax.Request
    try:
        success = page.evaluate("""(button) => {
            try:
                const form = button.closest('form');
                if (!form) return false;
                
                // Cria input hidden com dados do botão
                const hiddenInput = document.createElement('input');
                hiddenInput.type = 'hidden';
                hiddenInput.name = button.name || button.id;
                hiddenInput.value = button.value || button.id;
                form.appendChild(hiddenInput);
                
                // Usa PrimeFaces.ajax.Request se disponível
                if (typeof PrimeFaces !== 'undefined' && PrimeFaces.ajax && PrimeFaces.ajax.Request) {
                    const options = {
                        source: button.id,
                        process: button.id,
                        update: '@form',
                        formId: form.id,
                        params: []
                    };
                    
                    const paramObj = {};
                    paramObj[button.name || button.id] = button.value || button.id;
                    options.params.push(paramObj);
                    
                    PrimeFaces.ajax.Request.handle(options);
                    return true;
                }
                
                // Fallback: dispara submit
                const submitEvent = new Event('submit', {
                    bubbles: true,
                    cancelable: true
                });
                
                form._submitButton = button;
                form.dispatchEvent(submitEvent);
                
                if (!submitEvent.defaultPrevented) {
                    if (typeof jsf !== 'undefined' && jsf.ajax && jsf.ajax.request) {
                        jsf.ajax.request(button, null, {
                            'javax.faces.behavior.event': 'action'
                        });
                        return true;
                    }
                    form.submit();
                }
                
                return true;
            } catch (e) {
                console.error('Erro ao submeter:', e);
                return false;
            }
        }""", element)
        
        if success:
            log_info("✅ Aguardando resposta do Mosaico...")
            time.sleep(1)
            return True
        else:
            log_erro("Submit falhou")
    except Exception as e:
        x = 1 #log_erro(f"Erro: {str(e)[:80]}")
    
    # MÉTODO 3: Force click como último recurso
    try:
        #log_info("🔄 Tentando force click...")
        element.click(force=True, timeout=5000)
        #log_info("✅ Force click funcionou")
        time.sleep(1)
        return True
    except Exception as e:
        log_erro(f"Force click falhou: {str(e)[:50]}")
    
    return False


def preencher_minuta(page, rad_restrita: bool = True):
    """
    Preenche os formulários de características técnicas e informações adicionais

    Args:
        page: Objeto page do Playwright para navegação
        rad_restrita: Indica se a radiação restrita deve ser preenchida
    """
    try:
        # ========================
        # PARTE 1: CARACTERÍSTICAS TÉCNICAS
        # ========================
        # Clica no botão de características técnicas
        btn_carac = page.get_by_role("button", name=BOTOES['caracteristicas'])
        if btn_carac.count() > 0 and rad_restrita:
            btn_carac.click(no_wait_after=True)            
            # Aguarda carregamento
            page.wait_for_selector(".ui-blockui", state="detached", timeout=15000)
            wait_primefaces_ajax(page)
            #time.sleep(1)            
            # Busca e preenche o textarea
            try:
                #observação sobre radiação restrita
                page.fill("textarea:visible", FRASES['radiacao_Restrita_ct'])
                # Clica no botão salvar
                botao_salvar = page.get_by_role("button", name="Salvar") 
                if botao_salvar:                                                        
                    page.evaluate("""
                        const btn = document.getElementById('formAnalise:j_idt925');
                        btn.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                        btn.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                        btn.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                    """)
                    time.sleep(2)
                else:
                    log_erro("❌ Botão salvar características não encontrado")
            except Exception as e:
                log_erro(f"❌ Erro ao preencher características: {str(e)[:500]}")
        
        # ========================
        # PARTE 2: INFORMAÇÕES ADICIONAIS
        # ========================
        log_info("📋 Acessando Informações Adicionais...")
        
        # Clica no botão de informações adicionais
        time.sleep(3)
        btn_infos = page.get_by_role("button", name=BOTOES['infos_adicionais'])
        
        while btn_infos.count() == 0:
            btn_infos = page.get_by_role("button", name=BOTOES['infos_adicionais'])

        btn_infos.click(no_wait_after=True)
        
        # Aguarda carregamento
        page.wait_for_selector(".ui-blockui", state="detached", timeout=15000)
        wait_primefaces_ajax(page)
        time.sleep(1)
        
        log_info("✅ Página de Informações Adicionais carregada")
        
        # Ativa o checkbox
        try:            
            checkbox_div = page.query_selector("#formAnalise\\:checkBoxAcompanharProcesso")
            while not checkbox_div:
                checkbox_div = page.query_selector("#formAnalise\\:checkBoxAcompanharProcesso")
            if checkbox_div:
                # Clica na div do checkbox para ativá-lo
                checkbox_box = checkbox_div.query_selector(".ui-chkbox-box")
                is_checked = checkbox_box.evaluate("el => el.classList.contains('ui-state-active')")
                if not is_checked:
                    if checkbox_box:
                        checkbox_box.click()
                        log_info("✅ Checkbox ativado")
                        time.sleep(1)
                    else:
                        log_erro("❌ Elemento checkbox-box não encontrado")
                    # Preenche o textarea das informações adicionais
                    try:
                        textarea_infos = page.query_selector("#formAnalise\\:textAreaAcompanhar")
                        if textarea_infos:                    
                            page.fill("#formAnalise\\:textAreaAcompanhar", FRASES['analise_simplificada'])
                            log_info("✅ Textarea de informações adicionais preenchido")                    
                            # Clica no botão salvar informações adicionais
                            botao_salvar_infos = page.get_by_role("button", name="Salvar")
                            if botao_salvar_infos:
                                botao_salvar_infos.click(force=True, timeout=8000)
                                log_info("✅ Informações adicionais salvas")
                                time.sleep(2)
                                wait_primefaces_ajax(page)
                            else:
                                    log_erro("❌ Falha ao salvar informações adicionais")
                        else:
                            log_erro("❌ Textarea de informações adicionais não encontrado")
                    except Exception as e:
                        log_erro(f"❌ Erro ao preencher informações adicionais: {str(e)[:50]}")
            else:
                log_erro("❌ Checkbox não encontrado")
        except Exception as e:
            log_erro(f"❌ Erro ao ativar checkbox: {str(e)[:50]}")            
        
        log_info("📝 Preenchimento de minuta concluído")
        
    except Exception as e:
        log_erro(f"❌ Erro crítico no preenchimento de minuta: {str(e)[:80]}")


def solicitar_reautenticacao_mfa():
    """
    Solicita ao usuário que faça re-autenticação MFA
    Retorna quando o usuário confirmar que concluiu
    """
    log_info(SEPARADOR_LINHA)
    log_info("🔐 REAUTENTICAÇÃO MFA NECESSÁRIA")
    log_info(SEPARADOR_LINHA)
    log_info("⏰ Passaram-se mais de 30 minutos desde o primeiro download")
    log_info("🔑 Por favor, realize a autenticação MFA no navegador")
    log_info("✅ Pressione ENTER quando tiver concluído a autenticação")
    log_info(SEPARADOR_LINHA)
    input()
    log_info("✅ Continuando processamento de downloads...")


def baixar_pdfs(page, requerimento, tempo_primeiro_download):
    """
    Baixa todos os PDFs da página de anexos com retry inteligente
    
    Args:
        page: Objeto page do Playwright
        requerimento: Número do requerimento (formato XX/XXXXX)
        tempo_primeiro_download: Tempo do primeiro download bem-sucedido (None se ainda não houve)
    
    Returns:
        tuple: (total_pdfs_baixados, tempo_primeiro_download_atualizado, requer_reautenticacao)
    """
    num, ano = requerimento.split("/")
    
    # Cria a pasta do requerimento se não existir
    pasta_destino = criar_pasta_se_nao_existir(requerimento)
    
    total_pdfs_baixados = 0
    requer_reautenticacao = False
    
    # Percorre cada botão para revelar PDFs
    for nome_botao in BOTOES_PDF:
        tentativa_botao = 0
        sucesso_botao = False
        
        # Retry para cada botão
        while tentativa_botao < MAX_TENTATIVAS_BOTAO and not sucesso_botao:
            tentativa_botao += 1
            
            try:
                # Busca o botão pelo nome/texto
                botao = page.get_by_role("button", name=nome_botao)
                
                # Verifica se o botão NÃO existe - indica erro
                if botao.count() == 0:
                    log_erro(f"❌ Botão '{nome_botao}' não encontrado (tentativa {tentativa_botao}/{MAX_TENTATIVAS_BOTAO})")
                    
                    # Verifica se passou de 30 minutos desde o primeiro download
                    if tempo_primeiro_download is not None:
                        tempo_decorrido = time.time() - tempo_primeiro_download
                        if tempo_decorrido > TIMEOUT_SESSAO_MFA:
                            log_info(f"⏰ Mais de 30 minutos desde o primeiro download ({int(tempo_decorrido // 60)} min)")
                            solicitar_reautenticacao_mfa()
                            # Zera o contador após re-autenticação
                            tempo_primeiro_download = time.time()
                    
                    # Aguarda antes de tentar novamente
                    time.sleep(2)
                    continue
                
                # Clica no botão para revelar PDFs
                log_info(f"🎯 Buscando: {nome_botao}")
                botao.first.click()
                
                # Aguarda o carregamento dos PDFs
                time.sleep(1)
                wait_primefaces_ajax(page)
                
                # Busca todos os links de PDF que foram revelados
                pdf_links = page.query_selector_all("a[href*='.pdf'], a[href*='download']")
                
                # Extrai informações da tabela
                tabela = page.query_selector("table.analiseTable")
                linhas_dados = []
                
                if tabela:
                    # Pega todas as linhas da tabela (exceto cabeçalho)
                    linhas = tabela.query_selector_all("tr")
                    
                    # Identifica o cabeçalho (primeira linha)
                    if len(linhas) > 0:
                        cabecalho = linhas[0].query_selector_all("th, td")
                        headers = [col.inner_text().strip() for col in cabecalho]
                        
                        # Processa as linhas de dados (exceto cabeçalho)
                        for linha in linhas[1:]:
                            colunas = linha.query_selector_all("th, td")
                            dados = [col.inner_text().strip() for col in colunas]
                            
                            if len(dados) >= len(headers):
                                linha_info = {}
                                for i, header in enumerate(headers):
                                    if i < len(dados):
                                        linha_info[header] = dados[i]
                                linhas_dados.append(linha_info)
                
                if pdf_links:
                    log_info(f"📄 {len(pdf_links)} PDF(s) encontrado(s) para {nome_botao}")
                    
                    # Verifica se há correspondência entre PDFs e linhas da tabela
                    if len(pdf_links) != len(linhas_dados):
                        log_info(f"⚠ AVISO: {len(pdf_links)} PDFs mas {len(linhas_dados)} linhas na tabela!")
                    
                    # Conta quantos PDFs foram processados (baixados ou já existentes)
                    pdfs_processados_neste_botao = 0
                    
                    # Baixa cada PDF encontrado
                    for idx, link in enumerate(pdf_links):
                        tentativa_download = 0
                        download_bem_sucedido = False
                        
                        while tentativa_download < MAX_TENTATIVAS_DOWNLOAD and not download_bem_sucedido:
                            tentativa_download += 1
                            
                            try:
                                # Verifica se o link está visível/disponível
                                if not link.is_visible():
                                    break
                                
                                # Pega informações da linha correspondente da tabela
                                linha_info = None
                                if idx < len(linhas_dados):
                                    linha_info = linhas_dados[idx]
                                
                                # Gera nome do arquivo baseado nas informações da tabela (ANTES do download)
                                nome_arquivo_temp = f"anexo_{idx + 1}.pdf"  # Nome temporário padrão
                                
                                if linha_info:
                                    try:
                                        # Extrai informações da tabela
                                        doc_id = linha_info.get("ID", f"#{idx + 1}")
                                        tipo_doc = linha_info.get("Tipo de Documento", "Documento")
                                        data_hora = linha_info.get("Data - Hora", "")
                                        
                                        # Processa a data para formato yyyy.mm.dd
                                        data_formatada = ""
                                        if data_hora:
                                            try:
                                                # Remove espaços extras e separa data da hora
                                                data_parte = data_hora.split()[0] if data_hora else ""
                                                
                                                # Padrões de data comuns
                                                padroes = [
                                                    r"(\d{2})/(\d{2})/(\d{4})",  # dd/mm/yyyy
                                                    r"(\d{4})-(\d{2})-(\d{2})",  # yyyy-mm-dd
                                                    r"(\d{2})-(\d{2})-(\d{4})",  # dd-mm-yyyy
                                                ]
                                                
                                                for padrao in padroes:
                                                    match = re.search(padrao, data_parte)
                                                    if match:
                                                        if padrao == padroes[0] or padrao == padroes[2]:  # dd/mm/yyyy ou dd-mm-yyyy
                                                            dia, mes, ano_data = match.groups()
                                                        else:  # yyyy-mm-dd
                                                            ano_data, mes, dia = match.groups()
                                                        
                                                        data_formatada = f"{ano_data}.{mes.zfill(2)}.{dia.zfill(2)}"
                                                        break
                                                
                                                if not data_formatada:
                                                    data_formatada = "0000.00.00"
                                            except Exception as e:
                                                data_formatada = "0000.00.00"
                                                log_erro(f"Erro ao processar data: {str(e)[:50]}")
                                        else:
                                            data_formatada = "0000.00.00"
                                        
                                        # Limpa caracteres inválidos para nome de arquivo
                                        tipo_doc_limpo = re.sub(CARACTERES_INVALIDOS, '_', tipo_doc)
                                        doc_id_limpo = re.sub(CARACTERES_INVALIDOS, '_', str(doc_id))
                                        
                                        # Monta o novo nome: [tipo][data - ID id] nome_original [req num de ano].ext
                                        nome_arquivo_temp = f"[{tipo_doc_limpo}][{data_formatada} - ID {doc_id_limpo}] temp [req {num} de {ano}].pdf"
                                        
                                    except Exception as e:
                                        log_erro(f"Erro ao processar informações da tabela: {str(e)[:50]}")
                                        # Fallback para nome simples
                                        nome_arquivo_temp = f"[{nome_botao}] anexo_{idx + 1}.pdf"
                                else:
                                    # Fallback quando não há informação da tabela
                                    nome_arquivo_temp = f"[{nome_botao}] anexo_{idx + 1}.pdf"
                                
                                # Procura por arquivos existentes que começem com o mesmo padrão
                                nome_base_busca = nome_arquivo_temp.split('] temp [')[0] + ']'  # Remove "temp" e tudo depois
                                arquivos_existentes = [f for f in os.listdir(pasta_destino) if f.startswith(nome_base_busca)]
                                
                                if arquivos_existentes:
                                    #log_info(f"⏭️ Arquivo já existe, pulando: {arquivos_existentes[0]}")
                                    download_bem_sucedido = True  # Marca como sucesso para não tentar novamente
                                    pdfs_processados_neste_botao += 1  # Conta como processado
                                    break
                                
                                # Se não existe, faz o download
                                with page.expect_download() as download_info:
                                    link.click()
                                
                                download = download_info.value
                                
                                # Pega o nome real do arquivo baixado
                                nome_arquivo_real = download.suggested_filename
                                if not nome_arquivo_real or nome_arquivo_real == "":
                                    nome_arquivo_real = f"anexo_{idx + 1}.pdf"
                                
                                # Extrai nome base e extensão do arquivo real
                                nome_base_real, extensao_real = os.path.splitext(nome_arquivo_real)
                                
                                # Monta o nome final usando o nome real do arquivo
                                if linha_info:
                                    try:
                                        doc_id = linha_info.get("ID", f"#{idx + 1}")
                                        tipo_doc = linha_info.get("Tipo de Documento", "Documento")
                                        data_hora = linha_info.get("Data - Hora", "")
                                        
                                        # Usa a mesma lógica de formatação de data
                                        data_formatada = "0000.00.00"
                                        if data_hora:
                                            data_parte = data_hora.split()[0] if data_hora else ""
                                            padroes = [
                                                r"(\d{2})/(\d{2})/(\d{4})",
                                                r"(\d{4})-(\d{2})-(\d{2})",
                                                r"(\d{2})-(\d{2})-(\d{4})",
                                            ]
                                            for padrao in padroes:
                                                match = re.search(padrao, data_parte)
                                                if match:
                                                    if padrao == padroes[0] or padrao == padroes[2]:
                                                        dia, mes, ano_data = match.groups()
                                                    else:
                                                        ano_data, mes, dia = match.groups()
                                                    data_formatada = f"{ano_data}.{mes.zfill(2)}.{dia.zfill(2)}"
                                                    break
                                        
                                        tipo_doc_limpo = re.sub(CARACTERES_INVALIDOS, '_', tipo_doc)
                                        doc_id_limpo = re.sub(CARACTERES_INVALIDOS, '_', str(doc_id))
                                        
                                        nome_arquivo_final = f"[{tipo_doc_limpo}][{data_formatada} - ID {doc_id_limpo}] {nome_base_real} [req {num} de {ano}]{extensao_real}"
                                    except:
                                        nome_arquivo_final = f"[{nome_botao}] {nome_base_real}{extensao_real}"
                                else:
                                    nome_arquivo_final = f"[{nome_botao}] {nome_base_real}{extensao_real}"
                                
                                # Salva o arquivo com o nome final
                                caminho_completo = os.path.join(pasta_destino, nome_arquivo_final)
                                download.save_as(caminho_completo)
                                
                                log_info(f"✅ Baixado: {nome_arquivo_final}")
                                total_pdfs_baixados += 1
                                pdfs_processados_neste_botao += 1  # Conta como processado
                                download_bem_sucedido = True
                                
                                # Marca o tempo do primeiro download
                                if tempo_primeiro_download is None:
                                    tempo_primeiro_download = time.time()
                                    log_info("⏱️ Primeiro download realizado - iniciando contagem de tempo")
                                
                            except Exception as e:
                                log_erro(f"❌ Erro ao baixar PDF {idx + 1} de {nome_botao} (tent {tentativa_download}/{MAX_TENTATIVAS_DOWNLOAD}): {str(e)[:50]}")
                                
                                # Verifica se passou de 30 minutos desde o primeiro download
                                if tempo_primeiro_download is not None:
                                    tempo_decorrido = time.time() - tempo_primeiro_download
                                    if tempo_decorrido > TIMEOUT_SESSAO_MFA:
                                        log_info(f"⏰ Mais de 30 minutos desde o primeiro download ({int(tempo_decorrido // 60)} min)")
                                        solicitar_reautenticacao_mfa()
                                        # Zera o contador após re-autenticação
                                        tempo_primeiro_download = time.time()
                                
                                if tentativa_download < MAX_TENTATIVAS_DOWNLOAD:
                                    log_info(f"🔄 Tentando novamente em 2 segundos...")
                                    time.sleep(2)
                    
                    # Verifica se todos os PDFs esperados foram processados (baixados ou já existentes)
                    if len(pdf_links) > 0 and pdfs_processados_neste_botao == len(pdf_links):
                        sucesso_botao = True
                        log_info(f"✅ Todos os {len(pdf_links)} PDFs foram processados com sucesso")
                    elif len(pdf_links) > 0 and pdfs_processados_neste_botao > 0:
                        # Alguns arquivos foram processados, mas não todos
                        log_erro(f"⚠️ Esperava processar {len(pdf_links)} PDFs, mas apenas {pdfs_processados_neste_botao} foram processados")
                    elif len(pdf_links) > 0:
                        # Nenhum arquivo foi processado
                        log_erro(f"❌ Nenhum dos {len(pdf_links)} PDFs foi processado")
                    
                else:
                    log_info(f"ℹ️ Nenhum PDF encontrado para: {nome_botao}")
                    sucesso_botao = True  # Não há PDFs, então não precisa tentar novamente
                    
            except Exception as e:
                log_erro(f"❌ Erro ao processar botão {nome_botao} (tentativa {tentativa_botao}/{MAX_TENTATIVAS_BOTAO}): {str(e)[:50]}")
                
                # Verifica se passou de 30 minutos desde o primeiro download
                if tempo_primeiro_download is not None:
                    tempo_decorrido = time.time() - tempo_primeiro_download
                    if tempo_decorrido > TIMEOUT_SESSAO_MFA:
                        log_info(f"⏰ Mais de 30 minutos desde o primeiro download ({int(tempo_decorrido // 60)} min)")
                        solicitar_reautenticacao_mfa()
                        # Zera o contador após re-autenticação
                        tempo_primeiro_download = time.time()
                
                if tentativa_botao < MAX_TENTATIVAS_BOTAO:
                    log_info(f"🔄 Tentando botão novamente em 2 segundos...")
                    time.sleep(2)
    
    if total_pdfs_baixados > 0:
        #log_info("⚠️ Nenhum PDF foi baixado")
    #else:
        log_info(f"💾 Total de {total_pdfs_baixados} PDF(s) salvos em: {pasta_destino}")
    
    return total_pdfs_baixados, tempo_primeiro_download, requer_reautenticacao


def abrir_caixa_de_entrada(page_obj, retorno_para_estudo=False):
    """Navega para a lista de requerimentos e configura visualização"""
    # Navega para a lista
    lista_url = f"{MOSAICO_BASE_URL}"
    page_obj.goto(lista_url)
    page_obj.wait_for_load_state("load")

    # Clica em "Em Análise"
    if not retorno_para_estudo:
        page_obj.click(CSS_SELECTORS['menu_emAnalise'], timeout=3600000) 
        
    else:  # Clica em "Retorno para Estudo"
        page_obj.click(CSS_SELECTORS['menu_retornoParaEstudo'], timeout=3600000) 

    page_obj.wait_for_load_state("load")
    
    # Seleciona 100 itens por página e aguarda atualização
    page_obj.select_option("select.ui-paginator-rpp-options", value="100")
    time.sleep(2) 
    page_obj.wait_for_load_state("networkidle")  # Aguarda requisições AJAX terminarem
    wait_primefaces_ajax(page_obj)    

    return page_obj


def baixar_documentos(RETORNO_PARA_ESTUDO):
    """Função principal que baixa documentos dos requerimentos ORCN"""
    try:
        log_info(MENSAGENS_STATUS['iniciando_automacao'])
        
        # Mostra informações do log de downloads se existir
        
        log_downloads = carregar_log_downloads()
        if log_downloads:
            log_info(f"📋 Log de downloads encontrado com {len(log_downloads)} requerimento(s) registrado(s)")
            concluidos = sum(1 for status in log_downloads.values() if status.get('status') == 'completed')
            if concluidos > 0:
                log_info(f"✅ {concluidos} requerimento(s) já baixado(s) com sucesso")
        
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                PROFILE_DIR,
                headless=False,
                executable_path=CHROME_PATH,
                args=CHROME_ARGS,
                accept_downloads=True  # IMPORTANTE: permite downloads
            )
            
            page = browser.new_page()
            
            # Controle de tempo - inicia apenas após o primeiro download
            tempo_primeiro_download = None
            
            # Navega para a lista
            page = abrir_caixa_de_entrada(page,retorno_para_estudo=RETORNO_PARA_ESTUDO)
            
            log_info(SEPARADOR_LINHA)
            log_info("🤖 AUTOMAÇÃO ORCN - DOWNLOAD DE ANEXOS")
            log_info(SEPARADOR_LINHA)
            
            # Seleciona todas as linhas
            if RETORNO_PARA_ESTUDO==False:
                rows = page.query_selector_all(CSS_SELECTORS['tabela_dados_em_analise'])                
            else:
                rows = page.query_selector_all(CSS_SELECTORS['tabela_dados'])
            log_info(f"🔎 {len(rows)} linhas encontradas na tabela")
            
            criar_json_dos_novos_requerimentos(rows)

            # Cria um dicionário com os dados de cada linha ANTES de iterar
            log_info("📋 Mapeando requerimentos...")
            linhas_dados = []
            todos_requerimentos = []
            
            for i, row in enumerate(reversed(rows), start=1):
                try:
                    cols = row.query_selector_all("td")
                    dados = [col.inner_text().strip() for col in cols]
                    if (len(cols) < 2):# or (dados[TAB_REQUERIMENTOS['status']] not in STATUS_EM_ANALISE):
                        continue
                    
                    requerimento = cols[1].inner_text().strip()
                    todos_requerimentos.append(requerimento)
                    
                    # Armazena os dados da linha
                    linhas_dados.append({
                        'indice': i,
                        'requerimento': requerimento,
                        'row': row
                    })
                except Exception as e:
                    log_erro(f"Erro ao ler linha {i}: {str(e)[:50]}")

            log_info(f"✅ {len(linhas_dados)} requerimentos mapeados")
            
            # Filtra requerimentos que já foram baixados com sucesso
            requerimentos_pendentes = obter_requerimentos_pendentes(todos_requerimentos)
            
            # Se não há requerimentos pendentes, finaliza
            if not requerimentos_pendentes:
                log_info("🎉 Todos os requerimentos já foram baixados com sucesso!")
                limpar_log_downloads_se_completo(todos_requerimentos)
                log_info("Pressione ENTER para encerrar...")
                input()
                browser.close()
                return
            
            # Filtra linhas_dados para incluir apenas requerimentos pendentes
            linhas_dados = [linha for linha in linhas_dados if linha['requerimento'] in requerimentos_pendentes]
            log_info(f"⏳ {len(linhas_dados)} requerimento(s) serão processados")

            # Processa cada linha dos dados salvos
            requerimentos_processados = []
            
            for linha_info in linhas_dados:
                i = linha_info['indice']
                requerimento = linha_info['requerimento']
                
                log_info(SEPARADOR_LINHA)
                log_info(f"▶️  Requerimento {i}: {requerimento}")
                log_info(SEPARADOR_LINHA)
                
                # Marca o requerimento como em progresso no log
                marcar_requerimento_em_progresso(requerimento)
                
                # IMPORTANTE: Recarrega a linha atual usando busca manual
                row_atual = None
                try:
                    # Recarrega todas as linhas da tabela
                    if RETORNO_PARA_ESTUDO==False:
                        linhas_atualizadas = page.query_selector_all(CSS_SELECTORS['tabela_dados_em_analise'])
                    else:
                        linhas_atualizadas = page.query_selector_all(CSS_SELECTORS['tabela_dados'])
                                    
                    
                    # Procura manualmente pela linha com o requerimento
                    for idx, linha in enumerate(linhas_atualizadas):
                        try:
                            cols = linha.query_selector_all("td")
                            if len(cols) >= 2:
                                requerimento_da_linha = cols[1].inner_text().strip()
                                if requerimento_da_linha == requerimento:
                                    row_atual = linha
                                    break
                        except:
                            continue
                    
                    if not row_atual:
                        log_info(f"⚠️ Requerimento {requerimento} não encontrado na lista atualizada, pulando...")
                        continue
                        
                except Exception as e:
                    log_erro(f"Erro ao recarregar linhas: {str(e)[:50]}, pulando...")
                    continue
                
                # Busca botão "Visualizar em Tela cheia" na linha atual 
                btn = row_atual.query_selector("button[type='submit'][title='Visualizar em Tela cheia']")
                if not btn:
                    btn = row_atual.query_selector("button[title*='Tela cheia']")
                
                if not btn:
                    log_info("⚠️ Botão não encontrado, pulando...")
                    continue
                
                # Clica no botão
                if not primefaces_click(page, btn, "Visualizar em Tela cheia"):
                    log_info("⚠️ Não foi possível clicar, pulando...")
                    continue
                
                # Aguarda carregar
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except:
                    pass
                wait_primefaces_ajax(page)
                
                time.sleep(1)
                
                iframe_element = page.wait_for_selector("#__frameDetalhe", timeout=10000)

                if iframe_element:
                    detalhes_requerimento = iframe_element.get_attribute("src")
                    if detalhes_requerimento:
                        page.goto(detalhes_requerimento)
                        
                        # Recupera dados do solicitante, fabricante, laboratório e OCD
                        log_info("📊 Coletando dados adicionais do requerimento...")
                        solicitante_id = "formAnalise:output-solicitante-requerimento:output-solicitante-requerimento"
                        selector = "#" + solicitante_id.replace(":", "\\:")
                        try:
                            dados_solicitante = page.eval_on_selector(selector, """
                                (t) => {
                                    const linhas = Array.from(t.querySelectorAll("tr"));
                                    const resultado = {};
                                    for (const tr of linhas) {
                                        const celulas = tr.querySelectorAll("td");
                                        if (celulas.length === 2) {
                                            const chave = celulas[0].innerText.trim().replace(/:$/, '');
                                            const valor = celulas[1].innerText.trim();
                                            resultado[chave] = valor;
                                        }
                                    }
                                    return resultado;
                                }
                                """)
                            log_info(f"✅ Dados do solicitante coletados: {len(dados_solicitante)} campo(s)")
                        except Exception as e:
                            log_erro(f"❌ Erro ao coletar dados do solicitante: {str(e)[:50]}")
                            dados_solicitante = {}
                        
                        # Validação crítica dos dados do solicitante
                        from core.utils import validar_dados_criticos
                        validar_dados_criticos(
                            dados_solicitante=dados_solicitante,
                            nome_requerimento=requerimento,
                            contexto="coleta de dados do solicitante"
                        )
                        
                        fabricante_id = "formAnalise:output-fabricante-requerimento:output-fabricante-requerimento"
                        selector = "#" + fabricante_id.replace(":", "\\:")
                        try:
                            dados_fabricante = page.eval_on_selector(selector, """
                                (t) => {
                                    const linhas = Array.from(t.querySelectorAll("tr"));
                                    const resultado = {};
                                    for (const tr of linhas) {
                                        const celulas = tr.querySelectorAll("td");
                                        if (celulas.length === 2) {
                                            const chave = celulas[0].innerText.trim().replace(/:$/, '');
                                            const valor = celulas[1].innerText.trim();
                                            resultado[chave] = valor;
                                        }
                                    }
                                    return resultado;
                                }
                                """)
                            log_info(f"✅ Dados do fabricante coletados: {len(dados_fabricante)} campo(s)")
                        except Exception as e:
                            log_erro(f"❌ Erro ao coletar dados do fabricante: {str(e)[:50]}")
                            dados_fabricante = {}
                        
                        # Validação crítica dos dados do fabricante
                        from core.utils import validar_dados_criticos
                        validar_dados_criticos(
                            dados_fabricante=dados_fabricante,
                            nome_requerimento=requerimento,
                            contexto="coleta de dados do fabricante"
                        )
                        
                        lab_id = "formAnalise:output-laboratorio-requerimento:output-laboratorio-requerimento"
                        selector = "#" + lab_id.replace(":", "\\:")
                        try:
                            dados_lab = page.eval_on_selector(selector, """
                                (t) => {
                                    const linhas = Array.from(t.querySelectorAll("tr"));
                                    const resultado = {};
                                    for (const tr of linhas) {
                                        const celulas = tr.querySelectorAll("td");
                                        if (celulas.length === 2) {
                                            const chave = celulas[0].innerText.trim().replace(/:$/, '');
                                            const valor = celulas[1].innerText.trim();
                                            resultado[chave] = valor;
                                        }
                                    }
                                    return resultado;
                                }
                                """)
                            log_info(f"✅ Dados do laboratório coletados: {len(dados_lab)} campo(s)")
                        except Exception as e:
                            log_erro(f"❌ Erro ao coletar dados do laboratório: {str(e)[:50]}")
                            dados_lab = {}	
                        
                        # Validação crítica dos dados do laboratório
                        from core.utils import validar_dados_criticos
                        validar_dados_criticos(
                            dados_lab=dados_lab,
                            nome_requerimento=requerimento,
                            contexto="coleta de dados do laboratório"
                        )
                        
                        labelOCD = page.locator("text=Dados do Certificado")
                        table = labelOCD.locator("xpath=following::table[1]")

                        dados_ocd = table.evaluate("""
                        (t) => {
                            const r = {};
                            for (const tr of t.querySelectorAll("tr")) {
                                const td = tr.querySelectorAll("td");
                                if (td.length === 2) r[td[0].innerText.trim().replace(/:$/, '')] = td[1].innerText.trim();
                            }
                            return r;
                        }
                        """)

                        if len(dados_ocd) > 0:  
                            log_info(f"✅ Dados do OCD coletados: {len(dados_ocd)} campo(s)")
                        else:
                            log_erro(f"❌ Erro ao coletar dados do OCD")
                        
                        # Validação crítica dos dados do OCD
                        from core.utils import validar_dados_criticos
                        validar_dados_criticos(
                            dados_ocd=dados_ocd,
                            nome_requerimento=requerimento,
                            contexto="coleta de dados do OCD"
                        )
                        
                        # Salva os dados coletados no JSON do requerimento
                        json_path = req_para_fullpath(requerimento)                
                        nome_json = Path(json_path).name
                        
                        # Remove underscore inicial para manter consistência com criação inicial
                        nome_arquivo_json = nome_json[1:] if nome_json.startswith('_') else nome_json
                        caminho_json = os.path.join(json_path, f"{nome_arquivo_json}.json")
                        
                        # Verifica se o JSON existe, se não, cria um básico
                        if not os.path.exists(caminho_json):
                            log_info(f"📝 JSON não encontrado, criando arquivo básico: {nome_arquivo_json}.json")
                            # Cria estrutura básica do JSON
                            dados_json = {
                                "requerimento": {
                                    "num_req": requerimento,
                                    "status": "Em Análise"
                                }
                            }
                            try:
                                with open(caminho_json, "w", encoding="utf-8") as f:
                                    json.dump(dados_json, f, ensure_ascii=False, indent=4)
                            except Exception as e:
                                log_erro(f"❌ Erro ao criar JSON básico: {str(e)[:50]}")
                                continue
                        
                        # Carrega o JSON existente ou recém-criado
                        try:
                            with open(caminho_json, "r", encoding="utf-8") as f:
                                dados_json = json.load(f)
                        except Exception as e:
                            log_erro(f"❌ Erro ao ler JSON: {str(e)[:50]}")
                            continue
                        
                        # Atualiza os dados coletados
                        dados_atualizados = False
                        if dados_ocd != {}:
                            dados_json["ocd"] = dados_ocd
                            dados_atualizados = True
                        if dados_lab != '':
                            dados_json["lab"] = dados_lab
                            dados_atualizados = True
                        if dados_fabricante != '':
                            dados_json["fabricante"] = dados_fabricante
                            dados_atualizados = True
                        if dados_solicitante != '':
                            dados_json["solicitante"] = dados_solicitante
                            dados_atualizados = True
                    
                        # Salva apenas se houve atualizações
                        if dados_atualizados: #teogenes
                            try:
                                with open(caminho_json, "w", encoding="utf-8") as f:
                                    json.dump(dados_json, f, ensure_ascii=False, indent=4)
                                log_info(f"✅ Dados adicionais salvos no JSON: {nome_arquivo_json}.json")
                            except Exception as e:
                                log_erro(f"❌ Erro ao salvar JSON: {str(e)[:50]}")
                        else:
                            log_info("ℹ️ Nenhum dado adicional coletado para salvar")
                        
                        eh_rad_restrita = testar_radiacao_restrita(dados_json["requerimento"].get("tipo_equipamento", ""))
                        preencher_minuta(page,rad_restrita=eh_rad_restrita)

                        # Navega para anexos
                        anexos_btn = page.get_by_role("button", name=BOTOES['anexos'])
                        
                        try:
                            if anexos_btn:                        
                                anexos_btn.click(no_wait_after=True)
                                # Aguarda um seletor específico da nova "tela" ou da área que muda
                                page.wait_for_selector(".ui-blockui", state="detached", timeout=15000)
                                log_info("🔄 Buscando anexos...")
                            else:
                                log_info("⚠️ Botão 'Anexos' não encontrado.")
                            
                            wait_primefaces_ajax(page)
                            log_info("✅ Página de Anexos carregada")
                            
                            # BAIXA OS PDFs com retry inteligente
                            pdfs_baixados, tempo_primeiro_download, requer_reautenticacao = baixar_pdfs(
                                page, 
                                requerimento, 
                                tempo_primeiro_download
                            )
                            
                            # Marca o requerimento como concluído no log
                            if pdfs_baixados > 0:
                                marcar_requerimento_concluido(requerimento, pdfs_baixados)
                                requerimentos_processados.append(requerimento)
                                log_info(f"✅ Requerimento {requerimento} marcado como concluído ({pdfs_baixados} arquivos)")
                            else:
                                marcar_requerimento_com_erro(requerimento, "Nenhum arquivo foi baixado")
                                log_info(f"⚠️ Requerimento {requerimento} marcado com erro (0 arquivos baixados)")
                            
                        except Exception as e:
                            erro_msg = f"Erro ao acessar anexos: {str(e)}"
                            log_erro(erro_msg)
                            marcar_requerimento_com_erro(requerimento, erro_msg)
                else:
                    erro_msg = "iframe_element não encontrado"
                    log_info(f"⚠️ {erro_msg}, pulando...")
                    marcar_requerimento_com_erro(requerimento, erro_msg)
                    continue

                # Volta para a lista
                page = abrir_caixa_de_entrada(page,retorno_para_estudo=RETORNO_PARA_ESTUDO)
            
            log_info(SEPARADOR_LINHA)
            log_info("✅ PROCESSAMENTO CONCLUÍDO!")
            log_info(SEPARADOR_LINHA)
            
            # Verifica se todos os requerimentos foram processados com sucesso e limpa o log
            limpar_log_downloads_se_completo(requerimentos_processados)
            
            log_info("Pressione ENTER para encerrar...")
            input()
            browser.close()
        
    except Exception as e:
        log_erro_critico(f"Erro crítico durante download de documentos: {str(e)}")
        raise
