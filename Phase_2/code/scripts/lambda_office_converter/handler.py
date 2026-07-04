"""
AWS Lambda Handler for Office to PDF Conversion
Using LibreOffice 26.2 in Lambda Container
"""
import json
import base64
import subprocess
import tempfile
import os
from pathlib import Path


def handler(event, context):
    """
    Lambda handler for Office to PDF conversion.

    Expected payload:
    {
        "operation": "convert-to-pdf",
        "filename": "document.docx",
        "extension": ".docx",
        "content_base64": "<base64-encoded-file>"
    }

    Returns:
    {
        "ok": true,
        "pdf_base64": "<base64-encoded-pdf>"
    }
    """
    try:
        print(f"Received event: {json.dumps({k: v if k != 'content_base64' else f'{v[:50]}...' for k, v in event.items()})}")

        # Parse input
        operation = event.get('operation')
        if operation != 'convert-to-pdf':
            return {
                'ok': False,
                'error': f'Unknown operation: {operation}'
            }

        filename = event.get('filename', 'document')
        content_base64 = event.get('content_base64')

        if not content_base64:
            return {
                'ok': False,
                'error': 'Missing content_base64 in payload'
            }

        # Decode file content
        try:
            content_bytes = base64.b64decode(content_base64)
        except Exception as e:
            return {
                'ok': False,
                'error': f'Failed to decode base64 content: {str(e)}'
            }

        print(f"Processing file: {filename} ({len(content_bytes)} bytes)")

        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Write input file
            input_path = os.path.join(temp_dir, filename)
            with open(input_path, 'wb') as f:
                f.write(content_bytes)

            print(f"Input file written: {input_path}")

            # Convert to PDF using LibreOffice
            print("Running LibreOffice conversion...")
            result = subprocess.run([
                'libreoffice',
                '--headless',
                '--invisible',
                '--nodefault',
                '--view',
                '--nolockcheck',
                '--nologo',
                '--norestore',
                '--convert-to',
                'pdf',
                '--outdir',
                temp_dir,
                input_path
            ], capture_output=True, timeout=60, check=False)

            stdout = result.stdout.decode('utf-8', errors='ignore')
            stderr = result.stderr.decode('utf-8', errors='ignore')

            print(f"LibreOffice stdout: {stdout}")
            print(f"LibreOffice stderr: {stderr}")
            print(f"Exit code: {result.returncode}")

            # Find output PDF
            input_name = Path(input_path).stem
            pdf_path = os.path.join(temp_dir, f"{input_name}.pdf")

            if not os.path.exists(pdf_path):
                # List what's in temp dir for debugging
                print(f"Contents of {temp_dir}:")
                for item in os.listdir(temp_dir):
                    print(f"  - {item}")

                error_msg = stderr or stdout or f"Exit code {result.returncode}"
                raise RuntimeError(f"PDF not created at {pdf_path}. Error: {error_msg}")

            # Read PDF and encode to base64
            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()

            pdf_base64 = base64.b64encode(pdf_bytes).decode('ascii')

            print(f"✓ Conversion successful. PDF size: {len(pdf_bytes)} bytes")

            return {
                'ok': True,
                'pdf_base64': pdf_base64
            }

    except subprocess.TimeoutExpired:
        return {
            'ok': False,
            'error': 'LibreOffice conversion timed out after 60 seconds'
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            'ok': False,
            'error': str(e)
        }
