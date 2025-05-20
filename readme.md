This documentation provides a comprehensive and detailed explanation of the IIT JEE Tutor application, covering its core components: the LLM Gateway (`llm_gateway.py`), the Agent/Workflow (`agent.py`), and the User Interface (`main.py`), along with their integration.

-----

## IIT JEE Tutor Application: Comprehensive Technical Documentation

### 1\. Introduction and Architecture Overview

The IIT JEE Tutor is an interactive web application built with Streamlit that leverages a Large Language Model (LLM) to provide step-by-step explanations for IIT JEE-related questions. Its architecture is modular, separating concerns into three primary components:

1.  **LLM Gateway (`llm_gateway.py`):** Handles secure and configured access to the underlying Large Language Model (Azure OpenAI in this case).
2.  **Agent/Workflow (`agent.py`):** Defines the tutor's core intelligence and conversational flow using LangGraph, orchestrating how questions are answered, explanations are generated, and student feedback is processed.
3.  **User Interface (`main.py`):** The Streamlit application that provides the interactive front-end, manages session state, displays explanations, and handles user input (questions, feedback, settings).

This modular design promotes maintainability, scalability, and easier debugging.

### 2\. `llm_gateway.py` - LLM Client Configuration

This file acts as a centralized point for configuring and providing the LLM client, ensuring consistent and secure access to the language model across the application.

#### 2.1. Purpose

  * **Abstraction:** Hides the specific LLM implementation details (e.g., Azure OpenAI) from the rest of the application.
  * **Centralized Configuration:** All LLM-related settings (deployment name, API version, temperature, credentials) are managed in one place.
  * **Security:** Encourages the use of environment variables for sensitive API keys and endpoints.

#### 2.2. Code Breakdown

```python
import os
from langchain_openai import AzureChatOpenAI
from typing import TypedDict, List, Dict, Any, Optional
from pydantic import BaseModel, Field

# Retrieve Azure OpenAI credentials from environment variables
AZURE_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")

def get_openai_client():
    """
    Initializes and returns an AzureChatOpenAI client instance.
    The client is configured using environment variables for API key and endpoint.
    It uses the 'gpt-4o' deployment with a temperature of 0 for deterministic responses.
    """
    if not AZURE_API_KEY:
        raise ValueError("AZURE_OPENAI_API_KEY environment variable not set.")
    if not AZURE_ENDPOINT:
        raise ValueError("AZURE_OPENAI_ENDPOINT environment variable not set.")

    llm = AzureChatOpenAI(
        deployment_name="gpt-4o",  # Specifies the deployed model name in Azure
        openai_api_version="2024-12-01-preview", # Defines the API version for compatibility
        temperature=0,              # Sets the creativity/randomness to 0 for factual responses
        azure_endpoint=AZURE_ENDPOINT, # Your Azure OpenAI service endpoint
        api_key=AZURE_API_KEY,      # Your Azure OpenAI API key
    )
    return llm

if __name__ == "__main__":
    # Example usage for testing the LLM client and structured output
    class test(BaseModel):
        joke: str = Field(description="joke in terms of space")
        name: str = Field(description="name of any history story of space realted to stars")

    try:
        client = get_openai_client()
        # Demonstrates how to use with_structured_output for schema enforcement
        structured_client = client.with_structured_output(test)
        response = structured_client.invoke("tell me a joke about ai")
        print(response)
    except ValueError as e:
        print(f"Configuration error: {e}")
    except Exception as e:
        print(f"Error during test invocation: {e}")
```

#### 2.3. Key Features and Considerations

  * **`AzureChatOpenAI`:** This class from `langchain_openai` is used to interact with Azure OpenAI deployments.
  * **`deployment_name`:** Crucial for specifying which specific model deployment (e.g., `gpt-4o`) configured in your Azure resource will be used.
  * **`temperature=0`:** For a tutor application, deterministic and factual responses are paramount. A temperature of 0 ensures minimal creativity and focuses the LLM on providing precise information.
  * **Environment Variables:** Best practice for managing sensitive credentials. Ensure `AZURE_OPENAI_API_KEY` and `AZURE_OPENAI_ENDPOINT` are set in the environment where the application runs.
  * **`with_structured_output()`:** Demonstrated in the `if __name__ == "__main__":` block, this LangChain feature is vital for enforcing that the LLM's responses conform to a Pydantic `BaseModel` schema. This is extensively used in `agent.py` to ensure reliable parsing of LLM outputs.

