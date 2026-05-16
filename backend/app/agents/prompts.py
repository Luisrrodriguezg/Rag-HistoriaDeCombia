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
GRADE_DOC_PROMPT = """Eres un evaluador estricto de relevancia de documentos.

Pregunta del usuario:
{question}

Fragmento de documento:
{document}

¿El fragmento contiene información que ayude DIRECTAMENTE a responder la pregunta?
Responde únicamente con una palabra: "yes" o "no". No agregues nada más."""


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
GROUNDING_PROMPT = """Eres un verificador. Determina si la respuesta del asistente está
respaldada ÚNICAMENTE por la información del contexto provisto.

Contexto:
{context}

Respuesta del asistente:
{answer}

¿Cada afirmación de la respuesta está respaldada por el contexto?
Responde únicamente con "yes" o "no"."""
