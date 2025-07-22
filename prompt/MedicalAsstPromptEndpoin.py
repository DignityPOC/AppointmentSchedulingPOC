# langgraph_server.py
from fastapi import FastAPI
from pydantic import BaseModel
from langgraph.graph import StateGraph, END
from typing import TypedDict, Literal
from langchain.schema import HumanMessage
from langchain.chat_models import AzureChatOpenAI
import requests

OPENAI_API_KEY = ""
OPENAI_API_BASE = ""
DEPLOYMENT_NAME = "gpt-4o-mini"
OPENAI_API_VERSION = "2024-12-01-preview"

llm = AzureChatOpenAI(
    deployment_name=DEPLOYMENT_NAME,
    openai_api_key=OPENAI_API_KEY,
    openai_api_base=OPENAI_API_BASE,
    openai_api_version=OPENAI_API_VERSION
)

class State(TypedDict, total=False):
    user_input: str
    action: Literal["schedule", "reschedule", "cancel"]
    response: str

def interpret_input(state: State) -> State:
    return state

def supervisor(state: State) -> State:
    intent = state["user_input"].lower()
    if "reschedule" in intent:
        action = "reschedule"
    elif "cancel" in intent:
        action = "cancel"
    else:
        action = "schedule"
    return {**state, "action": action}

def verify_patient(state: State) -> State:
    return state

API_BASE = "http://localhost:8000"

def schedule(state: State) -> State:
    payload = {"patient_name": "John Wick", "date": "2024-06-10"}
    res = requests.post(f"{API_BASE}/schedule", json=payload)
    return {**state, "response": res.json()["message"]}

def reschedule(state: State) -> State:
    payload = {"patient_name": "John Wick", "date": "2024-06-12"}
    res = requests.post(f"{API_BASE}/reschedule", json=payload)
    return {**state, "response": res.json()["message"]}

def cancel(state: State) -> State:
    payload = {"patient_name": "John Wick"}
    res = requests.post(f"{API_BASE}/cancel", json=payload)
    return {**state, "response": res.json()["message"]}

def llm_response_wrapper(state: State) -> State:
    prompt = f"""
You are a hospital assistant. A user asked: "{state['user_input']}"
The action taken: "{state['action']}"
System says: "{state['response']}"
Respond politely.
"""
    response = llm([HumanMessage(content=prompt)])
    return {**state, "response": response.content}

builder = StateGraph(State)
builder.set_entry_point("interpret_input")

builder.add_node("interpret_input", interpret_input)
builder.add_node("supervisor", supervisor)
builder.add_node("verify_patient", verify_patient)
builder.add_node("schedule", schedule)
builder.add_node("reschedule", reschedule)
builder.add_node("cancel", cancel)
builder.add_node("llm_response_wrapper", llm_response_wrapper)

builder.add_edge("interpret_input", "supervisor")
builder.add_edge("supervisor", "verify_patient")
builder.add_conditional_edges("verify_patient", lambda s: s["action"], {
    "schedule": "schedule",
    "reschedule": "reschedule",
    "cancel": "cancel"
})
builder.add_edge("schedule", "llm_response_wrapper")
builder.add_edge("reschedule", "llm_response_wrapper")
builder.add_edge("cancel", "llm_response_wrapper")
builder.add_edge("llm_response_wrapper", END)

graph = builder.compile()

app = FastAPI()

class ChatRequest(BaseModel):
    user_input: str

class ChatResponse(BaseModel):
    response: str

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    result = graph.invoke({"user_input": request.user_input})
    return {"response": result["response"]}
