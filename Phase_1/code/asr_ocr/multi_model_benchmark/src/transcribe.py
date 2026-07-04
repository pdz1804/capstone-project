import argparse
import soundfile as sf
import torch
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
from pydub import AudioSegment
import os
from tqdm import tqdm

def convert_and_split_audio(input_file, output_dir, chunk_length_ms=1*60*1000, target_sample_rate=16000):
    audio = AudioSegment.from_file(input_file)
    
    # Convert sample rate
    audio = audio.set_frame_rate(target_sample_rate)
    
    # Split audio into chunks
    chunks = [audio[i:i + chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]
    
    output_files = []
    for idx, chunk in enumerate(chunks):
        chunk_name = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(input_file))[0]}_chunk{idx}.wav")
        chunk.export(chunk_name, format="wav")
        output_files.append(chunk_name)
    
    return output_files

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Transcribe speech from a WAV file using Wav2Vec2.0.")
    parser.add_argument(
        "wav_file",
        type=str,
        nargs='?',
        default="default.wav",
        help="Path to the WAV file to be transcribed (default: 'default.wav')"
    )
    parser.add_argument(
        "--model_name",
        type=str,
        default="facebook/wav2vec2-large-xlsr-53",
        help="Name of the pretrained model to use (default: 'facebook/wav2vec2-large-xlsr-53')"
    )
    args = parser.parse_args()

    # Convert and split the audio file
    output_dir = "chunks"
    os.makedirs(output_dir, exist_ok=True)
    chunk_files = convert_and_split_audio(args.wav_file, output_dir)

    # Load pretrained model and processor
    try:
        processor = Wav2Vec2Processor.from_pretrained(args.model_name)
        model = Wav2Vec2ForCTC.from_pretrained(args.model_name)
    except Exception as e:
        print(f"Error loading model: {e}")
        return

    transcriptions = []

    for chunk_file in tqdm(chunk_files, desc="Processing chunks"):
        # Load the audio file
        try:
            audio_input, sample_rate = sf.read(chunk_file)
        except Exception as e:
            print(f"Error reading the audio file {chunk_file}: {e}")
            continue

        # Ensure the audio is sampled at 16kHz as expected by the model
        if sample_rate != 16000:
            print(f"Expected sampling rate 16000, but got {sample_rate} for file {chunk_file}")
            continue

        # Preprocess the audio file
        input_values = processor(audio_input, sampling_rate=sample_rate, return_tensors="pt").input_values

        # Perform inference
        try:
            with torch.no_grad():
                logits = model(input_values).logits

            # Get predicted ids
            predicted_ids = torch.argmax(logits, dim=-1)

            # Decode the ids to text
            transcription = processor.decode(predicted_ids[0])
            transcriptions.append(transcription)
        except Exception as e:
            print(f"Error during inference on file {chunk_file}: {e}")

    # Save transcriptions to a text file
    with open("transcriptions.txt", "w") as f:
        for idx, transcription in enumerate(transcriptions):
            f.write(f"Chunk {idx}:\n{transcription}\n\n")

    print("Transcriptions saved to transcriptions.txt")

if __name__ == "__main__":
    main()