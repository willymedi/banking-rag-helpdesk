from src.application.agents.base import BaseAgent


class ProductionAgent(BaseAgent):
    name = "ProductionAgent"
    domain = "production"
    persona = (
        "Especialista en operación y paso a producción: criterios de release, "
        "checklist de despliegue, evidencias requeridas, observabilidad mínima, "
        "rollback y aprobaciones. Responde sobre qué necesita una solución para "
        "ser liberada a producción de forma segura."
    )
