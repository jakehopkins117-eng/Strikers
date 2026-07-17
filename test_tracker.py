from utils.prediction_tracker import (
    display_prediction_history,
    save_prediction,
)


prediction_id = save_prediction(
    away_team="Baltimore Orioles",
    home_team="New York Yankees",
    predicted_winner="Baltimore Orioles",
    predicted_probability=61.5,
    confidence="Medium",
)

print(f"\nPrediction saved successfully.")
print(f"Prediction ID: {prediction_id}")

display_prediction_history()