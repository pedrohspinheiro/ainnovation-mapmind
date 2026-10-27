from pathlib import Path
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.tools import Tool

AREAS_FILE = Path(__file__).parent / "data" / "areas.md"


def load_areas_tool() -> Tool:
    """Load the areas document and return a tool that retrieves matching areas from it."""
    text = AREAS_FILE.read_text(encoding="utf-8")
    # Drop the leading HTML comment, then one Document per area block
    text = text.split("-->", 1)[-1] if text.lstrip().startswith("<!--") else text
    blocks = [b.strip() for b in text.split("\n---\n") if b.strip()]
    docs = [
        Document(
            page_content=block,
            metadata={"area": block.splitlines()[0].removeprefix("Área:").strip()},
        )
        for block in blocks
    ]

    bm25_retriever = BM25Retriever.from_documents(docs, k=3)

    def retrieve_areas(query: str) -> str:
        """Retrieves areas of study (interests, skills, pros, cons, doubts) matching a query."""
        results = bm25_retriever.invoke(query)
        if results:
            return "\n\n---\n\n".join(doc.page_content for doc in results)
        return "Nenhuma área encontrada para esta pesquisa."

    return Tool(
        name="areas_retriever",
        func=retrieve_areas,
        description=(
            "Pesquisa no documento da equipa as áreas/percursos que correspondem a uma consulta "
            "(interesses, competências, tipo de trabalho, estilo de aprendizagem). "
            "Devolve vantagens, desvantagens e dúvidas a esclarecer de cada área."
        ),
    )


areas_tool = load_areas_tool()
