import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.prompts import ChatPromptTemplate
from typing import TypedDict, List, Dict, Optional
from pydantic import BaseModel, Field
from llm_gateway import get_openai_client
import re
import traceback

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Define the state structure
class AgentState(TypedDict):
    question: str
    context: str
    subject: str
    explanation_steps: List[Dict[str, str]]
    student_feedback: Optional[str]
    response: Optional[str]
    is_understood: bool


# Define input schema for API
class TutorRequest(BaseModel):
    question: str
    context: str
    subject: str
    feedback: Optional[str] = None


# Define the structured output schema for explanation
class Step(BaseModel):
    title: str = Field(description="Brief title describing the purpose of this step")
    content: str = Field(
        description="Detailed explanation, calculation, or derivation for this step, using LaTeX math/chem notation where applicable"
    )


class ExplanationSteps(BaseModel):
    steps: List[Step] = Field(
        description="List of detailed, sequential steps that fully solve the problem"
    )


# Define the structured output schema for feedback processing
class FeedbackResponse(BaseModel):
    response: str = Field(
        description="Response to the student's feedback, clarifying points or acknowledging understanding"
    )
    is_understood: bool = Field(
        description="Whether the student's feedback indicates they have understood the solution"
    )


# Narration and Validation Functions
def clean_for_narration(text: str) -> str:
    """Remove LaTeX syntax and convert equations to plain English for narration."""
    physics_formulas = {
        r"\$KE = \\frac\{1\}\{2\}mv\^2\$": "kinetic energy equals one-half m v squared",
        r"\$W = \\frac\{1\}\{2\}m\(v\^2 - u\^2\)\$": "work equals one-half m times v squared minus u squared",
        r"\$F = ma\$": "force equals mass times acceleration",
        r"\$E = mc\^2\$": "energy equals m c squared",
        r"\$s = ut \+ \\frac\{1\}\{2\}at\^2\$": "s equals u t plus one-half a t squared",
        r"\$v = u \+ at\$": "v equals u plus a t",
        r"\$v\^2 = u\^2 \+ 2as\$": "v squared equals u squared plus 2 a s",
        r"\\begin\{bmatrix\}.*?\\end\{bmatrix\}": "matrix",
    }
    for formula, narration in physics_formulas.items():
        text = re.sub(formula, narration, text)
    text = re.sub(
        r"\$s = ut \+ \\frac\{1\}\{2\}at\^2\$",
        "The displacement s equals initial velocity u times time t plus one-half times acceleration a times time squared",
        text,
    )
    text = re.sub(r"\$v = \\frac\{ds\}\{dt\}\$", "velocity v equals ds by dt", text)
    text = re.sub(r"\$([^$]+)\$", lambda m: convert_latex_to_speech(m.group(1)), text)
    text = (
        text.replace("$", "")
        .replace("\\", "")
        .replace("^2", " squared")
        .replace("^3", " cubed")
        .replace("_", " sub ")
    )
    return text.strip()


