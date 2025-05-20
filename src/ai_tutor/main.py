import streamlit as st
from gtts import gTTS
import os
import tempfile
import re
import base64
import streamlit.components.v1 as components
from agent import build_tutor_graph, AgentState
from llm_gateway import get_openai_client


# Helper functions
def clean_latex_for_tts(text):
    """Clean LaTeX content for TTS by replacing common LaTeX commands with spoken equivalents."""
    try:
        text = text.replace("$", "")
        text = re.sub(r"\\frac\{([^}]+)\}\{([^}]+)\}", r"\1 over \2", text)
        text = re.sub(r"\^(\d+)", r" to the power \1", text)
        text = re.sub(r"_(\d+)", r" subscript \1", text)
        text = re.sub(r"\\sqrt\{([^}]+)\}", r"square root of \1", text)
        text = re.sub(r"\\vec\{([^}]+)\}", r"vector \1", text)
        return text
    except Exception as e:
        st.warning(f"Error cleaning LaTeX for TTS: {e}")
        return text


def generate_tts(text):
    """Generate TTS audio file and return the file path."""
    try:
        clean_text = clean_latex_for_tts(text)
        tts = gTTS(text=clean_text, lang="en")
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(temp_file.name)
        return temp_file.name
    except Exception as e:
        st.warning(f"TTS generation failed: {e}")
        return None


