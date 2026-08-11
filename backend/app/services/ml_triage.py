import numpy as np
import xgboost as xgb
from pydantic import BaseModel

class IncidentData(BaseModel):
    caller_description: str
    location_lat: float
    location_lng: float
    time_of_day: int
    weather_condition: str

# Dummy initialization for XGBoost model since we don't have the new training pipeline yet
class DummyTriageModel:
    def predict_severity(self, incident: IncidentData) -> str:
        # Placeholder logic: real implementation would use xgb.Booster
        if "fire" in incident.caller_description.lower():
            return "CRITICAL"
        elif "accident" in incident.caller_description.lower():
            return "HIGH"
        return "MEDIUM"

triage_model = DummyTriageModel()

def get_incident_triage(incident: IncidentData) -> str:
    """Returns the severity of an incident using ML model."""
    return triage_model.predict_severity(incident)
