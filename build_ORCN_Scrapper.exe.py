"""
Script auxiliar para compilar o projeto com PyInstaller
"""

import subprocess
import sys
import os

def build_executable():
    """Constrói o executável usando PyInstaller"""
    
    # Comando PyInstaller
    cmd = [
        "pyinstaller",
        "--onefile",
        "--console",  # Mantém a janela do console para exibir logs
        "--name=ORCN_Scrapper",
        #"--icon=icon.ico",  # Adicione um ícone se desejar
        "--add-data=meu_perfil_chrome;meu_perfil_chrome",  # Inclui perfil do Chrome
        "tbn_scrapper_ajax.py"
    ]
    
    print("🔨 Compilando executável...")
    print(f"Comando: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ Compilação concluída com sucesso!")
        print(f"📦 Executável criado em: dist/ORCN_Scrapper.exe")
        
    except subprocess.CalledProcessError as e:
        print("❌ Erro na compilação:")
        print(e.stdout)
        print(e.stderr)
        return False
    
    return True

def install_requirements():
    """Instala dependências necessárias"""
    requirements = [
        "openpyxl",
        "playwright",
        "pyinstaller"
    ]
    
    print("📦 Instalando dependências...")
    for req in requirements:
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", req], check=True)
            print(f"✅ {req} instalado")
        except subprocess.CalledProcessError:
            print(f"❌ Erro ao instalar {req}")
            return False
    
    # Instala browsers do Playwright
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        print("✅ Playwright chromium instalado")
    except subprocess.CalledProcessError:
        print("❌ Erro ao instalar Playwright browsers")
        return False
    
    return True

if __name__ == "__main__":
    print("🚀 ORCN Scrapper - Build Script")
    print("=" * 50)
    
    # Verifica se está no diretório correto
    if not os.path.exists("tbn_scrapper_ajax.py"):
        print("❌ Erro: tbn_scrapper_ajax.py não encontrado!")
        print("Execute este script no mesmo diretório do arquivo principal.")
        sys.exit(1)
    
    # Instala dependências
    if not install_requirements():
        print("❌ Falha ao instalar dependências")
        sys.exit(1)
    
    # Compila executável
    if not build_executable():
        print("❌ Falha na compilação")
        sys.exit(1)
    
    print("\n" + "=" * 50)
    print("✅ BUILD CONCLUÍDO!")
    print("📁 Executável disponível em: dist/ORCN_Scrapper.exe")
    print("\n📝 Como usar:")
    print("  • Modo normal: ORCN_Scrapper.exe")
    print("  • Modo debug:  ORCN_Scrapper.exe debug")
    print("=" * 50)