import streamlit as st
import requests
import json
import PyPDF2
from docx import Document  
import copy

# Constants
TOKEN_THRESHOLD = 10000
with open("chatbob_prompt.txt", "r") as f:
    SYSTEM_TEXT = f.read()

# Chat Context Builder 
def build_context_messages(messages, system_text=SYSTEM_TEXT, uploaded_files={}, token_threshold=TOKEN_THRESHOLD):
    context_messages = []
    token_count = 0
    doc_context = ""

    # Read uploaded files content
    for filename, data in uploaded_files.items():
        doc_context += f"Document: {filename}  \n{data}  \n"
    doc_tokens = doc_context.split()
    
    # Truncate document context if too long
    max_doc_tokens = int(token_threshold * 0.75)
    if len(doc_tokens) > max_doc_tokens:
        doc_tokens = doc_tokens[:max_doc_tokens]
        doc_context = " ".join(doc_tokens) + "  \n...[truncated]"

    # Base context with system text and document context
    base_context = system_text + "  \n\nExtra context:  \n" + doc_context
    base_tokens = len(base_context.split())

    # Add messages in reverse until limit
    for msg in reversed(messages):
        msg_tokens = len(msg["content"].split())
        if token_count + msg_tokens + base_tokens > token_threshold:
            break
        context_messages.insert(0, copy.deepcopy(msg))
        token_count += msg_tokens

    # Add system message at the start
    context_messages.insert(0, {"role": "system", "content": base_context})
    return context_messages

# Stream response
def stream_response(messages):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {st.secrets['openrouter_api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "openai/gpt-oss-20b:free",
        "messages": messages,
        "stream": True,
    }

    with requests.post(url, headers=headers, data=json.dumps(payload), stream=True) as r:
        full_response = ""
        for line in r.iter_lines():
            if line and line.startswith(b"data: "):
                try:
                    data = json.loads(line[6:].decode("utf-8"))
                    if "choices" in data:
                        delta = data["choices"][0]["delta"]
                        if "content" in delta:
                            full_response += delta["content"]
                            yield delta["content"]
                except json.JSONDecodeError:
                    continue
        # Save final response to session state
        st.session_state.messages.append({"role": "assistant", "content": full_response})

# Function to handle text files
def handle_txt_file(uploaded_file):
    return uploaded_file.getvalue().decode("utf-8")

# Function to handle PDF files 
def handle_pdf_file(uploaded_file):
    pdf_reader = PyPDF2.PdfReader(uploaded_file)
    text = ""
    for page_num in range(len(pdf_reader.pages)):
        page = pdf_reader.pages[page_num]
        text += page.extract_text() + "  \n"
    return text

# Function to handle DOCX files
def handle_docx_file(uploaded_file):
    doc = Document(uploaded_file)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "  \n"
    return text

# --- Streamlit App ---

st.set_page_config(page_title="ChatBob", page_icon="🤖")

st.title("🤖 ChatBob")
st.caption("Bob Keijzer's AI Assistant")

# Initialize session state for uploaded documents
if "uploaded_docs" not in st.session_state:
    st.session_state.uploaded_docs = {}

# Initialize chat history 
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar.expander('Info', expanded=True):
    st.image("BOB.jpg", width=150, caption="Bob Keijzer")
    st.markdown("**About my assistant**  \nThis chatbot is a demo project, a fun and functional way to show off my interest in AI, not a final product.")

# Create an expander in the sidebar
with st.sidebar.expander('Docs', expanded=True):
    # File uploader inside the expander (multiple files allowed)
    uploaded_files = st.file_uploader("Upload documents", type=["txt", "pdf", "docx"], accept_multiple_files=True)
    
    # Clear previous uploaded documents if the user uploads new ones
    if "uploaded_docs" in st.session_state:
        st.session_state.uploaded_docs = {}

    # Check if files were uploaded
    if uploaded_files:
        for uploaded_file in uploaded_files:
            # Check the file type and process accordingly
            if uploaded_file.type == "text/plain":
                file_content = handle_txt_file(uploaded_file)
            elif uploaded_file.type == "application/pdf":
                file_content = handle_pdf_file(uploaded_file)
            elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                file_content = handle_docx_file(uploaded_file)
            else:
                file_content = f"Uploaded file type: {uploaded_file.type}. File not supported."

            # Store the content in session state with filename as the key
            st.session_state.uploaded_docs[uploaded_file.name] = file_content


# Display all chat history 
if "messages" in st.session_state:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# User input
if prompt := st.chat_input("Ask something..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Container for streaming assistant reply
    with st.chat_message("assistant"):
        response_container = st.empty()

        # Create context messages by including the document context
        context_messages = build_context_messages(
            st.session_state.messages,  
            system_text=SYSTEM_TEXT,
            uploaded_files=st.session_state.uploaded_docs,
            token_threshold=TOKEN_THRESHOLD
        )
        # Stream the response
        response_container.write_stream(stream_response(context_messages))
