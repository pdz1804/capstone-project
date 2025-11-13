import argparse
import sys
from pathlib import Path
from audio_processor import process_lectures
from slide_processor import SlideOCR
import logging

def setup_logging():
    """Configure logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('lecture_processing.log')
        ]
    )

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Process lecture videos and slides.')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # ASR command
    asr_parser = subparsers.add_parser('asr', help='Process lecture videos with ASR')
    asr_parser.add_argument('videos', nargs='+', help='Video files to process')
    asr_parser.add_argument('--output-dir', default='results/asr', help='Output directory for transcripts')
    
    # OCR command
    ocr_parser = subparsers.add_parser('ocr', help='Process lecture slides with OCR')
    ocr_parser.add_argument('slides', nargs='+', help='Slide images to process')
    ocr_parser.add_argument('--output-dir', default='results/ocr', help='Output directory for OCR results')
    
    # Process all command
    all_parser = subparsers.add_parser('all', help='Process both videos and slides')
    all_parser.add_argument('--videos', nargs='+', help='Video files to process')
    all_parser.add_argument('--slides', nargs='+', help='Slide images to process')
    all_parser.add_argument('--output-dir', default='results', help='Base output directory')
    
    return parser.parse_args()

def main():
    """Main entry point for the application."""
    setup_logging()
    args = parse_arguments()
    
    if args.command == 'asr':
        logging.info("Starting ASR processing...")
        process_lectures(args.videos, args.output_dir)
        logging.info("ASR processing completed.")
        
    elif args.command == 'ocr':
        logging.info("Starting OCR processing...")
        ocr = SlideOCR(args.output_dir)
        
        # Process all input paths, handling both files and directories
        input_files = []
        for path in args.slides:
            path = Path(path)
            if path.is_file():
                input_files.append(str(path))
            elif path.is_dir():
                # Add all PDF and image files from the directory
                input_files.extend([str(p) for p in path.glob('*.pdf')])
                input_files.extend([str(p) for p in path.glob('*.jpg')])
                input_files.extend([str(p) for p in path.glob('*.jpeg')])
                input_files.extend([str(p) for p in path.glob('*.png')])
        
        if not input_files:
            logging.error(f"No valid input files found in {args.slides}")
            sys.exit(1)
            
        logging.info(f"Found {len(input_files)} files to process")
        ocr.process_slides(input_files)
        logging.info("OCR processing completed.")
        
    elif args.command == 'all':
        if args.videos:
            logging.info("Starting ASR processing...")
            asr_output = Path(args.output_dir) / 'asr'
            process_lectures(args.videos, str(asr_output))
            
        if args.slides:
            logging.info("Starting OCR processing...")
            ocr_output = Path(args.output_dir) / 'ocr'
            ocr = SlideOCR(ocr_output)
            ocr.process_slides(args.slides)
            
        logging.info("All processing completed.")
        
    else:
        logging.error("Please specify a valid command (asr, ocr, or all).")
        sys.exit(1)

if __name__ == "__main__":
    main()
