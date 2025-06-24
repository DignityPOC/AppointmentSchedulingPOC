from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

class AppState(TypedDict):
    input_text: str
    output: str

def generate_dummy(state: AppState) -> AppState:
    return {"output": f"Input value is: {state['input_text']}"}

def build_graph():
    g = StateGraph(AppState)
    g.add_node("generate", generate_dummy)
    g.add_edge(START, "generate")
    g.add_edge("generate", END)
    g.set_entry_point("generate")
    g.set_finish_point("generate")
    return g.compile()
