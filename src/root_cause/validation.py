def validate_setup_tvir(tvir: dict) -> None:
    if not isinstance(tvir, dict) or not isinstance(tvir.get("context"), dict):
        raise TypeError("A setup TVIR with a context object is required")
    context = tvir["context"]
    if context.get("violation_type") != "setup":
        raise ValueError("Only setup timing paths are supported")
    launch = context.get("launch_clock") or context.get("clock")
    capture = context.get("capture_clock") or context.get("clock")
    if launch and capture and launch != capture:
        raise ValueError("Cross-clock paths are outside the setup repair scope")
