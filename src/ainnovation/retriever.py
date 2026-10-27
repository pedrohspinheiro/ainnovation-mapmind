import re
import unicodedata
from pathlib import Path
import pandas as pd
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

DATA_FILE = Path(__file__).parent / "data" / "data.xlsx"

# Sheet names in data.xlsx (matched ignoring case and surrounding spaces)
AREAS_SHEET = "areas"      # generic areas with comparison criteria
FACULTIES_SHEET = "curso"  # universities/faculties with official links

STEM_LENGTH = 5  # crude Portuguese stemming: "programar" and "Programação" both become "progr"


def preprocess(text: str) -> list[str]:
    """Lowercase, strip accents and truncate words so related word forms match in BM25."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return [w[:STEM_LENGTH] for w in re.findall(r"\w+", text) if len(w) > 2]


def read_sheet(name: str) -> pd.DataFrame:
    """Read a sheet by name, ignoring case and surrounding spaces."""
    sheets = pd.read_excel(DATA_FILE, sheet_name=None)
    for sheet_name, df in sheets.items():
        if sheet_name.strip().lower() == name:
            return df.fillna("")
    raise ValueError(f"Sheet '{name}' not found in {DATA_FILE.name}; found {list(sheets)}")


def load_documents(sheet: str, title_column: str) -> list[Document]:
    """Turn each row of an Excel sheet into a Document ("column: value" per line)."""
    df = read_sheet(sheet)
    return [
        Document(
            page_content="\n".join(f"{col}: {row[col]}" for col in df.columns if str(row[col]).strip()),
            metadata={"title": str(row[title_column])},
        )
        for _, row in df.iterrows()
    ]


def build_retriever(sheet: str, title_column: str, k: int = 3) -> BM25Retriever:
    """Build a BM25 retriever over one sheet of the data file."""
    return BM25Retriever.from_documents(
        load_documents(sheet, title_column), k=k, preprocess_func=preprocess
    )


def search(retriever: BM25Retriever, query: str) -> str:
    """Run a query and join the matching documents into one string."""
    results = retriever.invoke(query)
    if results:
        return "\n\n---\n\n".join(doc.page_content for doc in results)
    return "Nenhum resultado encontrado para esta pesquisa."


areas_retriever = build_retriever(AREAS_SHEET, "Área / Percurso Genérico")
faculties_retriever = build_retriever(FACULTIES_SHEET, "Faculdade / Escola")