### 3\. `agent.py` - Tutor Workflow and Business Logic

This file contains the core intelligence of the IIT JEE Tutor. It defines the conversational flow and decision-making process using **LangGraph**, a library for building stateful, multi-actor applications with LLMs.

#### 3.1. Purpose

  * **Workflow Orchestration:** Defines the sequence of operations, from initial explanation generation to processing feedback and refining explanations.
  * **State Management:** Maintains the conversation's context and progress within the `AgentState`.
  * **LLM Interaction Logic:** Formulates prompts, makes LLM calls, and parses LLM responses for various tutoring tasks.
  * **Feedback Integration:** Incorporates student feedback into the tutoring process to provide personalized guidance.

#### 3.2. Code Breakdown

##### 3.2.1. State Definition (`AgentState`)

```python
from typing import TypedDict, List, Dict, Any, Optional
from pydantic import BaseModel, Field
import json
import re
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI # Although get_openai_client handles this, it's a common import
from langgraph.graph import StateGraph, END
from llm_gateway import get_openai_client # Import the LLM client

class AgentState(TypedDict):
    """
    Represents the state of the tutoring session, passed between graph nodes.
    """
    question: str
    context: str
    subject: str  # The subject of the question (Physics, Chemistry, Mathematics)
    current_step: int # Index of the current explanation step being processed/displayed
    explanation_steps: List[Dict[str, str]] # List of explanation steps: [{'title': '...', 'content': '...'}]
    student_feedback: Optional[str] # The student's latest feedback
    next_action: str # Determines the next transition in the graph (e.g., "present_step", "wait_for_feedback")
    current_explanation: str # The specific explanation text currently generated or presented
```

##### 3.2.2. Structured Output Schemas (`BaseModel`s)

Pydantic models are used to ensure the LLM generates output in a predictable, parseable JSON format.

```python
class FeedbackDecision(BaseModel):
    """
    Schema for the LLM's decision after processing student feedback.
    """
    action: str = Field(
        description="The next action to take based on feedback",
        enum=["clarify_current", "proceed_to_next", "reexplain_current"]
    )
    clarification: Optional[str] = Field(
        description="Additional explanation or rephrasing if clarification/re-explanation is needed."
    )

class Step(BaseModel):
    """
    Schema for a single step within an explanation.
    """
    title: str = Field(description="Brief title of the step")
    content: str = Field(description="Detailed explanation with LaTeX math if applicable")

class ExplanationSteps(BaseModel):
    """
    Schema for the complete list of explanation steps.
    """
    steps: List[Step] = Field(description="List of 3-6 steps to solve the problem")
```

##### 3.2.3. Graph Nodes (Functions)

