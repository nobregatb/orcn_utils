import os
import subprocess

FFMPEG_PATH = r"C:\Users\tbnobrega\Desktop\ffmpeg\bin\ffmpeg.exe"

def compactar_videos(pasta_entrada, fator=10):
    pasta_saida = os.path.join(pasta_entrada, "compressed")
    os.makedirs(pasta_saida, exist_ok=True)

    arquivos = [f for f in os.listdir(pasta_entrada) if f.lower().endswith(".mp4")]

    if not arquivos:
        print("Nenhum vídeo .mp4 encontrado na pasta.")
        return

    for nome in arquivos:
        caminho_entrada = os.path.join(pasta_entrada, nome)
        caminho_saida = os.path.join(pasta_saida, nome)

        print(f"\n📦 Compactando: {nome}")

        # Configuração de compressão otimizada para vídeos de tela
        comando = [
            FFMPEG_PATH,
            "-i", caminho_entrada,
            "-vcodec", "libx264",
            "-preset", "veryslow",
            "-crf", "34",          # 18–28 = boa qualidade, 30–36 = compressão forte
            "-g", "250",           # GOP longo (menos keyframes)
            "-r", "10",            # reduz FPS (se telas mudam pouco)
            "-acodec", "aac",
            "-b:a", "64k",         # áudio bem leve
            "-movflags", "+faststart",  # otimiza reprodução
            caminho_saida
        ]

        subprocess.run(comando, check=True)
        print(f"✅ Vídeo compactado: {caminho_saida}")

    print("\n🎉 Todos os vídeos foram compactados com sucesso!")

# ======= USO ========
# Exemplo: compactar todos os vídeos em "C:\Videos"
pasta = r"C:\Users\tbnobrega\Desktop\demo"
compactar_videos(pasta, fator=10)