def get_binary_file_downloader_html(bin_file, file_label="File"):
    """Generate HTML for audio player."""
    with open(bin_file, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    return f"""
        <audio controls autoplay>
          <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
    """


def create_typewriter_effect(text, speed=50):
    """Create custom HTML/JS for typewriter effect with MathJax 3 support."""
    escaped_text = text.replace("`", "\\`").replace('"', '\\"').replace("\n", "\\n")
    js_code = f"""
    <div id="typewriter-container">{escaped_text}</div>
    
    <script>
        function renderMathJax() {{
            if (window.MathJax) {{
                MathJax.typesetPromise().catch(err => console.error('MathJax error:', err));
            }}
        }}
        
        if (!window.MathJax) {{
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js';
            script.async = true;
            script.onload = () => {{
                MathJax.config = {{
                    tex: {{
                        inlineMath: [['$','$'], ['\\\\(','\\\\)']]
                    }},
                    startup: {{
                        typeset: true
                    }}
                }};
                renderMathJax();
            }};
            script.onerror = () => {{
                console.error('Failed to load MathJax');
                document.getElementById('typewriter-container').innerHTML = `{escaped_text.replace('<', '<').replace('>', '>')}`;
            }};
            document.head.appendChild(script);
        }} else {{
            renderMathJax();
        }}
    </script>
    """
    return js_code


def main():
    st.set_page_config(page_title="IIT JEE Tutor", layout="wide")
    st.title("IIT JEE Tutor")

    # Initialize session state
    if "current_state" not in st.session_state:
        st.session_state.current_state = None
    if "workflow_active" not in st.session_state:
        st.session_state.workflow_active = False
    if "tts_enabled" not in st.session_state:
        st.session_state.tts_enabled = True
    if "typewriter_enabled" not in st.session_state:
        st.session_state.typewriter_enabled = True
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "current_step" not in st.session_state:
        st.session_state.current_step = 0
    if "explanation_steps" not in st.session_state:
        st.session_state.explanation_steps = []
    if "waiting_for_feedback" not in st.session_state:
        st.session_state.waiting_for_feedback = False
    if "audio_files" not in st.session_state:
        st.session_state.audio_files = []

    # Sidebar for avatar and controls
    with st.sidebar:
        st.header("Tutor Avatar")
        avatar_path = "avatar.png"
        if os.path.exists(avatar_path):
            st.image(avatar_path, width=150, caption="IIT JEE Tutor")
        else:
            st.warning("Avatar image not found. Please add 'avatar.png'.")

        st.header("Settings")
        st.session_state.tts_enabled = st.checkbox(
            "Enable Voice", value=st.session_state.tts_enabled
        )
        st.session_state.typewriter_enabled = st.checkbox(
            "Enable Typewriter Effect", value=st.session_state.typewriter_enabled
        )

        if st.session_state.tts_enabled:
            st.session_state.typewriter_speed = st.slider(
                "Typewriter Speed", 10, 100, 50
            )

        subject_options = ["Physics", "Chemistry", "Mathematics"]
        selected_subject = st.selectbox("Subject", subject_options)

    # Main layout
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Ask a Question")
        question = st.text_input(
            "Question",
            value="What is the formula for kinetic energy and how do we derive it?",
        )
        context = st.text_input("Context", value="IIT JEE preparation")

        if st.button("Start", disabled=st.session_state.workflow_active):
            if question and context:
                with st.spinner("Initializing tutor workflow..."):
                    st.session_state.workflow_active = True
                    st.session_state.messages = []
                    st.session_state.waiting_for_feedback = False
                    st.session_state.current_step = 0
                    st.session_state.explanation_steps = []
                    st.session_state.audio_files = []

                    initial_state = {
                        "question": question,
                        "context": context,
                        "subject": selected_subject,
                        "current_step": 0,
                        "explanation_steps": [],
                        "student_feedback": None,
                        "next_action": "",
                        "current_explanation": "",
                    }

                    tutor_graph = build_tutor_graph()
                    try:
                        result = initial_state
                        for event in tutor_graph.stream(initial_state):
                            if "state" in event:
                                result = event["state"]
                                st.session_state.current_state = result
                                if result.get("explanation_steps"):
                                    st.session_state.explanation_steps = result[
                                        "explanation_steps"
                                    ]
                                if result.get("next_action") in [
                                    "wait_for_feedback",
                                    "end",
                                ]:
                                    break

                        st.session_state.current_step = result.get("current_step", 0)
                        st.session_state.waiting_for_feedback = (
                            result.get("next_action") == "wait_for_feedback"
                        )

                        st.session_state.messages.append(
                            {
                                "type": "info",
                                "content": f"Starting the {selected_subject} tutor workflow...",
                            }
                        )

                        # Render all steps immediately
                        if st.session_state.explanation_steps:
                            for i, step in enumerate(
                                st.session_state.explanation_steps
                            ):
                                message = f"**Step {i + 1}: {step['title']}**\n\n{step['content']}"
                                if st.session_state.typewriter_enabled:
                                    st.session_state.messages.append(
                                        {
                                            "type": "typewriter",
                                            "content": message,
                                            "key": f"typewriter_step_{i}",
                                        }
                                    )
                                else:
                                    st.session_state.messages.append(
                                        {
                                            "type": "explanation",
                                            "content": message,
                                            "key": f"step_{i}",
                                        }
                                    )

                                if st.session_state.tts_enabled:
                                    audio_file = generate_tts(step["content"])
                                    if audio_file:
                                        st.session_state.audio_files.append(audio_file)
                                        st.session_state.messages.append(
                                            {
                                                "type": "audio",
                                                "file": audio_file,
                                                "key": f"audio_step_{i}",
                                            }
                                        )
                            st.session_state.waiting_for_feedback = True
                        else:
                            st.session_state.messages.append(
                                {
                                    "type": "error",
                                    "content": "No explanation steps generated. Please try again.",
                                }
                            )
                            st.session_state.workflow_active = False
                            st.session_state.waiting_for_feedback = False

                    except Exception as e:
                        st.session_state.messages.append(
                            {
                                "type": "error",
                                "content": f"Error initializing: {str(e)}",
                            }
                        )
                        # Fallback: Render any steps available
                        if st.session_state.explanation_steps:
                            for i, step in enumerate(
                                st.session_state.explanation_steps
                            ):
                                message = f"**Step {i + 1}: {step['title']}**\n\n{step['content']}"
                                if st.session_state.typewriter_enabled:
                                    st.session_state.messages.append(
                                        {
                                            "type": "typewriter",
                                            "content": message,
                                            "key": f"typewriter_fallback_{i}",
                                        }
                                    )
                                else:
                                    st.session_state.messages.append(
                                        {
                                            "type": "explanation",
                                            "content": message,
                                            "key": f"fallback_step_{i}",
                                        }
                                    )

                                if st.session_state.tts_enabled:
                                    audio_file = generate_tts(step["content"])
                                    if audio_file:
                                        st.session_state.audio_files.append(audio_file)
                                        st.session_state.messages.append(
                                            {
                                                "type": "audio",
                                                "file": audio_file,
                                                "key": f"audio_fallback_{i}",
                                            }
                                        )
                            st.session_state.waiting_for_feedback = True
                        else:
                            st.session_state.messages.append(
                                {
                                    "type": "error",
                                    "content": "No steps available due to workflow error.",
                                }
                            )
                            st.session_state.workflow_active = False
                            st.session_state.waiting_for_feedback = False

                    st.session_state.messages.append(
                        {
                            "type": "info",
                            "content": f"Current state: step={st.session_state.current_step}, next_action={result.get('next_action', '')}",
                        }
                    )
                    st.rerun()
            else:
                st.error("Please provide a question and context.")

        feedback = st.text_input(
            "Your Feedback",
            value="",
            disabled=not (
                st.session_state.workflow_active
                and st.session_state.waiting_for_feedback
            ),
        )

        submit_feedback = st.button(
            "Submit Feedback",
            disabled=not (
                st.session_state.workflow_active
                and st.session_state.waiting_for_feedback
            ),
        )

        if submit_feedback and st.session_state.waiting_for_feedback:
            if st.session_state.current_state:
                with st.spinner("Processing feedback..."):
                    try:
                        feedback_message = f"Feedback submitted: {feedback or 'None'}"
                        st.session_state.messages.append(
                            {"type": "info", "content": feedback_message}
                        )

                        current_state = st.session_state.current_state.copy()
                        current_state["student_feedback"] = feedback

                        tutor_graph = build_tutor_graph()
                        result = current_state
                        for event in tutor_graph.stream(current_state):
                            if "state" in event:
                                result = event["state"]
                                st.session_state.current_state = result
                                if result.get("explanation_steps"):
                                    st.session_state.explanation_steps = result[
                                        "explanation_steps"
                                    ]
                                if result.get("next_action") in [
                                    "wait_for_feedback",
                                    "end",
                                ]:
                                    break

                        st.session_state.waiting_for_feedback = (
                            result.get("next_action") == "wait_for_feedback"
                        )
                        st.session_state.current_step = result.get("current_step", 0)

                        if result["next_action"] == "present_step":
                            if st.session_state.current_step < len(
                                st.session_state.explanation_steps
                            ):
                                step = st.session_state.explanation_steps[
                                    st.session_state.current_step
                                ]
                                message = f"**Step {st.session_state.current_step + 1}: {step['title']}**\n\n{result['current_explanation']}"

                                if st.session_state.typewriter_enabled:
                                    st.session_state.messages.append(
                                        {
                                            "type": "typewriter",
                                            "content": message,
                                            "key": f"typewriter_step_{st.session_state.current_step}",
                                        }
                                    )
                                else:
                                    st.session_state.messages.append(
                                        {
                                            "type": "explanation",
                                            "content": message,
                                            "key": f"step_{st.session_state.current_step}",
                                        }
                                    )

                                if st.session_state.tts_enabled:
                                    audio_file = generate_tts(
                                        result["current_explanation"]
                                    )
                                    if audio_file:
                                        st.session_state.audio_files.append(audio_file)
                                        st.session_state.messages.append(
                                            {
                                                "type": "audio",
                                                "file": audio_file,
                                                "key": f"audio_step_{st.session_state.current_step}",
                                            }
                                        )
                            else:
                                message = f"**Final Message**\n\n{result['current_explanation']}"
                                st.session_state.messages.append(
                                    {
                                        "type": "explanation",
                                        "content": message,
                                        "key": "final",
                                    }
                                )
                                st.session_state.waiting_for_feedback = False
                                st.session_state.workflow_active = False
                                st.session_state.messages.append(
                                    {"type": "info", "content": "Workflow completed!"}
                                )

                        elif result["next_action"] == "wait_for_feedback":
                            if (
                                "current_explanation" in result
                                and result["current_explanation"]
                            ):
                                message = f"**Additional Explanation**\n\n{result['current_explanation']}"
                                if st.session_state.typewriter_enabled:
                                    st.session_state.messages.append(
                                        {
                                            "type": "typewriter",
                                            "content": message,
                                            "key": f"typewriter_additional_{len(st.session_state.messages)}",
                                        }
                                    )
                                else:
                                    st.session_state.messages.append(
                                        {
                                            "type": "explanation",
                                            "content": message,
                                            "key": f"additional_{len(st.session_state.messages)}",
                                        }
                                    )

                                if st.session_state.tts_enabled:
                                    audio_file = generate_tts(
                                        result["current_explanation"]
                                    )
                                    if audio_file:
                                        st.session_state.audio_files.append(audio_file)
                                        st.session_state.messages.append(
                                            {
                                                "type": "audio",
                                                "file": audio_file,
                                                "key": f"audio_additional_{len(st.session_state.messages)}",
                                            }
                                        )

                        elif result["next_action"] == "end":
                            message = (
                                f"**Final Message**\n\n{result['current_explanation']}"
                            )
                            st.session_state.messages.append(
                                {
                                    "type": "explanation",
                                    "content": message,
                                    "key": "final",
                                }
                            )
                            st.session_state.waiting_for_feedback = False
                            st.session_state.workflow_active = False
                            st.session_state.messages.append(
                                {"type": "info", "content": "Workflow completed!"}
                            )

                    except Exception as e:
                        st.session_state.messages.append(
                            {
                                "type": "error",
                                "content": f"Error processing feedback: {str(e)}",
                            }
                        )
                        # Preserve steps and allow feedback
                        if st.session_state.explanation_steps:
                            st.session_state.waiting_for_feedback = True
                        else:
                            st.session_state.waiting_for_feedback = False
                            st.session_state.workflow_active = False

                        st.session_state.messages.append(
                            {
                                "type": "info",
                                "content": f"Current state: step={st.session_state.current_step}, next_action={result.get('next_action', '')}",
                            }
                        )
                    st.rerun()

    with col2:
        st.subheader("Status")
        status_placeholder = st.empty()
        if st.session_state.workflow_active:
            if (
                st.session_state.explanation_steps
                and st.session_state.current_step
                < len(st.session_state.explanation_steps)
            ):
                step = st.session_state.explanation_steps[st.session_state.current_step]
                status_placeholder.text(
                    f"Step {st.session_state.current_step + 1}: {step['title']}"
                )
            else:
                status_placeholder.text(
                    "Waiting for feedback"
                    if st.session_state.waiting_for_feedback
                    else "Completed"
                )
        else:
            status_placeholder.text("Ready")

        if st.button("Clear"):
            for audio_file in st.session_state.audio_files:
                try:
                    if os.path.exists(audio_file):
                        os.unlink(audio_file)
                except Exception as e:
                    st.warning(f"Error removing audio file: {e}")

            st.session_state.current_state = None
            st.session_state.workflow_active = False
            st.session_state.waiting_for_feedback = False
            st.session_state.messages = []
            st.session_state.current_step = 0
            st.session_state.explanation_steps = []
            st.session_state.audio_files = []
            status_placeholder.text("Ready")
            st.rerun()

    # Explanation display
    st.subheader("Explanations")
    explanation_container = st.container()

    with explanation_container:
        for msg in st.session_state.messages:
            if msg["type"] == "explanation":
                st.markdown(msg["content"], unsafe_allow_html=True)
            elif msg["type"] == "typewriter":
                typewriter_html = create_typewriter_effect(
                    msg["content"],
                    speed=(
                        st.session_state.typewriter_speed
                        if hasattr(st.session_state, "typewriter_speed")
                        else 50
                    ),
                )
                components.html(typewriter_html, height=600)
            elif msg["type"] == "audio":
                html_audio = get_binary_file_downloader_html(msg["file"])
                components.html(html_audio, height=50)
            elif msg["type"] == "info":
                st.info(msg["content"])
            elif msg["type"] == "error":
                st.error(msg["content"])

    # Clean up audio files when closing
    for file in st.session_state.audio_files:
        try:
            if os.path.exists(file):
                os.unlink(file)
        except:
            pass


if __name__ == "__main__":
    main()