These functions represent the "nodes" in the LangGraph. Each takes the current `AgentState` and returns an updated `AgentState`.

  * **`initialize_explanation(state: AgentState) -> AgentState`:**

      * **Role:** The entry point for generating the initial, comprehensive step-by-step explanation.
      * **Process:**
        1.  Retrieves the LLM client using `get_openai_client()`.
        2.  Applies `with_structured_output(ExplanationSteps)` to the LLM to ensure the response is a list of `Step` objects.
        3.  Constructs a `ChatPromptTemplate` with detailed system instructions for an IIT JEE tutor. This prompt guides the LLM to:
              * Break down the problem into 3-6 clear, sequential steps.
              * Provide specific guidance for Physics, Chemistry, and Mathematics (e.g., show derivations, balanced equations, proper notation).
              * Emphasize showing *all* mathematical working with **LaTeX notation** (e.g., `$E=mc^2$`).
              * Discourage summarization and encourage detailed, whiteboard-like explanations.
        4.  Invokes the LLM with the user's `question`, `subject`, and `context`.
        5.  Parses the structured LLM response.
        6.  **Error Handling/Fallback:** If the LLM returns an empty or invalid response (e.g., due to parsing issues or hallucination), it provides a generic 3-step fallback explanation to prevent the application from crashing.
      * **State Update:** Updates `state["explanation_steps"]`, sets `state["current_step"]` to `0`, and `state["next_action"]` to `"present_step"`.

  * **`present_current_step(state: AgentState) -> AgentState`:**

      * **Role:** Prepares the content of the current explanation step for display.
      * **Process:**
        1.  Checks if `explanation_steps` is empty or if `current_step` is out of bounds. If so, it transitions to `"end"` or provides an appropriate message.
        2.  Retrieves the `content` of the step identified by `state["current_step"]` from `state["explanation_steps"]`.
      * **State Update:** Sets `state["current_explanation"]` to the content of the current step, and sets `state["next_action"]` to `"wait_for_feedback"` to pause for user interaction.

  * **`process_feedback(state: AgentState) -> AgentState`:**

      * **Role:** Analyzes student feedback and dynamically determines the subsequent action in the tutoring flow.
      * **Process:**
        1.  Retrieves the LLM client and applies `with_structured_output(FeedbackDecision)` to get a structured decision.
        2.  Constructs a `ChatPromptTemplate` that presents the `current_step_content` and the `student_feedback` to the LLM.
        3.  The prompt instructs the LLM to decide on one of three actions:
              * `"clarify_current"`: If the student asks for more details or elaboration on the current step. The LLM should provide the `clarification`.
              * `"reexplain_current"`: If the student indicates confusion and needs the current step explained differently. The LLM provides a new `clarification`.
              * `"proceed_to_next"`: If the student understands or is ready to move on.
        4.  Invokes the LLM with the context.
        5.  Based on the LLM's `action` in the `FeedbackDecision` object:
              * If `clarify_current` or `reexplain_current`: Updates `state["current_explanation"]` with the LLM's `clarification` and keeps `next_action` as `"wait_for_feedback"` to allow the student to review the additional explanation.
              * If `proceed_to_next`: Increments `state["current_step"]`, sets `state["next_action"]` to `"present_step"`, and clears `student_feedback`.
      * **Error Handling:** Catches LLM errors during feedback processing and defaults to `proceed_to_next` to prevent session blockage.

##### 3.2.4. Graph Construction (`build_tutor_graph()`)

```python
def build_tutor_graph():
    """
    Constructs the LangGraph StateGraph defining the tutor's workflow.
    """
    workflow = StateGraph(AgentState) # Initialize graph with the AgentState

    # Add nodes to the graph
    workflow.add_node("initialize", initialize_explanation)
    workflow.add_node("present_step", present_current_step)
    workflow.add_node("process_feedback", process_feedback)

    # Set the entry point for the workflow
    workflow.set_entry_point("initialize")

    # Define direct edges (unconditional transitions)
    workflow.add_edge("initialize", "present_step")

    # Define conditional edges (transitions based on state values)
    workflow.add_conditional_edges(
        "present_step",
        lambda state: state["next_action"], # The state key that determines the next edge
        {
            "wait_for_feedback": "process_feedback", # If waiting for feedback, go to process_feedback node
            "end": END # If explanation is complete or no steps, end the workflow
        }
    )
    workflow.add_conditional_edges(
        "process_feedback",
        lambda state: state["next_action"],
        {
            "present_step": "present_step",      # If student proceeds, go to present_step for the next step
            "wait_for_feedback": "process_feedback", # If clarification/re-explanation, loop back to process_feedback (after current_explanation is updated)
            "end": END                           # If the session ends (e.g., all steps done, or explicit end)
        }
    )

    return workflow.compile() # Compile the graph for execution
```

#### 3.3. Workflow Diagram

```mermaid
graph TD
    A[Start] --> B(initialize_explanation)
    B --> C(present_current_step)
    C -- next_action = "wait_for_feedback" --> D(process_feedback)
    C -- next_action = "end" --> E[End Session]
    D -- action = "proceed_to_next" --> C
    D -- action = "clarify_current" --> D
    D -- action = "reexplain_current" --> D
    D -- action = "end" --> E
```

### 4\. `main.py` - User Interface and Application Flow

This file is the Streamlit application that provides the user-facing interface, manages the application's state, and visualizes the tutor's interactions.

#### 4.1. Purpose

  * **User Interaction:** Provides input fields for questions, context, and feedback.
  * **Display Explanations:** Renders the LLM-generated explanations with formatting, typewriter effects, and Text-to-Speech (TTS).
  * **Session Management:** Uses `st.session_state` to maintain the application's state across reruns.
  * **Feature Toggling:** Allows users to enable/disable TTS and typewriter effects.
  * **Workflow Control:** Triggers the LangGraph workflow based on user actions (Start, Submit Feedback, Clear).

