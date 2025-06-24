import os
from dotenv import load_dotenv
import json
from typing_extensions import TypedDict, Annotated
from typing import Literal 

from langchain_core.pydantic_v1 import constr, BaseModel, Field, validator
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts.chat import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable, RunnableConfig

from langgraph.graph import START, END, StateGraph, MessagesState
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import tools_condition, ToolNode, create_react_agent
from langchain.tools import StructuredTool

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from langgraph.types import Command

from langchain_core.tools import tool
from langchain_core.output_parsers import JsonOutputKeyToolsParser
from cancel_appointment import cancel_appointment
from schedule_appointment import schedule_appointment

# Load env file
env_path = 'environment.env'
load_dotenv(env_path)

# Instantiate Gemini LLM

llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-pro",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0,
)

# Instantiate Gemini Embeddings
embeddings = GoogleGenerativeAIEmbeddings(
    model="models/embedding-001",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
)


class AgentState(TypedDict):
    messages: MessagesState


@tool(description="Check availability of a doctor by name.")
def check_availability_by_doctor(doctor_name: str) -> str:
    # Dummy logic — you can replace this with DB/API logic
    available_doctors = {
        "Dr. John": "Available tomorrow at 10 AM",
        "Dr. Jane": "Fully booked this week"
    }
    return available_doctors.get(doctor_name, "Doctor not found.")


@tool(description="Check availability of doctors based on specialization.")
def check_availability_by_specialization(specialization: str) -> str:
    if specialization.lower() == "cardiologist":
        return "Dr. Heart is available on Monday and Thursday."
    elif specialization.lower() == "dermatologist":
        return "Dr. Skin is available on Wednesday."
    else:
        return "No doctors available for that specialization right now."


def create_agent(llm, tools: list, system_prompt: str):
    system_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("placeholder", "{messages}"),
        ]
    )
    agent = create_react_agent(model=llm, tools=tools, prompt=system_prompt)
    return agent


#  Instantiate agents using Gemini LLM
information_agent = create_agent(
    llm=llm,
    tools=[check_availability_by_doctor, check_availability_by_specialization],
    system_prompt="""You are a specialized agent to provide information related to availability of doctors or any FAQs related to hospital based on the query. You have access to the tools. Ask the user politely if you need more information to proceed. Always assume the current year is 2025."""
)

booking_agent = create_agent(
    llm=llm,
    tools=[ cancel_appointment, schedule_appointment],
    system_prompt="""You are a specialized agent to set, cancel appointments based on the query. You have access to the tools. Ask the user politely if you need more information to proceed. Always assume the current year is 2025."""
)


# Nodes to invoke the agents
def information_node(state: AgentState):
    result = information_agent.invoke(state)
    return Command(
        update={
            "messages": state["messages"] + [
                AIMessage(content=result["messages"][-1].content, name="information_node")
            ]
        },
        goto="supervisor",
    )


def booking_node(state: AgentState):
    result = booking_agent.invoke(state)
    return Command(
        update={
            "messages": state["messages"] + [
                AIMessage(content=result["messages"][-1].content, name="booking_node")
            ]
        },
        goto="supervisor",
    )


# Define your workers
members_dict = {
    "information_node": "specialized agent to provide information related to availability of doctors or any FAQs related to hospital.",
    "booking_node": "specialized agent to only book, cancel or reschedule appointments"
}
options = list(members_dict.keys()) + ["FINISH"]

worker_info = '\n\n'.join(
    [f'WORKER: {member} \nDESCRIPTION: {description}' for member, description in members_dict.items()]
) + '\n\nWORKER: FINISH \nDESCRIPTION: If user query is answered, route to FINISH.'

# System prompt for Gemini
system_prompt = (
    "You are a supervisor tasked with managing a conversation between the following specialized assistants.\n"
    f"### SPECIALIZED ASSISTANTS:\n{worker_info}\n\n"
    "Your primary role is to help the user make an appointment with the doctor or provide updates on FAQs and doctor's availability.\n"
    "When a user asks something, choose the right assistant to handle it.\n"
    "When the user's query has been fully answered, respond with FINISH.\n"
    "Always provide reasoning for your routing decision."
)

# Define routing output schema
class Router(TypedDict):
    next: Annotated[Literal["information_node", "booking_node", "FINISH"], "worker to route to next"]
    reasoning: Annotated[str, "Support proper reasoning for routing to the worker"]


# Supervisor node
def supervisor_node(state: AgentState) -> Command[Literal["information_node", "booking_node", "__end__"]]:
    messages = [{"role": "system", "content": system_prompt}] + [state["messages"][-1]]

    # Initial user query (used to restore context if re-routing)
    query = ''
    if len(state['messages']) == 1:
        query = state['messages'][0].content

    # Gemini LLM with output schema
    response = llm.with_structured_output(Router).invoke(messages)
    goto = response["next"]
    reasoning = response["reasoning"]

    if goto == "FINISH":
        goto = END

    # Update messages if it's the first turn
    if query:
        return Command(
            goto=goto,
            update={
                "next": goto,
                "query": query,
                "cur_reasoning": reasoning,
                "messages": [HumanMessage(content=f"user's identification number is {state['id_number']}")]
            }
        )

    return Command(
        goto=goto,
        update={
            "next": goto,
            "cur_reasoning": reasoning
        }
    )

# agent state
class AgentState(TypedDict):
    messages: MessagesState
    next: str
    query: str
    cur_reasoning: str
    id_number: str  # Can be user ID or similar identifier
