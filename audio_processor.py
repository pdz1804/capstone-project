import os
import sys
import torch
import whisper
import librosa
import soundfile as sf
from tqdm import tqdm
from pathlib import Path
import logging
import numpy as np

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class AudioExtractor:
    def __init__(self, output_dir="data/audio"):
        """Initialize the audio extractor with output directory."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def extract_audio(self, video_path, output_format='wav'):
        """
        Extract audio from a video file using moviepy.
        
        Args:
            video_path (str): Path to the video file
            output_format (str): Output audio format (wav, mp3, etc.)
            
        Returns:
            str: Path to the extracted audio file, or None if extraction failed
        """
        try:
            from moviepy.editor import VideoFileClip
            
            video_path = Path(video_path)
            output_path = self.output_dir / f"{video_path.stem}.{output_format}"
            
            # Skip if already extracted
            if output_path.exists():
                logging.info(f"Audio already extracted: {output_path}")
                return str(output_path)
            
            try:
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
                
                logging.info(f"Successfully extracted audio to {output_path}")
                return str(output_path)
                
            except Exception as e:
                logging.error(f"Error extracting audio with moviepy: {str(e)}")
                if 'video' in locals():
                    video.close()
                return None
            
        except ImportError:
            logging.error("moviepy is required for audio extraction. Please install it with: pip install moviepy")
            return None
            
        except Exception as e:
            logging.error(f"Error extracting audio from {video_path}: {str(e)}")
            return None

class PhoWhisperASR:
    def __init__(self, model_name="small"):
        """Initialize the Whisper ASR model."""
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logging.info(f"Loading Whisper model: {model_name} on {self.device}")
        try:
            self.model = whisper.load_model(model_name, device=self.device)
        except Exception as e:
            logging.error(f"Error loading model {model_name}: {str(e)}")
            logging.info("Available models: " + ", ".join(whisper.available_models()))
            raise
        
    def transcribe(self, audio_path, language=None, chunk_size=30, overlap=1.0):
        """
        Transcribe audio using Whisper, handling long audio files by processing in chunks.
        
        Args:
            audio_path (str or Path): Path to the audio file (must be WAV format)
            language (str, optional): Language code (e.g., "vi" for Vietnamese). If None, auto-detect.
            chunk_size (int): Size of each audio chunk in seconds (default: 30)
            overlap (float): Overlap between chunks in seconds (default: 1.0)
            
        Returns:
            dict: Transcription result with segments and text
        """
        try:
            import soundfile as sf
            import numpy as np
            
            audio_path = str(Path(audio_path).resolve())
            logging.info(f"Transcribing audio: {audio_path}")
            
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Audio file not found: {audio_path}")
                
            if not audio_path.lower().endswith('.wav'):
                raise ValueError("Only WAV files are supported for transcription.")
            
            try:
                # Load the entire audio file
                audio, sample_rate = sf.read(audio_path)
                
                # Convert to mono if stereo
                if len(audio.shape) > 1:
                    audio = np.mean(audio, axis=1)
                
                # Resample to 16kHz if needed
                if sample_rate != 16000:
                    import librosa
                    audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=16000)
                    sample_rate = 16000
                
                # Normalize audio
                audio = audio.astype(np.float32)
                max_val = np.max(np.abs(audio), initial=1.0)
                if max_val > 0:
                    audio = audio / max_val
                
                # Calculate chunk sizes
                chunk_samples = int(chunk_size * sample_rate)
                overlap_samples = int(overlap * sample_rate)
                step = max(1, chunk_samples - overlap_samples)
                
                # Process in chunks
                all_segments = []
                total_length = len(audio)
                
                for start in range(0, total_length, step):
                    end = min(start + chunk_samples, total_length)
                    chunk = audio[start:end]
                    
                    # Skip very short chunks at the end
                    if len(chunk) < sample_rate * 0.5:  # Skip chunks shorter than 0.5s
                        continue
                    
                    # Pad the last chunk if needed
                    if len(chunk) < chunk_samples:
                        chunk = np.pad(chunk, (0, chunk_samples - len(chunk)), 'constant')
                    
                    # Convert to tensor and process
                    audio_tensor = torch.from_numpy(chunk).to(self.model.device)
                    mel = whisper.log_mel_spectrogram(audio_tensor)
                    
                    # Only detect language on first chunk if not specified
                    current_lang = language
                    if start == 0 and language is None:
                        _, probs = self.model.detect_language(mel)
                        current_lang = max(probs, key=probs.get)
                        logging.info(f"Detected language: {current_lang}")
                    
                    # Transcribe chunk
                    options = whisper.DecodingOptions(
                        fp16=False,
                        language=current_lang,
                        without_timestamps=True
                    )
                    
                    result = whisper.decode(self.model, mel, options)
                    if result.text.strip():
                        all_segments.append({
                            'start': start / sample_rate,
                            'end': end / sample_rate,
                            'text': result.text.strip()
                        })
                
                # Combine all segments
                full_text = ' '.join(seg['text'] for seg in all_segments)
                
                return {
                    'text': full_text,
                    'language': current_lang or 'unknown',
                    'segments': all_segments
                }
                
            except Exception as e:
                logging.error(f"Error processing audio: {str(e)}")
                import traceback
                logging.error(traceback.format_exc())
                return None
            
        except ImportError as e:
            logging.error(f"Required package missing: {str(e)}")
            return None
            
        except Exception as e:
            logging.error(f"Error during transcription: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return None

def process_lectures(video_paths, output_dir="results"):
    """Process multiple lecture videos for ASR."""
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # Initialize components
    extractor = AudioExtractor()
    asr = PhoWhisperASR()
    
    results = []
    
    for video_path in tqdm(video_paths, desc="Processing lectures"):
        try:
            # Extract audio
            audio_path = extractor.extract_audio(video_path)
            if not audio_path:
                continue
                
            # Transcribe audio
            result = asr.transcribe(audio_path)
            if not result:
                continue
                
            # Save results
            output_file = output_dir / f"{Path(video_path).stem}_transcript.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result['text'])
                
            results.append({
                'video': str(video_path),
                'audio': audio_path,
                'transcript': result['text'],
                'output_file': str(output_file)
            })
            
            logging.info(f"Saved transcript to {output_file}")
            
        except Exception as e:
            logging.error(f"Error processing {video_path}: {str(e)}")
            continue
            
    return results

def main():
    if len(sys.argv) < 2:
        print("Usage: python audio_processor.py <video_file1> [<video_file2> ...]")
        print("Note: For files with spaces, enclose the path in quotes.")
        return 1
    
    video_paths = []
    for path in sys.argv[1:]:
        # Handle paths with spaces that might be split
        if not video_paths or ' ' in path or os.path.exists(path):
            video_paths.append(path)
        else:
            # If the path doesn't exist, it might be part of a previous path with spaces
            video_paths[-1] = f"{video_paths[-1]} {path}"
    
    # Verify paths exist
    valid_paths = []
    for path in video_paths:
        if not os.path.exists(path):
            print(f"Error: File not found - {path}")
            continue
        valid_paths.append(path)
    
    if not valid_paths:
        print("No valid video files found to process.")
        return 1
        
    print(f"\nProcessing {len(valid_paths)} video(s):")
    for i, path in enumerate(valid_paths, 1):
        print(f"  {i}. {path}")
    
    try:
        results = process_lectures(valid_paths)
        print("\nProcessing complete!")
        if results:
            print("\nTranscripts saved to:")
            for result in results:
                if 'output_file' in result:
                    print(f"- {result['output_file']}")
        return 0
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())
