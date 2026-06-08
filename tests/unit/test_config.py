from gradescope_autograde.config import (
    AppConfig,
    LLMConfig,
    load_config,
)


def test_default_config():
    config = AppConfig()
    assert config.llm.provider == "opencode-go"
    assert config.llm.model == "deepseek-v4-flash"
    assert config.lmstudio.auto_discover is True
    assert config.workflow.review_threshold == 0.7

def test_load_example_config():
    config = load_config("config/config.example.yaml")
    assert config.auth is not None
    assert config.llm.provider == "opencode-go"

def test_llm_config_multimodal():
    config = LLMConfig()
    assert config.multimodal_model == "mimo-v2.5"
