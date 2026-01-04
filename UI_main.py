"""
AI Prompt Failure Diagnosis Agent using Agentic AI
Built with LangGraph, Groq, and Gradio
"""

import os
import json
import re
from typing import TypedDict, Annotated, List, Dict, Literal
from datetime import datetime
import gradio as gr

# LangChain and LangGraph imports
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages


# CONFIGURATION


GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")


# STATE DEFINITION


class DiagnosisState(TypedDict):
    """State object that flows through the diagnosis workflow"""

    messages: Annotated[list, add_messages]
    original_prompt: str
    expected_output: str
    actual_output: str
    failure_categories: List[str]
    root_cause_analysis: str
    improved_prompt: str
    explanation: str
    quality_metrics: Dict[str, any]
    error: str


# LLM INITIALIZATION


def get_llm(temperature=0.3):
    """Initialize Groq LLM with LLaMA 3.3"""
    if not GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY not set. Please set it as an environment variable."
        )

    return ChatGroq(
        api_key=GROQ_API_KEY,
        model="llama-3.3-70b-versatile",
        temperature=temperature,
        max_tokens=2048,
    )


# QUALITY ANALYSIS FUNCTIONS


def analyze_prompt_quality(prompt: str) -> Dict[str, any]:
    """
    Rule-based quality checks for prompts
    """
    metrics = {
        "token_count": len(prompt.split()),
        "character_count": len(prompt),
        "has_clear_instruction": False,
        "has_examples": False,
        "has_constraints": False,
        "has_output_format": False,
        "instruction_density": 0.0,
        "quality_score": 0.0,
    }

    prompt_lower = prompt.lower()

    # Check for clear instructions
    instruction_keywords = [
        "create",
        "generate",
        "write",
        "analyze",
        "summarize",
        "explain",
        "describe",
        "list",
        "compare",
        "evaluate",
    ]
    metrics["has_clear_instruction"] = any(
        keyword in prompt_lower for keyword in instruction_keywords
    )

    # Check for examples
    example_indicators = ["example:", "for example", "e.g.", "such as", "like this"]
    metrics["has_examples"] = any(
        indicator in prompt_lower for indicator in example_indicators
    )

    # Check for constraints
    constraint_keywords = [
        "must",
        "should",
        "don't",
        "avoid",
        "only",
        "exactly",
        "no more than",
        "at least",
        "maximum",
        "minimum",
    ]
    metrics["has_constraints"] = any(
        keyword in prompt_lower for keyword in constraint_keywords
    )

    # Check for output format specification
    format_keywords = [
        "format:",
        "output:",
        "structure:",
        "json",
        "markdown",
        "bullet points",
        "numbered list",
        "table",
    ]
    metrics["has_output_format"] = any(
        keyword in prompt_lower for keyword in format_keywords
    )

    # Calculate instruction density (instructions per 100 words)
    if metrics["token_count"] > 0:
        instruction_count = sum(
            1 for keyword in instruction_keywords if keyword in prompt_lower
        )
        metrics["instruction_density"] = (
            instruction_count / metrics["token_count"]
        ) * 100

    # Calculate overall quality score (0-100)
    score = 0
    score += 25 if metrics["has_clear_instruction"] else 0
    score += 25 if metrics["has_examples"] else 0
    score += 25 if metrics["has_constraints"] else 0
    score += 25 if metrics["has_output_format"] else 0
    metrics["quality_score"] = score

    return metrics


# AGENT NODES


def analyze_quality_node(state: DiagnosisState) -> DiagnosisState:
    """
    Node 1: Perform rule-based quality analysis
    """
    try:
        prompt = state["original_prompt"]
        quality_metrics = analyze_prompt_quality(prompt)

        state["quality_metrics"] = quality_metrics
        state["messages"].append(
            AIMessage(
                content=f"Quality analysis complete. Score: {quality_metrics['quality_score']}/100"
            )
        )

        return state

    except Exception as e:
        state["error"] = f"Quality analysis error: {str(e)}"
        return state


