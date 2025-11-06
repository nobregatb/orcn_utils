# -*- coding: utf-8 -*-
"""
Script para gerar apenas os arquivos JSON dos requerimentos sem baixar arquivos.
Este script coleta todos os dados dos requerimentos (solicitante, fabricante, laboratório, OCD)
e salva nos arquivos JSON, mas não faz download de documentos.
"""

import os
from pathlib import Path
import sys, json
import time
from playwright.sync_api import sync_playwright
from datetime import datetime

# Adiciona o diretório raiz ao path para imports
sys.path.append(str(Path(__file__).parent))

from core.log_print import log_info, log_erro, log_erro_critico
from core.const import (
    BOTOES, CHROME_PATH, TBN_FILES_FOLDER, CHROME_PROFILE_DIR, 
    REQUERIMENTOS_DIR_INBOX, MOSAICO_BASE_URL, CHROME_ARGS,
    EXCEL_SHEET_NAME, EXCEL_TABLE_NAME, STATUS_EM_ANALISE, STATUS_AUTOMATICO, 
    SEPARADOR_LINHA, MENSAGENS_STATUS, MENSAGENS_ERRO, 
    CSS_SELECTORS, TAB_REQUERIMENTOS, TIPOS_DOCUMENTOS, FRASES
)
from core.utils import (
    is_bundled, get_files_folder, get_profile_dir, req_para_fullpath, 
    criar_pasta_se_nao_existir, carregar_json, salvar_json
)


# Define FILES_FOLDER e PROFILE_DIR baseado no modo de execução
FILES_FOLDER = get_files_folder()
PROFILE_DIR = get_profile_dir()


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
        x = 1 #log_erro(f"Erro: {str(e)[:80]}")
    
    # MÉTODO 3: Force click como último recurso
    try:
        element.click(force=True, timeout=2000)
        time.sleep(1)
        return True
    except Exception as e:
        log_erro(f"Force click falhou: {str(e)[:50]}")
    
    return False



def abrir_caixa_de_entrada(page_obj):
    """Navega para a lista de requerimentos e configura visualização"""
    # Navega para a lista
    lista_url = f"{MOSAICO_BASE_URL}"
    page_obj.goto(lista_url)
    page_obj.wait_for_load_state("load")

    # Clica em "Em Análise"
    page_obj.click(CSS_SELECTORS['menu_emAnalise'], timeout=3600000) 
    page_obj.wait_for_load_state("load")
    
    # Seleciona 100 itens por página e aguarda atualização
    page_obj.select_option("select.ui-paginator-rpp-options", value="100")
    time.sleep(2) 
    page_obj.wait_for_load_state("networkidle")  # Aguarda requisições AJAX terminarem
    wait_primefaces_ajax(page_obj)
    
    return page_obj


def coletar_dados_completos_requerimento(page, requerimento, dados_basicos):
    """
    Coleta todos os dados do requerimento (básicos + adicionais) e salva o JSON completo.
    
    Args:
        page: Objeto page do Playwright
        requerimento: Número do requerimento (formato XX/XXXXX)
        dados_basicos: Dados básicos do requerimento da tabela principal
    
    Returns:
        bool: True se coletou e salvou dados com sucesso, False caso contrário
    """
    try:
        log_info("📊 Coletando dados completos do requerimento...")
        
        # Coleta dados do solicitante
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
        
        # Coleta dados do fabricante
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
        
        # Coleta dados do laboratório
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
        
        # Coleta dados do OCD
        ocd_id = 'formAnalise:j_idt232'
        selector = "#" + ocd_id.replace(":", "\\:")
        try:
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
            log_info(f"✅ Dados do OCD coletados: {len(dados_ocd)} campo(s)")
        except Exception as e:
            log_erro(f"❌ Erro ao coletar dados do OCD: {str(e)[:50]}")
            dados_ocd = {}
        
        # Cria o JSON completo com todos os dados
        dados_json_completo = {
            "requerimento": dados_basicos
        }
        
        # Adiciona os dados adicionais coletados (apenas se não estiverem vazios)
        if dados_solicitante:
            dados_json_completo["solicitante"] = dados_solicitante
        if dados_fabricante:
            dados_json_completo["fabricante"] = dados_fabricante
        if dados_lab:
            dados_json_completo["lab"] = dados_lab
        if dados_ocd:
            dados_json_completo["ocd"] = dados_ocd
        
        # Cria a pasta do requerimento se não existir
        pasta_destino = criar_pasta_se_nao_existir(requerimento)
        nome_pasta = os.path.basename(pasta_destino)
        
        # Remove underscore inicial para manter consistência
        nome_arquivo_json = nome_pasta[1:] if nome_pasta.startswith('_') else nome_pasta
        caminho_json = os.path.join(pasta_destino, f"{nome_arquivo_json}.json")
        
        # Salva o JSON completo
        try:
            with open(caminho_json, "w", encoding="utf-8") as f:
                json.dump(dados_json_completo, f, ensure_ascii=False, indent=4)
            
            total_secoes = sum([
                1 if dados_solicitante else 0,
                1 if dados_fabricante else 0,
                1 if dados_lab else 0,
                1 if dados_ocd else 0
            ])
            
            log_info(f"✅ JSON completo salvo: {nome_arquivo_json}.json ({total_secoes} seções adicionais)")
            return True
            
        except Exception as e:
            log_erro(f"❌ Erro ao salvar JSON completo: {str(e)[:50]}")
            return False
            
    except Exception as e:
        log_erro(f"❌ Erro crítico na coleta de dados: {str(e)[:80]}")
        return False


