from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import Tool

from ainnovation_mapmind.retriever import areas_retriever, faculties_retriever, search


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


def search_areas(query: str) -> str:
    """Searches the generic areas/paths that match a query."""
    return search(areas_retriever, query)

areas_tool = Tool(
    name="areas_retriever",
    func=search_areas,
    description=(
        "Pesquisa as áreas/percursos genéricos que correspondem a uma consulta "
        "(interesses, competências, tipo de trabalho, estilo de aprendizagem). "
        "Devolve vantagens, desvantagens e dúvidas a esclarecer de cada área."
    ),
)


def search_faculties(query: str) -> str:
    """Searches universities and faculties that match a query."""
    return search(faculties_retriever, query)

faculties_tool = Tool(
    name="faculties_retriever",
    func=search_faculties,
    description=(
        "Pesquisa universidades e faculdades por área ou palavras-chave "
        "(ex.: 'Engenharia', 'Direito', 'Açores'). Devolve a oferta e o link oficial da faculdade."
    ),
)