def classify_failure_node(state: DiagnosisState) -> DiagnosisState:
    """
    Node 2: Classify failure categories using LLM
    """
    try:
        llm = get_llm(temperature=0.2)

        original_prompt = state["original_prompt"]
        expected_output = state["expected_output"]
        actual_output = state["actual_output"]

        system_prompt = """You are an expert prompt engineering diagnostician. Analyze the failed prompt and classify the failure into one or more categories.

**Failure Categories:**
1. **Ambiguity** - Unclear or vague instructions
2. **Missing Constraints** - Lacks necessary boundaries or rules
3. **Missing Examples** - No examples to guide the model
4. **Overloaded Instructions** - Too many conflicting objectives
5. **Poor Role Definition** - Unclear context or persona
6. **Formatting Issues** - Output structure not specified
7. **Context Loss** - Missing background information
8. **Conflicting Objectives** - Contradictory instructions

Analyze the prompt and identify ALL applicable failure categories.

Return your response as a JSON object with this structure:
{
  "categories": ["category1", "category2", ...],
  "brief_reasoning": "One sentence explaining the classification"
}

Return ONLY the JSON, no other text."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=f"""**Original Prompt:**
{original_prompt}

**Expected Output:**
{expected_output}

**Actual Output:**
{actual_output}

Classify the failure categories."""
            ),
        ]

        response = llm.invoke(messages)
        content = response.content.strip()

        # Extract JSON from response
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            state["failure_categories"] = result.get("categories", [])
            state["messages"].append(
                AIMessage(
                    content=f"Identified {len(state['failure_categories'])} failure categories"
                )
            )
        else:
            state["failure_categories"] = ["Unknown"]

        return state

    except Exception as e:
        state["error"] = f"Classification error: {str(e)}"
        state["failure_categories"] = ["Analysis Error"]
        return state


def diagnose_root_cause_node(state: DiagnosisState) -> DiagnosisState:
    """
    Node 3: Perform deep root cause analysis
    """
    try:
        llm = get_llm(temperature=0.3)

        original_prompt = state["original_prompt"]
        expected_output = state["expected_output"]
        actual_output = state["actual_output"]
        categories = state["failure_categories"]
        quality_metrics = state["quality_metrics"]

        system_prompt = """You are an expert in LLM behavior and prompt engineering. Perform a deep root cause analysis explaining WHY the prompt failed.

Focus on:
- How the LLM interpreted (or misinterpreted) the instructions
- What context or constraints were missing
- Why the actual output differs from expected output
- Specific prompt engineering principles that were violated

Provide a clear, technical analysis in 3-4 paragraphs. Be specific and reference actual parts of the prompt."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=f"""**Original Prompt:**
{original_prompt}

**Expected Output:**
{expected_output}

**Actual Output:**
{actual_output}

**Identified Failure Categories:**
{', '.join(categories)}

**Quality Metrics:**
- Token Count: {quality_metrics.get('token_count')}
- Has Clear Instruction: {quality_metrics.get('has_clear_instruction')}
- Has Examples: {quality_metrics.get('has_examples')}
- Has Constraints: {quality_metrics.get('has_constraints')}
- Quality Score: {quality_metrics.get('quality_score')}/100

Provide a detailed root cause analysis."""
            ),
        ]

        response = llm.invoke(messages)
        state["root_cause_analysis"] = response.content.strip()
        state["messages"].append(AIMessage(content="Root cause analysis complete"))

        return state

    except Exception as e:
        state["error"] = f"Root cause analysis error: {str(e)}"
        state["root_cause_analysis"] = "Unable to perform root cause analysis"
        return state


def generate_improved_prompt_node(state: DiagnosisState) -> DiagnosisState:
    """
    Node 4: Generate improved prompt based on diagnosis
    """
    try:
        llm = get_llm(temperature=0.4)

        original_prompt = state["original_prompt"]
        categories = state["failure_categories"]
        root_cause = state["root_cause_analysis"]
        expected_output = state["expected_output"]

        system_prompt = """You are an expert prompt engineer. Based on the failure analysis, create an improved version of the prompt.

