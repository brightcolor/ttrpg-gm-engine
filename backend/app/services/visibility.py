SECRET_KEYS = {"secret", "secrets", "gm_secret", "gm_data", "hidden", "spoiler"}


def strip_secret_fields(value):
    if isinstance(value, dict):
        return {k: strip_secret_fields(v) for k, v in value.items() if k not in SECRET_KEYS}
    if isinstance(value, list):
        return [strip_secret_fields(item) for item in value]
    return value


def can_view(visibility: str, viewer: str = "player") -> bool:
    if viewer in ("admin", "gm"):
        return True
    return visibility in ("public", "party", "character")

