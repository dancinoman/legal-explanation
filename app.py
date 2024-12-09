import streamlit as st
import os
from dotenv import load_dotenv
from typing_extensions import List, TypedDict

from pdfquery import PDFQuery
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.vectorstores import InMemoryVectorStore

#from langchain_core.documents import Document # Uncomment for pdf usage
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langgraph.graph import START, StateGraph
from langchain import hub

load_dotenv()

def get_from_pdf(pdf_file):
    """
    Extracts text from uploaded PDF using pdfquery.

    Args:
        pdf_file: A file object containing the uploaded PDF.

    Returns:
        str: The cleaned text extracted from the PDF.
    """
    pdf = PDFQuery(pdf_file)
    pdf.load()
    text_elements = pdf.pq('LTTextLineHorizontal')
    # Cleaning the text
    return ''.join([t.text for t in text_elements if t.text.strip() != '' and t.text.strip().replace('_', '') != ""])


def process_and_answer(question, document_text):
    """
    Processes the uploaded PDF, performs retrieval and generation steps,
    and returns the answer to the user's question.

    Args:
        question: str, The user's question.

    Returns:
        str: The answer generated by the language model.
    """


    if document_text is not None:

        # Split the text into smaller chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks = text_splitter.split_text(document_text)

        # start embedding
        llm = ChatGroq(model="llama3-8b-8192")
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")

        vector_store = InMemoryVectorStore(embeddings)
        store = vector_store.add_texts(chunks)

        prompt = hub.pull("rlm/rag-prompt")

        class State(TypedDict):
            question: str
            context: str
            answer: str

        def retrieve(state):
            retrieve_text = vector_store.similarity_search(state['question'])
            return {'context': retrieve_text}

        def generate(state):
            text_content = state['context']
            message = prompt.invoke({'question': state['question'], 'context': text_content})
            response = llm.invoke(message)
            return {'answer': response.content}

        graph_builder = StateGraph(State).add_sequence([retrieve, generate])
        graph_builder.add_edge(START, "retrieve")
        graph = graph_builder.compile()

        result = graph.invoke({"question": question})
        return result["answer"]
    else:
        return "Please upload a contract PDF."


def main():
    """
    Streamlit app entry point.
    """
    st.title("Document Question Answering")
    st.write('### Upload your pdf document and then ask any question.')
    # Get text from uploaded PDF
    uploaded_file = st.file_uploader("Upload Contract PDF", type="pdf")


    if uploaded_file:
        document_text = get_from_pdf(uploaded_file)
        user_question = st.text_input("Question: ")
        if user_question:
            answer = process_and_answer(user_question, document_text)
            st.write(f"Answer: {answer}")


if __name__ == "__main__":
    main()