**Guidelines for improvement:**
1. Add clear, specific instructions
2. Include relevant examples if missing
3. Define explicit constraints and boundaries
4. Specify output format clearly
5. Add role/context if beneficial
6. Remove ambiguity and conflicting instructions
7. Structure the prompt logically

Return your response as a JSON object:
{
  "improved_prompt": "The complete improved prompt text",
  "key_changes": ["change 1", "change 2", ...],
  "reasoning": "Brief explanation of improvements"
}

Return ONLY the JSON, no other text."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=f"""**Original Prompt:**
{original_prompt}

**Expected Output:**
{expected_output}

**Failure Categories:**
{', '.join(categories)}

**Root Cause Analysis:**
{root_cause}

Generate an improved prompt that addresses these issues."""
            ),
        ]

        response = llm.invoke(messages)
        content = response.content.strip()

        # Extract JSON from response
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            state["improved_prompt"] = result.get("improved_prompt", original_prompt)

            # Store explanation with key changes
            key_changes = result.get("key_changes", [])
            reasoning = result.get("reasoning", "")
            state["explanation"] = f"**Key Changes:**\n" + "\n".join(
                [f"- {change}" for change in key_changes]
            )
            state["explanation"] += f"\n\n**Reasoning:**\n{reasoning}"
        else:
            state["improved_prompt"] = "Unable to generate improved prompt"
            state["explanation"] = "Error in prompt generation"

        state["messages"].append(AIMessage(content="Improved prompt generated"))

        return state

    except Exception as e:
        state["error"] = f"Prompt improvement error: {str(e)}"
        state["improved_prompt"] = state["original_prompt"]
        state["explanation"] = "Unable to generate improvements"
        return state


def error_handler_node(state: DiagnosisState) -> DiagnosisState:
    """
    Handle errors gracefully
    """
    error_msg = state.get("error", "Unknown error occurred")
    state["explanation"] = (
        f"⚠️ **Error**: {error_msg}\n\nPlease check your inputs and API key."
    )
    return state


# ROUTING LOGIC


def route_after_quality(state: DiagnosisState) -> Literal["classify", "error"]:
    """Route after quality analysis"""
    if state.get("error"):
        return "error"
    return "classify"


def route_after_classify(state: DiagnosisState) -> Literal["diagnose", "error"]:
    """Route after classification"""
    if state.get("error"):
        return "error"
    return "diagnose"


def route_after_diagnose(state: DiagnosisState) -> Literal["improve", "error"]:
    """Route after diagnosis"""
    if state.get("error"):
        return "error"
    return "improve"


# GRAPH CONSTRUCTION


def create_diagnosis_graph():
    """
    Build the LangGraph workflow for prompt diagnosis
    """
    workflow = StateGraph(DiagnosisState)

    # Add nodes
    workflow.add_node("analyze_quality", analyze_quality_node)
    workflow.add_node("classify", classify_failure_node)
    workflow.add_node("diagnose", diagnose_root_cause_node)
    workflow.add_node("improve", generate_improved_prompt_node)
    workflow.add_node("error", error_handler_node)

    # Define edges
    workflow.set_entry_point("analyze_quality")

    workflow.add_conditional_edges(
        "analyze_quality",
        route_after_quality,
        {"classify": "classify", "error": "error"},
    )

    workflow.add_conditional_edges(
        "classify", route_after_classify, {"diagnose": "diagnose", "error": "error"}
    )

    workflow.add_conditional_edges(
        "diagnose", route_after_diagnose, {"improve": "improve", "error": "error"}
    )

    workflow.add_edge("improve", END)
    workflow.add_edge("error", END)

    return workflow.compile()


# GRADIO INTERFACE


def diagnose_prompt(
    original_prompt: str, expected_output: str, actual_output: str, groq_key: str
) -> tuple:
    """
    Main function to process prompt diagnosis
    """
    # Set API key
    global GROQ_API_KEY
    GROQ_API_KEY = groq_key or GROQ_API_KEY

    if not GROQ_API_KEY:
        return "❌ Please provide your Groq API key", "", "", ""

    if not original_prompt.strip():
        return "❌ Please provide the original prompt", "", "", ""

    if not expected_output.strip():
        return "❌ Please provide the expected output", "", "", ""

    if not actual_output.strip():
        return "❌ Please provide the actual output", "", "", ""

    try:
        # Initialize state
        initial_state = {
            "messages": [],
            "original_prompt": original_prompt,
            "expected_output": expected_output,
            "actual_output": actual_output,
            "failure_categories": [],
            "root_cause_analysis": "",
            "improved_prompt": "",
            "explanation": "",
            "quality_metrics": {},
            "error": "",
        }

        # Create and run agent
        agent = create_diagnosis_graph()
        result = agent.invoke(initial_state)

        # Format results
        quality_metrics = result.get("quality_metrics", {})
        quality_report = f"""## 📊 Quality Analysis

