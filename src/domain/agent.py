from dataclasses import dataclass


@dataclass(frozen=True)
class AgentSettings:
    llm_api_key: str
    llm_base_url: str | None
    llm_model: str
    llm_temperature: float
    llm_request_timeout: float
