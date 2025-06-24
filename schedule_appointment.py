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



#appointments_df = pd.DataFrame(
    #columns=["firstName", "lastName", "emailId", "date", "time", "createdOn"]
#)

@tool(description="Schedule a new appointment.")
def schedule_appointment(state: ScheduleState) -> ScheduleState:
    try:
        schedule_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        state["scheduleTime"] = schedule_time

        # Append to in-memory DataFrame
        new_entry = {
            "firstName": state["firstName"],
            "lastName": state["lastName"],
            "emailId": state["emailId"],
            "date": state["date"],
            "time": state["time"],
            "createdOn": schedule_time,
        }

        #appointments_df = pd.concat(
           # [appointments_df, pd.DataFrame([new_entry])], ignore_index=True
        #)

        # Optional: Save DataFrame to CSV (acts as persistent backup)
        #appointments_df.to_csv("appointments_data.csv", index=False)

        row = f"{state['firstName']}, {state['lastName']}, {state['emailId']}, {state['date']}, {state['time']}, CreateOn:{schedule_time}\n"
        with open("appointments.txt", "a") as f:
            f.write(row)
        state["message"] = "Appointment scheduled successfully."
    except:
        state["message"] = (
            "Something went wrong while scheduling the appointment. Please contact administrator."
        )

    return state


def build_appointment_graph():
    g = StateGraph(ScheduleState)
    g.add_node("schedule", schedule_appointment)
    g.add_edge(START, "schedule")
    g.add_edge("schedule", END)
    g.set_entry_point("schedule")
    g.set_finish_point("schedule")
    return g.compile()
