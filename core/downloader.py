import os
from pathlib import Path
import sys, json
import time
import re
from openpyxl import load_workbook
from playwright.sync_api import sync_playwright
from datetime import datetime
from core.log_print import log_info, log_erro, log_erro_critico
from core.const import (
    CHROME_PATH, TBN_FILES_FOLDER, CHROME_PROFILE_DIR, 
    REQUERIMENTOS_DIR_PREFIX, MOSAICO_BASE_URL, BOTOES_PDF, CHROME_ARGS,
    TIMEOUT_LIMITE_SESSAO, EXCEL_SHEET_NAME, EXCEL_TABLE_NAME, 
    STATUS_EM_ANALISE, STATUS_AUTOMATICO, SEPARADOR_LINHA,
    MENSAGENS_STATUS, MENSAGENS_ERRO, CARACTERES_INVALIDOS, FORMATO_NOME_ARQUIVO,
    CSS_SELECTORS, TAB_REQUERIMENTOS
)

# Detecta se está sendo executado como executável PyInstaller
def is_bundled():
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


# Define FILES_FOLDER baseado no modo de execução
FILES_FOLDER = TBN_FILES_FOLDER
PROFILE_DIR = os.path.join(Path(__file__).parent.parent, CHROME_PROFILE_DIR)

if is_bundled():
    FILES_FOLDER = os.path.dirname(sys.executable)
    PROFILE_DIR = os.path.join(FILES_FOLDER, CHROME_PROFILE_DIR)
    log_info(MENSAGENS_STATUS['modo_executavel'].format(FILES_FOLDER))
else:
    log_info(MENSAGENS_STATUS['modo_script'].format(FILES_FOLDER))



def req_para_fullpath(req):
    """Converte número do requerimento (num/ano) para caminho completo da pasta"""
    num, ano = req.split("/")
    requerimento = rf"{REQUERIMENTOS_DIR_PREFIX}\{ano}.{num}"
    full_path = os.path.join(FILES_FOLDER, requerimento)
    return full_path
    
def criar_pasta_se_nao_existir(req):
    """Cria pasta do requerimento se não existir e retorna o caminho"""
    full_path = req_para_fullpath(req)
    if not os.path.exists(full_path):
        os.makedirs(full_path, exist_ok=True)
        log_info(f"📁 Pasta criada: {full_path}")
    return full_path

def criar_json_dos_novos_requerimentos(rows):
    for i, row in enumerate(rows, start=1):
        try:
            cols = row.query_selector_all("td") 
            dados = [col.inner_text().strip() for col in cols]
            if dados[TAB_REQUERIMENTOS['status']] in STATUS_EM_ANALISE:
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
                    pasta = criar_pasta_se_nao_existir(requerimento_json['num_req'])
                    nome_pasta = os.path.basename(pasta)
                    dados_json = {}
                    dados_json["requerimento"] = requerimento_json
                    with open(os.path.join(pasta, f"{nome_pasta}.json"), "w", encoding="utf-8") as f:
                        json.dump(dados_json, f, ensure_ascii=False, indent=4)
        except Exception as e:
            log_erro(f"Erro ao ler linha {i}: {str(e)[:50]}")

    log_info(f"Total de requerimentos processados e arquivos JSON salvos!")

