from typing import Dict, Any, List
from pydantic import BaseModel, Field

class ToolCallStep(BaseModel):
    tool_name: str = Field(..., description="Name of the tool to execute")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments to pass to the tool")
    explanation: str = Field(..., description="Explanation of why this tool is being used")

class ExecutionPlan(BaseModel):
    goal: str = Field(..., description="The overall goal of this plan")
    steps: List[ToolCallStep] = Field(..., description="Ordered list of steps to execute the plan")
