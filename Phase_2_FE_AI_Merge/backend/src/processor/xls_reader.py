import logging
import os
import subprocess
import tempfile

log = logging.getLogger(__name__)


class XlsParser():
    def convert_xls_to_xlsx(self, xls_path: str) -> str:
        output_dir = os.path.dirname(xls_path) or tempfile.gettempdir()
        try:
            subprocess.run(
                [
                    "libreoffice",
                    "--headless",
                    "--convert-to",
                    "xlsx",
                    "--outdir",
                    output_dir,
                    xls_path,
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "LibreOffice is required to process .xls files but was not found"
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else ""
            raise RuntimeError(
                "Failed to convert .xls to .xlsx. "
                f"{stderr}".strip()
            ) from exc

        converted_path = os.path.splitext(xls_path)[0] + ".xlsx"
        if not os.path.exists(converted_path):
            raise RuntimeError("Conversion failed or output file not found")
        return converted_path
