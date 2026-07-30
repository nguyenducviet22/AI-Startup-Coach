from app.llm.openrouter import ChatCompletionClient, OpenRouterChatClient


def get_chat_client() -> ChatCompletionClient:
    return OpenRouterChatClient()
