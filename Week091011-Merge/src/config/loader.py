"""
Configuration loader for Unified RAG Pipeline.

Supports:
- YAML configuration files
- CLI argument overrides
- Environment variable substitution
- Default value handling
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


def get_default_config_path() -> Path:
    """Get the default configuration file path."""
    # Look for config in multiple locations
    possible_paths = [
        Path(__file__).parent.parent.parent / "config" / "default.yaml",  # src/../config/
        Path.cwd() / "config" / "default.yaml",  # ./config/
        Path.cwd() / "default.yaml",  # ./default.yaml
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return possible_paths[0]  # Return first path even if doesn't exist


@dataclass
class ColQwenConfig:
    """Configuration for ColQwen image retrieval model."""
    model: str = "vidore/colqwen2-v1.0"
    dtype: str = "bfloat16"
    quantization: Optional[str] = None  # null, "4bit", "8bit"
    load_in_4bit: bool = False
    load_in_8bit: bool = False
    device_map: str = "auto"
    pdf_dpi: int = 150
    batch_size: int = 1


@dataclass
class ChunkingConfig:
    """Configuration for text chunking."""
    enabled: bool = True
    chunk_size: int = 1000
    chunk_overlap: int = 200
    min_chunk_size: int = 50
    separators: list = field(default_factory=lambda: ["\n\n", "\n", ". ", " ", ""])
    strip_whitespace: bool = True


@dataclass
class RerankerConfig:
    """Configuration for reranker."""
    enabled: bool = False
    model: Optional[str] = None
    top_k_multiplier: int = 2


@dataclass
class TextRetrievalConfig:
    """Configuration for text-based retrieval."""
    methods: list = field(default_factory=lambda: ["bm25", "dense", "hybrid"])
    default_method: str = "hybrid"
    top_k: int = 10
    embedding_model: str = "all-MiniLM-L6-v2"
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    reranker: RerankerConfig = field(default_factory=RerankerConfig)


@dataclass
class ImageRetrievalConfig:
    """Configuration for image-based retrieval."""
    enabled: bool = False
    methods: list = field(default_factory=lambda: ["colqwen"])
    top_k: int = 5
    colqwen: ColQwenConfig = field(default_factory=ColQwenConfig)


@dataclass
class GenerationConfig:
    """Configuration for LLM generation."""
    enabled: bool = True
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.0
    max_tokens: int = 2000
    enable_citations: bool = True
    citation_style: str = "numbered"


@dataclass
class LoggingConfig:
    """Configuration for logging."""
    level: str = "INFO"
    to_file: bool = True
    log_dir: str = "output/logs"
    separate_logs: bool = True
    retrieval_log: str = "retrieval.log"
    generation_log: str = "generation.log"


@dataclass
class PipelineSettings:
    """Top-level pipeline settings."""
    mode: str = "full"
    rag_mode: str = "text"
    enable_processing: bool = True
    enable_retrieval: bool = True
    enable_generation: bool = True
    enable_evaluation: bool = False


class ConfigLoader:
    """
    Loads and manages pipeline configuration from YAML files.
    
    Usage:
        loader = ConfigLoader("config/default.yaml")
        config = loader.load()
        
        # Override with CLI args
        config = loader.merge_cli_args(args)
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path) if config_path else get_default_config_path()
        self._config: Dict[str, Any] = {}
    
    def load(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}. Using defaults.")
            return self._get_defaults()
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
            
            logger.info(f"Loaded configuration from: {self.config_path}")
            
            # Substitute environment variables
            self._substitute_env_vars(self._config)
            
            return self._config
            
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return self._get_defaults()
    
    def _substitute_env_vars(self, config: Dict[str, Any]) -> None:
        """Recursively substitute ${ENV_VAR} patterns with environment values."""
        for key, value in config.items():
            if isinstance(value, dict):
                self._substitute_env_vars(value)
            elif isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                config[key] = os.environ.get(env_var)
    
    def _get_defaults(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            "pipeline": asdict(PipelineSettings()),
            "text_retrieval": {
                "methods": ["bm25", "dense", "hybrid"],
                "default_method": "hybrid",
                "top_k": 10,
                "embedding_model": "all-MiniLM-L6-v2",
                "chunking": asdict(ChunkingConfig()),
                "reranker": asdict(RerankerConfig())
            },
            "image_retrieval": {
                "enabled": False,
                "methods": ["colqwen"],
                "top_k": 5,
                "colqwen": asdict(ColQwenConfig())
            },
            "generation": asdict(GenerationConfig()),
            "logging": asdict(LoggingConfig())
        }
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a nested config value using dot notation.
        
        Example:
            loader.get("image_retrieval.colqwen.model")
        """
        keys = key_path.split(".")
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path: str, value: Any) -> None:
        """
        Set a nested config value using dot notation.
        
        Example:
            loader.set("image_retrieval.colqwen.quantization", "4bit")
        """
        keys = key_path.split(".")
        config = self._config
        
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        config[keys[-1]] = value


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to YAML config file. Uses default if None.
    
    Returns:
        Configuration dictionary.
    """
    loader = ConfigLoader(config_path)
    return loader.load()


