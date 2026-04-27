import random
import re
from dataclasses import dataclass


ROLL_RE = re.compile(r"(?P<count>\d*)d(?P<sides>\d+)(?P<keep>k[hl]\d+)?", re.IGNORECASE)
TERM_RE = re.compile(r"[+-]?[^+-]+")


@dataclass
class RollPart:
    expression: str
    rolls: list[int]
    kept: list[int]
    subtotal: int


def _roll_term(term: str) -> tuple[int, RollPart | None]:
    sign = -1 if term.startswith("-") else 1
    clean = term[1:] if term[:1] in "+-" else term
    match = ROLL_RE.fullmatch(clean.strip())
    if not match:
        return sign * int(clean), None
    count = int(match.group("count") or 1)
    sides = int(match.group("sides"))
    if count > 100 or sides > 10000:
        raise ValueError("dice expression exceeds configured safety limits")
    rolls = [random.randint(1, sides) for _ in range(count)]
    kept = rolls[:]
    keep = match.group("keep")
    if keep:
        mode = keep[1]
        amount = int(keep[2:])
        ordered = sorted(rolls, reverse=mode == "h")
        kept = ordered[:amount]
    subtotal = sign * sum(kept)
    return subtotal, RollPart(clean, rolls, kept, subtotal)


def roll_dice_expression(expression: str) -> dict:
    compact = expression.replace(" ", "")
    if not compact or not re.fullmatch(r"[0-9dDkKhHlL+\-]+", compact):
        raise ValueError("invalid dice expression")
    total = 0
    parts: list[RollPart] = []
    for term in TERM_RE.findall(compact):
        value, part = _roll_term(term)
        total += value
        if part:
            parts.append(part)
    return {
        "expression": expression,
        "total": total,
        "parts": [part.__dict__ for part in parts],
    }

