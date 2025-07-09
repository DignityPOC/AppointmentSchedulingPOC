from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage
from create_agent import supervisor_node, information_node, booking_node 
from typing_extensions import TypedDict 
from langgraph.graph import START, END, StateGraph, MessagesState

class AgentState(TypedDict):
    messages: MessagesState
    next: str
    query: str
    cur_reasoning: str
    id_number: str

def build_gemini_graph():
    builder = StateGraph(AgentState)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("information_node", information_node)
    builder.add_node("booking_node", booking_node)
 
    builder.add_conditional_edges(
    "supervisor",
    lambda state: state.get("next", "__end__"),
    {
        "information_node": "information_node",
        "booking_node": "booking_node",
        "__end__": END,
    },
)

    builder.add_edge("information_node", "supervisor")
    builder.add_edge("booking_node", "supervisor")

    #builder.add_edge("information_node", "supervisor")
    #builder.add_edge("booking_node", "supervisor")
    
    builder.set_entry_point("supervisor")
    return builder.compile()
