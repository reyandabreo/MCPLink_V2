"""Document tools: parse, summarize and edit Word documents via LLM."""
import json
import re
from typing import Optional, List
from pydantic import BaseModel, Field
from app.tools.registry import tool_registry
from app.sandbox.limits import resolve_sandbox_path
from app.config import settings
from app.tools._llm_helper import call_llm


def _ok(message: str, data: dict = None, files_modified: list = None) -> str:
    return json.dumps({
        "status": "success",
        "message": message,
        "data": data or {},
        "files_modified": files_modified or [],
    })

 
def _err(message: str) -> str:
    return json.dumps({"status": "error", "message": message})


def _strip_markdown(text: str) -> str:
    """Remove markdown formatting markers, returning clean plain prose."""
    # Remove heading markers: # Heading → Heading
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove bold/italic: **text** / *text* / __text__ / _text_
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'_{1,2}(.*?)_{1,2}', r'\1', text, flags=re.DOTALL)
    # Remove inline code backticks
    text = re.sub(r'`([^`]*)`', r'\1', text)
    # Remove bullet / numbered list markers
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    # Remove horizontal rules
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    # Collapse 3+ blank lines → one blank line
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _require_docx():
    try:
        from docx import Document
        return Document
    except ImportError:
        return None


# ── parse_docx ────────────────────────────────────────────────────────────────

class ParseDocxArgs(BaseModel):
    file_path: str = Field(..., description="Relative path to the .docx file inside the sandbox")


@tool_registry.register(
    "parse_docx",
    "Extract text content from a Word (.docx) document inside the sandbox.",
    ParseDocxArgs,
)
def parse_docx(args: ParseDocxArgs) -> str:
    path = resolve_sandbox_path(args.file_path)
    if not path.exists():
        return _err(f"File not found: {args.file_path}")
    if path.suffix.lower() != ".docx":
        return _err(f"Not a .docx file: {args.file_path}")

    Document = _require_docx()
    if not Document:
        return _err("python-docx is not installed. Run: pip install python-docx")

    try:
        doc = Document(str(path))
    except Exception as e:
        return _err(f"Failed to open document: {e}")

    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    full_text = "\n".join(paragraphs)

    return _ok(
        f"Parsed {len(paragraphs)} paragraphs from {args.file_path}.",
        data={
            "text": full_text,
            "paragraph_count": len(paragraphs),
            "char_count": len(full_text),
        },
    )


# ── summarize_document ────────────────────────────────────────────────────────

class SummarizeDocumentArgs(BaseModel):
    file_path: str = Field(..., description="Relative path to the document inside the sandbox (.txt, .py, .docx)")
    max_length: Optional[int] = Field(None, description="Approximate target word count for the summary (default: 150)")


@tool_registry.register(
    "summarize_document",
    "Summarize the contents of a document using the configured LLM.",
    SummarizeDocumentArgs,
)
def summarize_document(args: SummarizeDocumentArgs) -> str:
    path = resolve_sandbox_path(args.file_path)
    if not path.exists():
        return _err(f"File not found: {args.file_path}")

    ext = path.suffix.lower()

    if ext == ".docx":
        Document = _require_docx()
        if not Document:
            return _err("python-docx is not installed. Run: pip install python-docx")
        try:
            doc = Document(str(path))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as e:
            return _err(f"Could not read .docx: {e}")
    else:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return _err(f"Could not read file: {e}")

    if not text.strip():
        return _err("Document is empty.")

    target_words = args.max_length or 150
    truncated = text[:12_000]
    truncation_note = " (input was truncated for length)" if len(text) > 12_000 else ""

    try:
        llm_prompt = (
            f"Summarize the following document in approximately {target_words} words.\n"
            "Be concise and factual. Return only the summary text.\n\n"
            f"{truncated}"
        )
        summary = call_llm(llm_prompt)
    except Exception as e:
        return _err(f"LLM summarization failed: {e}")

    return _ok(
        f"Summarized {args.file_path}{truncation_note}.",
        data={"summary": summary, "source_chars": len(text)},
    )


