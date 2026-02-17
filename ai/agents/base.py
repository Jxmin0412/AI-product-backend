"""Base agent class for the AI Product Curator agent system."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import logging

from ai.llm_client import get_llm_client

logger = logging.getLogger(__name__)


@dataclass
class AgentState:
    """Shared state passed between agents in the workflow."""
    # Input
    user_query: str
    mode: str = "consumer"  # 'consumer' or 'business'

    # Query Handler Agent outputs
    extracted_product_name: Optional[str] = None
    extracted_category: Optional[str] = None
    extracted_price_range: Optional[tuple] = None
    extracted_features: List[str] = field(default_factory=list)
    extracted_brand: Optional[str] = None
    query_intent: Optional[str] = None

    # Data Collector Agent outputs
    raw_product_data: List[Dict[str, Any]] = field(default_factory=list)
    scraping_errors: List[str] = field(default_factory=list)

    # Data Processor Agent outputs
    processed_products: List[Dict[str, Any]] = field(default_factory=list)
    deduplicated_products: List[Dict[str, Any]] = field(default_factory=list)

    # Consumer Recommender Agent outputs
    ranked_products: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[Dict[str, Any]] = field(default_factory=list)
    recommendation_reasons: Dict[str, str] = field(default_factory=dict)

    # Business Analytics Agent outputs
    market_metrics: Dict[str, Any] = field(default_factory=dict)
    competitive_analysis: Dict[str, Any] = field(default_factory=dict)
    business_insights: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    session_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_query": self.user_query,
            "mode": self.mode,
            "extracted_product_name": self.extracted_product_name,
            "extracted_category": self.extracted_category,
            "extracted_price_range": self.extracted_price_range,
            "query_intent": self.query_intent,
            "processed_products": self.processed_products,
            "recommendations": self.recommendations,
            "market_metrics": self.market_metrics,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "errors": self.errors
        }


class BaseAgent(ABC):
    """Abstract base class for all agents in the system."""

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"agent.{name}")
        self.llm_client = get_llm_client()

    @abstractmethod
    async def process(self, state: AgentState) -> AgentState:
        pass

    def log_start(self, state: AgentState):
        self.logger.info(f"{self.name} started processing query: {state.user_query[:50]}...")

    def log_end(self, state: AgentState):
        self.logger.info(f"{self.name} completed processing")

    def log_error(self, error: Exception, state: AgentState):
        self.logger.error(f"{self.name} error: {error}", exc_info=True)
        state.errors.append(f"{self.name}: {str(error)}")

    async def generate_text(self, prompt: str, system_prompt: str = None, **kwargs) -> str:
        try:
            return await self.llm_client.generate(prompt, system_prompt=system_prompt, **kwargs)
        except Exception as e:
            self.logger.error(f"Text generation failed: {e}")
            return ""

    async def extract_json(self, prompt: str, system_prompt: str = None) -> Optional[Dict[str, Any]]:
        try:
            return await self.llm_client.extract_json(prompt, system_prompt=system_prompt)
        except Exception as e:
            self.logger.error(f"JSON extraction failed: {e}")
            return None

    def __repr__(self):
        return f"<{self.__class__.__name__}(name='{self.name}')>"
