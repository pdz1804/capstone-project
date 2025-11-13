from google import genai
from pathlib import Path
import os
import argparse
import sys

def extract_audio(video_path, output_format='wav', output_dir="data/audio"):
    from moviepy.editor import VideoFileClip
    
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{video_path.stem}.{output_format}"
    
    # Skip if already extracted
    if output_path.exists():
        return str(output_path)
    
    # Load video file
    video = VideoFileClip(str(video_path))
    
    # Extract audio
    audio = video.audio
    
    # Write audio file
    audio.write_audiofile(str(output_path), fps=16000, logger=None)
    
    # Close the video file
    video.close()
    
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise Exception("Failed to create output audio file")
    
    return str(output_path)
            

def audio_to_text(audio_path):       
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)

    # chat = client.chats.create(
    #     model="gemini-2.5-flash",)

    # while True:
    #     message = input("You: ")
    #     if message.lower() in ["exit", "quit"]:
    #         break
    #     res = chat.send_message(message)
    
    #     print("Gemini: ", res.text)

    uploaded_file = client.files.upload(file=audio_path)

    response = client.models.generate_content_stream(
        model="gemini-2.5-flash",
        contents=["Transcribe this audio in lines", uploaded_file]
    )
    audio_to_text = ""
    for chunk in response:
        print(chunk)
        audio_to_text += chunk.text
    return audio_to_text

def main():
    video_paths = []
    for path in sys.argv[1:]:
        if not video_paths or ' ' in path or os.path.exists(path):
            video_paths.append(path)
            audio_path = extract_audio(path)
            text = audio_to_text(audio_path)

            output_path = "results_gemini/asr"
            output_dir = Path(output_path)
            output_dir.mkdir(exist_ok=True, parents=True)
            output_file = output_dir / f"{Path(path).stem}_transcript.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(text)
    
if __name__ == "__main__":
    main()