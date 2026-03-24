"""ColQwen embeddings: local GPU/CPU or AWS SageMaker endpoint (Phase_2_PDZ_002 contract)."""

from __future__ import annotations

import os
import base64
import io
import json
import logging
import threading
from typing import Any, Dict, List, Tuple

from PIL import Image

logger = logging.getLogger(__name__)


def _as_tensor(outputs: Any) -> Any:
    import torch

    if isinstance(outputs, torch.Tensor):
        return outputs
    if hasattr(outputs, "last_hidden_state"):
        return outputs.last_hidden_state
    if isinstance(outputs, (tuple, list)) and outputs:
        first = outputs[0]
        if isinstance(first, torch.Tensor):
            return first
    raise TypeError(f"Unexpected ColQwen output: {type(outputs)!r}")


def _bool_from_cfg(inf: Dict[str, Any]) -> bool:
    v = inf.get("use_aws_sagemaker")
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes")
    return bool(v)


class ColQwenInferenceService:
    """
    When use_aws_sagemaker is True, calls SageMaker Runtime with:
      {"operation": "embed-query", "query": "..."}
      {"operation": "embed-images", "images_base64": ["..."]}
    """

    def __init__(self, yaml_config: Dict[str, Any]):
        self._cfg = yaml_config
        self._lock = threading.Lock()
        self._model = None
        self._processor = None

    @property
    def _inf(self) -> Dict[str, Any]:
        return self._cfg.get("inference", {}) or {}

    @property
    def _img(self) -> Dict[str, Any]:
        return self._cfg.get("image_retrieval", {}) or {}

    @property
    def use_sagemaker(self) -> bool:
        if os.getenv("USE_AWS_SAGEMAKER_INFERENCE", "").strip().lower() in ("1", "true", "yes"):
            return True
        return _bool_from_cfg(self._inf)

    @property
    def endpoint_name(self) -> str:
        return (self._inf.get("sagemaker_endpoint_name") or "phase2-colqwen-rt").strip()

    @property
    def aws_region(self) -> str:
        return (self._inf.get("aws_region") or "us-west-2").strip()

    @property
    def colqwen_model(self) -> str:
        return (self._img.get("colqwen", {}) or {}).get("model", "vidore/colqwen2-v1.0")

    def _sagemaker_runtime(self):
        import boto3

        return boto3.client("sagemaker-runtime", region_name=self.aws_region)

    def _invoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        rt = self._sagemaker_runtime()
        body = json.dumps(payload).encode("utf-8")
        resp = rt.invoke_endpoint(
            EndpointName=self.endpoint_name,
            ContentType="application/json",
            Body=body,
        )
        return json.loads(resp["Body"].read().decode("utf-8"))

    def embed_query(self, query: str) -> List[List[float]]:
        if self.use_sagemaker:
            data = self._invoke({"operation": "embed-query", "query": query})
            return data["embedding"]
        model, processor = self._ensure_local()
        import torch

        device = next(model.parameters()).device
        q_inputs = processor.process_queries([query]).to(device)
        with torch.no_grad():
            out = _as_tensor(model(**q_inputs))
        return out[0].float().cpu().tolist()

    def embed_images(self, images: List[Image.Image]) -> Tuple[List[List[List[float]]], List[int]]:
        if self.use_sagemaker:
            b64s = []
            for im in images:
                buf = io.BytesIO()
                im.convert("RGB").save(buf, format="PNG")
                b64s.append(base64.b64encode(buf.getvalue()).decode("ascii"))
            data = self._invoke({"operation": "embed-images", "images_base64": b64s})
            embs = data["embeddings"]
            n_patches = data.get("n_patches_per_image") or [len(x) for x in embs]
            return embs, list(n_patches)

        model, processor = self._ensure_local()
        import torch

        device = next(model.parameters()).device
        all_emb: List[List[List[float]]] = []
        n_patches: List[int] = []
        with torch.no_grad():
            for im in images:
                inputs = processor.process_images([im.convert("RGB")]).to(device)
                out = _as_tensor(model(**inputs))
                t = out[0].float().cpu().tolist()
                all_emb.append(t)
                n_patches.append(len(t))
        return all_emb, n_patches

    def _ensure_local(self) -> Tuple[Any, Any]:
        with self._lock:
            if self._model is not None:
                return self._model, self._processor
            self._load_local()
            return self._model, self._processor

    def _load_local(self) -> None:
        import torch
        from transformers import BitsAndBytesConfig

        cq = self._img.get("colqwen", {}) or {}
        model_name = cq.get("model", self.colqwen_model)
        dtype_str = cq.get("dtype", "bfloat16")
        load_4 = cq.get("load_in_4bit", False)
        load_8 = cq.get("load_in_8bit", False)
        has_cuda = torch.cuda.is_available()

        dtype_map = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}
        torch_dtype = dtype_map.get(dtype_str, torch.bfloat16)
        if not has_cuda:
            torch_dtype = torch.float32

        model_kwargs: Dict[str, Any] = {}
        if has_cuda and (load_4 or load_8):
            if load_4:
                model_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch_dtype,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                )
            else:
                model_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
        else:
            model_kwargs["dtype"] = torch_dtype

        is_25 = "colqwen2.5" in model_name.lower() or "2.5" in model_name
        if is_25:
            from colpali_engine.models import ColQwen2_5, ColQwen2_5_Processor

            self._processor = ColQwen2_5_Processor.from_pretrained(model_name)
            self._model = ColQwen2_5.from_pretrained(model_name, **model_kwargs).eval()
        else:
            from colpali_engine.models import ColQwen2, ColQwen2Processor

            self._processor = ColQwen2Processor.from_pretrained(model_name)
            self._model = ColQwen2.from_pretrained(model_name, **model_kwargs).eval()

        if has_cuda and not (load_4 or load_8):
            self._model = self._model.to("cuda")

        logger.info("ColQwen loaded locally: %s (sagemaker=%s)", model_name, self.use_sagemaker)
