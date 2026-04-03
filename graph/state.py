from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class OrchestratorState(TypedDict):
    task_type: str
    messages: Annotated[list, add_messages]
    result_summary: str
