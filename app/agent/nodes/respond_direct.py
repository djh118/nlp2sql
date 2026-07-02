from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState


async def respond_direct(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer

    response_text = state.get("direct_response", "")
    writer({"result": [{"message": response_text}]})
