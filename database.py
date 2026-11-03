import json
import random
from pathlib import Path
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, select
from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

Base = declarative_base()

engine = create_async_engine("sqlite+aiosqlite:///interview_bot.db")
async_session = async_sessionmaker(engine, expire_on_commit=False)

BANK_PATH = Path(__file__).parent / "data" / "bank" / "questions.json"


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    position = Column(String, index=True)
    level = Column(String, index=True)
    type = Column(String)  # theory / behavioral / coding
    text = Column(Text, unique=True)  # уникальность текста защищает от дублей при повторной загрузке банка


class InterviewResult(Base):
    __tablename__ = "interview_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True)
    position = Column(String)
    level = Column(String)
    question_type = Column(String)
    question = Column(Text)
    answer = Column(Text)
    evaluation = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _seed_questions_from_bank()


async def _seed_questions_from_bank() -> None:
    """Загружает вопросы из JSON-банка в БД, пропуская уже существующие (по тексту)."""
    bank = json.loads(BANK_PATH.read_text(encoding="utf-8"))

    async with async_session() as session:
        result = await session.execute(select(Question.text))
        existing_texts = {row[0] for row in result.all()}

        new_questions = [
            Question(position=item["position"], level=item["level"], type=item["type"], text=item["text"])
            for item in bank
            if item["text"] not in existing_texts
        ]
        if new_questions:
            session.add_all(new_questions)
            await session.commit()


async def get_random_questions(position: str, level: str, count: int = 4) -> list[dict]:
    """Берёт случайные вопросы под вакансию+уровень, гарантируя минимум 1 coding-вопрос, если он есть в пуле."""
    async with async_session() as session:
        result = await session.execute(
            select(Question).where(Question.position == position, Question.level == level)
        )
        pool = result.scalars().all()

    if not pool:
        return []

    coding_questions = [q for q in pool if q.type == "coding"]
    other_questions = [q for q in pool if q.type != "coding"]

    selected = []
    if coding_questions:
        selected.append(random.choice(coding_questions))

    remaining_slots = max(count - len(selected), 0)
    remaining_pool = [q for q in other_questions if q not in selected]
    selected.extend(random.sample(remaining_pool, min(remaining_slots, len(remaining_pool))))

    random.shuffle(selected)
    return [{"text": q.text, "type": q.type} for q in selected]


async def save_interview_answer(user_id: int, position: str, level: str, question_type: str, question: str, answer: str, evaluation: str) -> None:
    async with async_session() as session:
        session.add(InterviewResult(
            user_id=user_id, position=position, level=level, question_type=question_type,
            question=question, answer=answer, evaluation=evaluation,
        ))
        await session.commit()


async def save_feedback(user_id: int, content: str) -> None:
    async with async_session() as session:
        session.add(Feedback(user_id=user_id, content=content))
        await session.commit()