# ledger-api — 가계부 API (FastAPI + SQLAlchemy + Supabase PostgreSQL)

- **GitHub**: https://github.com/insung1939/ledger-api
- **Render**: _(배포 후 https://ledger-api-….onrender.com 주소를 여기에 적는다)_ → `/docs`

> 클라우드컴퓨팅실습 W4 과제. 3주차에 메모리에 담던 가계부 데이터를 관계형 DB(Supabase PostgreSQL)에 저장하고,
> FastAPI를 GitHub → Render로 배포해 인터넷 주소의 API가 Supabase를 읽고 쓰는 것을 확인한다.

## 구조

```
요청 → FastAPI(main.py) → SQLAlchemy ORM(models.py) → PostgreSQL(Supabase, Session pooler :5432)
```

| 파일 | 맡는 일 |
|---|---|
| `database.py` | Engine · SessionLocal · Base · `get_db` (DB 연결의 세 부품 + 요청마다 세션 열고 닫기) |
| `models.py` | 테이블 3개 — `accounts` 1:N `transactions` N:1 `categories` |
| `schemas.py` | Pydantic 입출력 형식 (Create / Read / 중첩 `AccountReadWithTx`) |
| `main.py` | 앱 생성 · `create_all` · 엔드포인트 8개 |
| `seed.py` | 샘플 데이터(카테고리·계좌·거래) 투입 — 두 번 실행해도 안전 |
| `render.yaml` | Render Blueprint (Build/Start 명령·환경변수 선언) |
| `.env.example` | 연결 문자열 형식 견본 (`.env`는 Git 제외) |

### 데이터베이스 스키마 (models.py)

```
accounts      id PK · name VARCHAR(100) · balance BIGINT
categories    id PK · name VARCHAR(50) UNIQUE · kind VARCHAR(10)
transactions  id PK · account_id FK→accounts.id (NOT NULL) · category_id FK→categories.id (NULL 허용)
              amount BIGINT · memo VARCHAR(200) · occurred_at TIMESTAMP DEFAULT now()
```

### 엔드포인트 (CRUD API 명세)

| 메서드 | 경로 | 하는 일 | 단계 |
|---|---|---|---|
| POST | `/accounts` | 계좌 생성 (201) | ③ |
| GET | `/accounts` | 계좌 목록 | ③ |
| GET | `/accounts/{id}` | 계좌 단건 (없으면 404) | ③ |
| POST | `/transactions` | 거래 생성 — 계좌 없으면 친절한 404 | ④ |
| GET | `/accounts/{id}/detail` | 계좌 + 거래 목록 **중첩 응답** (relationship) | ④ |
| GET | `/stats/by-category` | 카테고리별 지출 합계 (GROUP BY · SUM · COUNT) | ④ |
| POST | `/transfers?from_id&to_id&amount` | 이체 — 출금+입금을 한 commit으로(원자성, `with_for_update`) | ⑦ 확장 |
| GET | `/accounts-with-tx` | 전 계좌 + 거래를 SELECT 2번으로 (`selectinload`, N+1 해결) | ⑦ 확장 |

## 로컬 실행

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env    # DATABASE_URL 을 본인 Supabase Session pooler 문자열로 교체
python -c "import database; print(database.engine)"   # Engine(postgresql+psycopg://…) 이면 OK
python seed.py          # 샘플 데이터
uvicorn main:app --reload   # http://127.0.0.1:8000/docs
```

`.env`가 없거나 `DATABASE_URL`을 못 읽으면 `database.py`가 자동으로 로컬 SQLite(`ledger.db`)로 넘어간다(워크북 ③-⑦ 우회).

## 배포 (Render)

| 항목 | 값 |
|---|---|
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Environment | `DATABASE_URL` = `.env`의 값 그대로 (Supabase Session pooler, `postgresql+psycopg://…:5432/postgres`) |

코드는 로컬과 한 줄도 다르지 않다. `os.getenv("DATABASE_URL")`이 로컬에서는 `.env`를, Render에서는 Environment Variables를 읽는다.

---

## 실습 기록

### ① 결과 확인

_(Supabase Table Editor의 `transactions` 캡처와 Render `/docs`의 `GET /accounts` 캡처를 여기에 붙인다)_

![supabase-transactions](docs/supabase_transactions.png)
![render-docs](docs/render_accounts.png)

### ② 핵심 개념 되새김

- **계좌·거래를 두 테이블로 나눈 이유(1:N)** — 계좌 하나에 거래가 여러 건 붙는다. 거래마다 계좌 이름·잔액을 복사해 두면 계좌 이름 하나를 고칠 때 모든 거래 행을 함께 고쳐야 하고, 하나라도 빠지면 같은 계좌가 둘로 갈라진다. 거래는 `account_id`라는 번호만 가리키고(외래키), 이름이 필요할 때 JOIN(또는 `relationship`)으로 붙인다. 외래키 덕에 "존재하지 않는 계좌의 거래"는 DB가 처음부터 거절한다.
- **SQLAlchemy 모델 클래스와 실제 테이블의 대응** — `class Account(Base)` 하나가 `CREATE TABLE accounts` 하나다. `__tablename__`이 테이블 이름, 클래스 속성 하나가 컬럼 하나이고, 타입 표기가 제약조건이 된다(`Mapped[str]` → NOT NULL, `Mapped[str | None]` → NULL 허용, `ForeignKey(...)` → FK). `Base.metadata.create_all()`이 이 정의를 읽어 없는 테이블을 만들고, 연결 문자열 앞머리(`sqlite` / `postgresql+psycopg`)를 보고 DB별 문법 차이를 알아서 맞춘다.
- **접속 문자열을 `.env`로 분리하는 이유** — 연결 문자열 한 줄에 DB 관리자 비밀번호가 그대로 들어 있다. 코드에 적으면 GitHub에 올라가 공개되고, 커밋 이력에 영원히 남는다. `.env`에 두고 `.gitignore`로 제외하면 코드는 공개하되 비밀은 내 PC와 Render 환경변수에만 있다. 또 로컬(SQLite)과 운영(Supabase)처럼 환경마다 접속 정보가 달라도 코드는 그대로 두고 이 한 줄만 바꾸면 된다.

### ③ 자유 로그

- **단계 1 (SQLite)** — `ledger-sql/`의 네 파일(step1_create · step2_data · step3_join_agg · step4_transfer)을 실행해 CREATE·INSERT·JOIN·GROUP BY·트랜잭션을 확인했다. GROUP BY 결과는 교통 -1,500 / 식비 -12,000 두 줄. `step4`를 여러 번 실행했더니 잔액이 -200,000원까지 내려가 있었다 → 이체 스크립트는 실행할 때마다 10만 원씩 옮기므로 당연한 결과였고, `ledger.db`를 지우고 step1부터 다시 돌려 400,000 / 1,100,000원으로 맞췄다. `raise ValueError("일부러 실패")`를 출금과 입금 사이에 넣으면 출금 UPDATE가 이미 실행됐는데도 `rollback()`이 잔액을 원상복구하는 것을 봤다(원자성).
- **단계 3·4 (FastAPI → DB)** — 처음엔 `.env`를 `sqlite:///./ledger.db`로 두고(③-⑦ 우회) 8개 경로를 모두 호출해 201/404/422/400 응답을 확인한 뒤, Supabase 연결 문자열로 바꿔 같은 코드를 다시 실행했다. 코드는 한 줄도 바꾸지 않았다.
- **단계 7 (확장)** — `/transfers`에서 commit 직전에 예외를 일부러 일으켜도 `GET /accounts` 잔액이 그대로였다(rollback). `/accounts-with-tx`는 계좌 3개·거래 6건을 불러오는 데 SELECT가 정확히 2번만 나갔다(`selectinload`). 계좌 수만큼 SELECT가 나가는 N+1과 비교해 봤다.
- **AI 활용과 검증** — Claude Code에게 워크북(교재 04)을 그대로 따라 파일을 만들게 하고, 워크북의 각 「확인」 명령(`print(database.engine)`, `Base.metadata.tables`, `model_fields.keys()` 등)과 `curl`·`TestClient` 호출 결과를 워크북에 적힌 기대값과 하나씩 대조해 검증했다. SELECT 횟수는 SQLAlchemy 이벤트 리스너로 세어 확인했다.
- **아직 안 풀린 것 / 메모** — _(Supabase·Render 연결 중 막힌 점이 있으면 여기에 적는다)_
