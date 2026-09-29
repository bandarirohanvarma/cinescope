"""Download and import a MovieLens dataset (movies, external ids and ratings)."""

import csv
import logging
import re
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Movie

logger = logging.getLogger(__name__)

DATASETS = {
    # ~100k ratings, ~9.7k movies: fast, good for development.
    "ml-latest-small": "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip",
    # 32M ratings, ~87k movies: the full benchmark dataset.
    "ml-32m": "https://files.grouplens.org/datasets/movielens/ml-32m.zip",
}

TITLE_YEAR = re.compile(r"^(?P<title>.*?)\s*\((?P<year>\d{4})(?:[-–]\d{0,4})?\)\s*$")
# MovieLens writes "Matrix, The" / "Amelie, L'"; move the article back to the front.
TRAILING_ARTICLE = re.compile(
    r"^(?P<rest>.+), (?P<article>The|A|An|Les|La|Le|L'|Il|El|Los|Las|Die|Der|Das|Den|Det)$"
)
COPY_BATCH = 50_000


def download(dataset: str, data_dir: Path) -> Path:
    """Download and unzip a dataset into data_dir/raw. Returns the extracted folder."""
    raw_dir = data_dir / "raw"
    target = raw_dir / dataset
    if (target / "movies.csv").exists():
        return target

    raw_dir.mkdir(parents=True, exist_ok=True)
    archive = raw_dir / f"{dataset}.zip"
    logger.info("Downloading %s", DATASETS[dataset])
    with httpx.stream("GET", DATASETS[dataset], timeout=None, follow_redirects=True) as response:
        response.raise_for_status()
        with archive.open("wb") as file:
            for chunk in response.iter_bytes():
                file.write(chunk)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(raw_dir)
    archive.unlink()
    return target


def parse_title(raw: str) -> tuple[str, int | None]:
    """'Matrix, The (1999)' -> ('The Matrix', 1999)."""
    title, year = raw.strip(), None
    if match := TITLE_YEAR.match(title):
        title, year = match["title"], int(match["year"])
    if match := TRAILING_ARTICLE.match(title):
        article = match["article"]
        separator = "" if article.endswith("'") else " "
        title = f"{article}{separator}{match['rest']}"
    return title, year


def read_movies(folder: Path) -> list[dict]:
    """Join movies.csv and links.csv into rows for the movies table.

    Only the TMDB link is kept; TMDB enrichment fills in IMDb ids and all other details.
    """
    with (folder / "links.csv").open(encoding="utf-8") as f:
        links = {row["movieId"]: row for row in csv.DictReader(f)}

    seen_tmdb: set[int] = set()
    rows = []
    with (folder / "movies.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tmdb = links.get(row["movieId"], {}).get("tmdbId")
            tmdb_id = int(tmdb) if tmdb else None
            # A handful of MovieLens entries share a TMDB id; keep the first one.
            if tmdb_id in seen_tmdb:
                tmdb_id = None
            seen_tmdb.add(tmdb_id)
            title, _year = parse_title(row["title"])
            rows.append({"movielens_id": int(row["movieId"]), "title": title, "tmdb_id": tmdb_id})
    return rows


def read_ratings(folder: Path, movie_ids: dict[int, int]) -> Iterator[tuple]:
    with (folder / "ratings.csv").open(encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # header: userId,movieId,rating,timestamp
        for user_id, ml_movie_id, rating, timestamp in reader:
            movie_id = movie_ids.get(int(ml_movie_id))
            if movie_id is not None:
                yield (
                    int(user_id),
                    movie_id,
                    Decimal(rating),
                    datetime.fromtimestamp(int(timestamp), tz=UTC),
                )


async def import_dataset(session: AsyncSession, folder: Path) -> dict[str, int]:
    movies = read_movies(folder)
    linked = [m for m in movies if m["tmdb_id"] is not None]
    unlinked = [m for m in movies if m["tmdb_id"] is None]
    for start in range(0, len(linked), 5_000):
        stmt = insert(Movie).values(linked[start : start + 5_000])
        # A movie may already exist from a TMDB list sync: attach its MovieLens id.
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=["tmdb_id"], set_={"movielens_id": stmt.excluded.movielens_id}
            )
        )
    for start in range(0, len(unlinked), 5_000):
        stmt = insert(Movie).values(unlinked[start : start + 5_000])
        await session.execute(stmt.on_conflict_do_nothing(index_elements=["movielens_id"]))
    await session.commit()

    result = await session.execute(
        select(Movie.movielens_id, Movie.id).where(Movie.movielens_id.is_not(None))
    )
    movie_ids = dict(result.tuples().all())

    await session.execute(text("TRUNCATE movielens_ratings"))
    connection = await session.connection()
    raw = (await connection.get_raw_connection()).driver_connection
    total = 0
    batch: list[tuple] = []
    for record in read_ratings(folder, movie_ids):
        batch.append(record)
        if len(batch) >= COPY_BATCH:
            await raw.copy_records_to_table("movielens_ratings", records=batch)
            total += len(batch)
            batch.clear()
            logger.info("Imported %s ratings", f"{total:,}")
    if batch:
        await raw.copy_records_to_table("movielens_ratings", records=batch)
        total += len(batch)
    await session.commit()

    return {"movies": len(movies), "ratings": total}
