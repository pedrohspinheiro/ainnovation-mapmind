from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.prebuilt import ToolNode
from langgraph.graph import START, StateGraph
from langgraph.prebuilt import tools_condition
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pathlib import Path #para o caminho do ficheiro

from ainnovation.tools import areas_tool, faculties_tool, search_web_tool

#A prompt
SYSTEM_PROMPT = prompts("prompts/system.md").read_text(encoding="utf-8")

load_dotenv()  # reads GOOGLE_API_KEY from .env

# Generate the chat interface, including the tools
chat = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
tools = [areas_tool, faculties_tool, search_web_tool]
chat_with_tools = chat.bind_tools(tools)

# Generate the AgentState and Agent graph
class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

def assistant(state: AgentState): #o nosso assistente, onde mandamos o prompt para nos ajudar
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    return {"messages": [chat_with_tools.invoke(messages)]}

## The graph
builder = StateGraph(AgentState)

# Define nodes: these do the work
builder.add_node("assistant", assistant)
builder.add_node("tools", ToolNode(tools))

# Define edges: these determine how the control flow moves
builder.add_edge(START, "assistant")
builder.add_conditional_edges(
    "assistant",
    # If the latest message requires a tool, route to tools
    # Otherwise, provide a direct response
    tools_condition,
)
builder.add_edge("tools", "assistant")
agent = builder.compile()

def print_trace(messages, start=0, max_chars=150):
    """Print one short line per step so the workflow is easy to follow."""
    for i, m in enumerate(messages[start:], start=start + 1):
        if isinstance(m, HumanMessage):
            print(f"{i}. 🧑 USER: {m.text}")
        elif isinstance(m, AIMessage) and m.tool_calls:
            for call in m.tool_calls:
                print(f"{i}. 🤖 MODEL → calls tool '{call['name']}' with {call['args']}")
        elif isinstance(m, AIMessage):
            print(f"{i}. 🤖 ANSWER: {m.text}")
        elif isinstance(m, ToolMessage):
            result = m.text.replace("\n", " ")
            suffix = "..." if len(result) > max_chars else ""
            print(f"{i}. 🔧 TOOL '{m.name}' returned: {result[:max_chars]}{suffix}")
    print()


if __name__ == "__main__":
    name = input("Olá, qual é o teu nome? ").strip()
    # Simple chat loop for manual testing
    OPENING = f"Olá, {name}! Vou ser o teu agente para te ajudar a explorar diferentes opções de percursos académicos!"
    messages = [AIMessage(content=OPENING)]
    print(f"🤖 {OPENING}") #to print the opening message

    #first question - will lead us to the next part
    FIRST_QUESTION = f"Diz-me, {name}, quais sãos os teus interesses, competências, valores e preferências?"

    while (text := input("Tu: ").strip()):
        seen = len(messages) + 1  # skip echoing the user message just typed
        messages = agent.invoke({"messages": messages + [HumanMessage(content=text)]})["messages"]
        print_trace(messages, start=seen)
