import os

# Base URL of the Orchestrator / Analyzer service
ORCHESTRATOR_URL: str = os.getenv("ORCHESTRATOR_URL", "http://localhost:9000")

# When True, /collect/flush will NOT perform any outbound HTTP calls and will
# instead return the payload that would have been sent.
SIMULATION_MODE: bool = os.getenv("SIMULATION_MODE", "true").lower() in {"1", "true", "yes"}

# Maximum number of events that will be kept in memory at any time.
BUFFER_MAX_EVENTS: int = int(os.getenv("COLLECTOR_BUFFER_MAX_EVENTS", "2000"))
