import asyncio
from uuid import UUID

import typer
from sqlmodel import Session, select

from lagransala.core.models import Venue
from lagransala.deps import initialize_sqlmodel

cli = typer.Typer()


@cli.command()
def serve():
    import uvicorn

    from .web.app import app

    uvicorn.run(app, host="0.0.0.0", port=8000)


def get_venue_by_slug(db_session: Session, venue_slug: str) -> Venue | None:
    venue = db_session.exec(select(Venue).where(Venue.slug == venue_slug)).first()
    return venue


@cli.command()
def list_venues():
    engine = initialize_sqlmodel()
    with Session(engine) as db_session:
        venues = db_session.exec(select(Venue)).all()
    for venue in venues:
        print(venue.slug, venue.id)


@cli.command()
def extract(venue_slug: str | None = None):
    from .extraction.app import main

    engine = initialize_sqlmodel()

    if venue_slug is not None:
        with Session(engine) as db_session:
            venue = get_venue_by_slug(db_session, venue_slug)
            if venue is None:
                raise ValueError(f"Venue with slug {venue_slug} not found")
        print(f"Extracting events from {venue.name}")
        asyncio.run(main([venue_slug]))
    else:
        asyncio.run(main())


if __name__ == "__main__":
    cli()
