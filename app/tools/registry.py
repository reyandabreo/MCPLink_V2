from typing import Dict, Any, Type, Callable
from pydantic import BaseModel
from app.core.exceptions import MCPLinkError

class ToolConfig(BaseModel):
    name: str
    description: str
    args_schema: Type[BaseModel]
    callable: Callable

class ToolRegistry:
    """Central registry for all tools available to the AI Agent."""
    
    def __init__(self):
        self._tools: Dict[str, ToolConfig] = {}
        
    def register(self, name: str, description: str, args_schema: Type[BaseModel]):
        """Decorator to register a tool function."""
        def decorator(func: Callable):
            if name in self._tools:
                raise MCPLinkError(f"Tool {name} is already registered.")
                
            self._tools[name] = ToolConfig(
                name=name,
                description=description,
                args_schema=args_schema,
                callable=func
            )
            return func
        return decorator
        
    def get_tool(self, name: str) -> ToolConfig:
        if name not in self._tools:
            raise MCPLinkError(f"Tool {name} not found in registry.")
        return self._tools[name]
        
    def list_tools(self) -> Dict[str, dict]:
        """Returns schemas for all registered tools."""
        return {
            name: {
                "description": tool.description,
                "parameters": tool.args_schema.model_json_schema()
            }
            for name, tool in self._tools.items()
        }

# Global registry instance
tool_registry = ToolRegistry()
