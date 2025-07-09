from fastapi import FastAPI
from pydantic import BaseModel
from graph_logic import build_graph
from schedule_appointment import build_appointment_graph
from cancel_appointment import build_cancel_appointment_graph
from gemini_graph import build_gemini_graph
from langchain_core.messages import HumanMessage, AIMessage
from typing import List, Optional
from langchain_core.messages import BaseMessage
from pydantic import parse_obj_as, BaseModel
from typing import List, Optional, Literal

app = FastAPI()
graph = build_graph()
schedule_graph = build_appointment_graph()
cancel_schedule_graph = build_cancel_appointment_graph()
gemini_graph = build_gemini_graph()

class ChatMessage(BaseModel):
    role: Literal["user", "ai", "human", "assistant"]
    content: str


class Req(BaseModel):
    input_text: str
    messages: Optional[List[ChatMessage]] = None


class Req(BaseModel):
    input_text: str
    messages: Optional[List[dict]] = None


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
    initial_state = {"input_text": req.input_text}
    final_state = graph.invoke(initial_state)
    return {"result": final_state["output"]}


@app.post("/ScheduleAppointment")
def ScheduleAppointment(req: ScheduleReq):
    initial_state = {
        "firstName": req.firstName,
        "lastName": req.lastName,
        "emailId": req.emailId,
        "date": req.date,
        "time": req.time,
    }
    final_state = schedule_graph.invoke(initial_state)
    return {"Message": final_state["message"]}

@app.post("/CancelAppointment")
def CancelAppointment(req: CancelScheduleReq):
    initial_state = {"emailId": req.emailId}
    final_state = cancel_schedule_graph.invoke(initial_state)
    return {"Message": final_state["message"]}

@app.post("/gemini-agent")
def run_gemini_agent(req: Req):
    messages = []

    if req.messages:
        parsed_messages = parse_obj_as(List[ChatMessage], req.messages)
        for m in parsed_messages:
            role = m.role
            if role == "human":
                role = "user"
            elif role == "assistant":
                role = "ai"

            if role == "user":
                messages.append(HumanMessage(content=m.content))
            elif role == "ai":
                messages.append(AIMessage(content=m.content))

    if messages and isinstance(messages[-1], HumanMessage):
        raise ValueError(
            "Cannot append another user message; the last message is already from the user."
        )
    # Always append the latest input_text as a new user message
    messages.append(HumanMessage(content=req.input_text))

    # Validate last message is from user
    if not isinstance(messages[-1], HumanMessage):
        raise ValueError("Gemini requires the last message to be from the user.")

    initial_state = {
        "messages": messages,
        "next": "",
        "query": "",
        "cur_reasoning": "",
        "id_number": "U001",
    }
    final_state = gemini_graph.invoke(initial_state, config={"recursion_limit": 5})

    # If routing is not FINISH, run the next agent node
    if final_state.get("next") and final_state["next"] != "__end__":
        final_state = gemini_graph.invoke(final_state, config={"recursion_limit": 5})

    return {
        "messages": [
            {"role": m.type, "content": m.content, "next": final_state.get("next")}
            for m in final_state["messages"]
        ],
        "reasoning": final_state.get("cur_reasoning", ""),
    }