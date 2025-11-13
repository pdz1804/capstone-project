#!/usr/bin/env python3
"""
Simple Docling Multimodal Testing Script

This script reads files from input folder, processes them with DocumentProcessor,
and saves results to output folder.
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from typing import Dict, List, Any
from src.document_processor import MultimodalDocumentProcessor, ProcessingConfig
print("✓ Using src MultimodalDocumentProcessor")

def main():
    """Main function with command line interface"""
    parser = argparse.ArgumentParser(description='Simple Docling Multimodal Testing')
    parser.add_argument('--input-folder', default='input', help='Input folder path (default: input)')
    parser.add_argument('--output-folder', default='output', help='Output folder path (default: output)')
    
    args = parser.parse_args()
    
    input_folder = args.input_folder
    output_folder = args.output_folder
    
    # Create folders if they don't exist
    os.makedirs(input_folder, exist_ok=True)
    os.makedirs(output_folder, exist_ok=True)
    
    print(f"\n📁 Input folder: {input_folder}")
    print(f"📁 Output folder: {output_folder}")
    
    # Get all files from input folder
    input_files = []
    for file in os.listdir(input_folder):
        file_path = os.path.join(input_folder, file)
        if os.path.isfile(file_path):
            input_files.append(file_path)
    
    if not input_files:
        print("❌ No files found in input folder")
        return
    
    print(f"\n🔍 Found {len(input_files)} files to process:")
    for file_path in input_files:
        print(f"   - {os.path.basename(file_path)}")
    
    # Create MultimodalDocumentProcessor instance with enhanced config for multimodal processing
    try:
        config = ProcessingConfig(
            use_gpu=True,           # Use GPU acceleration
            enable_ocr=True,        # Enable OCR for text extraction  
            enable_vlm=True,        # Enable VLM for image analysis and table understanding
            enable_asr=True,        # Enable ASR for audio content
            ocr_engine="easyocr",   # Use EasyOCR with GPU for ADVANCED image processing
            ocr_languages=["eng"],  # Focus on English for better accuracy
            vlm_model="granite_docling",  # Use VLM for visual understanding - currently this is just for design, not in used yet
            export_images=True,     # Extract and save images
            export_tables=True,     # Extract and save tables
            export_metadata=True,   # Include detailed metadata
            create_subfolder_per_doc=True  # Organize outputs
        )
        processor = MultimodalDocumentProcessor(input_folder, output_folder, config)
        print("✓ MultimodalDocumentProcessor created successfully with enhanced multimodal config")
        print(f"  - GPU support: {config.use_gpu}")
        print(f"  - OCR engine: {config.ocr_engine}")
        print(f"  - VLM enabled: {config.enable_vlm}")
        print(f"  - Image extraction: {config.export_images}")
        print(f"  - Table extraction: {config.export_tables}")
    except Exception as e:
        print(f"❌ Error creating MultimodalDocumentProcessor: {e}")
        return
    
    # Use the MultimodalDocumentProcessor's built-in batch processing
    print(f"\n🚀 Starting batch processing using MultimodalDocumentProcessor...")
    
    try:
        # Convert string paths to Path objects for the processor
        file_paths = [Path(file_path) for file_path in input_files]
        
        # Use the processor's batch method which handles everything
        batch_results = processor.process_batch(file_paths)
        
        # Display detailed results
        print(f"\n{'='*60}")
        print("📊 BATCH PROCESSING RESULTS")
        print(f"{'='*60}")
        
        for idx, result in enumerate(batch_results['results'], 1):
            file_name = os.path.basename(result['file_path'])
            print(f"\n{idx}. {file_name}")
            print(f"   ✅ Status: SUCCESS")
            print(f"   ⏱️ Time: {result['processing_time']:.2f}s")
            print(f"   📄 Type: {result['file_type']}")
            print(f"   📊 Size: {result.get('file_size', 0):,} bytes")
            
            # Show exported formats
            exported = result.get('exported_files', {})
            if exported:
                print(f"   📂 Exports:")
                for format_type, path in exported.items():
                    if isinstance(path, list):
                        print(f"      - {format_type}: {len(path)} items")
                    else:
                        print(f"      - {format_type}: {os.path.basename(path)}")
        
        # Show failed files
        if batch_results['errors']:
            print(f"\n❌ FAILED FILES ({len(batch_results['errors'])}):")
            for idx, error in enumerate(batch_results['errors'], 1):
                file_name = os.path.basename(error['file_path'])
                print(f"   {idx}. {file_name}: {error.get('error', 'Unknown error')}")
        
        # Summary stats
        success_rate = (batch_results['processed_files'] / batch_results['total_files']) * 100
        print(f"\n{'='*60}")
        print("📈 FINAL SUMMARY")
        print(f"{'='*60}")
        print(f"Total files: {batch_results['total_files']}")
        print(f"Successful: {batch_results['processed_files']}")
        print(f"Failed: {batch_results['failed_files']}")
        print(f"Success rate: {success_rate:.1f}%")
        print(f"Total time: {batch_results['processing_time']:.2f}s")
        print(f"Average time per file: {batch_results['processing_time']/batch_results['total_files']:.2f}s")
        
        # Show processing statistics
        stats = processor.get_processing_stats()
        print(f"\n📋 PROCESSING STATISTICS:")
        print(f"   File types processed: {stats['file_types']}")
        if stats.get('errors'):
            print(f"   Errors encountered: {len(stats['errors'])}")
        
        print(f"\n✅ Batch processing completed!")
        print(f"📁 Results saved in: {output_folder}")
        
    except Exception as e:
        print(f"❌ FAILED - Batch processing error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()