#!/usr/bin/env python3
"""
Main entry point for the Unified RAG Pipeline.

This script properly sets up the Python path and runs the pipeline.
Use this instead of running src/unified_rag_pipeline.py directly.

Usage:
    python run_pipeline.py --input input/ --output output/ --mode full
"""

import sys
import os
from pathlib import Path

# Add src directory to Python path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

# Now import and run the main function
from unified_rag_pipeline import main

if __name__ == "__main__":
    main()
