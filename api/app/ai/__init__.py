"""The AI features: plan review and drafting a plan from a brain dump.

- `schemas`: the agents' typed outputs (Pydantic models used as `output_type`)
- `agents`: the Pydantic AI agents, their instructions and the look-back tool
- `provider`: builds the Gemini model from settings (the key stays server-side)
- `service`: runs an agent for a request: throttling, timeout, failure mapping,
  usage logging, and turning the model's output into data the app acts on
"""
