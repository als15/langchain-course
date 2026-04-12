import os


def get_llm(temperature: float = 0.5):
    """Get the LLM based on LLM_PROVIDER env var. 'ollama' for local, 'openai' for cloud."""
    provider = os.environ.get("LLM_PROVIDER", "ollama")
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model="gpt-4o", temperature=temperature, max_retries=3)
    else:
        from langchain_ollama import ChatOllama

        return ChatOllama(model="llama3.1", temperature=temperature)
