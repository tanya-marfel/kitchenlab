"""Pinned-revision variant of the BreachMirror demo target."""

from transformers import AutoModel

def load_customer_model():
    model = AutoModel.from_pretrained(
        "example-org/customer-model",
        revision="a1b2c3d4e5f6789012345678901234567890abcd",
    )
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
