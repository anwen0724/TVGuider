def validate_tvir(tvir: dict) -> None:
    if not isinstance(tvir, dict) or not isinstance(tvir.get("context"), dict):
        raise TypeError("A TVIR with a context object is required")