def convert_latex_to_speech(latex: str) -> str:
    """Convert LaTeX equations to readable speech."""
    latex = latex.strip()
    latex = re.sub(r"\\frac\{([^}]+)\}\{([^}]+)\}", r"the fraction \1 over \2", latex)
    replacements = [
        (r"\\sqrt\{([^}]+)\}", r"the square root of \1"),
        (r"\\int", "the integral of"),
        (r"\\sum", "the sum of"),
        (r"\\lim", "the limit as"),
        (r"\\log", "log"),
        (r"\\ln", "natural log"),
        (r"\\sin", "sine"),
        (r"\\cos", "cosine"),
        (r"\\tan", "tangent"),
        (r"\\Delta", "delta"),
        (r"\\theta", "theta"),
        (r"\\alpha", "alpha"),
        (r"\\beta", "beta"),
        (r"\\gamma", "gamma"),
        (r"\\omega", "omega"),
        (r"\\pi", "pi"),
        (r"\^\{?([\w\d\+\-]+)\}?", r" to the power of \1"),
        (r"\_\{?([\w\d]+)\}?", r" sub \1"),
        (r"\\times", "times"),
        (r"\\cdot", "dot"),
        (r"\\approx", "approximately equals"),
        (r"\\neq", "not equal to"),
        (r"\\leq", "less than or equal to"),
        (r"\\geq", "greater than or equal to"),
        (r"\\pm", "plus or minus"),
        (r"\\in", "is an element of"),
        (r"\\rightarrow", "approaches or implies"),
        (r"\\Rightarrow", "implies"),
        (r"\\leftrightarrow", "if and only if"),
        (r"\\Leftrightarrow", "if and only if"),
        (r"\\infty", "infinity"),
        (r"\\partial", "the partial derivative with respect to"),
        (r"\\nabla", "nabla"),
        (r"\\vec\{(\w)\}", r"vector \1"),
        (r"\{", ""),
        (r"\}", ""),
    ]
    for pattern, replacement in replacements:
        latex = re.sub(pattern, replacement, latex)
    match = re.match(r"(.+?)\s*(=|\\leq|\\geq|\\neq|\\approx)\s*(.+)", latex)
    if match:
        left, op, right = match.groups()
        op_speech = {
            "=": "equals",
            "\\leq": "is less than or equal to",
            "\\geq": "is greater than or equal to",
            "\\neq": "is not equal to",
            "\\approx": "is approximately equal to",
        }.get(op, op)
        return f"{left.strip()} {op_speech} {right.strip()}"
    return latex.replace("  ", " ").strip()


def validate_latex(content: str) -> bool:
    """Basic validation for LaTeX syntax."""
    try:
        if content.count("$") % 2 != 0:
            print(f"Warning: Unbalanced $ in content: {content[:100]}...")
            return False
        if "$$" in content or "\\\\" in content:
            if "\\\\" in content and not re.search(r"\$.*\\\\.*\$", content):
                print(f"Warning: Invalid LaTeX sequence in: {content[:100]}...")
                return False
        return True
    except Exception as e:
        print(f"Error during LaTeX validation: {e}")
        return False


