from sqlalchemy import create_engine, inspect, text

from app.models import migrate_provider_columns


def test_existing_catalogues_keep_bhashini_provider_attribution():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE catalogues (id VARCHAR(36) PRIMARY KEY, audio_used BOOLEAN)")
        )
        connection.execute(
            text("INSERT INTO catalogues (id, audio_used) VALUES ('audio', 1), ('text', 0)")
        )
    migrate_provider_columns(engine)
    migrate_provider_columns(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("catalogues")}
    assert {
        "asr_provider",
        "translation_provider",
        "translation_pending",
        "requested_output_languages",
    } <= columns
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT id, asr_provider, translation_provider, translation_pending "
                "FROM catalogues ORDER BY id"
            )
        ).all()
    assert rows == [
        ("audio", "Bhashini", "Bhashini", 0),
        ("text", None, "Bhashini", 0),
    ]
    engine.dispose()
