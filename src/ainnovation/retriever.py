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
            df.columns = df.columns.str.strip()  # e.g. "Valores Pessoais " -> "Valores Pessoais"
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
faculties_retriever = build_retriever(FACULTIES_SHEET, "Nome da Instituição / Faculdade")


# --- Compatibility matrix -------------------------------------------------
# Profile topics (one question each) and the area columns each answer is compared with.
CRITERIA = {
    "interesses": ["Interesse & Motivação", "Palavras-Chave (CNA)"],
    "competencias": ["Competências Desenvolvidas"],
    "valores": ["Valores Pessoais"],
    "preferencias": ["Tipo de Trabalho Esperado", "Estilo de Aprendizagem"],
}
WEIGHTS = {"interesses": 0.35, "competencias": 0.30, "valores": 0.15, "preferencias": 0.20}
AREA_COLUMN = "Área / Percurso Genérico"
MIN_CONFIDENCE = 0.25  # below this best total, the answers are too vague to suggest areas

# Common words in answers that say nothing about the student (compared after preprocess)
STOPWORDS = {preprocess(w)[0] for w in (
    "que com para por uma uns umas mais muito muita pouco gosto gostar gosta adoro "
    "sou tenho também não como isso isto coisas coisa bom boa bem acho porque quando "
    "minha meu minhas meus tudo algo ser estar fazer area areas"
).split()}


def normalize_topic(topic: str) -> str:
    """'Competências' -> 'competencias', so the app's keys match CRITERIA."""
    topic = unicodedata.normalize("NFKD", topic.strip().lower())
    return "".join(c for c in topic if not unicodedata.combining(c))


def answer_words(answer: str) -> list[str]:
    """Meaningful words of an answer, in their original form (for justifications)."""
    return [w for w in re.findall(r"\w+", answer) if (p := preprocess(w)) and p[0] not in STOPWORDS]


def score_answer(answer: str, text: str) -> tuple[float, list[str]]:
    """Share of the answer's meaningful words found in the area text (0-1), plus those words."""
    words = answer_words(answer)
    text_tokens = set(preprocess(text))
    matched = [w for w in words if preprocess(w)[0] in text_tokens]
    return (len(matched) / len(words) if words else 0.0), list(dict.fromkeys(matched))


def compute_compatibility(profile: dict[str, str], top: int = 3) -> list[dict]:
    """Score every area against the student's answers (topic -> free text) and return the best ones."""
    answers = {normalize_topic(t): a for t, a in profile.items()}
    areas = read_sheet(AREAS_SHEET)
    ranking = []
    for _, row in areas.iterrows():
        criteria = {}
        for topic, columns in CRITERIA.items():
            text = " ".join(str(row[col]) for col in columns)
            score, matched = score_answer(answers.get(topic, ""), text)
            criteria[topic] = {"score": round(score, 2), "matched": matched}
        total = sum(WEIGHTS[t] * c["score"] for t, c in criteria.items())
        ranking.append({"area": row[AREA_COLUMN], "total": round(total, 2), "criteria": criteria})
    ranking.sort(key=lambda r: r["total"], reverse=True)
    return ranking[:top]


def format_compatibility(ranking: list[dict]) -> str:
    """One line per area: total score and, per topic, the score and the student's words that matched."""
    if not ranking or ranking[0]["total"] < MIN_CONFIDENCE:
        weak = [t for t in CRITERIA if not any(r["criteria"][t]["matched"] for r in ranking)]
        return (
            "CONFIANÇA BAIXA: as respostas não chegam para sugerir áreas. "
            f"Pede exemplos concretos sobre: {', '.join(weak) or 'todos os tópicos'}."
        )
    return "\n".join(
        f"- {r['area']}: {r['total']:.0%} | " + "; ".join(
            f"{t} {c['score']:.0%} ({', '.join(c['matched']) or 'sem coincidências'})"
            for t, c in r["criteria"].items()
        )
        for r in ranking
    )
