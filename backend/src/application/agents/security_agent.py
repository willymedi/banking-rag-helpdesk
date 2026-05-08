from src.application.agents.base import BaseAgent


class SecurityAgent(BaseAgent):
    name = "SecurityAgent"
    domain = "security"
    persona = (
        "Especialista en seguridad de aplicaciones, lineamientos de protección "
        "de APIs, manejo de datos sensibles, controles de cumplimiento y "
        "privacidad. Responde sobre qué controles aplican, qué evitar en logs, "
        "y cómo cumplir lineamientos internos del banco."
    )
