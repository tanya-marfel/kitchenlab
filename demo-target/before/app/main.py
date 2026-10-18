"""Small internal assistant used as the BreachMirror demo target."""

from transformers import AutoModel


def load_customer_model():
    # The hub revision is resolved when this process starts.
    model = AutoModel.from_pretrained("example-org/customer-model")
    return model


TOOLS = [
    {
        "name": "write_file",
        "description": "Write a file in the application workspace",
        "capability": "write",
    },
    {
        "name": "fetch_url",
        "description": "Retrieve an external document",
        "capability": "network",
    },
]


def answer(question: str) -> str:
    load_customer_model()
    return f"draft reply for {question}"
