def openai_response(response):
    data = response.model_dump(mode="json")
    choice = next(iter(data.get("choices") or []), {})
    return {
        "content": (choice.get("message") or {}).get("content"),
        "model": data.get("model"),
        "finish_reason": choice.get("finish_reason"),
        "usage": data.get("usage"),
        "response": data,
    }


class ResponseRecorder:
    def __init__(self, client, stage, responses, on_response=None):
        self.client = client
        self.stage = stage
        self.responses = responses
        self.on_response = on_response

    def generate(self, prompt):
        generate_response = getattr(self.client, "generate_response", None)
        if callable(generate_response):
            response = generate_response(prompt)
        else:
            response = {
                "content": self.client.generate(prompt),
                "model": getattr(getattr(self.client, "cfg", None), "model", None),
                "finish_reason": None,
                "usage": None,
                "response": None,
            }
        self.responses[self.stage] = response
        if self.on_response is not None:
            self.on_response(self.stage, response)
        return response["content"] or ""