**Basic Metrics:**
- Token Count: {quality_metrics.get('token_count', 0)}
- Character Count: {quality_metrics.get('character_count', 0)}
- Instruction Density: {quality_metrics.get('instruction_density', 0):.2f}%

**Quality Checks:**
- ✓ Clear Instruction: {'Yes' if quality_metrics.get('has_clear_instruction') else 'No'}
- ✓ Has Examples: {'Yes' if quality_metrics.get('has_examples') else 'No'}
- ✓ Has Constraints: {'Yes' if quality_metrics.get('has_constraints') else 'No'}
- ✓ Output Format Specified: {'Yes' if quality_metrics.get('has_output_format') else 'No'}

**Overall Quality Score: {quality_metrics.get('quality_score', 0)}/100**
"""

        categories = result.get("failure_categories", [])
        diagnosis_report = f"""## 🔍 Failure Diagnosis

**Identified Categories:**
{chr(10).join([f'- **{cat}**' for cat in categories])}

**Root Cause Analysis:**

{result.get('root_cause_analysis', 'No analysis available')}
"""

        improved_prompt = result.get("improved_prompt", "No improved prompt generated")

        explanation = f"""## 💡 Improvement Explanation

{result.get('explanation', 'No explanation available')}

---

**Why This Will Work Better:**
The improved prompt addresses the identified failure categories by adding clarity, structure, and explicit constraints. It follows prompt engineering best practices to produce more reliable outputs.
"""

        return quality_report, diagnosis_report, improved_prompt, explanation

    except Exception as e:
        error_msg = (
            f"❌ **Error**: {str(e)}\n\nPlease check your API key and try again."
        )
        return error_msg, "", "", ""


# Example prompts for demonstration
EXAMPLE_PROMPTS = [
    {
        "original": "Write something about AI",
        "expected": "A detailed technical explanation of artificial intelligence covering machine learning, neural networks, and applications",
        "actual": "AI is cool. It helps computers think.",
    },
    {
        "original": "Create a marketing email",
        "expected": "A professional email with subject line, clear value proposition, call-to-action, and friendly tone for B2B SaaS product",
        "actual": "Hey, buy our product. It's great. Click here.",
    },
    {
        "original": "Analyze the data and give insights but keep it short and detailed with examples",
        "expected": "Concise analysis with 3-4 key insights, each supported by specific data points",
        "actual": "The data shows various trends. Here are some insights: sales increased, customers are happy, market is growing.",
    },
]


def load_example(choice):
    """Load example prompt based on selection"""
    if choice == "Example 1: Vague Instructions":
        example = EXAMPLE_PROMPTS[0]
    elif choice == "Example 2: Missing Context":
        example = EXAMPLE_PROMPTS[1]
    elif choice == "Example 3: Conflicting Instructions":
        example = EXAMPLE_PROMPTS[2]
    else:
        return "", "", ""

    return example["original"], example["expected"], example["actual"]


def create_gradio_interface():
    """
    Create Gradio UI for the diagnosis agent
    """
    with gr.Blocks(title="AI Prompt Failure Diagnosis Agent") as demo:
        gr.Markdown(
            """
        # 🔧 AI Prompt Failure Diagnosis Agent
        
        **Debug and improve your LLM prompts with AI-powered analysis**
        
        This agentic system analyzes why your prompts failed and provides actionable improvements.
        
        ### How it works:
        1. **Analyze** - Rule-based quality checks
        2. **Classify** - Identify failure categories
        3. **Diagnose** - Deep root cause analysis
        4. **Improve** - Generate better prompts with explanations
        """
        )

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 🔑 API Configuration")
                groq_key_input = gr.Textbox(
                    label="Groq API Key",
                    placeholder="Enter your Groq API key (gsk_...)",
                    type="password",
                    value=GROQ_API_KEY,
                )
                gr.Markdown("[Get your free Groq API key](https://console.groq.com/)")

        gr.Markdown("---")

        with gr.Row():
            with gr.Column():
                gr.Markdown("### 📝 Input: Failed Prompt Information")

                example_dropdown = gr.Dropdown(
                    choices=[
                        "Select an example...",
                        "Example 1: Vague Instructions",
                        "Example 2: Missing Context",
                        "Example 3: Conflicting Instructions",
                    ],
                    label="Load Example",
                    value="Select an example...",
                )

                original_prompt_input = gr.Textbox(
                    label="Original Prompt (that failed)",
                    placeholder="Enter the prompt that didn't work as expected...",
                    lines=5,
                )

                expected_output_input = gr.Textbox(
                    label="Expected Output",
                    placeholder="Describe what you wanted the LLM to produce...",
                    lines=4,
                )

                actual_output_input = gr.Textbox(
                    label="Actual Output (what you got)",
                    placeholder="Paste the unsatisfactory output you received...",
                    lines=4,
                )

                diagnose_btn = gr.Button(
                    "🔍 Diagnose & Improve Prompt", variant="primary", size="lg"
                )

        gr.Markdown("---")
        gr.Markdown("### 📊 Diagnosis Results")

        with gr.Row():
            with gr.Column():
                quality_output = gr.Markdown(label="Quality Analysis")
            with gr.Column():
                diagnosis_output = gr.Markdown(label="Failure Diagnosis")

        with gr.Row():
            with gr.Column():
                improved_prompt_output = gr.Textbox(label="✨ Improved Prompt", lines=8)
            with gr.Column():
                explanation_output = gr.Markdown(label="Improvement Explanation")

        # Event handlers
        example_dropdown.change(
            fn=load_example,
            inputs=[example_dropdown],
            outputs=[original_prompt_input, expected_output_input, actual_output_input],
        )

        diagnose_btn.click(
            fn=diagnose_prompt,
            inputs=[
                original_prompt_input,
                expected_output_input,
                actual_output_input,
                groq_key_input,
            ],
            outputs=[
                quality_output,
                diagnosis_output,
                improved_prompt_output,
                explanation_output,
            ],
        )

        gr.Markdown(
            """
        ---
        ### 🎯 Failure Categories Detected
        
        The agent can identify these common prompt failures:
        
        | Category | Description |
        |----------|-------------|
        | **Ambiguity** | Unclear or vague instructions |
        | **Missing Constraints** | Lacks necessary boundaries or rules |
        | **Missing Examples** | No examples to guide the model |
        | **Overloaded Instructions** | Too many conflicting objectives |
        | **Poor Role Definition** | Unclear context or persona |
        | **Formatting Issues** | Output structure not specified |
        | **Context Loss** | Missing background information |
        | **Conflicting Objectives** | Contradictory instructions |
        
        ### 💡 Tips for Better Prompts
        
        - **Be Specific**: Clear instructions get clear results
        - **Add Examples**: Show the model what you want
        - **Define Constraints**: Set boundaries and rules
        - **Specify Format**: Tell the model how to structure output
        - **Provide Context**: Give relevant background information
        - **One Goal at a Time**: Avoid conflicting objectives
        
        ### 🛠️ Built With
        - **LangGraph** - Agentic workflow orchestration
        - **Groq + LLaMA 3.3 70B** - Fast, intelligent analysis
        - **Gradio** - Interactive UI
        """
        )

    return demo


# MAIN EXECUTION


if __name__ == "__main__":
    demo = create_gradio_interface()
    demo.launch()
