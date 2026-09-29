"""Run pipeline jobs by hand.

python -m app.pipeline bootstrap              # everything, first-time setup
python -m app.pipeline movielens --dataset ml-32m
python -m app.pipeline tmdb-lists
python -m app.pipeline tmdb-changes --days 3
python -m app.pipeline tmdb-enrich --limit 500
python -m app.pipeline wikipedia --limit 500
python -m app.pipeline stats
"""

import argparse
import asyncio
import logging

from app.pipeline import jobs
from app.pipeline.movielens import DATASETS


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("bootstrap", "movielens"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--dataset", choices=DATASETS, default="ml-latest-small")
    sub.add_parser("genres")
    sub.add_parser("tmdb-lists")
    sub.add_parser("tmdb-changes").add_argument("--days", type=int, default=1)
    for name in ("tmdb-enrich", "wikipedia"):
        sub.add_parser(name).add_argument("--limit", type=int)
    sub.add_parser("embed").add_argument("--refresh", action="store_true")
    sub.add_parser("reminders")
    sub.add_parser("stats")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    runners = {
        "bootstrap": lambda: jobs.bootstrap(args.dataset),
        "movielens": lambda: jobs.import_movielens(args.dataset),
        "genres": jobs.sync_genres,
        "tmdb-lists": jobs.refresh_lists,
        "tmdb-changes": lambda: jobs.refresh_changes(args.days),
        "tmdb-enrich": lambda: jobs.enrich_tmdb(args.limit),
        "wikipedia": lambda: jobs.enrich_wikipedia(args.limit),
        "embed": lambda: jobs.embed_movies(args.refresh),
        "reminders": jobs.send_due_reminders,
        "stats": jobs.stats,
    }
    print(asyncio.run(runners[args.command]()))


if __name__ == "__main__":
    main()