'''def atualizar_excel(rows) -> list:
    """Atualiza planilha com novos requerimentos em análise (apenas no modo debug)"""
    if not debug_mode:
        # Modo não-debug: processa todos os requerimentos sem verificar Excel
        log_info("📋 Modo produção: processando todos os requerimentos da lista")
        todos_requerimentos = []
        for i, row in enumerate(rows, start=1):
            try:
                cols = row.query_selector_all("td") 
                if len(cols) >= 2:
                    requerimento = cols[1].inner_text().strip()
                    todos_requerimentos.append(requerimento)
                    log_info(f"📋 Requerimento encontrado: {requerimento}")
            except Exception as e:
                log_erro(f"Erro ao ler linha {i}: {str(e)[:50]}")
        
        log_info(f"📊 Total de requerimentos a processar: {len(todos_requerimentos)}")
        return todos_requerimentos
    
    # Modo debug: funcionalidade original com Excel
    log_info("🐛 Modo debug: verificando planilha Excel...")
    if not os.path.exists(LOG_REQUERIMENTOS):
        log_info(f"⚠ Planilha não encontrada: {LOG_REQUERIMENTOS}")
        log_info("📋 Processando todos os requerimentos da lista")
        todos_requerimentos = []
        for i, row in enumerate(rows, start=1):
            try:
                cols = row.query_selector_all("td") 
                if len(cols) >= 2:
                    requerimento = cols[1].inner_text().strip()
                    todos_requerimentos.append(requerimento)
            except Exception as e:
                log_erro(f"Erro ao ler linha {i}: {str(e)[:50]}")
        return todos_requerimentos
    
    novosAnalises = []
    wb = load_workbook(LOG_REQUERIMENTOS)
    ws = wb[EXCEL_SHEET_NAME]
    tabRequerimentos = ws.tables[EXCEL_TABLE_NAME]
    
    for i, row in enumerate(rows, start=1):
        cols = row.query_selector_all("td") 
        dados = [col.inner_text().strip() for col in cols]
        dados[0] = STATUS_AUTOMATICO
        
        linhas_existentes = [tuple(row) for row in ws.iter_rows(values_only=True)]
        
        if (dados[9] == STATUS_EM_ANALISE) or (dados[9] == 'Em Análise - RE'):
            novalinha = dados[:10]
            if tuple(novalinha) not in linhas_existentes:
                ws.append(novalinha)
                log_info(f"✅ Linha adicionada: {novalinha[1]}")
                novosAnalises.append(novalinha[1])
            else:
                log_info(f"⏭️  Linha já existe: {novalinha[1]}")
    
    # Atualiza referência da tabela
    ref_atual = tabRequerimentos.ref
    ultima_linha = ws.max_row
    col_inicio, linha_inicio = ref_atual.split(":")[0][0], ref_atual.split(":")[0][1:]
    col_fim = ref_atual.split(":")[1][0]
    nova_ref = f"{col_inicio}{linha_inicio}:{col_fim}{ultima_linha}"
    tabRequerimentos.ref = nova_ref

    wb.save(LOG_REQUERIMENTOS)
    wb.close()
    
    log_info(f"📊 Total de novos requerimentos: {len(novosAnalises)}")
    return novosAnalises'''

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
                try {
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
        log_erro(f"Onclick falhou: {str(e)[:50]}")
    
    # MÉTODO 2: Submit via PrimeFaces.ajax.Request
    try:
        success = page.evaluate("""(button) => {
            try {
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
        log_erro(f"Erro: {str(e)[:80]}")
    
    # MÉTODO 3: Force click como último recurso
    try:
        log_info("🔄 Tentando force click...")
        element.click(force=True, timeout=2000)
        log_info("✅ Force click funcionou")
        time.sleep(1)
        return True
    except Exception as e:
        log_erro(f"Force click falhou: {str(e)[:50]}")
    
    return False

def baixar_pdfs(page, requerimento):
    """Baixa todos os PDFs da página de anexos"""
    num, ano = requerimento.split("/")
    pasta_destino = os.path.join(FILES_FOLDER, f"Requerimentos\\_{ano}.{num}")
    
    # Cria a pasta do requerimento se não existir
    pasta_destino = criar_pasta_se_nao_existir(requerimento)
    
    total_pdfs_baixados = 0
    
    # Percorre cada botão para revelar PDFs
    for nome_botao in BOTOES_PDF:
        try:
            # Busca o botão pelo nome/texto
            botao = page.get_by_role("button", name=nome_botao)
            
            # Verifica se o botão existe e está visível
            if botao.count() > 0:
                log_info(f"🎯 Buscando: {nome_botao}")
                
                # Clica no botão
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
                    
                    # Baixa cada PDF encontrado
                    for idx, link in enumerate(pdf_links):
                        try:
                            # Verifica se o link está visível/disponível
                            if not link.is_visible():
                                continue
                            
                            # Pega informações da linha correspondente da tabela
                            linha_info = None
                            if idx < len(linhas_dados):
                                linha_info = linhas_dados[idx]
                            
                            # Pega o nome do arquivo original do link
                            href = link.get_attribute('href')
                            texto = link.inner_text().strip()
                            
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
                                                        dia, mes, ano = match.groups()
                                                    else:  # yyyy-mm-dd
                                                        ano, mes, dia = match.groups()
                                                    
                                                    data_formatada = f"{ano}.{mes.zfill(2)}.{dia.zfill(2)}"
                                                    break
                                            
                                            if not data_formatada:
                                                data_formatada = "0000.00.00"
                                                log_info(f"⚠ Não foi possível processar a data: {data_hora}")
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
                            
                            # Verifica se arquivo já existe ANTES de iniciar o download
                            caminho_completo_temp = os.path.join(pasta_destino, nome_arquivo_temp)
                            
                            # Procura por arquivos existentes que começem com o mesmo padrão
                            nome_base_busca = nome_arquivo_temp.split('] temp [')[0] + ']'  # Remove "temp" e tudo depois
                            arquivos_existentes = [f for f in os.listdir(pasta_destino) if f.startswith(nome_base_busca)]
                            
                            if arquivos_existentes:
                                log_info(f"⏭️ Arquivo já existe, pulando: {arquivos_existentes[0]}")
                                continue
                            
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
                                                    dia, mes, ano = match.groups()
                                                else:
                                                    ano, mes, dia = match.groups()
                                                data_formatada = f"{ano}.{mes.zfill(2)}.{dia.zfill(2)}"
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
                            
                        except Exception as e:
                            log_erro(f"Erro ao baixar PDF {idx + 1} de {nome_botao}: {str(e)[:50]}")
                else:
                    log_info(f"ℹ Nenhum PDF encontrado para: {nome_botao}")
                    
            else:
                log_info(f"⚠ Botão não encontrado: {nome_botao}")
                
        except Exception as e:
            log_erro(f"Erro ao processar botão {nome_botao}: {str(e)[:50]}")
            continue
    
    if total_pdfs_baixados == 0:
        log_info("⚠ Nenhum PDF foi baixado")
    else:
        log_info(f"💾 Total de {total_pdfs_baixados} PDF(s) salvos em: {pasta_destino}")

def abrir_caixa_de_entrada(page_obj):
    """Navega para a lista de requerimentos e configura visualização"""
    # Navega para a lista
    lista_url = f"{MOSAICO_BASE_URL}"
    page_obj.goto(lista_url)
    page_obj.wait_for_load_state("load")
    
    # Clica em "Todos"
    page_obj.click("#menuForm\\:todos", timeout=3600000) 
    page_obj.wait_for_load_state("load")
    
    # Seleciona 100 itens por página e aguarda atualização
    page_obj.select_option("select.ui-paginator-rpp-options", value="100")
    time.sleep(2) 
    page_obj.wait_for_load_state("networkidle")  # Aguarda requisições AJAX terminarem
    wait_primefaces_ajax(page_obj)
     # Pausa adicional para garantir que a tabela seja recarregada
    
    return page_obj

def baixar_documentos():
    """Função principal que baixa documentos dos requerimentos ORCN"""
    try:
        log_info(MENSAGENS_STATUS['iniciando_automacao'])
        
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                PROFILE_DIR,
                headless=False,
                executable_path=CHROME_PATH,
                args=CHROME_ARGS,
                accept_downloads=True  # IMPORTANTE: permite downloads
            )
            
            page = browser.new_page()
            
            # Inicia timer para controle de timeout do Mosaico
            inicio_execucao = time.time()
            limite_tempo = TIMEOUT_LIMITE_SESSAO  # 28 minutos em segundos
            
            # Navega para a lista
            page = abrir_caixa_de_entrada(page)
            
            log_info(SEPARADOR_LINHA)
            log_info("🤖 AUTOMAÇÃO ORCN - DOWNLOAD DE ANEXOS")
            log_info(SEPARADOR_LINHA)
            
            # Seleciona todas as linhas
            rows = page.query_selector_all(CSS_SELECTORS['tabela_dados'])
            log_info(f"🔎 {len(rows)} linhas encontradas na tabela")
            
            criar_json_dos_novos_requerimentos(rows)

            # Cria um dicionário com os dados de cada linha ANTES de iterar
            log_info("📋 Mapeando requerimentos...")
            linhas_dados = []
            
            for i, row in enumerate(reversed(rows), start=1):
                try:
                    cols = row.query_selector_all("td")
                    dados = [col.inner_text().strip() for col in cols]
                    if (len(cols) < 2) or (dados[TAB_REQUERIMENTOS['status']] not in STATUS_EM_ANALISE):
                        continue
                    
                    requerimento = cols[1].inner_text().strip()
                    
                    # Armazena os dados da linha
                    linhas_dados.append({
                        'indice': i,
                        'requerimento': requerimento,
                        'row': row
                    })
                except Exception as e:
                    log_erro(f"Erro ao ler linha {i}: {str(e)[:50]}")

            log_info(f"✅ {len(linhas_dados)} requerimentos mapeados")

            # Processa cada linha dos dados salvos
            for linha_info in linhas_dados:
                # Verifica se o tempo limite foi atingido (27 minutos)
                tempo_decorrido = time.time() - inicio_execucao
                if tempo_decorrido > limite_tempo:
                    minutos_decorridos = int(tempo_decorrido // 60)
                    log_info(SEPARADOR_LINHA)
                    log_info("⏰ TIMEOUT PREVENTIVO ATIVADO!")
                    log_info(SEPARADOR_LINHA)
                    log_info(f"⚠ Tempo decorrido: {minutos_decorridos} minutos")
                    log_info("⚠ Encerrando aplicação para evitar timeout do Mosaico (30 min)")
                    log_info("⚠ Execute novamente o script para continuar processando")
                    log_info(SEPARADOR_LINHA)
                    log_info("Pressione ENTER para encerrar...")
                    input()
                    browser.close()
                    return
                
                i = linha_info['indice']
                requerimento = linha_info['requerimento']
                
                # Só processa se for um requerimento que ainda não foi baixado
                '''full_path = req_para_fullpath(requerimento)
                if os.path.exists(full_path):
                    log_info(f"⏭️ Requerimento {requerimento} já processado, pulando...")
                    continue'''
                
                log_info(SEPARADOR_LINHA)
                log_info(f"▶ Requerimento {i}: {requerimento}")
                log_info(SEPARADOR_LINHA)
                
                # IMPORTANTE: Recarrega a linha atual usando busca manual
                # Busca pela linha que contém este requerimento específico
                row_atual = None
                try:
                    # Recarrega todas as linhas da tabela
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
                        log_info(f"⚠ Requerimento {requerimento} não encontrado na lista atualizada, pulando...")
                        continue
                        
                except Exception as e:
                    log_erro(f"Erro ao recarregar linhas: {str(e)[:50]}, pulando...")
                    continue
                
                # Busca botão "Visualizar em Tela cheia" na linha atual 
                btn = row_atual.query_selector("button[type='submit'][title='Visualizar em Tela cheia']")
                if not btn:
                    btn = row_atual.query_selector("button[title*='Tela cheia']")
                
                if not btn:
                    log_info("⚠ Botão não encontrado, pulando...")
                    continue
                
                # Clica no botão
                if not primefaces_click(page, btn, "Visualizar em Tela cheia"):
                    log_info("⚠ Não foi possível clicar, pulando...")
                    continue
                
                # Aguarda carregar
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except:
                    pass
                wait_primefaces_ajax(page)
                
                log_info(f"🌐 URL: {page.url}")
                
                # Busca botão "Anexos"
                time.sleep(2)
                
                iframe_element = page.wait_for_selector("#__frameDetalhe", timeout=10000)

                if iframe_element:
                    detalhes_requerimento = iframe_element.get_attribute("src")
                    if detalhes_requerimento:
                        page.goto(detalhes_requerimento)
                        ## recupera dados do requerente, ocd, fabricante, etc
                        solicitante_id = "formAnalise:output-solicitante-requerimento:output-solicitante-requerimento"
                        selector = "#" + solicitante_id.replace(":", "\\:")
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
                        fabricante_id = "formAnalise:output-fabricante-requerimento:output-fabricante-requerimento"
                        ## recupera dados do fabricante
                        selector = "#" + fabricante_id.replace(":", "\\:")
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
                        lab_id = "formAnalise:output-laboratorio-requerimento:output-laboratorio-requerimento"
                        selector = "#" + lab_id.replace(":", "\\:")
                        dados_lab= page.eval_on_selector(selector, """
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
                        tabelas_ids = page.eval_on_selector_all("table[id]", """
                            (tabelas) => tabelas.map(t => t.id)
                            """)
                        ocd_id = 'formAnalise:j_idt202'
                        selector = "#" + ocd_id.replace(":", "\\:")
                        dados_ocd = page.eval_on_selector(selector, """
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
                        json_path = req_para_fullpath(requerimento)                
                        nome_json = Path(json_path).name # o json tem o mesmo nome da pasta do requerimento
                        with open(os.path.join(json_path, f"{nome_json}.json"), "r", encoding="utf-8") as f:
                            #dados_ocd = {}
                            dados_json = json.load(f)
                            #dados_json = dados_req
                            #dados_json["requerimento"] = dados_req
                            if dados_ocd != {}:
                                dados_json["ocd"] = dados_ocd  # Use indexação, não append
                            if dados_lab != '':
                                dados_json["lab"] = dados_lab
                            if dados_fabricante != '':
                                dados_json["fabricante"] = dados_fabricante
                            if dados_solicitante != '':
                                dados_json["solicitante"] = dados_solicitante

                        with open(os.path.join(json_path, f"{nome_json}.json"), "w", encoding="utf-8") as f:
                            json.dump(dados_json, f, ensure_ascii=False, indent=4)

                        anexos_btn = page.get_by_role("button", name="Anexos")
                        try:
                            if anexos_btn:                        
                                anexos_btn.click(no_wait_after=True)
                                # Aguarda um seletor específico da nova "tela" ou da área que muda
                                page.wait_for_selector(".ui-blockui", state="detached", timeout=15000)
                                log_info("🔄 Buscando anexos...")
                            else:
                                log_info("Botão 'Anexos' não encontrado.")
                            wait_primefaces_ajax(page)
                            
                            log_info("✅ Página de Anexos carregada")
                            
                            # BAIXA OS PDFs
                            baixar_pdfs(page, requerimento)                        
                        except Exception as e:
                            log_erro(f"expect_navigation falhou: {str(e)}")
                else:
                    log_info("⚠ iframe_element não encontrado, pulando...")
                    continue

                # Volta para a lista
                log_info("↩ Voltando para a lista...")
                page = abrir_caixa_de_entrada(page)
            
            log_info(SEPARADOR_LINHA)
            log_info("✅ PROCESSAMENTO CONCLUÍDO!")
            log_info(SEPARADOR_LINHA)
            log_info("Pressione ENTER para encerrar...")
            input()
            browser.close()
        
    except Exception as e:
        log_erro_critico(f"Erro crítico durante download de documentos: {str(e)}")
        raise
