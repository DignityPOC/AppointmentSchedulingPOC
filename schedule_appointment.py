from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from datetime import datetime
import pandas as pd
from langchain_core.tools import tool

class ScheduleState(TypedDict):
    firstName: str
    lastName: str
    emailId: str
    date: str
    time: str
    message: str


@tool(description="Schedule a new appointment. Based on First Name and LastName provided")
def schedule_appointment(state: ScheduleState) -> ScheduleState:
    try:
        schedule_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        state["scheduleTime"] = schedule_time

        row = f"{state['firstName']}, {state['lastName']}, {state['emailId']}, {state['date']}, {state['time']}, CreateOn:{schedule_time}\n"
        with open("appointments.txt", "a") as f:
            f.write(row)
        return "Appointment scheduled successfully."
    except:
        return "Something went wrong while scheduling the appointment. Please contact administrator."

def build_appointment_graph():
    g = StateGraph(ScheduleState)
    g.add_node("schedule", schedule_appointment)
    g.add_edge(START, "schedule")
    g.add_edge("schedule", END)
    g.set_entry_point("schedule")
    g.set_finish_point("schedule")
    return g.compile()
