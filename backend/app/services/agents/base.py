"""
BaseAgent abstract interface for CodeForge AI Step 12 Multi-Agent Architecture.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict
from sqlalchemy.orm import Session
from app.models.multi_agent import AgentRun, AgentRunStep


class BaseAgent(ABC):
    """
    Abstract base class for all specialized agents in the CodeForge AI multi-agent system.
    Enforces structured context input, structured schema output, confidence reporting,
    and execution through durable step tracking.
    """
    def __init__(self, agent_type: str):
        self.agent_type = agent_type

    @abstractmethod
    async def execute(
        self,
        db: Session,
        run: AgentRun,
        step: AgentRunStep,
        context: Dict[str, Any]
    ) -> Any:
        """
        Executes specialized agent logic using structured context.
        Returns a structured Pydantic result model.
        Must never modify the original user repository directly.
        Must never expose secrets or credentials.
        """
        pass
