from datetime import datetime


def format_game_time(game_date):
    game_time = datetime.fromisoformat(
        game_date.replace("Z", "+00:00")
    )

    return game_time.strftime("%I:%M %p")


def get_split_record(team_record, split_type):
    records = team_record.get("records", {})
    split_records = records.get("splitRecords", [])

    for split in split_records:
        if split.get("type") == split_type:
            wins = split.get("wins", 0)
            losses = split.get("losses", 0)

            return f"{wins}-{losses}"

    return "Unknown"