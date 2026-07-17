import csv
import os
from datetime import datetime
from typing import Optional


DATA_DIRECTORY = "data"
PREDICTIONS_FILE = os.path.join(DATA_DIRECTORY, "predictions.csv")

FIELDNAMES = [
    "prediction_id",
    "date",
    "away_team",
    "home_team",
    "predicted_winner",
    "predicted_probability",
    "confidence",
    "actual_winner",
    "correct",
]


def ensure_predictions_file() -> None:
    """
    Create the data directory and predictions CSV file if they do not exist.
    """

    os.makedirs(DATA_DIRECTORY, exist_ok=True)

    if not os.path.exists(PREDICTIONS_FILE):
        with open(
            PREDICTIONS_FILE,
            mode="w",
            newline="",
            encoding="utf-8",
        ) as file:
            writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
            writer.writeheader()


def generate_prediction_id(away_team: str, home_team: str) -> str:
    """
    Generate a readable unique ID for a prediction.
    """

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    away_clean = away_team.lower().replace(" ", "-")
    home_clean = home_team.lower().replace(" ", "-")

    return f"{timestamp}-{away_clean}-at-{home_clean}"


def save_prediction(
    away_team: str,
    home_team: str,
    predicted_winner: str,
    predicted_probability: float,
    confidence: str,
) -> str:
    """
    Save a new prediction to the CSV file.

    Returns the prediction ID.
    """

    ensure_predictions_file()

    prediction_id = generate_prediction_id(away_team, home_team)

    prediction = {
        "prediction_id": prediction_id,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "away_team": away_team,
        "home_team": home_team,
        "predicted_winner": predicted_winner,
        "predicted_probability": round(predicted_probability, 2),
        "confidence": confidence,
        "actual_winner": "",
        "correct": "",
    }

    with open(
        PREDICTIONS_FILE,
        mode="a",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writerow(prediction)

    return prediction_id


def update_prediction_result(
    prediction_id: str,
    actual_winner: str,
) -> bool:
    """
    Add the actual winner to a saved prediction.

    Returns True when the prediction was found and updated.
    Returns False when the prediction ID was not found.
    """

    ensure_predictions_file()

    predictions = []
    prediction_found = False

    with open(
        PREDICTIONS_FILE,
        mode="r",
        newline="",
        encoding="utf-8",
    ) as file:
        reader = csv.DictReader(file)

        for row in reader:
            if row["prediction_id"] == prediction_id:
                row["actual_winner"] = actual_winner

                predicted_winner = row["predicted_winner"].strip().lower()
                actual_winner_clean = actual_winner.strip().lower()

                row["correct"] = (
                    "True"
                    if predicted_winner == actual_winner_clean
                    else "False"
                )

                prediction_found = True

            predictions.append(row)

    if prediction_found:
        with open(
            PREDICTIONS_FILE,
            mode="w",
            newline="",
            encoding="utf-8",
        ) as file:
            writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(predictions)

    return prediction_found


def get_prediction_accuracy() -> Optional[float]:
    """
    Calculate prediction accuracy using completed predictions.

    Returns None if no completed predictions are available.
    """

    ensure_predictions_file()

    completed_predictions = 0
    correct_predictions = 0

    with open(
        PREDICTIONS_FILE,
        mode="r",
        newline="",
        encoding="utf-8",
    ) as file:
        reader = csv.DictReader(file)

        for row in reader:
            if row["correct"] == "True":
                completed_predictions += 1
                correct_predictions += 1

            elif row["correct"] == "False":
                completed_predictions += 1

    if completed_predictions == 0:
        return None

    return round(
        (correct_predictions / completed_predictions) * 100,
        2,
    )


def display_prediction_history() -> None:
    """
    Display all saved predictions and current accuracy.
    """

    ensure_predictions_file()

    with open(
        PREDICTIONS_FILE,
        mode="r",
        newline="",
        encoding="utf-8",
    ) as file:
        predictions = list(csv.DictReader(file))

    print("\n" + "=" * 72)
    print("STRIKERS PREDICTION HISTORY".center(72))
    print("=" * 72)

    if not predictions:
        print("\nNo predictions have been recorded yet.")
        return

    for prediction in predictions:
        actual_winner = prediction["actual_winner"] or "Pending"
        correct = prediction["correct"] or "Pending"

        print(f"\nID: {prediction['prediction_id']}")
        print(
            f"Matchup: {prediction['away_team']} at "
            f"{prediction['home_team']}"
        )
        print(
            f"Prediction: {prediction['predicted_winner']} "
            f"({prediction['predicted_probability']}%)"
        )
        print(f"Confidence: {prediction['confidence']}")
        print(f"Actual winner: {actual_winner}")
        print(f"Correct: {correct}")
        print("-" * 72)

    accuracy = get_prediction_accuracy()

    if accuracy is None:
        print("\nAccuracy: No completed predictions yet.")
    else:
        print(f"\nOverall prediction accuracy: {accuracy}%")