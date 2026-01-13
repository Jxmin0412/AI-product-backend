"""
LangGraph workflow orchestration for the AI Product Curator agent system.
Defines the workflow graph and agent execution sequence.
"""
from typing import Dict, Any, TypedDict, List, Optional, Annotated
from langgraph.graph import StateGraph, END
import logging
import uuid
from datetime import datetime
from operator import add

from agents.base_agent import AgentState
from agents.query_handler import QueryHandlerAgent
from agents.data_collector import DataCollectorAgent
from agents.data_processor import DataProcessorAgent
from agents.consumer_recommender import ConsumerRecommenderAgent
from agents.business_analytics import BusinessAnalyticsAgent

logger = logging.getLogger(__name__)


class WorkflowState(TypedDict, total=False):
    """
    TypedDict state for LangGraph workflow.
    Maps to AgentState fields.
    """
    # Input
    user_query: str
    mode: str
    session_id: str

    # Query Handler outputs
    extracted_product_name: Optional[str]
    extracted_category: Optional[str]
    extracted_price_range: Optional[tuple]
    extracted_features: List[str]
    extracted_brand: Optional[str]
    query_intent: Optional[str]

    # Data Collector outputs
    raw_product_data: List[Dict[str, Any]]
    scraping_errors: List[str]

    # Data Processor outputs
    processed_products: List[Dict[str, Any]]
    deduplicated_products: List[Dict[str, Any]]

    # Consumer Recommender outputs
    ranked_products: List[Dict[str, Any]]
    recommendations: List[Dict[str, Any]]
    recommendation_reasons: Dict[str, str]

    # Business Analytics outputs
    market_metrics: Dict[str, Any]
    competitive_analysis: Dict[str, Any]
    business_insights: List[Dict[str, Any]]

    # Metadata
    timestamp: str
    errors: Annotated[List[str], add]


