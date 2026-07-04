import os
import cv2
import numpy as np
from pathlib import Path
from PIL import Image
import logging
from tqdm import tqdm
import tempfile
from pdf2image import convert_from_path
import shutil
import pytesseract
import sys
import subprocess
import shutil
from typing import List, Dict, Any, Optional, Union
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SlideOCR:
    def __init__(self, output_dir="results/ocr"):
        """Initialize the SlideOCR processor."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure Tesseract path
        self.setup_tesseract()
        
        # Check if poppler is in the path, if not, use the local one
        self.poppler_path = None
        if os.name == 'nt':  # Windows
            local_poppler = Path('poppler/bin')
            if local_poppler.exists():
                self.poppler_path = str(local_poppler.resolve())
    
    def setup_tesseract(self):
        """Set up OCR configuration."""
        # Try to find Tesseract in the system PATH
        self.use_pytesseract = False
        
        # Try to use pytesseract if available
        try:
            # Test if pytesseract is working
            pytesseract.get_tesseract_version()
            self.use_pytesseract = True
            print("Using pytesseract for OCR")
            return
        except (pytesseract.TesseractNotFoundError, Exception) as e:
            print(f"pytesseract not available: {e}")
        
        # If we get here, no OCR solution is available
        print("Warning: No OCR solution is available.")
        print("Please install Tesseract OCR or ensure pytesseract is properly configured.")
        print("You can install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki")
        
    def preprocess_image(self, image_path):
        """Preprocess image for better OCR results."""
        try:
            # Read image
            img = cv2.imread(str(image_path))
            if img is None:
                raise ValueError(f"Could not read image: {image_path}")
                
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Apply thresholding to preprocess the image
            gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            
            # Apply dilation to connect text components
            kernel = np.ones((1, 1), np.uint8)
            gray = cv2.dilate(gray, kernel, iterations=1)
            
            # Apply erosion to remove noise
            gray = cv2.erode(gray, kernel, iterations=1)
            
            return gray
            
        except Exception as e:
            logging.error(f"Error preprocessing image {image_path}: {str(e)}")
            return None
    
    def extract_text_tesseract(self, image_path, lang='vie+eng'):
        try:
            if not hasattr(self, 'use_pytesseract') or not self.use_pytesseract:
                print("Warning: Tesseract OCR is not available. Please install Tesseract for better results.")
                print("You can install it from: https://github.com/UB-Mannheim/tesseract/wiki")
                return "[OCR not available - please install Tesseract OCR]"
                
            # Preprocess image
            processed_img = self.preprocess_image(image_path)
            if processed_img is None:
                return None
                
            try:
                # Try using pytesseract
                custom_config = f'--oem 3 -l {lang}'
                text = pytesseract.image_to_string(
                    processed_img,
                    config=custom_config
                )
                return text.strip()
                
            except pytesseract.TesseractNotFoundError:
                print("Error: Tesseract is not installed or not in your PATH.")
                print("Please install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki")
                return "[Tesseract OCR not installed]"
                
            except Exception as e:
                logging.error(f"Error in Tesseract OCR for {image_path}: {str(e)}")
                return f"[OCR Error: {str(e)}]"
                
        except Exception as e:
            logging.error(f"Unexpected error in extract_text_tesseract for {image_path}: {str(e)}")
            return None
    
    def _get_organized_path(self, input_path, output_dir, page=None):
        # Create a subdirectory based on the input filename
        base_name = input_path.stem
        doc_output_dir = output_dir / base_name
        doc_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate output filename
        if page is not None:
            output_file = doc_output_dir / f"page_{page:03d}.txt"
        else:
            output_file = doc_output_dir / "content.txt"
            
        return output_file
        
    def process_slides(self, input_paths, output_dir=None):
        if output_dir is None:
            output_dir = self.output_dir
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
        results = []
        
        for input_path in tqdm(input_paths, desc="Processing slides"):
            try:
                input_path = Path(input_path)
                if not input_path.exists():
                    logging.warning(f"File not found: {input_path}")
                    continue
                
                # Handle PDF files
                if input_path.suffix.lower() == '.pdf':
                    pdf_results = self._process_pdf(input_path, output_dir)
                    results.extend(pdf_results)
                # Handle image files
                else:
                    # Extract text with Tesseract
                    text = self.extract_text_tesseract(input_path)
                    
                    if text:
                        # Get organized output path
                        output_file = self._get_organized_path(input_path, output_dir)
                        output_file.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Save results
                        with open(output_file, 'w', encoding='utf-8') as f:
                            f.write(text)
                            
                        results.append({
                            'source': str(input_path),
                            'page': 1,
                            'text': text,
                            'output_file': str(output_file)
                        })
                        
                        logging.info(f"Processed {input_path.name} -> {output_file}")
                
            except Exception as e:
                logging.error(f"Error processing {input_path}: {str(e)}")
                continue
                
        return results
        
    def _process_pdf(self, pdf_path, output_dir):
        """Process a PDF file by converting it to images and performing OCR on each page."""
        results = []
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Get the base output directory for this PDF
            doc_output_dir = output_dir / pdf_path.stem
            doc_output_dir.mkdir(parents=True, exist_ok=True)
            
            # Convert PDF to images
            images = convert_from_path(
                str(pdf_path),
                output_folder=temp_dir,
                poppler_path=self.poppler_path,
                fmt='jpeg',
                thread_count=2
            )
            
            # Process each page
            for i, image in enumerate(images, 1):
                try:
                    # Save the image
                    img_path = Path(temp_dir) / f"page_{i:03d}.jpg"
                    image.save(img_path, 'JPEG')
                    
                    # Extract text with Tesseract
                    text = self.extract_text_tesseract(img_path)
                    
                    if text:
                        # Save results in organized structure
                        output_file = doc_output_dir / f"page_{i:03d}.txt"
                        with open(output_file, 'w', encoding='utf-8') as f:
                            f.write(text)
                            
                        results.append({
                            'source': str(pdf_path),
                            'page': i,
                            'text': text,
                            'output_file': str(output_file)
                        })
                        
                        logging.info(f"Processed {pdf_path.name} (page {i}) -> {output_file}")
                        
                except Exception as e:
                    logging.error(f"Error processing page {i} of {pdf_path.name}: {str(e)}")
                    continue
                    
        except Exception as e:
            logging.error(f"Error converting PDF {pdf_path}: {str(e)}")
        finally:
            # Clean up temporary files
            shutil.rmtree(temp_dir, ignore_errors=True)
            
        return results

    def process_slide_directory(self, directory_path, output_dir=None):
        """Process all slide files in a directory."""
        directory = Path(directory_path)
        if not directory.exists() or not directory.is_dir():
            raise ValueError(f"Directory not found: {directory_path}")
        
        # Get all PDF files in the directory
        try:
            slide_files = list(directory.glob('*.pdf'))
            if not slide_files:
                print(f"No PDF files found in {directory_path}")
                return []
        except Exception as e:
            print(f"Error listing PDF files in {directory_path}: {e}")
            return []
        
        # Process all slide files
        all_results = []
        for slide_file in slide_files:
            try:
                # Handle non-ASCII filenames
                file_name = str(slide_file.name.encode('utf-8', 'replace'), 'utf-8', 'replace')
                print(f"\nProcessing: {file_name}")
                
                # Process the file
                results = self.process_slides([str(slide_file.absolute())])
                all_results.extend(results)
                
                # Print summary for this file
                print(f"  - Processed {len(results)} pages")
                if results:
                    output_dir = str(Path(results[0]['output_file']).parent)
                    print(f"  - Output directory: {output_dir}")
                    
            except Exception as e:
                print(f"Error processing {file_name}: {str(e)}")
                import traceback
                traceback.print_exc()
        
        return all_results

def safe_print(*args, **kwargs):
    """Safely print text that might contain non-ASCII characters."""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # If we can't print unicode, try with a simpler encoding
        text = ' '.join(str(arg) for arg in args)
        print(text.encode('ascii', 'replace').decode('ascii'), **kwargs)

if __name__ == "__main__":
    import sys
    import argparse
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Process lecture slides with OCR')
    parser.add_argument('input', nargs='*', help='Input files or directories to process')
    parser.add_argument('--output', '-o', default='results/ocr', help='Output directory')
    
    args = parser.parse_args()
    
    if not args.input:
        parser.print_help()
        sys.exit(1)
    
    # Initialize OCR processor
    try:
        ocr_processor = SlideOCR(output_dir=args.output)
        
        # Process all input paths
        all_results = []
        for input_path in args.input:
            input_path = Path(input_path)
            if input_path.is_dir():
                results = ocr_processor.process_slide_directory(input_path, args.output)
            else:
                results = ocr_processor.process_slides([str(input_path.absolute())], args.output)
            all_results.extend(results)
        
        # Print summary
        print("\nProcessing complete!")
        print(f"Processed {len(all_results)} pages in total")
        print(f"Results saved in: {args.output}")
        
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        safe_print(f"An error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
