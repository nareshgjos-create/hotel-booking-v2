import streamlit as st
import requests

CHAT_URL = "http://127.0.0.1:8000/chat"

st.set_page_config(
    page_title="Hotel Booking Agent",
    page_icon="🏨",
    layout="centered"
)

st.markdown("""
<style>
    .chat-message-user {
        background-color: #007bff;
        color: white;
        padding: 10px 15px;
        border-radius: 18px 18px 4px 18px;
        margin: 5px 0;
        max-width: 80%;
        margin-left: auto;
        text-align: right;
    }
    .chat-message-bot {
        background-color: #ffffff;
        color: #333;
        padding: 10px 15px;
        border-radius: 18px 18px 18px 4px;
        margin: 5px 0;
        max-width: 80%;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "profile_set" not in st.session_state:
    st.session_state.profile_set = False

st.title("🏨 Hotel Booking Agent")
st.caption("Powered by AI Agents — Search + Availability + Booking")
st.divider()

with st.sidebar:
    st.header("👤 Your Profile")
    st.caption("Fill in your details before chatting")

    name = st.text_input(
        "Full Name",
        value=st.session_state.user_name,
        placeholder="John Doe"
    )
    email = st.text_input(
        "Email",
        value=st.session_state.user_email,
        placeholder="john@example.com"
    )

    if st.button("💾 Save Profile", use_container_width=True):
        if name and email:
            st.session_state.user_name = name
            st.session_state.user_email = email
            st.session_state.profile_set = True
            st.success("Profile saved! ✅")
        else:
            st.error("Name and Email are required!")

    st.divider()

    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.divider()

    st.markdown("### 🤖 Active Agents")
    st.markdown("""
    - 🔍 **Search Agent**
    - 📅 **Availability Agent**
    - 🛎️ **Booking Agent**
    """)

    st.divider()

    st.markdown("### 🏙️ Available Cities")
    st.markdown("""
    - 🇬🇧 London
    - 🇫🇷 Paris
    - 🇪🇸 Barcelona
    - 🇦🇪 Dubai
    """)

    st.divider()

    st.markdown("### 💡 Try saying:")
    st.markdown("""
    - *"Find hotels in Paris"*
    - *"Check availability for hotel 1 from 2026-04-10 to 2026-04-12 for 2 guests"*
    - *"Book hotel 1 for 2 guests from 2026-04-10 to 2026-04-12"*
    """)

chat_container = st.container()

with chat_container:
    if not st.session_state.messages:
        st.markdown("""
        <div class='chat-message-bot'>
        👋 Hello! I'm your hotel booking assistant.<br><br>
        I can help you:<br>
        🔍 find hotels<br>
        📅 check availability<br>
        🛎️ complete bookings<br><br>
        Please fill in your profile on the left, then start chatting!
        </div>
        """, unsafe_allow_html=True)

    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(
                f"<div class='chat-message-user'>{msg['content']}</div>",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f"<div class='chat-message-bot'>{msg['content']}</div>",
                unsafe_allow_html=True
            )

user_input = st.chat_input("Type your message here...")

if user_input:
    if not st.session_state.profile_set:
        st.warning("⚠️ Please fill in your profile first!")
    else:
        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })

        with st.spinner("🤖 Agents are thinking..."):
            try:
                response = requests.post(
                    CHAT_URL,
                    json={
                        "message": user_input,
                        "user_name": st.session_state.user_name,
                        "user_email": st.session_state.user_email
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    agent_reply = data.get("response", "❌ Backend returned no response field.")
                else:
                    agent_reply = f"❌ Backend error: {response.status_code} - {response.text}"

            except Exception as e:
                agent_reply = f"❌ Cannot connect to server: {str(e)}"

        st.session_state.messages.append({
            "role": "assistant",
            "content": agent_reply
        })

        st.rerun()