#parse.py

from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
import streamlit as st
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

# Template to guide the Llama model in extracting relevant data from DOM content
template = (
    "You are tasked with extracting specific information from the following text content: {dom_content}. "
    "Please follow these instructions carefully: \n\n"
    "1. **Extract Information:** Only extract the information that directly matches the provided description: {parse_description}. "
    "2. **No Extra Content:** Do not include any additional text, comments, or explanations in your response. "
    "3. **Empty Response:** If no information matches the description, return an empty string ('')."
    "4. **Direct Data Only:** Your output should contain only the data that is explicitly requested, with no other text."
)

# Initialize the Llama model
model = OllamaLLM(model="llama3.1")

def parse_with_ollama(dom_chunks, parse_description):
    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | model

    parsed_results = []

    for i, chunk in enumerate(dom_chunks, start=1):
        # Check if parsing should stop
        if st.session_state.stop_parsing:
            logging.info("Parsing stopped by user.")
            break

        try:
            # Feed DOM content and description into the model for parsing
            response = chain.invoke(
                {"dom_content": chunk, "parse_description": parse_description}
            )
            logging.info(f"Parsed batch {i} of {len(dom_chunks)}")
            parsed_results.append(response)
        except Exception as e:
            logging.error(f"Error parsing chunk {i}: {e}")
            parsed_results.append(f"Error parsing chunk {i}: {e}")

    # Combine results from all chunks
    return "\n".join(parsed_results)
