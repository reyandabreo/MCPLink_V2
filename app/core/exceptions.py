class MCPLinkError(Exception):
    """Base exception for MCPLink Backend"""
    pass

class PlanValidationError(MCPLinkError):
    """Raised when an LLM plan fails JSON schema validation"""
    pass

class PolicyViolationError(MCPLinkError):
    """Raised when an execution violates policy (timeout, paths, etc)"""
    pass

class ToolExecutionError(MCPLinkError):
    """Raised when a sandbox tool execution fails"""
    pass

class FileParsingError(MCPLinkError):
    """Raised when reading or extracting context from a document fails"""
    pass
