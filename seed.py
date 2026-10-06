"""샘플 데이터 투입 스크립트 — 워크북 ③-⑦·④-③·④-④에서 /docs와 SQL Editor로 넣는 데이터를
같은 세션(SQLAlchemy)으로 한 번에 넣는다. 두 번 실행해도 안전하다(이미 있으면 건너뜀).

실행: (.venv) python seed.py   ← .env의 DATABASE_URL이 가리키는 DB(Supabase 또는 SQLite)에 들어간다
"""
from sqlalchemy import select
from database import SessionLocal, engine, Base
import models

Base.metadata.create_all(bind=engine)
db = SessionLocal()
try:
    # ④-③ 카테고리 (SQL Editor의 INSERT와 같은 일) — UNIQUE 이므로 없는 것만 넣는다
    for name, kind in [("식비", "expense"), ("교통", "expense"), ("월급", "income")]:
        if db.execute(select(models.Category).where(models.Category.name == name)).scalar_one_or_none() is None:
            db.add(models.Category(name=name, kind=kind))
    db.commit()
    cat = {c.name: c.id for c in db.execute(select(models.Category)).scalars()}

    # ③-⑦ 계좌 — 이름이 같은 계좌가 이미 있으면 재사용
    acct = db.execute(select(models.Account).where(models.Account.name == "월급통장")).scalar_one_or_none()
    if acct is None:
        acct = models.Account(name="월급통장", balance=1500000)
        db.add(acct); db.commit(); db.refresh(acct)

    # ④-④ 거래 — 이 계좌에 거래가 하나도 없을 때만 넣는다
    if not acct.transactions:
        db.add_all([
            models.Transaction(account_id=acct.id, category_id=cat["월급"], amount=3000000, memo="월급"),
            models.Transaction(account_id=acct.id, category_id=cat["식비"], amount=-12000, memo="점심"),
            models.Transaction(account_id=acct.id, category_id=cat["교통"], amount=-1500,  memo="지하철"),
        ])
        db.commit()

    print("categories:", cat)
    print("accounts  :", [(a.id, a.name, a.balance) for a in db.execute(select(models.Account)).scalars()])
    print("transactions:", [(t.id, t.account_id, t.category_id, t.amount, t.memo) for t in db.execute(select(models.Transaction)).scalars()])
finally:
    db.close()
