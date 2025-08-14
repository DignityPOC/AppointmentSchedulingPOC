import os
from dotenv import load_dotenv
import json
from typing_extensions import TypedDict, Annotated
from typing import Literal

'''from langchain_core.pydantic_v1 import constr, BaseModel, Field, validator'''
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
import time


# Load env file
env_path = "environment.env"
load_dotenv(env_path)

# Instantiate Gemini LLM

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.3,
)

# Instantiate Gemini Embeddings
embeddings = GoogleGenerativeAIEmbeddings(
    model="models/embedding-001",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
)


class AgentState(TypedDict):
    messages: MessagesState
    # messages: Annotated[list[StrOrMsg], ListAppend]


@tool(description="Check availability of a doctor by name.")
def check_availability_by_doctor(doctor_name: str) -> str:
    # Dummy logic — you can replace this with DB/API logic
    available_doctors = {
        "Dr. Puneet": "Available tomorrow at 10 AM",
        "Dr. Raj": "Fully booked this week",
    }
    return available_doctors.get(doctor_name, "Doctor not found.")


@tool(description="Check availability of doctors based on specialization.")
def check_availability_by_specialization(specialization: str) -> str:
    if specialization.lower() == "cardiologist":
        return "Dr. Puneet is available on Monday and Thursday."
    elif specialization.lower() == "dermatologist":
        return "Dr. Raj is available on Wednesday."
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
    system_prompt="""You are a specialized agent to provide information related to availability of doctors or any FAQs related to hospital based on the query. You have access to the tools. Ask the user politely if you need more information to proceed. Always assume the current year is 2025.""",
)

booking_agent = create_agent(
    llm=llm,
    tools=[cancel_appointment, schedule_appointment],
    system_prompt="""You are a specialized agent to set, cancel appointments based on the query. You have access to the tools. Ask the user politely if you need more information to proceed. Always assume the current year is 2025.""",
)


# Nodes to invoke the agents
def information_node(state: AgentState):
    time.sleep(5)
    valid_messages = [
        msg
        for msg in state["messages"]
        if isinstance(msg, (HumanMessage, AIMessage)) and msg.content.strip() != ""
    ]
    print("VALID MESSAGES >>>", valid_messages)

    try:
        result = information_agent.invoke({"messages": valid_messages})
        print("INFORMATION NODE RESULT >>>", result)
    except Exception as e:
        print("Error in information_node:", e)
        return Command(
            update={
                "messages": state["messages"]
                + [
                    AIMessage(
                        content="Sorry, something went wrong while fetching doctor availability."
                    )
                ]
            },
            goto="supervisor",
        )

    return Command(
        update={
            "messages": state["messages"]
            + [
                AIMessage(
                    content=result["messages"][-1].content, name="information_node"
                )
            ]
        },
        goto="supervisor",
    )


def booking_node(state: AgentState):
    time.sleep(2)
    print("Booking node called.")
    valid_messages = [
        msg
        for msg in state["messages"]
        if isinstance(msg, (HumanMessage, AIMessage)) and msg.content.strip() != ""
    ]

    try:
        result = booking_agent.invoke({"messages": valid_messages})
        print("BOOKING NODE RESULT >>>", result)
        response_msg = result["messages"][-1].content.strip()
    except Exception as e:
        print("Error in booking_node:", e)
        return Command(
            update={
                "messages": state["messages"]
                + [
                    AIMessage(
                        content="Sorry, something went wrong while handling booking."
                    )
                ]
            },
            goto="supervisor",
        )

    # If result is empty, end the loop
    if not response_msg:
        return Command(
            update={
                "messages": state["messages"]
                + [
                    AIMessage(
                        content="I'm sorry, I couldn't find enough information to proceed."
                    )
                ]
            },
            goto=END,
        )

    return Command(
        update={
            "messages": state["messages"]
            + [AIMessage(content=response_msg, name="booking_node")]
        },
        goto="supervisor",
    )


# Define your workers
members_dict = {
    "information_node": "specialized agent to provide information related to availability of doctors or any FAQs related to hospital.",
    "booking_node": "specialized agent to only book, cancel or reschedule appointments",
}
options = list(members_dict.keys()) + ["FINISH"]

