from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from datetime import datetime
from langchain_core.tools import tool


class CancelState(TypedDict):
    emailId: str
    cancelled: bool
    message: str

    # Step 2: Define node logic to cancel appointment

@tool(description="Cancel a user's appointment using their email.")
def cancel_appointment(state: CancelState) -> CancelState:
    email_to_cancel = state["emailId"]
    updated_lines = []
    cancelled = False

    try:
        with open("appointments.txt", "r") as f:
            lines = f.readlines()

        for line in lines:
            if email_to_cancel not in line:
                updated_lines.append(line)
            else:
                cancelled = True

        with open("appointments.txt", "w") as f:
            f.writelines(updated_lines)

        state["cancelled"] = cancelled
        state["message"] = (
            "Appointment cancelled successfully."
            if cancelled
            else "No appointment found for the provided email."
        )

    except FileNotFoundError:
        state["cancelled"] = False
        state["message"] = "Appointment file not found."

    return state


def build_cancel_appointment_graph():
    g = StateGraph(CancelState)
    g.add_node("cancel", cancel_appointment)
    g.add_edge(START, "cancel")
    g.add_edge("cancel", END)
    g.set_entry_point("cancel")
    g.set_finish_point("cancel")
    return g.compile()
