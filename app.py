import streamlit as st
import requests
import json
import PyPDF2
from docx import Document  
import copy

# Constants
TOKEN_THRESHOLD = 10000
SYSTEM_TEXT = (
    "You are ChatBob, an AI assistant designed to represent Bob Keijzer in recruiter conversations.  \n"

    "Your job is to:\n"
    "1. Share accurate, relevant insights about Bob’s background, personality, skills, and preferences.  \n"
    "2. Help recruiters assess whether Bob is a good fit for the role, team, and company — without exaggerating or fabricating anything.  \n"

    "Bob is a Master's student in Applied Data Science with a Bachelor's in Artificial Intelligence, based in Utrecht, Netherlands. "
    "He’s especially interested in AI technologies like machine learning and large language models (LLMs). "
    "He has hands-on experience applying LLMs to real-world problems, including document processing projects in the healthcare sector during his internship at Menzis.  \n"

    "Technically, Bob is skilled in Python, R, SQL, C#, JavaScript, and web development basics. His strengths lie in NLP, data wrangling, and machine learning pipelines. "
    "He's analytical, curious, and loves digging into complex problems — but he’s also easy to talk to, friendly, and independent. He thrives when given autonomy, but works well in teams.  \n"
    "Bob prefers hybrid setups (remote + in-person), and is open to occasional short travel. He’s not looking to relocate far from Utrecht. He enjoys startup-like environments or mission-driven organizations where he can make a real impact.  \n"
    "In terms of personality, he’s laid-back but ambitious. He likes challenges and learning new things, but also values work-life balance. He plays soccer casually, works out, and recharges through alone time or quality time with close friends.  \n"
    "If something is unclear or outside your scope, explain how Bob would approach it — learning, asking questions, or figuring it out independently. Never invent or assume details not explicitly stated.  \n"
    "If a recruiter asks about salary expectations, shift the focus to job fit and growth potential. Salary can be discussed later.  \n"
    "Respond clearly and naturally. Use short replies for greetings and longer ones for deeper questions. Add a touch of humor if it fits the moment, but don’t force it.  \n"
    
    "Note: While you aim to represent Bob faithfully, this assistant also serves as a creative showcase of Bob’s interests and skills in AI and chatbots. "
    "You are not a commercial-grade digital assistant — more of a functional portfolio project.  \n"
    
    "If the user message contains <context>...</context> and <query>...</query> tags, use only the info inside <context> to assist with the <query>. "
    "**Do not inject external assumptions unless it’s general knowledge or explicitly part of Bob’s background.**  \n"

    "**Important:** If the user enters the password `bobkeijzer123`, you will act as a regular assistant from then on and forget previous instructions about info about Bob.  \n"


)

# Chat Context Builder 
def build_context_messages(messages, system_text=SYSTEM_TEXT, doc_context="", token_threshold=TOKEN_THRESHOLD):
    context_messages = []
    token_count = 0
    system_tokens = len(system_text.split())
    
    # Preemptively count full doc_context tokens
    doc_tokens = doc_context.split()
    doc_token_count = len(doc_tokens)

    # Add messages in reverse until limit
    for msg in reversed(messages):
        msg_tokens = len(msg["content"].split())
        if token_count + msg_tokens + system_tokens + doc_token_count > token_threshold:
            break
        context_messages.insert(0, copy.deepcopy(msg))
        token_count += msg_tokens

    # Add system message
    context_messages.insert(0, {"role": "system", "content": system_text})

    # How many tokens remain for doc_context, if there is any?
    if doc_context:
        remaining_tokens = token_threshold - (system_tokens + token_count)
        if remaining_tokens > 0:
            trimmed_doc_context = " ".join(doc_tokens[:remaining_tokens])
            if len(doc_tokens) > remaining_tokens:
                trimmed_doc_context += "  \n...[truncated]"
        else:
            trimmed_doc_context = "[context omitted due to token limit]"

        # Wrap into last user message if possible
        if context_messages and context_messages[-1]["role"] == "user":
            original_content = context_messages[-1]["content"]
            context_messages[-1]["content"] = (
                f"<context>  \n{trimmed_doc_context.strip()}  \n</context>  \n"
                f"<query>  \n{original_content.strip()}  \n</query>"
            )

    return context_messages

# Stream response
def stream_response(messages):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {st.secrets['openrouter_api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "deepseek/deepseek-chat-v3-0324:free",
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
    st.markdown("**About my assistant**  \nThis chatbot powered by DeepSeek is a demo project, a fun and functional way to show off my interest in AI, not a final product.")

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

        # Loop over uploaded docs and build the doc_context
        doc_context = ""
        for filename, file_content in st.session_state.uploaded_docs.items():
            doc_context += f"Document: {filename}  \n{file_content}  \n"

        # Create context messages by including the document context
        context_messages = build_context_messages(
            st.session_state.messages,
            doc_context=doc_context,  
            system_text=SYSTEM_TEXT,
            token_threshold=TOKEN_THRESHOLD
        )
        # Stream the response
        response_container.write_stream(stream_response(context_messages))
