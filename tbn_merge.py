import ffmpeg


ffmpeg_path = r"C:\Users\tbnobrega\Desktop\ffmpeg\bin\ffmpeg.exe"

input_video = ffmpeg.input(r"C:\Users\tbnobrega\Desktop\demo\compressed\video.mp4")
input_audio = ffmpeg.input(r"C:\Users\tbnobrega\Desktop\demo\compressed\audio.mp3")

ffmpeg.output(
    input_video.video, input_audio.audio,
    r"C:\Users\tbnobrega\Desktop\demo\compressed\merge.mp4",
    vcodec='copy',  # mantém o vídeo original
    acodec='aac',   # converte o áudio para AAC (compatível)
    shortest=None   # para terminar quando o menor (áudio/vídeo) acabar
).run(cmd=ffmpeg_path)