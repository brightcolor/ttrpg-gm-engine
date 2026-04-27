from app.db.session import SessionLocal
from app.services.rulesets import ensure_builtin_rulesets


if __name__ == "__main__":
    db = SessionLocal()
    try:
        ensure_builtin_rulesets(db)
        print("Seeded built-in rulesets")
    finally:
        db.close()