def verificar_json_completo(requerimento):
    """
    Verifica se o arquivo JSON do requerimento já existe e contém dados completos.
    
    Args:
        requerimento: Número do requerimento (formato XX/XXXXX)
    
    Returns:
        bool: True se o JSON existe e está completo, False caso contrário
    """
    try:
        json_path = req_para_fullpath(requerimento)
        nome_json = Path(json_path).name
        
        # Remove underscore inicial para manter consistência
        nome_arquivo_json = nome_json[1:] if nome_json.startswith('_') else nome_json
        caminho_json = os.path.join(json_path, f"{nome_arquivo_json}.json")
        
        # Verifica se o arquivo existe
        if not os.path.exists(caminho_json):
            return False
        
        # Carrega o JSON e verifica se tem dados adicionais
        try:
            with open(caminho_json, "r", encoding="utf-8") as f:
                dados_json = json.load(f)
            
            # Considera completo se tem pelo menos uma das seções adicionais
            tem_dados_adicionais = any([
                'solicitante' in dados_json and dados_json['solicitante'],
                'fabricante' in dados_json and dados_json['fabricante'],
                'lab' in dados_json and dados_json['lab'],
                'ocd' in dados_json and dados_json['ocd']
            ])
            
            return tem_dados_adicionais
            
        except Exception as e:
            log_erro(f"❌ Erro ao ler JSON {caminho_json}: {str(e)[:50]}")
            return False
            
    except Exception as e:
        log_erro(f"❌ Erro ao verificar JSON para {requerimento}: {str(e)[:50]}")
        return False