# Updated generate_explanation
def generate_explanation(state: AgentState) -> AgentState:
    """Generate a complete, step-by-step solution to the problem."""
    llm = get_openai_client()

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are an expert IIT JEE tutor specializing in Physics, Chemistry, and Mathematics. Your task is to provide a **complete, step-by-step solution** to the given problem, leading to the final answer. Execute every calculation in full detail, showing all intermediate steps.

        **General Instructions:**
        1. **Solve Completely**: Work through the entire problem from start to finish. Perform all calculations, derivations, and matrix operations explicitly, showing every step.
        2. **Detailed Steps**: Break the solution into clear, sequential steps. Each step should contain a specific part of the solution process (e.g., a single matrix multiplication, a derivation, a substitution).
        3. **Show All Work**: Do not skip any calculations or assume prior knowledge beyond standard high-school/JEE level concepts. Define all variables, state formulas/theorems, and perform every operation element-wise for matrices. For matrix multiplication, show each element's computation: $c_{{ij}} = \\sum_k a_{{ik}} b_{{kj}}$.
        4. **Final Answer**: The final step must present the computed answer (e.g., numerical value, matrix, equation) clearly, using LaTeX and boxing it (e.g., $\\boxed{{ \\begin{{bmatrix}} x & y \\\\ z & w \\end{{bmatrix}} }}$).
        5. **Use LaTeX**: Use single '$' delimiters for all mathematical expressions, matrices (e.g., $\\begin{{bmatrix}} a & b \\\\ c & d \\end{{bmatrix}}$), and units. Ensure LaTeX is syntactically correct and avoid double dollar signs ($$).

        **Subject-Specific Guidance ({subject}):**
        * **Mathematics**: For matrix problems, explicitly compute each operation (e.g., $A^2$, $A^{{-1}}$). Show matrix multiplications row-by-column, determinants, adjoints, and inverses step-by-step. Verify matrix dimensions and invertibility. For each matrix operation, write out the resulting matrix after computation.
        * **Physics/Chemistry**: Apply relevant principles, but for matrix problems, focus on linear algebra as it’s Mathematics.

        **Output Format**:
        Respond ONLY with structured JSON containing the list of all solution steps. Each step must have:
        1. A `title` describing the step’s purpose (e.g., 'Compute Matrix $A^2$').
        2. The `content` with the full calculation, explanation, and LaTeX-formatted work, ending with the step’s result.""",
            ),
            (
                "human",
                """
        Please provide a full step-by-step solution for the following problem:
        Subject: {subject}
        Question: {question}
        Context/Given Information: {context}
        """,
            ),
        ]
    )

    try:
        structured_llm = llm.with_structured_output(ExplanationSteps)
        response = structured_llm.invoke(
            prompt.format(
                question=state["question"],
                subject=state.get("subject", "Mathematics"),
                context=state["context"],
            )
        )
        print(f"Debug: Raw LLM explanation response: {response}")
        if response is None or not hasattr(response, "steps") or not response.steps:
            print("Error: LLM returned None or empty steps for explanation.")
            steps = [
                {
                    "title": "Error Generating Solution",
                    "content": f"I encountered an issue generating the detailed solution for: '{state['question']}'. Please try rephrasing or check the question.",
                    "narration": "Error generating solution.",
                }
            ]
        else:
            steps = []
            for i, step in enumerate(response.steps):
                if not step.title or not step.content:
                    print(
                        f"Warning: Step {i+1} has missing title or content. Skipping."
                    )
                    continue
                if validate_latex(step.content):
                    narration = clean_for_narration(step.content)
                    steps.append(
                        {
                            "title": step.title,
                            "content": step.content,
                            "narration": narration,
                        }
                    )
                else:
                    print(f"Warning: LaTeX validation failed for Step {i+1} content.")
                    narration = clean_for_narration(step.content)
                    steps.append(
                        {
                            "title": step.title,
                            "content": step.content,
                            "narration": narration + " (LaTeX potentially invalid)",
                        }
                    )
            if not steps:
                print("Error: All generated steps failed validation or were empty.")
                steps = [
                    {
                        "title": "Error Processing Solution",
                        "content": "Failed to process the generated solution steps correctly.",
                        "narration": "Error processing solution.",
                    }
                ]
    except Exception as e:
        print(f"Error: Failed to get structured explanation output from LLM.")
        print(f"Exception Type: {type(e)}")
        print(f"Exception Args: {e.args}")
        print("Full Traceback:")
        traceback.print_exc()
        steps = [
            {
                "title": "LLM Error",
                "content": f"An error occurred while communicating with the AI model. Please try again later. Details: {e}",
                "narration": f"An error occurred: {str(e)}",
            }
        ]

    return {
        **state,
        "explanation_steps": steps,
        "response": None,
        "is_understood": False,
    }


def process_feedback(state: AgentState) -> AgentState:
    """Process student feedback on the provided solution and check for understanding."""
    if not state.get("explanation_steps") or state["explanation_steps"][0].get(
        "title", ""
    ).startswith("Error"):
        print(
            "Error: Cannot process feedback as no valid explanation/solution steps are available."
        )
        return {
            **state,
            "response": "I apologize, but there seems to be no valid solution loaded for me to discuss feedback on. Could you please ask the question again?",
            "is_understood": False,
        }

    feedback = state.get("student_feedback")
    if not feedback:
        print("Warning: No feedback provided by the student.")
        return {
            **state,
            "response": "No feedback was provided. Do you have any questions about the solution, or shall we move on?",
            "is_understood": state.get("is_understood", False),
        }

    llm = get_openai_client()
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are an expert IIT JEE tutor for Physics, Chemistry, and Mathematics. The student was provided with a detailed step-by-step solution to their question and has now given feedback. Analyze their feedback carefully in the context of the solution provided and respond appropriately.

        **Instructions:**
        1. **Analyze Feedback**: Understand the student's point. Are they confused about a specific step, calculation, concept, or formula? Do they think something is wrong? Or are they confirming understanding?
        2. **Address Confusion**: If the student expresses confusion, provide a targeted, detailed clarification. Refer to the specific step number or concept. Use LaTeX ($...$) for formulas or calculations.
        3. **Acknowledge Understanding**: If the student confirms understanding (e.g., "understood", "got it"), acknowledge positively and suggest readiness for another question.
        4. **Handle Disagreements**: If the student claims an error, re-evaluate the step. If they’re correct, acknowledge and correct; if the solution is correct, explain why.
        5. **Clarify Vague Feedback**: If feedback is vague (e.g., "It's wrong"), ask for specific details about which step or part is unclear.
        6. **Determine Understanding**: Set `is_understood` to `True` only if the feedback explicitly indicates understanding (e.g., "understood", "clear", "got it"). Otherwise, set to `False`.

        Respond ONLY with a structured JSON output containing:
        1. Your `response` text to the student.
        2. A boolean `is_understood` based on their latest feedback.""",
            ),
            (
                "human",
                """
        Original Question: {question}
        Subject: {subject}

        My Step-by-Step Solution Provided:
        {explanation_text}

        Student's Feedback: "{feedback}"

        Analyze this feedback and respond according to the instructions. Determine `is_understood` based *only* on this feedback.
        """,
            ),
        ]
    )

    try:
        structured_llm = llm.with_structured_output(FeedbackResponse)
        explanation_text = "\n\n".join(
            [
                f"**{i+1}. {step.get('title', 'Step ' + str(i+1))}**\n{step.get('content', 'N/A')}"
                for i, step in enumerate(state["explanation_steps"])
            ]
        )
        max_context_len = 3000
        if len(explanation_text) > max_context_len:
            explanation_text = (
                explanation_text[:max_context_len]
                + "\n... [solution truncated for brevity]"
            )
        response_obj = structured_llm.invoke(
            prompt.format(
                question=state["question"],
                subject=state["subject"],
                explanation_text=explanation_text,
                feedback=feedback,
            )
        )
        print(f"Debug: Raw LLM feedback response: {response_obj}")
        response_text = response_obj.response
        is_understood = response_obj.is_understood
    except Exception as e:
        print(f"Error: Failed to process feedback using LLM: {e}")
        response_text = "I apologize, I encountered an issue processing your feedback. Could you please rephrase it or ask your question again?"
        is_understood = False

    return {**state, "response": response_text, "is_understood": is_understood}


@app.post("/tutor")
async def tutor_endpoint(request: TutorRequest):
    """Handles initial questions and subsequent feedback for the AI tutor."""
    try:
        state: AgentState = {
            "question": request.question,
            "context": request.context,
            "subject": request.subject,
            "explanation_steps": [],
            "student_feedback": request.feedback,
            "response": None,
            "is_understood": False,
        }
        print(
            f"Processing request for question: '{request.question[:50]}...' with feedback: '{request.feedback}'"
        )
        state = generate_explanation(state)
        if state["explanation_steps"] and state["explanation_steps"][0].get(
            "title", ""
        ).startswith("Error"):
            print("Stopping processing due to error during explanation generation.")
            return state
        if request.feedback:
            print("Feedback provided, proceeding to process feedback.")
            state = process_feedback(state)
        else:
            print("No feedback provided, returning generated explanation steps.")
        return state
    except Exception as e:
        print(f"Fatal Error in tutor_endpoint: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"An unexpected server error occurred: {str(e)}"
        )


if __name__ == "__main__":
    print("Starting Uvicorn server on 0.0.0.0:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)
