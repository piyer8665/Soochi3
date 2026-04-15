# prompt_builder.py
# All prompts versioned in one place.
# Import from here — never define prompts inline in other modules.

PROMPT_VERSION = "2.0.0"


def get_scout_system_prompt() -> str:
    from reasoning.scout import SCOUT_SYSTEM_PROMPT
    return SCOUT_SYSTEM_PROMPT


def get_interpreter_system_prompt() -> str:
    from reasoning.interpreter import INTERPRETER_SYSTEM_PROMPT
    return INTERPRETER_SYSTEM_PROMPT


def get_writer_system_prompt() -> str:
    from reasoning.writer import WRITER_SYSTEM_PROMPT
    return WRITER_SYSTEM_PROMPT


def get_chat_system_prompt(compressed_dictionary: str) -> str:
    return f"""You are Soochi, an expert statistical analysis assistant.

You have already generated the following data dictionary for this dataset:

{compressed_dictionary}

Answer questions accurately and concisely based on the dictionary and your statistical expertise.
If asked about something not covered in the dictionary, say so clearly.
Never invent variable names, codes, or definitions not present in the dictionary."""


def get_chat_summary_prompt(chat_history: list) -> str:
    history_text = "\n".join([
        f"{msg['role'].upper()}: {msg['content']}"
        for msg in chat_history
    ])
    return f"""Summarize the following conversation about a statistical dataset.
Keep all important findings, answers, and decisions. Be concise.

{history_text}

Return a compressed summary that preserves all key information."""