def gerar_jsons_sem_download():
    """Função principal que gera JSONs dos requerimentos sem baixar arquivos"""
    try:
        log_info("🚀 INICIANDO GERAÇÃO DE JSONs SEM DOWNLOAD")
        log_info("Este script coleta apenas os dados dos requerimentos, SEM baixar arquivos")
        
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                PROFILE_DIR,
                headless=False,
                executable_path=CHROME_PATH,
                args=CHROME_ARGS,
                accept_downloads=False  # NÃO permite downloads
            )
            
            page = browser.new_page()
            
            # Navega para a lista
            page = abrir_caixa_de_entrada(page)
            
            log_info(SEPARADOR_LINHA)
            log_info("🤖 AUTOMAÇÃO ORCN - GERAÇÃO DE JSONs APENAS")
            log_info(SEPARADOR_LINHA)
            
            # Seleciona todas as linhas
            rows = page.query_selector_all(CSS_SELECTORS['tabela_dados_em_analise'])
            log_info(f"🔎 {len(rows)} linhas encontradas na tabela")

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
                    
                    # Cria um dicionário com os dados básicos do requerimento usando TAB_REQUERIMENTOS
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
                    
                    # Armazena os dados da linha
                    linhas_dados.append({
                        'indice': i,
                        'requerimento': requerimento,
                        'dados_basicos': requerimento_json,
                        'row': row
                    })
                except Exception as e:
                    log_erro(f"Erro ao ler linha {i}: {str(e)[:50]}")

            log_info(f"✅ {len(linhas_dados)} requerimentos mapeados")
            
            # Filtra requerimentos que já têm JSON completo
            log_info("🔍 Verificando quais requerimentos já possuem JSON completo...")
            requerimentos_pendentes = []
            requerimentos_ja_completos = 0
            
            for linha_info in linhas_dados:
                requerimento = linha_info['requerimento']
                if verificar_json_completo(requerimento):
                    requerimentos_ja_completos += 1
                    log_info(f"⏭️ Requerimento {requerimento} já possui JSON completo, pulando...")
                else:
                    requerimentos_pendentes.append(linha_info)
            
            log_info(SEPARADOR_LINHA)
            log_info(f"📊 Resumo da verificação:")
            log_info(f"  • Total encontrados: {len(linhas_dados)}")
            log_info(f"  • Já completos: {requerimentos_ja_completos}")
            log_info(f"  • Pendentes: {len(requerimentos_pendentes)}")
            log_info(SEPARADOR_LINHA)
            
            # Se não há requerimentos pendentes, finaliza
            if not requerimentos_pendentes:
                log_info("🎉 Todos os requerimentos já possuem JSONs completos!")
                log_info("Pressione ENTER para encerrar...")
                input()
                browser.close()
                return
            
            log_info(f"⚙️ Processando {len(requerimentos_pendentes)} requerimento(s) pendente(s)...")

            # Processa cada linha dos dados pendentes
            requerimentos_processados = 0
            requerimentos_com_erro = 0
            
            for linha_info in requerimentos_pendentes:
                i = linha_info['indice']
                requerimento = linha_info['requerimento']
                dados_basicos = linha_info['dados_basicos']
                
                log_info(SEPARADOR_LINHA)
                log_info(f"▶️ Requerimento {i}: {requerimento}")
                log_info(SEPARADOR_LINHA)
                
                # IMPORTANTE: Recarrega a linha atual usando busca manual
                row_atual = None
                try:
                    # Recarrega todas as linhas da tabela
                    linhas_atualizadas = page.query_selector_all(CSS_SELECTORS['tabela_dados_em_analise'])
                    
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
                        requerimentos_com_erro += 1
                        continue
                        
                except Exception as e:
                    log_erro(f"Erro ao recarregar linhas: {str(e)[:50]}, pulando...")
                    requerimentos_com_erro += 1
                    continue
                
                # Busca botão "Visualizar em Tela cheia" na linha atual 
                btn = row_atual.query_selector("button[type='submit'][title='Visualizar em Tela cheia']")
                if not btn:
                    btn = row_atual.query_selector("button[title*='Tela cheia']")
                
                if not btn:
                    log_info("⚠️ Botão não encontrado, pulando...")
                    requerimentos_com_erro += 1
                    continue
                
                # Clica no botão
                if not primefaces_click(page, btn, "Visualizar em Tela cheia"):
                    log_info("⚠️ Não foi possível clicar, pulando...")
                    requerimentos_com_erro += 1
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
                        
                        # Coleta dados completos do requerimento e salva JSON (SEM baixar arquivos)
                        if coletar_dados_completos_requerimento(page, requerimento, dados_basicos):
                            requerimentos_processados += 1
                            log_info(f"✅ Requerimento {requerimento} processado com sucesso")
                        else:
                            requerimentos_com_erro += 1
                            log_erro(f"❌ Erro ao processar requerimento {requerimento}")
                else:
                    log_info(f"⚠️ iframe_element não encontrado para {requerimento}, pulando...")
                    requerimentos_com_erro += 1
                    continue

                # Volta para a lista
                page = abrir_caixa_de_entrada(page)
            
            log_info(SEPARADOR_LINHA)
            log_info("✅ PROCESSAMENTO CONCLUÍDO!")
            log_info(SEPARADOR_LINHA)
            log_info(f"📊 Resumo final:")
            log_info(f"  • Total de requerimentos encontrados: {len(linhas_dados)}")
            log_info(f"  • Já completos (pulados): {requerimentos_ja_completos}")
            log_info(f"  • Pendentes processados: {len(requerimentos_pendentes)}")
            log_info(f"  • Processados com sucesso: {requerimentos_processados}")
            log_info(f"  • Com erro: {requerimentos_com_erro}")
            log_info(f"  • Taxa de sucesso: {(requerimentos_processados/len(requerimentos_pendentes)*100):.1f}%" if requerimentos_pendentes else "0%")
            log_info(SEPARADOR_LINHA)
            log_info("💡 Os arquivos JSON foram atualizados com dados adicionais")
            log_info("📁 Nenhum arquivo foi baixado - apenas dados coletados")
            log_info("Pressione ENTER para encerrar...")
            input()
            browser.close()
        
    except Exception as e:
        log_erro_critico(f"Erro crítico durante geração de JSONs: {str(e)}")
        raise


if __name__ == "__main__":
    print("🔧 GERADOR DE JSONs SEM DOWNLOAD")
    print("=" * 40)
    print("Este script irá:")
    print("✅ Navegar pelos requerimentos em análise")
    print("✅ Coletar dados adicionais (solicitante, fabricante, laboratório, OCD)")
    print("✅ Atualizar os arquivos JSON de cada requerimento")
    print("❌ NÃO baixar nenhum arquivo PDF")
    print("")
    
    resposta = input("Deseja continuar? (s/N): ").strip().lower()
    
    if resposta in ['s', 'sim', 'y', 'yes']:
        gerar_jsons_sem_download()
    else:
        print("Operação cancelada pelo usuário.")