#### 4.2. Key Features and Integration Points

  * **Streamlit Setup:** `st.set_page_config` and `st.title` define the basic page layout.
  * **Session State (`st.session_state`):**
      * Crucial for persistence across Streamlit reruns.
      * Stores `current_state` (the `AgentState` object from `agent.py`), `workflow_active`, `tts_enabled`, `typewriter_enabled`, `messages` (a list of dicts to display, including content, type, and keys), `current_step`, `explanation_steps`, `waiting_for_feedback`, and `audio_files`.
  * **Sidebar Controls:**
      * **Avatar:** Displays an image (`avatar.png`).
      * **Settings:** Checkboxes for `tts_enabled` and `typewriter_enabled`, and a slider for `Typewriter Speed`.
      * **Subject Selection:** A select box to choose the subject, which is passed to the `AgentState`.
  * **Input and Start Button:**
      * `st.text_input` for `question` and `context`.
      * **"Start" Button Logic:**
        1.  When clicked, it initializes the `AgentState` with user inputs and calls `build_tutor_graph()`.
        2.  It then uses `tutor_graph.stream(initial_state)` to start the LangGraph workflow.
        3.  Crucially, `main.py` *iterates through the stream events*. This allows `main.py` to update its `st.session_state` with the latest `AgentState` as the graph progresses.
        4.  It immediately displays *all* generated `explanation_steps` in the initial response using the typewriter effect and TTS (if enabled). This is a design choice to show the full explanation upfront rather than step-by-step requiring feedback after each.
        5.  Sets `waiting_for_feedback = True` to enable the feedback input.
        6.  Handles errors during initialization.
  * **Feedback Mechanism:**
      * `st.text_input` for `Your Feedback`, enabled only when `workflow_active` and `waiting_for_feedback` are true.
      * **"Submit Feedback" Button Logic:**
        1.  Updates `st.session_state.current_state` with the `student_feedback`.
        2.  Re-invokes `tutor_graph.stream(current_state)` to process the feedback via the `process_feedback` node in `agent.py`.
        3.  Again, it iterates through the stream events to update the `AgentState` and `messages`.
        4.  Based on the `next_action` from `process_feedback` (e.g., `present_step`, `wait_for_feedback`, `end`), it updates the UI:
              * If `present_step`, it displays the *next* explanation step.
              * If `wait_for_feedback`, it displays the `current_explanation` (which might be a clarification from the LLM after feedback) and waits for more input.
              * If `end`, it concludes the session.
        5.  Handles errors during feedback processing.
  * **Explanation Display Area:**
      * Iterates through `st.session_state.messages` to render different types of content:
          * `"explanation"`: Rendered directly with `st.markdown` (for standard explanations).
          * `"typewriter"`: Uses `create_typewriter_effect` (custom HTML/JS) and `st.components.v1.html` for the typewriter animation.
          * `"audio"`: Uses `get_binary_file_downloader_html` and `st.components.v1.html` to embed an audio player.
          * `"info"` and `"error"`: Displayed with `st.info` and `st.error` respectively.
  * **Helper Functions (`clean_latex_for_tts`, `generate_tts`, `get_binary_file_downloader_html`, `create_typewriter_effect`):**
      * These functions facilitate the presentation layer, handling LaTeX cleaning for TTS, actual TTS generation, embedding audio, and the typewriter effect.
      * `clean_latex_for_tts` is critical for ensuring that mathematical expressions (which `agent.py` is instructed to generate in LaTeX) are pronounced correctly by `gTTS`.

#### 4.3. UI Integration with Agent Workflow

The seamless interaction between `main.py` and `agent.py` is achieved through:

1.  **Shared `AgentState`:** `main.py` maintains an `AgentState` object in `st.session_state.current_state`. This object is passed to and updated by the `tutor_graph.stream()` method.
2.  **Streaming Interface:** LangGraph's `.stream()` method allows `main.py` to receive updates to the `AgentState` incrementally as the graph executes. This enables dynamic UI updates without waiting for the entire workflow to complete.
3.  **`next_action` Field:** The `next_action` field within the `AgentState` (set by `agent.py` nodes) acts as a signal for `main.py` to determine its UI behavior (e.g., enable feedback, present next step).
4.  **`explanation_steps` and `current_explanation`:** `agent.py` populates these fields, and `main.py` reads them to display the tutoring content.

