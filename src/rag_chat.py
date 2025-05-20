# run_app.py
import os
from langchain_openai import AzureOpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain.retrievers import MultiVectorRetriever
from langchain_community.docstore.in_memory import InMemoryDocstore
from llm_gateway import get_openai_client
from langchain.storage import InMemoryStore
from langchain_community.tools.tavily_search import TavilySearchResults
from dotenv import load_dotenv
import os

load_dotenv()

AZURE_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
AZURE_OPENAI_EMBEDDINGS_ENDPOINT = os.getenv("AZURE_OPENAI_EMBEDDINGS_ENDPOINT")
AZURE_OPENAI_EMBEDDINGS_API_VERSION = os.getenv("AZURE_OPENAI_EMBEDDINGS_API_VERSION")
AZURE_API_KEY = os.getenv("AZURE_API_KEY")


def route_to_index(question, index_map):
    llm = get_openai_client()

    book_options = {
        "mechanics_vol1.pdf": "DC Pandey Mechanics Volume 1 (kinematics, laws of motion, work, energy)",
        "mechanics_vol2.pdf": "DC Pandey Mechanics Volume 2 (circular motion, gravitation, rotational motion)",
        "waves_thermodynamics.pdf": "DC Pandey Waves and Thermodynamics (waves, sound, thermodynamics, heat)",
        "electricity_magnetism.pdf": "DC Pandey Electricity and Magnetism (electricity, magnetism, current, electrostatics)",
        "optics_modern.pdf": "DC Pandey Optics and Modern Physics (optics, light, modern physics, quantum)",
    }

    prompt = f"""
    Given the question: "{question}"
    Select the most relevant DC Pandey book from the following options based on the topic of the question.
    Options:
    {', '.join([f'{k}: {v}' for k, v in book_options.items()])}
    Return only the filename (e.g., 'mechanics_vol1.pdf') of the selected book.
    """

    response = llm.invoke(prompt)
    selected_pdf = response.content.strip()

    if selected_pdf not in index_map:
        print(
            f"Warning: Invalid selection '{selected_pdf}'. Defaulting to mechanics_vol1.pdf"
        )
        selected_pdf = "mechanics_vol1.pdf"

    return selected_pdf, index_map[selected_pdf]


def load_retriever(index_path, embeddings):
    vector_store = FAISS.load_local(
        index_path, embeddings, allow_dangerous_deserialization=True
    )
    retriever = MultiVectorRetriever(
        vectorstore=vector_store,
        docstore=InMemoryStore(),  # Changed to InMemoryStore
        id_key="doc_id",
    )
    return retriever


def get_knowledge_from_internet(question, number_of_search_results=5):
    tavily_tool = TavilySearchResults(max_results=number_of_search_results)

    return tavily_tool.invoke(question)


def generate_answer(question, retriever, Knowledge_from_internet):
    retrieved_docs = retriever.invoke(question)
    context = "\n".join(
        [
            f"Page {doc.metadata.get('page', 'Unknown')}: {doc.page_content[:200]}..."
            for doc in retrieved_docs[:3]
        ]
    )
    book_title = (
        retrieved_docs[0].metadata.get("book_title", "Unknown DC Pandey Book")
        if retrieved_docs
        else "Unknown"
    )
    pages = (
        ", ".join(
            [str(doc.metadata.get("page", "Unknown")) for doc in retrieved_docs[:3]]
        )
        if retrieved_docs
        else "Unknown"
    )

    llm = get_openai_client()

    prompt = f"""
    Question: {question}
    Context from DC Pandey textbook: {context}
    Context from Internet : {Knowledge_from_internet}
    Format all mathematical expressions in LaTeX (e.g., use '$r = \\sqrt{{2mV / (qB^2)}}$' for equations).
    Use bold markdown for step titles (e.g., '**Step 1:**').
    Provide a detailed step-by-step explanation to answer the question, referencing the context where applicable.
    You also have access to the internet content so analyse it depply you can find the right approach and answer.from there also.
    At the end, include a reference to the specific DC Pandey book titled '{book_title}' and the page numbers (e.g., 'p. {pages}') where the information is derived.
    If possible, suggest a relevant section or topic from the book based on the question (e.g., 'Laws of Motion' or 'Thermodynamics').
    """

    answer = llm.invoke(prompt)
    return answer.content


def main():
    index_map = {
        "mechanics_vol1.pdf": "./indexes/faiss_index_mechanics_vol1",
        "mechanics_vol2.pdf": "./indexes/faiss_index_mechanics_vol2",
        "waves_thermodynamics.pdf": "./indexes/faiss_index_waves_thermodynamics",
        "electricity_magnetism.pdf": "./indexes/faiss_index_electricity_magnetism",
        "optics_modern.pdf": "./indexes/faiss_index_optics_modern",
    }

    embeddings = AzureOpenAIEmbeddings(
        azure_deployment=AZURE_DEPLOYMENT_NAME,
        azure_endpoint=AZURE_OPENAI_EMBEDDINGS_ENDPOINT,
        api_version=AZURE_OPENAI_EMBEDDINGS_API_VERSION,
        api_key=AZURE_API_KEY,
    )

    # questions = [
    #     "Explain the concept of inclined plane motion",
    #     "How does circular motion work?",
    #     "What is the first law of thermodynamics?"
    # ]

    questions = [
        """Solve this problem and give me the answer ands step by step solution.A charged particle of mass m and charge q is accelerated through a potential difference of
                V volts. It enters a region of uniform magnetic field B which is directed perpendicular to the
                direction of motion of the particle. The particle will move on a circular path of radius"""
    ]

    for question in questions:
        print(f"\nProcessing question: {question}")

        pdf_name, index_path = route_to_index(question, index_map)
        print(f"Routed to {pdf_name} at {index_path}")

        retriever = load_retriever(index_path, embeddings)

        Knowledge_from_internet = get_knowledge_from_internet(question)
        print(f"Knowledge from Internet: {Knowledge_from_internet}\n")

        answer = generate_answer(question, retriever, Knowledge_from_internet)
        print(f"Answer:\n{answer}\n")

        with open("answer.md", "w") as f:
            f.write(answer)


if __name__ == "__main__":
    main()
