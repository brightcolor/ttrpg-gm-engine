from app.services.dice import roll_dice_expression


def test_roll_simple_expression():
    result = roll_dice_expression("1d20+5")
    assert 6 <= result["total"] <= 25
    assert result["parts"][0]["expression"] == "1d20"


def test_roll_keep_highest():
    result = roll_dice_expression("4d6kh3")
    assert 3 <= result["total"] <= 18
    assert len(result["parts"][0]["rolls"]) == 4
    assert len(result["parts"][0]["kept"]) == 3


def test_rejects_invalid_expression():
    try:
        roll_dice_expression("1d20; drop table")
    except ValueError as exc:
        assert "invalid" in str(exc)
    else:
        raise AssertionError("invalid expression was accepted")

