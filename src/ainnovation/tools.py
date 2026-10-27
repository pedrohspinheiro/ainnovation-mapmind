from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import Tool


def search_web(query: str) -> str:
    """Searches the web using DuckDuckGo and returns the top results."""
    search_tool = DuckDuckGoSearchRun()
    results = search_tool.invoke(query)
    return results


# Initialize the tool
search_web_tool = Tool(
    name="search_web",
    func=search_web,
    description="Searches the web using DuckDuckGo and returns the top results."
)
