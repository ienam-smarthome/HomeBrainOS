from ollama_agent_unified import UnifiedAdaptiveMCPAgent
from ollama_agent_fast import OllamaUnavailable


AdaptiveFinalAnswerAgent = UnifiedAdaptiveMCPAgent


__all__ = [
    "AdaptiveFinalAnswerAgent",
    "OllamaUnavailable",
]
