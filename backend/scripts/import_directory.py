"""Import reviewed hospital listings; never creates users, chambers, or slots.

Run after migrations: python -m scripts.import_directory [--file PATH]
Review the official source before changing facts or source_checked_on in the dataset.
"""

import argparse
import asyncio
import json
from pathlib import Path

from pydantic import TypeAdapter
from sqlalchemy import select, text

from app.db.session import async_session_maker, engine
from app.models.directory import DirectoryDoctor
from app.schemas.directory import DirectoryImportRow

DEFAULT_DATASET = Path(__file__).resolve().parents[1] / "data" / "bangladesh_doctors.json"


def load_dataset(path=DEFAULT_DATASET):
    rows = TypeAdapter(list[DirectoryImportRow]).validate_python(json.loads(Path(path).read_text()))
    keys = [row.listing_key for row in rows]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate directory listing keys")
    if not rows:
        raise ValueError("Directory dataset must not be empty")
    return rows


async def import_rows(db, rows):
    # Serialize concurrent production imports; row updates preserve moderation decisions.
    if db.bind.dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(73910622)"))
    existing = {
        row.listing_key: row
        for row in await db.scalars(
            select(DirectoryDoctor).where(
                DirectoryDoctor.listing_key.in_([r.listing_key for r in rows])
            )
        )
    }
    added = updated = unchanged = 0
    for source in rows:
        facts = source.model_dump()
        row = existing.get(source.listing_key)
        if row is None:
            db.add(DirectoryDoctor(**facts, is_active=True))
            added += 1
        elif any(getattr(row, key) != value for key, value in facts.items()):
            for key, value in facts.items():
                setattr(row, key, value)
            updated += 1
        else:
            unchanged += 1
    await db.flush()
    return {"added": added, "updated": updated, "unchanged": unchanged}


async def main(path):
    rows = load_dataset(path)  # Validate the entire file before any writes.
    try:
        async with async_session_maker() as db, db.begin():
            result = await import_rows(db, rows)
        print(json.dumps({**result, "divisions": len({row.division for row in rows})}))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_DATASET)
    asyncio.run(main(parser.parse_args().file))