def merge_cli_args(config: Dict[str, Any], args) -> Dict[str, Any]:
    """
    Merge CLI arguments into configuration.
    CLI arguments override config file values.
    
    Args:
        config: Configuration dictionary from YAML
        args: argparse Namespace object
    
    Returns:
        Merged configuration dictionary
    """
    # Pipeline settings
    if hasattr(args, 'mode') and args.mode:
        config.setdefault("pipeline", {})["mode"] = args.mode
    
    if hasattr(args, 'rag_mode') and args.rag_mode:
        config.setdefault("pipeline", {})["rag_mode"] = args.rag_mode
    
    # Text retrieval
    if hasattr(args, 'retrievers') and args.retrievers:
        config.setdefault("text_retrieval", {})["methods"] = args.retrievers
    
    if hasattr(args, 'top_k') and args.top_k:
        config.setdefault("text_retrieval", {})["top_k"] = args.top_k
    
    # Chunking
    if hasattr(args, 'chunk_size') and args.chunk_size:
        config.setdefault("text_retrieval", {}).setdefault("chunking", {})["chunk_size"] = args.chunk_size
    
    if hasattr(args, 'chunk_overlap') and args.chunk_overlap:
        config.setdefault("text_retrieval", {}).setdefault("chunking", {})["chunk_overlap"] = args.chunk_overlap
    
    if hasattr(args, 'no_chunking') and args.no_chunking:
        config.setdefault("text_retrieval", {}).setdefault("chunking", {})["enabled"] = False
    
    # Reranker
    if hasattr(args, 'reranker') and args.reranker and args.reranker != "none":
        config.setdefault("text_retrieval", {}).setdefault("reranker", {})["enabled"] = True
        config["text_retrieval"]["reranker"]["model"] = args.reranker
    
    # Image retrieval
    if hasattr(args, 'image_retrieval') and args.image_retrieval:
        config.setdefault("image_retrieval", {})["enabled"] = True
    
    if hasattr(args, 'image_top_k') and args.image_top_k:
        config.setdefault("image_retrieval", {})["top_k"] = args.image_top_k
    
    if hasattr(args, 'colqwen_model') and args.colqwen_model:
        config.setdefault("image_retrieval", {}).setdefault("colqwen", {})["model"] = args.colqwen_model
    
    # Quantization options
    if hasattr(args, 'quantization') and args.quantization:
        config.setdefault("image_retrieval", {}).setdefault("colqwen", {})["quantization"] = args.quantization
        if args.quantization == "4bit":
            config["image_retrieval"]["colqwen"]["load_in_4bit"] = True
        elif args.quantization == "8bit":
            config["image_retrieval"]["colqwen"]["load_in_8bit"] = True
    
    # Generation
    if hasattr(args, 'no_generation') and args.no_generation:
        config.setdefault("generation", {})["enabled"] = False
    
    if hasattr(args, 'llm_provider') and args.llm_provider:
        config.setdefault("generation", {})["provider"] = args.llm_provider
    
    if hasattr(args, 'llm_model') and args.llm_model:
        config.setdefault("generation", {})["model"] = args.llm_model
    
    if hasattr(args, 'api_key') and args.api_key:
        config.setdefault("generation", {})["api_key"] = args.api_key
    
    # Logging
    if hasattr(args, 'log_level') and args.log_level:
        config.setdefault("logging", {})["level"] = args.log_level
    
    if hasattr(args, 'no_log_file') and args.no_log_file:
        config.setdefault("logging", {})["to_file"] = False
    
    return config

