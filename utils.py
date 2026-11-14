import io
import json
import os
from datetime import datetime
from typing import List, Optional, Union
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import ClientError
from pydantic import BaseModel, Field
from pypdf import PdfReader
from pypdf.errors import PdfReadError
import streamlit as st

load_dotenv()

STUDY_KIT_CHAR_LIMIT = 40000
GEMINI_TIMEOUT_MS = 45000

CANDIDATE_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash",
]



def _get_api_key() -> str:
    """Returns GEMINI_API_KEY from environment (.env) or Streamlit secrets."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if key and key != "your_api_key_here":
        return key

    try:
        secret_key = st.secrets.get("GEMINI_API_KEY", "").strip()
        if secret_key and secret_key != "your_api_key_here":
            return secret_key
    except Exception:
        pass

    return ""


class Flashcard(BaseModel):
    question: str = Field(description="The question or prompt for the flashcard.")
    answer: str = Field(description="The concise, accurate answer to the question.")


class QuizQuestion(BaseModel):
    question: str = Field(description="The multiple-choice question.")
    options: List[str] = Field(description="A list of exactly 4 plausible option strings.")
    correct_answer: str = Field(
        description="The exact text of the correct option (must match one of the items in options)."
    )
    explanation: str = Field(
        description="A clear and concise explanation of why the correct answer is right."
    )


class StudyKit(BaseModel):
    summary: List[str] = Field(
        description="A 5-bullet summary list capturing the most important concepts."
    )
    flashcards: List[Flashcard] = Field(
        description="A list of exactly 6 flashcards covering core terms and ideas."
    )
    quiz: List[QuizQuestion] = Field(
        description="A list of exactly 5 multiple-choice questions with 4 options each."
    )


class PreparedTextResult:
    def __init__(
        self,
        text: str,
        was_truncated: bool,
        total_pages: int = 0,
        total_chars: int = 0,
        file_count: int = 0,
    ):
        self.text = text
        self.was_truncated = was_truncated
        self.total_pages = total_pages
        self.total_chars = total_chars
        self.file_count = file_count

    def __iter__(self):
        return iter((self.text, self.was_truncated))

    def __getitem__(self, index):
        return (self.text, self.was_truncated)[index]

    def __len__(self):
        return 2


def extract_text_from_pdf(uploaded_file: Union[io.BytesIO, bytes, str, object]) -> str:
    if uploaded_file is None:
        raise ValueError("No file provided.")

    try:
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)

        reader = PdfReader(uploaded_file)
        if len(reader.pages) == 0:
            raise ValueError("The uploaded PDF has no pages.")

        extracted_pages = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text and page_text.strip():
                extracted_pages.append(page_text.strip())

        full_text = "\n\n".join(extracted_pages).strip()
        if not full_text:
            raise ValueError(
                "No readable text could be extracted from the PDF. "
                "The document may be empty, image-only (scanned), or encrypted."
            )
        return full_text

    except PdfReadError as e:
        raise ValueError(f"Failed to parse PDF document: {e}")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"An unexpected error occurred while reading the PDF: {e}")


def _evenly_sample_text(text: str, max_chars: int = STUDY_KIT_CHAR_LIMIT) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= max_chars:
        return cleaned

    slice_count = 8
    separator = "\n\n... [section omitted for faster generation] ...\n\n"
    body_budget = max(slice_count, max_chars - len(separator) * (slice_count - 1))
    slice_len = max(1, body_budget // slice_count)
    step = len(cleaned) / slice_count

    parts = []
    for index in range(slice_count):
        start = int(index * step)
        parts.append(cleaned[start:start + slice_len].strip())

    sampled = separator.join(part for part in parts if part)
    return sampled[:max_chars].rstrip() if len(sampled) > max_chars else sampled


def _make_gemini_client(api_key: str) -> genai.Client:
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS),
    )


def _content_config(model_name: str, **kwargs) -> types.GenerateContentConfig:
    try:
        return types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            **kwargs,
        )
    except Exception:
        return types.GenerateContentConfig(**kwargs)

def extract_and_prepare_text(
    uploaded_files: List[Union[io.BytesIO, object]],
    max_chars: int = 120000,
) -> PreparedTextResult:
    if not uploaded_files:
        raise ValueError("No PDF files provided.")

    doc_entries = []
    total_pages = 0

    for f in uploaded_files:
        file_name = getattr(f, "name", "Document.pdf")
        try:
            if hasattr(f, "seek"):
                f.seek(0)
            reader = PdfReader(f)
            num_pages = len(reader.pages)
            total_pages += num_pages

            pages_text = []
            for page in reader.pages:
                pt = page.extract_text()
                if pt and pt.strip():
                    pages_text.append(pt.strip())

            file_text = "\n\n".join(pages_text).strip()
            if file_text:
                doc_entries.append({
                    "name": file_name,
                    "text": file_text,
                    "pages": num_pages,
                    "length": len(file_text),
                })
        except Exception as e:
            doc_entries.append({
                "name": file_name,
                "text": f"[Error reading document: {e}]",
                "pages": 0,
                "length": 0,
            })

    valid_entries = [d for d in doc_entries if d["length"] > 0]
    if not valid_entries:
        raise ValueError(
            "None of the uploaded PDF files contained readable text. "
            "Please check that the PDFs are not scanned images or encrypted."
        )

    raw_total_chars = sum(d["length"] for d in valid_entries)
    headers_overhead = sum(len(f"\n--- Document: {d['name']} ---\n\n") for d in valid_entries)
    available_body_budget = max(100, max_chars - headers_overhead)
    was_truncated = raw_total_chars > available_body_budget

    prepared_parts = []
    for d in valid_entries:
        doc_header = f"\n--- Document: {d['name']} ---\n"
        if not was_truncated:
            prepared_parts.append(f"{doc_header}\n{d['text']}")
        else:
            ratio = d["length"] / raw_total_chars
            doc_budget = max(50, int(available_body_budget * ratio))
            if d["length"] > doc_budget:
                half = max(20, (doc_budget - 40) // 2)
                sampled_text = (
                    d["text"][:half].rstrip()
                    + "\n\n... [content condensed for token safety] ...\n\n"
                    + d["text"][-half:].lstrip()
                )
            else:
                sampled_text = d["text"]
            prepared_parts.append(f"{doc_header}\n{sampled_text}")

    combined_text = "\n".join(prepared_parts).strip()

    return PreparedTextResult(
        text=combined_text,
        was_truncated=was_truncated,
        total_pages=total_pages,
        total_chars=raw_total_chars,
        file_count=len(uploaded_files),
    )


def generate_study_materials(text: str) -> StudyKit:
    load_dotenv(override=True)
    api_key = _get_api_key()

    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing. Set it in .env or Streamlit secrets.")
    if not text or not text.strip():
        raise ValueError("Cannot generate study materials from empty text.")

    text = _evenly_sample_text(text, STUDY_KIT_CHAR_LIMIT)
    client = _make_gemini_client(api_key)

    prompt = (
        "You are an expert educator and study assistant. Carefully read the following study material "
        "and generate a high-quality study kit according to the structured schema:\n"
        "1. Exactly 5 concise, impactful bullet points summarizing the key ideas.\n"
        "2. Exactly 6 flashcards with clear questions and concise answers for effective revision.\n"
        "3. Exactly 5 multiple-choice questions, each with exactly 4 options, the correct answer, "
        "and a clear explanation.\n\n"
        f"--- Document Content ---\n{text}\n--- End of Document Content ---"
    )

    config_kwargs = dict(
        response_mime_type="application/json",
        response_schema=StudyKit,
        temperature=0.3,
    )

    last_error = None
    for model_name in CANDIDATE_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=_content_config(model_name, **config_kwargs),
            )
            if response.parsed:
                return response.parsed
            if response.text:
                return StudyKit.model_validate(json.loads(response.text))

        except ClientError as e:
            err_msg = str(e).lower()
            last_error = e
            if "401" in err_msg or "403" in err_msg or "api_key" in err_msg:
                raise ValueError("Invalid Gemini API key. Verify GEMINI_API_KEY in .env.")
            if "429" in err_msg or "resource_exhausted" in err_msg or "quota" in err_msg or "404" in err_msg:
                continue
            raise ValueError(f"Gemini API error ({model_name}): {e}")

        except Exception as e:
            last_error = e
            continue

    raise ValueError(f"Gemini could not complete the request right now. Details: {last_error}")
ANSWER_FORMAT_INSTRUCTIONS = {
    "2-Mark Answer (Crisp & Direct)": (
        "Format Requirement - 2-Mark Answer (Crisp & Direct):\n"
        "Provide exactly 2 to 3 concise sentences or bullet points. "
        "Strictly bold all key technical terms, definitions, and concepts (**like this**). "
        "Keep it direct, high-yield, and ideal for quick-scoring university exam questions."
    ),
    "5-Mark Answer (Structured)": (
        "Format Requirement - 5-Mark Answer (Structured):\n"
        "Structure the answer with:\n"
        "1. **Definition / Overview**: A crisp, formal 1-2 sentence definition.\n"
        "2. **Core Aspects / Key Points**: 4 to 5 clear bullet points with bold subheadings.\n"
        "3. **Example / Diagrammatic Explanation**: A short concrete example or text-based diagram illustrating the concept."
    ),
    "10-Mark Answer (Detailed Essay)": (
        "Format Requirement - 10-Mark Answer (Detailed Essay):\n"
        "Write a comprehensive, full-length university exam essay structured under the following clear Markdown headings:\n"
        "### 1. Introduction & Definition\n"
        "### 2. Core Concept & Architectural Mechanism\n"
        "### 3. Key Characteristics & Step-by-Step Working\n"
        "### 4. Advantages, Trade-offs & Real-World Applications\n"
        "### 5. Conclusion & Exam Takeaway"
    ),
    "Simple Explanation (EL5)": (
        "Format Requirement - Simple Explanation (EL5):\n"
        "Explain this concept as if explaining to a 5-year-old or beginner. "
        "Use a vivid, relatable real-world analogy and plain, simple language without intimidating jargon."
    ),
}


def _build_chat_contents(
    chat_history: Optional[List[dict]],
    current_prompt: str,
) -> List[types.Content]:
    raw_turns = []
    if chat_history:
        for msg in chat_history[-8:]:
            role = "model" if msg.get("role") in ("assistant", "model") else "user"
            text = (msg.get("content") or "").strip()
            if text:
                raw_turns.append((role, text))

    raw_turns.append(("user", current_prompt))

    while raw_turns and raw_turns[0][0] != "user":
        raw_turns.pop(0)

    merged_turns = []
    for role, text in raw_turns:
        if merged_turns and merged_turns[-1][0] == role:
            merged_turns[-1] = (role, merged_turns[-1][1] + "\n\n" + text)
        else:
            merged_turns.append((role, text))

    return [
        types.Content(role=role, parts=[types.Part.from_text(text=text)])
        for role, text in merged_turns
    ]


def ask_study_assistant(
    question: str,
    document_text: str,
    answer_format: str = "2-Mark Answer (Crisp & Direct)",
    chat_history: Optional[List[dict]] = None,
) -> str:
    load_dotenv(override=True)
    api_key = _get_api_key()

    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing or invalid.")
    if not question or not question.strip():
        raise ValueError("Please provide a question for the AI Tutor.")
    if not document_text or not document_text.strip():
        raise ValueError("No study document text is available to answer your question.")

    client = _make_gemini_client(api_key)

    system_instruction = (
        "You are an expert university professor and examination tutor assisting a university student.\n"
        "Your task is to answer the student's questions based strictly on the uploaded study notes provided below.\n\n"
        "--- UPLOADED STUDY NOTES ---\n"
        f"{document_text}\n"
        "--- END OF STUDY NOTES ---\n\n"
        "STRICT INSTRUCTIONS:\n"
        "1. Base your answers strictly on the facts and concepts present in the uploaded study notes.\n"
        "2. If the question or topic is NOT covered in the uploaded notes, you MUST start your response with "
        "the exact sentence:\n"
        "\"This topic is not covered in your uploaded documents, but here is the general concept:\"\n"
        "followed by a concise, authoritative explanation of the concept.\n"
        "3. If multiple documents are uploaded (such as lecture notes alongside a question bank or previous exam paper) "
        "and the user asks to solve or answer questions from one of the documents, identify every single question "
        "in that document and answer each one thoroughly using the information from the study notes document. "
        "Format each answer clearly with its question number and strictly follow the selected answer_format (e.g., 2-Mark, 5-Mark, or 10-Mark).\n"
        "4. Adhere strictly to the requested exam answer structure and formatting rules."
    )

    format_detail = ANSWER_FORMAT_INSTRUCTIONS.get(
        answer_format,
        ANSWER_FORMAT_INSTRUCTIONS["2-Mark Answer (Crisp & Direct)"],
    )

    current_prompt = (
        f"Student Question: {question.strip()}\n\n"
        f"Selected Answer Format: {answer_format}\n"
        f"{format_detail}"
    )

    contents = _build_chat_contents(chat_history, current_prompt)
    config_kwargs = dict(system_instruction=system_instruction, temperature=0.3)

    last_error = None
    for model_name in CANDIDATE_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=_content_config(model_name, **config_kwargs),
            )
            if response.text and response.text.strip():
                return response.text.strip()

        except ClientError as e:
            err_msg = str(e).lower()
            last_error = e
            if "401" in err_msg or "403" in err_msg or "api_key" in err_msg:
                raise ValueError("Invalid Gemini API key.")
            if "429" in err_msg or "resource_exhausted" in err_msg or "quota" in err_msg or "404" in err_msg:
                continue
            raise ValueError(f"Gemini API error ({model_name}): {e}")

        except Exception as e:
            last_error = e
            continue

    raise ValueError(f"Unable to generate response from AI Tutor. Details: {last_error}")
class QuizOnly(BaseModel):
    quiz: List[QuizQuestion] = Field(
        description="A list of exactly 5 multiple-choice questions with 4 options each."
    )


DIFFICULTY_INSTRUCTIONS = {
    "Easy": (
        "Difficulty: EASY. Create straightforward recall questions testing basic definitions and core vocabulary."
    ),
    "Medium": (
        "Difficulty: MEDIUM. Create applied understanding questions requiring students to reason about concepts."
    ),
    "Hard": (
        "Difficulty: HARD. Create analytically challenging questions requiring deep understanding and multi-step reasoning."
    ),
}


def generate_quiz_by_difficulty(text: str, difficulty: str = "Medium") -> List[QuizQuestion]:
    api_key = _get_api_key()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing or invalid.")
    if not text or not text.strip():
        raise ValueError("Cannot generate quiz from empty document text.")

    text = _evenly_sample_text(text, STUDY_KIT_CHAR_LIMIT)
    difficulty = difficulty if difficulty in DIFFICULTY_INSTRUCTIONS else "Medium"
    diff_instruction = DIFFICULTY_INSTRUCTIONS[difficulty]

    prompt = (
        "You are an expert university exam setter. Based on the following study material, "
        f"generate exactly 5 fresh multiple-choice questions.\n\n{diff_instruction}\n\n"
        "Rules:\n"
        "- Each question must have exactly 4 options as a list.\n"
        "- The correct_answer field must be the exact text of one of the 4 options.\n"
        "- Provide a clear, concise explanation for each correct answer.\n"
        "- Do NOT repeat questions from previous sessions — generate entirely new questions.\n\n"
        f"--- Study Material ---\n{text}\n--- End of Study Material ---"
    )

    config_kwargs = dict(
        response_mime_type="application/json",
        response_schema=QuizOnly,
        temperature=0.7,
    )

    client = _make_gemini_client(api_key)
    last_error = None

    for model_name in CANDIDATE_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=_content_config(model_name, **config_kwargs),
            )
            if response.parsed and response.parsed.quiz:
                return response.parsed.quiz
            if response.text:
                return QuizOnly.model_validate(json.loads(response.text)).quiz

        except ClientError as e:
            err_msg = str(e).lower()
            last_error = e
            if "401" in err_msg or "403" in err_msg:
                raise ValueError("Invalid Gemini API key.")
            if "429" in err_msg or "resource_exhausted" in err_msg or "quota" in err_msg or "404" in err_msg:
                continue
            raise ValueError(f"Gemini API error ({model_name}): {e}")

        except Exception as e:
            last_error = e
            continue

    raise ValueError(f"Unable to generate quiz. Details: {last_error}")


def generate_markdown_study_kit(title: str, kit: StudyKit) -> str:
    now_str = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    lines = [
        f"# 📚 AI Smart Study Kit: {title}",
        f"*Exported on {now_str}*",
        "", "---", "",
        "## 📌 5-Bullet Key Summary", "",
    ]
    for idx, bullet in enumerate(kit.summary, start=1):
        lines.append(f"{idx}. {bullet}")

    lines.extend(["", "---", "", "## 💡 Study Flashcards (6 Cards)", ""])
    for idx, card in enumerate(kit.flashcards, start=1):
        lines.extend([f"### Card {idx}", f"**Q:** {card.question}", "", f"**A:** {card.answer}", ""])

    lines.extend(["", "---", "", "## 📝 Practice Quiz (5 Questions)", ""])
    for idx, q in enumerate(kit.quiz, start=1):
        lines.append(f"### Question {idx}: {q.question}")
        lines.append("")
        for opt in q.options:
            lines.append(f"- [ ] {opt}")
        lines.extend(["", f"> **Correct Answer:** {q.correct_answer}", f"> **Explanation:** {q.explanation}", ""])

    lines.extend(["---", "*Generated by AI Smart Study & Quiz Generator*"])
    return "\n".join(lines)


def generate_text_study_kit(title: str, kit: StudyKit) -> str:
    now_str = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    divider = "=" * 70
    subdivider = "-" * 70

    lines = [
        divider,
        f"AI SMART STUDY KIT: {title.upper()}",
        f"Exported on: {now_str}",
        divider, "",
        subdivider, "1. 5-BULLET KEY CONCEPT SUMMARY", subdivider,
    ]
    for idx, bullet in enumerate(kit.summary, start=1):
        lines.extend([f"[{idx}] {bullet}", ""])

    lines.extend([subdivider, "2. STUDY FLASHCARDS (6 Cards)", subdivider])
    for idx, card in enumerate(kit.flashcards, start=1):
        lines.extend([f"--- Card {idx} ---", f"Question: {card.question}", f"Answer:   {card.answer}", ""])

    lines.extend([subdivider, "3. PRACTICE QUIZ (5 Multiple-Choice Questions)", subdivider])
    for idx, q in enumerate(kit.quiz, start=1):
        lines.append(f"Question {idx}: {q.question}")
        letters = ["A", "B", "C", "D"]
        for opt_idx, opt in enumerate(q.options):
            label = letters[opt_idx] if opt_idx < len(letters) else str(opt_idx + 1)
            lines.append(f"  [{label}] {opt}")
        lines.extend([f"  >> Correct Answer: {q.correct_answer}", f"  >> Explanation:    {q.explanation}", ""])

    lines.extend([divider, "Generated by AI Smart Study & Quiz Generator", divider])
    return "\n".join(lines)