# ── edit_docx_sections ────────────────────────────────────────────────────────

class EditDocxSectionsArgs(BaseModel):
    file_path: str = Field(
        ...,
        description=(
            "Relative path to the .docx file inside the sandbox to edit IN PLACE."
        ),
    )
    user_prompt: str = Field(
        ...,
        description=(
            "The user's full instruction describing what to edit. "
            "Example: 'Edit NLP_Exp_6.docx and fill the Implementation "
            "(answer sub-questions too), Conclusion, and Reference (3 IEEE) "
            "sections based on Aim, Objective and Theory.' "
            "The tool auto-extracts context from the document and parses this "
            "prompt to determine which sections to fill."
        ),
    )


@tool_registry.register(
    "edit_docx_sections",
    (
        "Edit a .docx Word document IN PLACE. "
        "Reads Aim / Objective / Theory from the document as context, "
        "parses the user_prompt to identify which sections to fill "
        "(Implementation, Conclusion, Reference, etc.), detects sub-questions "
        "inside those sections, generates content with AI, and inserts it into "
        "the correct locations. Saves back to the same file. "
        "Use this whenever the user wants to fill or update sections of a Word document."
    ),
    EditDocxSectionsArgs,
)
def edit_docx_sections(args: EditDocxSectionsArgs) -> str:
    # ── Step 1: Validate file ─────────────────────────────────────────────────
    path = resolve_sandbox_path(args.file_path)
    if not path.exists():
        return _err(f"File not found: {args.file_path}")
    if path.suffix.lower() != ".docx":
        return _err(f"Not a .docx file: {args.file_path}")

    Document = _require_docx()
    if not Document:
        return _err("python-docx is not installed. Run: pip install python-docx")

    try:
        doc = Document(str(path))
    except Exception as e:
        return _err(f"Failed to open document: {e}")

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _is_heading(para) -> bool:
        return para.style.name.startswith("Heading") if para.style else False

    def _heading_level(para) -> int:
        try:
            return int(para.style.name.split()[-1])
        except Exception:
            return 99

    def _norm(text: str) -> str:
        return re.sub(r"[^a-z ]", "", text.strip().lower()).strip()

    def _best_style() -> str:
        available = {s.name for s in doc.styles}
        for c in ("Body Text", "Normal"):
            if c in available:
                return c
        return "Normal"

    def _insert_after(anchor, lines: list[str]) -> None:
        """Insert paragraphs with the body style immediately after *anchor*."""
        style = _best_style()
        for text in reversed(lines):
            tmp = doc.add_paragraph(text, style=style)
            anchor._element.addnext(tmp._element)

    def _add_heading_safe(text: str, level: int = 1):
        try:
            return doc.add_heading(text, level=level)
        except Exception:
            p = doc.add_paragraph()
            p.add_run(text).bold = True
            return p

    # ── Step 2: Parse document into section map ───────────────────────────────
    KNOWN_SECTIONS = [
        "aim", "objective", "theory", "implementation",
        "conclusion", "reference", "result", "discussion",
    ]

    # section_map: norm_key → list of (text, para_object)
    section_map: dict[str, list[tuple[str, object]]] = {}
    current_section: str | None = None
    all_paras = list(doc.paragraphs)   # snapshot — never mutated

    for para in all_paras:
        text = para.text.strip()
        if not text:
            continue
        nk = _norm(text)
        is_sec = _is_heading(para) or any(
            nk == kw or nk.startswith(kw + " ") or kw in nk
            for kw in KNOWN_SECTIONS
        )
        if is_sec:
            matched = next(
                (kw for kw in KNOWN_SECTIONS if nk == kw or nk.startswith(kw) or kw in nk),
                None,
            )
            if matched:
                current_section = matched
                section_map.setdefault(current_section, [])
                continue
        if current_section:
            section_map.setdefault(current_section, []).append((text, para))

    # ── Step 3: Build context = Aim + Objective + Theory ─────────────────────
    def _txt(key: str) -> str:
        return " ".join(t for t, _ in section_map.get(key, []))

    context = "\n\n".join(filter(None, [
        f"Aim:\n{_txt('aim')}"        if section_map.get("aim")        else "",
        f"Objective:\n{_txt('objective')}" if section_map.get("objective") else "",
        f"Theory:\n{_txt('theory')}"  if section_map.get("theory")     else "",
    ])) or "No context sections found in document."

    # ── Step 4: Parse user prompt for target sections ─────────────────────────
    prompt_lower = args.user_prompt.lower()
    SECTION_KW = {
        "implementation": "Implementation",
        "conclusion":     "Conclusion",
        "reference":      "Reference",
        "bibliography":   "Reference",
        "result":         "Result",
        "discussion":     "Discussion",
    }
    requested_keys:  list[str]       = []
    requested_names: dict[str, str]  = {}
    for kw, display in SECTION_KW.items():
        if kw in prompt_lower:
            # Always store under canonical key (bibliography → reference)
            canonical = display.lower()
            if canonical not in requested_keys:
                requested_keys.append(canonical)
                requested_names[canonical] = display

    if not requested_keys:            # fallback
        for kw in KNOWN_SECTIONS:
            if kw not in ("aim", "objective", "theory") and kw in section_map:
                requested_keys.append(kw)
                requested_names[kw] = kw.capitalize()

    ref_count = 3
    m = re.search(r"(\d+)\s*(?:ieee\s*)?reference", prompt_lower)
    if m:
        ref_count = int(m.group(1))

    # ── Step 3 (spec): Detect implementation tasks ────────────────────────────
    # Patterns: a.  b.  c. / a) b) / i. ii. / 1. 2. / Q1. Q2.
    TASK_RE = re.compile(
        r"^(?:[a-zA-Z]\.|[a-zA-Z]\)|[ivxlcIVXLC]+\.|[ivxlcIVXLC]+\)|[0-9]+\.|[0-9]+\))[\s\S]",
    )
    CODE_KW_RE = re.compile(
        r"\b(write|implement|code|program|algorithm|script|function|class|method)\b",
        re.IGNORECASE,
    )

    def _is_task_line(text: str) -> bool:
        return bool(TASK_RE.match(text.strip()))

    def _needs_code(text: str) -> bool:
        return bool(CODE_KW_RE.search(text))

    # Collect (text, para_object) for tasks inside implementation
    impl_tasks: list[tuple[str, object]] = [
        (t, p)
        for t, p in section_map.get("implementation", [])
        if _is_task_line(t)
    ]

    # ── Step 5: Per-task generation for Implementation ────────────────────────
    # Each task gets its own LLM call → { code?, explanation }
    task_answers: dict[str, str] = {}   # task_text → generated answer block

    if "implementation" in requested_keys and impl_tasks:
        for task_text, _para in impl_tasks:
            wants_code = _needs_code(task_text) or _needs_code(args.user_prompt)
            if wants_code:
                task_prompt = (
                    f"You are writing an implementation section for an academic lab report.\n\n"
                    f"Context:\n{context}\n\n"
                    f"Task: {task_text}\n\n"
                    "Provide:\n"
                    "1. A short Python code snippet relevant to this task (4-12 lines).\n"
                    "2. A brief explanation (2-4 sentences) of what the code does.\n\n"
                    "Format your response EXACTLY as:\n"
                    "Code:\n<python code here>\n\nExplanation:\n<explanation here>\n\n"
                    "Rules:\n"
                    "- No markdown, no backticks, no asterisks.\n"
                    "- Code must be valid Python.\n"
                    "- Explanation must be plain prose."
                )
            else:
                task_prompt = (
                    f"You are writing an implementation section for an academic lab report.\n\n"
                    f"Context:\n{context}\n\n"
                    f"Task: {task_text}\n\n"
                    "Write a concise, technical answer (2-4 sentences) for this task.\n"
                    "Plain prose only — no markdown, no asterisks, no backticks."
                )
            try:
                raw = call_llm(task_prompt)
                task_answers[task_text] = _strip_markdown(raw)
            except Exception as e:
                task_answers[task_text] = f"[Generation failed: {e}]"

    # For the remaining implementation body (non-task lines) or if no tasks detected
    impl_general: str = ""
    if "implementation" in requested_keys and not impl_tasks:
        gen_prompt = (
            f"You are writing the Implementation section of an academic lab report.\n\n"
            f"Context:\n{context}\n\n"
            "Write a detailed implementation walkthrough with Python code examples.\n"
            "Structure: short intro → code snippet → explanation, repeated as needed.\n"
            "Format: 'Code:\\n<code>\\n\\nExplanation:\\n<text>' blocks.\n"
            "Plain text only — no markdown, no asterisks, no backticks."
        )
        try:
            impl_general = _strip_markdown(call_llm(gen_prompt))
        except Exception as e:
            impl_general = f"[Generation failed: {e}]"

    # ── Step 6: Generate Conclusion ───────────────────────────────────────────
    conclusion_text: str = ""
    if "conclusion" in requested_keys:
        conc_prompt = (
            f"Write a conclusion (120-200 words) for an experiment described below.\n\n"
            f"{context}\n\n"
            "Summarise what was demonstrated, what was learned, and its practical significance.\n"
            "Plain prose only. Do not repeat the heading. No markdown."
        )
        try:
            conclusion_text = _strip_markdown(call_llm(conc_prompt))
        except Exception as e:
            conclusion_text = f"[Generation failed: {e}]"

    # ── Step 6 (spec): Separate IEEE reference generation ─────────────────────
    reference_text: str = ""
    if "reference" in requested_keys:
        ref_prompt = (
            f"Generate exactly {ref_count} IEEE-format references for the following topic.\n\n"
            f"Topic context:\n{context}\n\n"
            f"Rules:\n"
            f"- Number each as [1], [2], ... [{ref_count}].\n"
            f"- Use real, credible sources directly relevant to the topic.\n"
            f"- One reference per line. No blank lines between them.\n"
            f"- Strict IEEE format: Author(s), 'Title,' Journal/Conference, vol., no., pp., year.\n"
            f"- No markdown, no asterisks.\n"
            f"Return ONLY the numbered reference list."
        )
        try:
            raw_refs = call_llm(ref_prompt)
            # Re-number to guarantee correct sequence
            lines = [l.strip() for l in raw_refs.split("\n") if l.strip()]
            renumbered, counter = [], 1
            for line in lines:
                line = re.sub(r"^\[?\d+\]?\.?\s*", f"[{counter}] ", line)
                renumbered.append(line)
                counter += 1
            reference_text = "\n".join(renumbered[:ref_count])
        except Exception as e:
            reference_text = f"[Generation failed: {e}]"

    # ── Step 7: Best-heading pre-selection pass ───────────────────────────────
    def _match_score(dk: str, tk: str) -> int:
        if dk == tk:             return 3
        if dk.startswith(tk) or tk.startswith(dk): return 2
        if tk in dk or dk in tk: return 1
        return 0

    # Also add aliases so "references" / "bibliography" heading → "reference" key
    HEADING_ALIASES = {
        "references": "reference",
        "bibliography": "reference",
        "bibliographies": "reference",
    }

    winner_para: dict[str, tuple[int, int, object]] = {}
    for i, para in enumerate(all_paras):
        if not para.text.strip():
            continue
        dk = _norm(para.text)
        resolved_dk = HEADING_ALIASES.get(dk, dk)  # normalise plurals/aliases
        for key in requested_keys:
            # match against both raw heading text and resolved alias
            score = max(_match_score(dk, key), _match_score(resolved_dk, key))
            if score == 0:
                continue
            prev = winner_para.get(key)
            if prev is None or score > prev[0]:
                winner_para[key] = (score, i, para)

    # ── Step 8: Insert per-task answers directly under each task paragraph ────
    sections_filled: list[str] = []
    sections_not_found: list[str] = []

    if "implementation" in requested_keys:
        if impl_tasks:
            for task_text, task_para in impl_tasks:
                answer = task_answers.get(task_text, "")
                if answer:
                    lines = [l.strip() for l in answer.split("\n") if l.strip()]
                    _insert_after(task_para, lines)
            sections_filled.append("Implementation")
        elif impl_general:
            # No detected tasks — insert block after section heading
            if "implementation" in winner_para:
                _, _, anchor = winner_para["implementation"]
                lines = [l.strip() for l in impl_general.split("\n\n") if l.strip()]
                if len(lines) == 1:
                    lines = [l.strip() for l in impl_general.split("\n") if l.strip()]
                _insert_after(anchor, lines)
                sections_filled.append("Implementation")
            else:
                _add_heading_safe("Implementation")
                for pt in impl_general.split("\n\n"):
                    if pt.strip():
                        doc.add_paragraph(pt.strip(), style=_best_style())
                sections_filled.append("Implementation (appended at end)")

    # ── Step 8 (Conclusion): Insert after heading ─────────────────────────────
    if "conclusion" in requested_keys and conclusion_text:
        lines = [l.strip() for l in conclusion_text.split("\n\n") if l.strip()]
        if len(lines) == 1:
            lines = [l.strip() for l in conclusion_text.split("\n") if l.strip()]
        if "conclusion" in winner_para:
            _, _, anchor = winner_para["conclusion"]
            _insert_after(anchor, lines)
            sections_filled.append("Conclusion")
        else:
            _add_heading_safe("Conclusion")
            for pt in lines:
                doc.add_paragraph(pt, style=_best_style())
            sections_filled.append("Conclusion (appended at end)")

    # ── Step 9: Insert References ─────────────────────────────────────────────
    if "reference" in requested_keys and reference_text:
        ref_lines = [l.strip() for l in reference_text.split("\n") if l.strip()]
        if "reference" in winner_para:
            _, _, anchor = winner_para["reference"]
            _insert_after(anchor, ref_lines)
            sections_filled.append("Reference")
        else:
            _add_heading_safe("References")
            for rl in ref_lines:
                doc.add_paragraph(rl, style=_best_style())
            sections_filled.append("Reference (appended at end)")

    # Other requested sections (result, discussion, etc.)
    for key in requested_keys:
        if key in ("implementation", "conclusion", "reference"):
            continue
        name = requested_names[key]
        if any(name in s for s in sections_filled):
            continue
        try:
            gen = _strip_markdown(call_llm(
                f"Write content for the '{name}' section of this academic report.\n\n"
                f"Context:\n{context}\n\nPlain prose, no markdown."
            ))
        except Exception as e:
            gen = f"[Generation failed: {e}]"
        lines = [l.strip() for l in gen.split("\n\n") if l.strip()]
        if key in winner_para:
            _, _, anchor = winner_para[key]
            _insert_after(anchor, lines)
            sections_filled.append(name)
        else:
            _add_heading_safe(name)
            for pt in lines:
                doc.add_paragraph(pt, style=_best_style())
            sections_filled.append(f"{name} (appended at end)")

    # ── Step 10: Save ─────────────────────────────────────────────────────────
    try:
        doc.save(str(path))
    except Exception as e:
        return _err(f"Failed to save document: {e}")

    msg_parts = []
    if sections_filled:
        msg_parts.append(f"Filled sections: {', '.join(sections_filled)}.")
    if sections_not_found:
        msg_parts.append(f"Not found (appended): {', '.join(sections_not_found)}.")

    return _ok(
        " ".join(msg_parts) or "Document updated.",
        data={
            "sections_filled":    sections_filled,
            "sections_not_found": sections_not_found,
            "tasks_answered":     list(task_answers.keys()),
            "context_used":       list(section_map.keys()),
        },
        files_modified=[args.file_path],
    )
