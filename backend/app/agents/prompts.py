"""Centralised prompt strings.

Keeping them here makes it easy to iterate without grepping through node code.
Each prompt has a single clear contract documented above it.
"""

# Canonical refusal — surface this verbatim from the frontend so it stays
# recognisable as the "no info" path.
REFUSAL_MESSAGE = (
    "No tengo suficiente información en mi base de conocimiento para responder esa pregunta. "
    "Si tienes documentos relacionados, súbelos y vuelve a intentarlo."
)


# Document grading prompt.
# Contract: returns either the literal "yes" or the literal "no".
# Tone is intentionally inclusive: false negatives (dropping a useful chunk)
# hurt more than false positives — the grounding check downstream is the
# real safety net.
GRADE_DOC_PROMPT = """Evalúa si el siguiente fragmento de documento podría ser ÚTIL
para responder la pregunta del usuario. Sé generoso: si el fragmento toca el tema
de la pregunta aunque sea parcialmente, responde "yes".

Pregunta:
{question}

Fragmento:
{document}

Responde únicamente con la palabra "yes" o la palabra "no", sin explicación."""


# Answer generation prompt.
# Contract: produce a concise answer grounded strictly in the provided context.
# If the context is insufficient, the model must output the REFUSAL_MESSAGE verbatim.
ANSWER_PROMPT = """Eres un asistente experto en Historia de Colombia.

Responde la pregunta del usuario USANDO ÚNICAMENTE la información del contexto.
Reglas estrictas:
1. Si el contexto NO contiene la información necesaria, responde EXACTAMENTE:
   "{refusal}"
2. No inventes nombres, fechas, eventos ni cifras.
3. Si citas un dato, asegúrate de que aparezca textualmente en el contexto.
4. Responde en español, en tono claro y conciso (máximo 5 oraciones).

Contexto:
{context}

Pregunta:
{question}

Respuesta:"""


# Grounding verification prompt.
# Contract: returns "yes" or "no".
# Tolerates reformulation and paraphrasing (Llama 3.1 8B can be overly strict
# when the answer doesn't repeat the context verbatim).
GROUNDING_PROMPT = """Verifica si la respuesta del asistente es CONSISTENTE con el
contexto provisto. Tolera reformulaciones, paráfrasis y resúmenes — lo importante es
que la respuesta no contradiga el contexto ni introduzca hechos completamente ausentes
de él.

Contexto:
{context}

Respuesta:
{answer}

Responde únicamente "yes" si la respuesta es consistente con el contexto, o "no" si
contradice o inventa información. Sin explicación."""
