from enum import Enum
from pydantic import BaseModel

class ProviderType(str, Enum):
    OPENCODE_GO = "opencode-go"
    LMSTUDIO = "lmstudio"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"

class LLMModel(BaseModel):
    model_config = {"protected_namespaces": ()}

    provider: ProviderType
    model_id: str
    display_name: str
    context_length: int = 4096
    multimodal: bool = False
    loaded: bool = True  # For LM Studio: is model in memory
    params_string: str = ""  # e.g. "4B", "12B"
    quantization: str = ""  # e.g. "Q4_K_M"