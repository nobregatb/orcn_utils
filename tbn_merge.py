import ffmpeg


ffmpeg_path = r"C:\Users\tbnobrega\Desktop\ffmpeg\bin\ffmpeg.exe"

input_video = ffmpeg.input(r"C:\Users\tbnobrega\Desktop\demo\compressed\troller-comprimido.mp4")
input_audio = ffmpeg.input(r"C:\Users\tbnobrega\Desktop\demo\compressed\eu me amo.mp3")

ffmpeg.output(
    input_video.video, input_audio.audio,
    r"C:\Users\tbnobrega\Desktop\demo\compressed\merge-troller.mp4",
    vcodec='copy',  # mantém o vídeo original
    acodec='aac',   # converte o áudio para AAC (compatível)
    shortest=None   # para terminar quando o menor (áudio/vídeo) acabar
).run(cmd=ffmpeg_path)