worker_info = (
    "\n\n".join(
        [
            f"WORKER: {member} \nDESCRIPTION: {description}"
            for member, description in members_dict.items()
        ]
    )
    + "\n\nWORKER: FINISH \nDESCRIPTION: If user query is answered, route to FINISH."
)

system_prompt = (
    "You are a supervisor tasked with managing a conversation between following workers. "
    "### SPECIALIZED ASSISTANT:\n"
    f"{worker_info}\n\n"
    "Your primary role is to help the user make an appointment with the doctor and provide updates on FAQs and doctor's availability. "
    "If a customer requests to know the availability of a doctor or to book, reschedule, or cancel an appointment, "
    "delegate the task to the appropriate specialized workers. Given the following user request,"
    " respond with the worker to act next. Each worker will perform a"
    " task and respond with their results and status. When finished,"
    " respond with FINISH."
    "UTILIZE last conversation to assess if the conversation should end you answered the query, then route to FINISH "
)


# Define routing output schema
class Router(TypedDict):
    next: Annotated[
        Literal["information_node", "booking_node", "FINISH"], "worker to route to next"
    ]
    reasoning: Annotated[str, "Support proper reasoning for routing to the worker"]


def supervisor_node(
    state: AgentState,
) -> Command[Literal["information_node", "booking_node", "__end__"]]:
    print("Routing from supervisor")

    messages = [{"role": "system", "content": system_prompt}]
    for msg in state["messages"]:
        if isinstance(msg, (HumanMessage, AIMessage)):
            messages.append(msg)

    query = ""
    if len(state["messages"]) == 1:
        query = state["messages"][0].content

    time.sleep(2)

    try:
        response = llm.with_structured_output(Router).invoke(messages)
        print("SUPERVISOR RESPONSE >>>", response)
    except Exception as e:
        print("Error in supervisor_node LLM call:", e)
        return Command(
            update={
                "messages": state["messages"]
                + [
                    AIMessage(
                        content="Oops! I'm having trouble deciding the next step. Please try rephrasing."
                    )
                ]
            },
            goto="supervisor",  # You can also fallback to a default node like "information_node"
        )

    # Ensure proper dict structure
    if not isinstance(response, dict) or "next" not in response:
        return Command(
            update={
                "messages": state["messages"]
                + [
                    AIMessage(
                        content="Sorry, I couldn't understand your request properly."
                    )
                ]
            },
            goto="supervisor",
        )

    goto = response["next"]
    reasoning = response["reasoning"]

    # Break loop if last response is already from the same node and same query
    last_two = state["messages"][-2:]
    if (
        len(state["messages"]) >= 2
        and isinstance(last_two[-1], AIMessage)
        and last_two[-1].name == "information_node"
        and isinstance(last_two[-2], HumanMessage)
        and goto == "information_node"
    ):
        print("Loop detected — finishing.")
        goto = END

    if (
        len(state["messages"]) >= 2
        and isinstance(last_two[-1], AIMessage)
        and last_two[-1].name == "booking_node"
        and isinstance(last_two[-2], HumanMessage)
        and goto == "booking_node"
    ):
        print("Booking loop detected — waiting for user.")
        goto = END

    if goto == "FINISH" and len(state["messages"]) <= 2:
        # print("length of message = "+ len(state["messages"]))
        print(
            "inside goto == finish and set the goto = information_node to recall entire steps of infonode"
        )
        goto = END
        # goto = "information_node"

    if goto == "FINISH":
        goto = END

    return Command(
        goto=goto,
        update={
            "next": goto,
            "query": query,
            "cur_reasoning": reasoning,
            "messages": state["messages"],
        },
    )


def safe_invoke(func, *args, retries=3, delay=5):
    for attempt in range(retries):
        try:
            return func(*args)
        except Exception as e:
            if "quota" in str(e).lower() or "429" in str(e):
                time.sleep(delay)
            else:
                raise
    raise RuntimeError("Too many failed retries")


# agent state
class AgentState(TypedDict):
    messages: MessagesState
    next: str
    query: str
    cur_reasoning: str
    id_number: str  # Can be user ID or similar identifier
