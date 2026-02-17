"""
LangGraph workflow orchestration for the AI Product Curator agent system.
"""
import logging
import uuid
from dataclasses import asdict
from datetime import datetime
from operator import add
from typing import Dict, Any, TypedDict, List, Optional, Annotated

from langgraph.graph import StateGraph, END

from ai.agents.base import AgentState
from ai.agents.query_handler import QueryHandlerAgent
from ai.agents.data_collector import DataCollectorAgent
from ai.agents.data_processor import DataProcessorAgent
from ai.agents.consumer_recommender import ConsumerRecommenderAgent
from ai.agents.business_analytics import BusinessAnalyticsAgent

logger = logging.getLogger(__name__)


class WorkflowState(TypedDict, total=False):
    """TypedDict state for LangGraph. Mirrors AgentState fields."""
    user_query: str
    mode: str
    session_id: str
    extracted_product_name: Optional[str]
    extracted_category: Optional[str]
    extracted_price_range: Optional[tuple]
    extracted_features: List[str]
    extracted_brand: Optional[str]
    query_intent: Optional[str]
    raw_product_data: List[Dict[str, Any]]
    scraping_errors: List[str]
    processed_products: List[Dict[str, Any]]
    deduplicated_products: List[Dict[str, Any]]
    ranked_products: List[Dict[str, Any]]
    recommendations: List[Dict[str, Any]]
    recommendation_reasons: Dict[str, str]
    market_metrics: Dict[str, Any]
    competitive_analysis: Dict[str, Any]
    business_insights: List[Dict[str, Any]]
    timestamp: str
    errors: Annotated[List[str], add]


# Fields that need defaults when converting dict → AgentState
_LIST_FIELDS = {
    "extracted_features", "raw_product_data", "scraping_errors",
    "processed_products", "deduplicated_products", "ranked_products",
    "recommendations", "business_insights", "errors",
}
_DICT_FIELDS = {"recommendation_reasons", "market_metrics", "competitive_analysis"}


class WorkflowOrchestrator:
    """Orchestrates the multi-agent workflow using LangGraph."""

    def __init__(self):
        self.agents = {
            "query_handler": QueryHandlerAgent(),
            "data_collector": DataCollectorAgent(),
            "data_processor": DataProcessorAgent(),
            "consumer_recommender": ConsumerRecommenderAgent(),
            "business_analytics": BusinessAnalyticsAgent(),
        }

        # Shared pipeline: query → collect → process
        # Then branch: consumer → recommender, business → analytics
        self.consumer_workflow = self._build_workflow("consumer_recommender")
        self.business_workflow = self._build_workflow("business_analytics")

        logger.info("WorkflowOrchestrator initialized")

    def _build_workflow(self, final_agent_name: str) -> StateGraph:
        """Build a 4-step workflow with a configurable final agent."""
        workflow = StateGraph(WorkflowState)

        pipeline = ["query_handler", "data_collector", "data_processor", final_agent_name]
        for name in pipeline:
            workflow.add_node(name, self._wrap_agent(self.agents[name]))

        workflow.set_entry_point(pipeline[0])
        for i in range(len(pipeline) - 1):
            workflow.add_edge(pipeline[i], pipeline[i + 1])
        workflow.add_edge(pipeline[-1], END)

        return workflow.compile()

    def _wrap_agent(self, agent):
        """Wrap agent to convert between WorkflowState dict and AgentState dataclass."""
        async def wrapper(state: WorkflowState) -> WorkflowState:
            # Dict → AgentState (with defaults for missing fields)
            kwargs = dict(state)
            kwargs.pop("timestamp", None)
            for f in _LIST_FIELDS:
                kwargs.setdefault(f, [])
            for f in _DICT_FIELDS:
                kwargs.setdefault(f, {})
            agent_state = AgentState(**{k: v for k, v in kwargs.items() if k in AgentState.__dataclass_fields__})

            result = await agent.process(agent_state)

            # AgentState → dict
            result_dict = asdict(result)
            result_dict["timestamp"] = result.timestamp.isoformat() if result.timestamp else datetime.now().isoformat()
            return result_dict
        return wrapper

    async def run(self, user_query: str, mode: str = "consumer", session_id: str = None) -> Dict[str, Any]:
        """Run the appropriate workflow."""
        try:
            session_id = session_id or str(uuid.uuid4())

            initial_state: WorkflowState = {
                "user_query": user_query,
                "mode": mode,
                "session_id": session_id,
                "extracted_features": [],
                "raw_product_data": [],
                "scraping_errors": [],
                "processed_products": [],
                "deduplicated_products": [],
                "ranked_products": [],
                "recommendations": [],
                "recommendation_reasons": {},
                "market_metrics": {},
                "competitive_analysis": {},
                "business_insights": [],
                "timestamp": datetime.now().isoformat(),
                "errors": [],
            }

            workflow = self.consumer_workflow if mode == "consumer" else self.business_workflow
            final_state = await workflow.ainvoke(initial_state)

            logger.info(f"{mode} workflow completed: {len(final_state.get('recommendations', []))} recommendations")
            return final_state

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}", exc_info=True)
            return {
                "user_query": user_query, "mode": mode, "session_id": session_id,
                "recommendations": [], "errors": [str(e)], "timestamp": datetime.now().isoformat(),
            }

    async def search_products(self, query: str, **kwargs) -> Dict[str, Any]:
        return await self.run(user_query=query, mode="consumer", **kwargs)

    async def analyze_market(self, query: str, **kwargs) -> Dict[str, Any]:
        return await self.run(user_query=query, mode="business", **kwargs)


_workflow_orchestrator: Optional[WorkflowOrchestrator] = None


def get_workflow_orchestrator() -> WorkflowOrchestrator:
    global _workflow_orchestrator
    if _workflow_orchestrator is None:
        _workflow_orchestrator = WorkflowOrchestrator()
    return _workflow_orchestrator
