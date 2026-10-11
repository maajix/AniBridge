def test_requeue_interrupted_downloads(client, monkeypatch):
    import importlib
    import sys
    from sqlmodel import Session

    # conftest re-imports app.db per test; drop a lifespan bound to an older engine
    monkeypatch.delitem(sys.modules, "app.core.lifespan", raising=False)
    lifespan = importlib.import_module("app.core.lifespan")
    from app.db import create_job, engine, get_client_task, upsert_client_task

    scheduled = []
    monkeypatch.setattr(
        lifespan, "schedule_download", lambda req: scheduled.append(req) or "new-job"
    )
    with Session(engine) as s:
        old = create_job(s).id
        upsert_client_task(
            s,
            hash="h1",
            name="Movie.2020.GERMAN.720p [STRM]",
            slug="movie",
            season=0,
            episode=1,
            language="German Dub",
            site="filmpalast",
            save_path="/dl",
            category="radarr",
            job_id=old,
            state="downloading",
        )

    assert lifespan.requeue_interrupted_downloads({old}) == 1
    assert scheduled == [
        {
            "slug": "movie",
            "season": 0,
            "episode": 1,
            "language": "German Dub",
            "site": "filmpalast",
            "title_hint": "Movie.2020.GERMAN.720p [STRM]",
            "mode": "strm",
        }
    ]
    with Session(engine) as s:
        assert get_client_task(s, "h1").job_id == "new-job"