class WorkflowOrchestrator:
    """
    Orchestrates the multi-agent workflow using LangGraph.
    Routes between consumer and business intelligence modes.
    """

    def __init__(self):
        """Initialize workflow orchestrator with agents."""
        self.query_handler = QueryHandlerAgent()
        self.data_collector = DataCollectorAgent()
        self.data_processor = DataProcessorAgent()
        self.consumer_recommender = ConsumerRecommenderAgent()
        self.business_analytics = BusinessAnalyticsAgent()

        # Build workflow graphs
        self.consumer_workflow = self._build_consumer_workflow()
        self.business_workflow = self._build_business_workflow()

        logger.info("WorkflowOrchestrator initialized")

    def _build_consumer_workflow(self) -> StateGraph:
        """
        Build the consumer-facing product search workflow.

        Flow: Query Handler -> Data Collector -> Data Processor -> Consumer Recommender
        """
        workflow = StateGraph(WorkflowState)

        # Add nodes (wrap agent process methods)
        workflow.add_node("query_handler", self._wrap_agent(self.query_handler))
        workflow.add_node("data_collector", self._wrap_agent(self.data_collector))
        workflow.add_node("data_processor", self._wrap_agent(self.data_processor))
        workflow.add_node("consumer_recommender", self._wrap_agent(self.consumer_recommender))

        # Define edges (sequential flow)
        workflow.set_entry_point("query_handler")
        workflow.add_edge("query_handler", "data_collector")
        workflow.add_edge("data_collector", "data_processor")
        workflow.add_edge("data_processor", "consumer_recommender")
        workflow.add_edge("consumer_recommender", END)

        return workflow.compile()

    def _build_business_workflow(self) -> StateGraph:
        """
        Build the business intelligence workflow.

        Flow: Query Handler -> Data Collector -> Data Processor -> Business Analytics
        """
        workflow = StateGraph(WorkflowState)

        # Add nodes
        workflow.add_node("query_handler", self._wrap_agent(self.query_handler))
        workflow.add_node("data_collector", self._wrap_agent(self.data_collector))
        workflow.add_node("data_processor", self._wrap_agent(self.data_processor))
        workflow.add_node("business_analytics", self._wrap_agent(self.business_analytics))

        # Define edges
        workflow.set_entry_point("query_handler")
        workflow.add_edge("query_handler", "data_collector")
        workflow.add_edge("data_collector", "data_processor")
        workflow.add_edge("data_processor", "business_analytics")
        workflow.add_edge("business_analytics", END)

        return workflow.compile()

    def _wrap_agent(self, agent):
        """
        Wrap an agent's process method to convert between WorkflowState and AgentState.
        """
        async def wrapper(state: WorkflowState) -> WorkflowState:
            # Convert WorkflowState to AgentState
            agent_state = self._to_agent_state(state)

            # Process
            result_state = await agent.process(agent_state)

            # Convert back to WorkflowState
            return self._to_workflow_state(result_state)

        return wrapper

    def _to_agent_state(self, workflow_state: WorkflowState) -> AgentState:
        """Convert WorkflowState dict to AgentState dataclass."""
        return AgentState(
            user_query=workflow_state.get("user_query", ""),
            mode=workflow_state.get("mode", "consumer"),
            extracted_product_name=workflow_state.get("extracted_product_name"),
            extracted_category=workflow_state.get("extracted_category"),
            extracted_price_range=workflow_state.get("extracted_price_range"),
            extracted_features=workflow_state.get("extracted_features", []),
            extracted_brand=workflow_state.get("extracted_brand"),
            query_intent=workflow_state.get("query_intent"),
            raw_product_data=workflow_state.get("raw_product_data", []),
            scraping_errors=workflow_state.get("scraping_errors", []),
            processed_products=workflow_state.get("processed_products", []),
            deduplicated_products=workflow_state.get("deduplicated_products", []),
            ranked_products=workflow_state.get("ranked_products", []),
            recommendations=workflow_state.get("recommendations", []),
            recommendation_reasons=workflow_state.get("recommendation_reasons", {}),
            market_metrics=workflow_state.get("market_metrics", {}),
            competitive_analysis=workflow_state.get("competitive_analysis", {}),
            business_insights=workflow_state.get("business_insights", []),
            session_id=workflow_state.get("session_id"),
            errors=workflow_state.get("errors", []),
        )

    def _to_workflow_state(self, agent_state: AgentState) -> WorkflowState:
        """Convert AgentState dataclass to WorkflowState dict."""
        return {
            "user_query": agent_state.user_query,
            "mode": agent_state.mode,
            "session_id": agent_state.session_id,
            "extracted_product_name": agent_state.extracted_product_name,
            "extracted_category": agent_state.extracted_category,
            "extracted_price_range": agent_state.extracted_price_range,
            "extracted_features": agent_state.extracted_features,
            "extracted_brand": agent_state.extracted_brand,
            "query_intent": agent_state.query_intent,
            "raw_product_data": agent_state.raw_product_data,
            "scraping_errors": agent_state.scraping_errors,
            "processed_products": agent_state.processed_products,
            "deduplicated_products": agent_state.deduplicated_products,
            "ranked_products": agent_state.ranked_products,
            "recommendations": agent_state.recommendations,
            "recommendation_reasons": agent_state.recommendation_reasons,
            "market_metrics": agent_state.market_metrics,
            "competitive_analysis": agent_state.competitive_analysis,
            "business_insights": agent_state.business_insights,
            "timestamp": agent_state.timestamp.isoformat() if agent_state.timestamp else datetime.now().isoformat(),
            "errors": agent_state.errors,
        }

    async def run(self, user_query: str, mode: str = "consumer", session_id: str = None) -> Dict[str, Any]:
        """
        Run the appropriate workflow based on mode.

        Args:
            user_query: User's search query or business question
            mode: 'consumer' or 'business'
            session_id: Optional session ID for tracking

        Returns:
            Dict[str, Any]: Final workflow state as dictionary
        """
        try:
            logger.info(f"Starting {mode} workflow for query: {user_query[:50]}...")

            # Generate session ID if not provided
            if not session_id:
                session_id = str(uuid.uuid4())

            # Initialize state
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

            # Select and run workflow
            if mode == "consumer":
                final_state = await self.consumer_workflow.ainvoke(initial_state)
            elif mode == "business":
                final_state = await self.business_workflow.ainvoke(initial_state)
            else:
                raise ValueError(f"Invalid mode: {mode}. Must be 'consumer' or 'business'")

            logger.info(f"{mode.capitalize()} workflow completed successfully")
            logger.info(f"Results: {len(final_state.get('recommendations', []))} recommendations")

            return final_state

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}", exc_info=True)
            return {
                "user_query": user_query,
                "mode": mode,
                "session_id": session_id,
                "recommendations": [],
                "errors": [str(e)],
                "timestamp": datetime.now().isoformat(),
            }

    async def search_products(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Convenience method for consumer product search.

        Args:
            query: Search query
            **kwargs: Additional parameters

        Returns:
            Search results with recommendations
        """
        return await self.run(user_query=query, mode="consumer", **kwargs)

    async def analyze_market(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Convenience method for business market analysis.

        Args:
            query: Analysis query
            **kwargs: Additional parameters

        Returns:
            Market analysis results
        """
        return await self.run(user_query=query, mode="business", **kwargs)


# Global workflow orchestrator instance
_workflow_orchestrator: Optional[WorkflowOrchestrator] = None


def get_workflow_orchestrator() -> WorkflowOrchestrator:
    """
    Get or create global workflow orchestrator instance.

    Returns:
        WorkflowOrchestrator: Global orchestrator instance
    """
    global _workflow_orchestrator

    if _workflow_orchestrator is None:
        _workflow_orchestrator = WorkflowOrchestrator()

    return _workflow_orchestrator
