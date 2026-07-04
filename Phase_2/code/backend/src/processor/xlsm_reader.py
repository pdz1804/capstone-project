import logging
import os
import subprocess
import tempfile

log = logging.getLogger(__name__)


class XlsmParser():
    def convert_xlsm_to_xlsx(self, xlsm_path: str) -> str:
        output_dir = os.path.dirname(xlsm_path) or tempfile.gettempdir()
        try:
            subprocess.run(
                [
                    "libreoffice",
                    "--headless",
                    "--convert-to",
                    "xlsx",
                    "--outdir",
                    output_dir,
                    xlsm_path,
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "LibreOffice is required to process .xlsm files but was not found"
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else ""
            raise RuntimeError(
                "Failed to convert .xlsm to .xlsx. "
                f"{stderr}".strip()
            ) from exc

        converted_path = os.path.splitext(xlsm_path)[0] + ".xlsx"
        if not os.path.exists(converted_path):
            raise RuntimeError("Conversion failed or output file not found")
        return converted_path


file = "/home/khoinn12/Documents/test_parsing/raw/excel/3df755cd7ba34e6ea727759d6791e185.xlsm"
parser = XlsmParser()
parser.convert_xlsm_to_xlsx(file)