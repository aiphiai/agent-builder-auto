

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict, Any, Optional
from pydantic import BaseModel, Field
import json
import re
from llm_gateway import get_openai_client

# Define the state structure
class AgentState(TypedDict):
    question: str
    context: str
    subject: str  # Added subject field
    current_step: int
    explanation_steps: List[Dict[str, str]]
    student_feedback: Optional[str]
    next_action: str
    current_explanation: str

# Define the structured output schema for process_feedback
class FeedbackDecision(BaseModel):
    action: str = Field(
        description="The next action to take",
        enum=["clarify_current", "proceed_to_next", "reexplain_current"]
    )
    clarification: Optional[str] = Field(
        description="Additional explanation if needed"
    )

# Define the structured output schema for initialize_explanation
class Step(BaseModel):
    title: str = Field(description="Brief title of the step")
    content: str = Field(description="Detailed explanation with LaTeX math if applicable")

class ExplanationSteps(BaseModel):
    steps: List[Step] = Field(description="List of 3-6 steps to solve the problem")

# Define the nodes
def initialize_explanation(state: AgentState) -> AgentState:
    """Break down the problem into step-by-step explanation."""
    llm = get_openai_client()
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert IIT JEE tutor. Break down the problem into 3-6 clear, sequential steps.
        
        For mathematics and numerical problems:
        1. Start by identifying the variables, constants, and what needs to be found
        2. Show ALL mathematical working in detail with step-by-step calculations
        3. Use LaTeX for all equations and mathematical notations
        
        For chemistry problems:
        1. Identify key chemical principles, compounds, or reactions involved
        2. Show balanced equations and detailed explanations of mechanisms
        3. Use proper chemical notation and LaTeX for equations
        
        For physics problems:
        1. Identify the physical principles involved
        2. Show detailed derivations and calculations
        3. Use LaTeX for equations and vector notations when needed
        
        DO NOT summarize or give overviews. Work through each step as if solving it on a whiteboard.
        Each step MUST include detailed working with LaTeX math notation for ALL formulas and calculations."""),
        ("human", """
        Question: {question}
        Subject: {subject}
        Context: {context}

        For each step:
        1. Provide a brief title
        2. Explain the concept involved
        3. Include ALL mathematical working (using LaTeX notation like $E=mc^2$)
        4. Show every single calculation in detail
        5. Don't skip steps or just provide answers without working

        Respond with a structured output containing the steps.
        """)
    ])

    try:
        # Use structured output to get ExplanationSteps directly
        structured_llm = llm.with_structured_output(ExplanationSteps)
        response = structured_llm.invoke(prompt.format(
            question=state["question"],
            subject=state.get("subject", "Physics"),  # Default to Physics if not specified
            context=state["context"]
        ))
        print(f"Debug: Raw LLM response: {response}")  # Log raw response
        if response is None or not hasattr(response, "steps"):
            print("Error: LLM returned None or invalid response")
            steps = [
                {"title": "Step 1: Introduction", "content": f"For the question '{state['question']}', let's break it down. This step introduces the concept."},
                {"title": "Step 2: Basic Explanation", "content": "This step provides a basic explanation to proceed."},
                {"title": "Step 3: Summary", "content": "This summarizes the key points."}
            ]
        else:
            steps = [{"title": step.title, "content": step.content} for step in response.steps]
            if not steps:
                print("Warning: No steps returned by LLM")
                steps = [
                    {"title": "Step 1: Introduction", "content": f"For the question '{state['question']}', let's break it down. This step introduces the concept."},
                    {"title": "Step 2: Basic Explanation", "content": "This step provides a basic explanation to proceed."},
                    {"title": "Step 3: Summary", "content": "This summarizes the key points."}
                ]
            elif len(steps) < 3 or len(steps) > 6:
                print(f"Warning: Expected 3-6 steps, got {len(steps)}")
    except Exception as e:
        print(f"Error: Failed to get structured output from LLM: {e}")
        steps = [
            {"title": "Step 1: Introduction", "content": f"For the question '{state['question']}', let's break it down. This step introduces the concept. Error: {e}"},
            {"title": "Step 2: Basic Explanation", "content": "This step provides a basic explanation to proceed."},
            {"title": "Step 3: Summary", "content": "This summarizes the key points."}
        ]

    return {
        **state,
        "explanation_steps": steps,
        "current_step": 0,
        "next_action": "present_step"
    }

def present_current_step(state: AgentState) -> AgentState:
    """Present the current step to the student."""
    if not state["explanation_steps"]:
        print("Warning: explanation_steps is empty")
        return {
            **state,
            "current_explanation": "No explanation steps available. Do you have any questions?",
            "next_action": "end"
        }
    if state["current_step"] < len(state["explanation_steps"]):
        current_step = state["explanation_steps"][state["current_step"]]
        return {
            **state,
            "current_explanation": current_step["content"],
            "next_action": "wait_for_feedback"
        }
    else:
        return {
            **state,
            "current_explanation": "We've completed all steps of the explanation. Do you have any questions?",
            "next_action": "end"
        }

def process_feedback(state: AgentState) -> AgentState:
    """Process student feedback and determine next action."""
    if not state["explanation_steps"]:
        print("Error: explanation_steps is empty in process_feedback")
        return {
            **state,
            "current_explanation": "No steps available to explain. Would you like to restart?",
            "next_action": "end"
        }
    if state["current_step"] >= len(state["explanation_steps"]):
        print("Error: current_step out of range")
        return {
            **state,
            "current_explanation": "All steps completed. Any further questions?",
            "next_action": "end"
        }

    llm = get_openai_client().with_structured_output(FeedbackDecision)
    feedback = state["student_feedback"] or "No feedback provided"
    current_step_content = state["explanation_steps"][state["current_step"]]["content"]

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an IIT JEE tutor. Analyze the student's feedback and respond appropriately.
        If they ask for more details on calculations or derivations, provide the missing steps with full mathematical working.
        If they're confused about a concept, provide alternative explanations with examples."""),
        ("human", """
        The student is learning about a problem. You've just explained:

        {current_step_content}

        The student responded: "{feedback}"

        Based on this feedback, determine what to do next:
        1. If they're asking for clarification, provide it with detailed mathematical working if applicable
        2. If they seem ready to move on (e.g., "okay", "looks good", "continue", or no feedback), proceed to the next step
        3. If they're confused, try explaining the current step differently with more detail

        Respond with a structured JSON object according to the schema provided.
        """)
    ])

    try:
        decision = llm.invoke(prompt.format(
            current_step_content=current_step_content,
            feedback=feedback
        ))
        action = decision.action
        clarification = decision.clarification
    except Exception as e:
        print(f"Error: Failed to get structured output from LLM: {e}")
        action = "proceed_to_next"
        clarification = ""

    if action == "clarify_current":
        return {
            **state,
            "current_explanation": clarification,
            "next_action": "wait_for_feedback"
        }
    elif action == "reexplain_current":
        return {
            **state,
            "current_explanation": f"Let me explain this differently: {clarification}",
            "next_action": "wait_for_feedback"
        }
    else:  # proceed_to_next
        return {
            **state,
            "current_step": state["current_step"] + 1,
            "next_action": "present_step",
            "student_feedback": None  # Reset feedback to avoid reusing old input
        }

# Build the graph
def build_tutor_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("initialize", initialize_explanation)
    workflow.add_node("present_step", present_current_step)
    workflow.add_node("process_feedback", process_feedback)
    workflow.add_edge("initialize", "present_step")
    workflow.add_conditional_edges(
        "present_step",
        lambda state: state["next_action"],
        {
            "wait_for_feedback": "process_feedback",
            "end": END
        }
    )
    workflow.add_conditional_edges(
        "process_feedback",
        lambda state: state["next_action"],
        {
            "present_step": "present_step",
            "wait_for_feedback": "process_feedback",
            "end": END
        }
    )
    workflow.set_entry_point("initialize")
    return workflow.compile()