from fastapi import FastAPI
from pydantic import BaseModel
from graph_logic import build_graph
from schedule_appointment import build_appointment_graph
from cancel_appointment import build_cancel_appointment_graph
from gemini_graph import build_gemini_graph  

from langchain_core.messages import HumanMessage

app = FastAPI()
graph = build_graph()
schedule_graph = build_appointment_graph()
cancel_schedule_graph = build_cancel_appointment_graph()
gemini_graph = build_gemini_graph()


class Req(BaseModel):
    input_text: str

class ScheduleReq(BaseModel):
    firstName: str
    lastName: str
    emailId: str
    date: str
    time: str
    
class CancelScheduleReq(BaseModel):
    emailId: str


@app.post("/process-input")
def process(req: Req):
    initial_state = {
        "input_text": req.input_text
    }
    final_state = graph.invoke(initial_state)
    return {"result": final_state["output"]}


@app.post("/ScheduleAppointment")
def ScheduleAppointment(req: ScheduleReq):
    initial_state = {
        "firstName": req.firstName,
        "lastName": req.lastName,
        "emailId": req.emailId,
        "date": req.date,
        "time": req.time
    }
    final_state = schedule_graph.invoke(initial_state)
    return {"Message": final_state["message"]}

@app.post("/CancelAppointment")
def CancelAppointment(req: CancelScheduleReq):
    initial_state = {
        "emailId": req.emailId
    }
    final_state = cancel_schedule_graph.invoke(initial_state)
    return {"Message": final_state["message"]}



# New Gemini endpoint
@app.post("/gemini-agent")
def run_gemini_agent(req: Req):
    initial_state = {
        "messages": [HumanMessage(content=req.input_text)],
        "next": "",
        "query": "",
        "cur_reasoning": "",
        "id_number": "U001"  # Example static ID; replace with dynamic if needed
    }
    final_state = gemini_graph.invoke(initial_state)
    return {
        "messages": [msg.content for msg in final_state["messages"]],
        "reasoning": final_state.get("cur_reasoning", "")
    }
