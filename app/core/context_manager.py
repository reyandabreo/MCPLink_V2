from app.memory.session_store import session_store
from app.memory.history import history_manager
from app.config import settings

class ContextManager:
    """Manages contextual memory and state during a session."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        
        # Ensure session exists
        if not session_store.get_session(session_id):
            session_store.create_session(session_id)
            
    def get_conversation_history(self) -> str:
        """Retrieves formatted prompt history."""
        prompts = history_manager.get_prompts(self.session_id)
        if not prompts:
            return ""
            
        history = "Conversation History:\n"
        for i, p in enumerate(prompts):
            history += f"Prompt {i+1}: {p}\n"
        return history
        
    def inject_document_content(self, content: str) -> str:
        """Injects large content while tracking/truncating basic token limits"""
        # Very crude token estimation: 1 word ~ 1.3 tokens
        approx_tokens = len(content.split()) * 1.3
        
        if approx_tokens > settings.TOKEN_LIMIT:
            # Optionally truncate or chunk here
            content = content[:int(settings.TOKEN_LIMIT * 3)] + "... [TRUNCATED DUE TO LENGTH]"
            
        return content

    def build_context(self, additional_context: str = "") -> str:
        """Combines history and explicit additional context."""
        context = self.get_conversation_history()
        if additional_context:
            context += f"\nAdditional Information:\n{self.inject_document_content(additional_context)}"
        return context