### 5\. Setup and Running the Application

#### 5.1. Prerequisites

  * Python 3.9+
  * `pip` (Python package installer)
  * An Azure OpenAI Service deployment with a model like `gpt-4o`.

#### 5.2. Environment Variables

Before running, set the following environment variables:

```bash
export AZURE_OPENAI_API_KEY="your_azure_openai_api_key_here"
export AZURE_OPENAI_ENDPOINT="https://your-resource-name.openai.azure.com/"
```

  * **On Linux/macOS:** You can add these to your `~/.bashrc`, `~/.zshrc`, or `~/.profile` file for permanent storage, or set them in your terminal session before running the app.
  * **On Windows (Command Prompt):** `set AZURE_OPENAI_API_KEY=your_key` and `set AZURE_OPENAI_ENDPOINT=your_endpoint`. For PowerShell, use `$env:AZURE_OPENAI_API_KEY="your_key"`.

#### 5.3. Project Structure

Ensure your files are organized as follows:

```
your_project_folder/
├── main.py
├── agent_api.py
├── llm_gateway.py
└── avatar.png (optional, for the sidebar image)
```

#### 5.4. Install Dependencies

Create a `requirements.txt` file with the following content:

```
streamlit
gtts
langchain
langchain-core
langchain-community
langgraph
openai
pydantic
```

Then install them:

```bash
pip install -r requirements.txt
```

#### 5.5. Run the Streamlit Application

For the UI in UI folder use main_ui.py Navigate to your `your_project_folder` in the terminal and run:
For agent backend run the agent_api.py as follows
```bash
pyhton agent_api.py
```


```bash
streamlit run main.py
```

This will open the application in your web browser.

### 6\. Extending and Troubleshooting

#### 6.1. Extending Functionality

  * **Add New Nodes:** To introduce new tutoring phases (e.g., quizzing, problem-solving, detailed feedback analysis), define new functions that update `AgentState` and add them as nodes in `build_tutor_graph()`.
  * **Refine Prompts:** The quality of the LLM's responses is directly tied to the prompts. Iterate and fine-tune system and human messages within `initialize_explanation` and `process_feedback` for better explanations and feedback handling.
  * **New LLM Integration:** If you want to switch from Azure OpenAI to another LLM provider (e.g., Google Gemini, Anthropic Claude), modify `llm_gateway.py` to return the appropriate LLM client from LangChain.
  * **Enhanced Feedback:** You could make `process_feedback` more sophisticated, perhaps by categorizing feedback (e.g., conceptual confusion vs. calculation error) and triggering different refinement sub-workflows.
  * **Persistent Data:** For long-running sessions or user history, consider integrating a database to store `AgentState` or conversation logs.

#### 6.2. Troubleshooting Common Issues

  * **`ValueError: AZURE_OPENAI_API_KEY environment variable not set.`:** Ensure you have correctly set the environment variables as described in section 5.2. Restart your terminal or IDE if necessary.
  * **LLM not responding or giving generic answers:**
      * Check your `deployment_name` in `llm_gateway.py` matches your Azure deployment exactly.
      * Verify your API key and endpoint are correct and active.
      * Review the prompts in `agent.py`. Are they clear, specific, and detailed enough?
      * For structured output issues, check your Pydantic `BaseModel` schemas for correctness. LLMs can sometimes fail to adhere to complex schemas.
  * **Streamlit not updating:** Ensure `st.rerun()` is called after state changes that should trigger a UI update.
  * **TTS errors:** Check your internet connection (gTTS might require it for initial setup or specific voices), and ensure `gTTS` is installed. Review `clean_latex_for_tts` if LaTeX pronunciations are odd.
  * **Typewriter effect not working:** Inspect browser console for JavaScript errors. Ensure MathJax scripts are correctly loaded and `escaped_text` is properly formatted.
  * **Temporary audio files not deleting:** There's a cleanup loop at the end of `main.py` and a "Clear" button that attempts to delete files. If issues persist, check OS permissions on the temporary directory.

This comprehensive documentation should serve as a solid foundation for any developer working with or extending the IIT JEE Tutor application.