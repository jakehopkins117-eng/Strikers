from services.comparison import display_team_comparison
from services.games import display_today_games
from services.players import display_player_search
from services.prediction import display_prediction
from services.standings import display_standings
from services.teams import display_team_search


def display_menu():
    print("\n" + "=" * 45)
    print("STRIKERS")
    print("Baseball Analytics Platform")
    print("=" * 45)

    print("\n1. View today's games")
    print("2. Search for a team")
    print("3. View MLB standings")
    print("4. Search for a player")
    print("5. Compare two teams")
    print("6. Predict a matchup")
    print("7. Exit")


def main():
    while True:
        display_menu()

        choice = input("\nChoose an option: ").strip()

        if choice == "1":
            display_today_games()

        elif choice == "2":
            display_team_search()

        elif choice == "3":
            display_standings()

        elif choice == "4":
            display_player_search()

        elif choice == "5":
            display_team_comparison()

        elif choice == "6":
            display_prediction()

        elif choice == "7":
            print("\nThanks for using Strikers!")
            break

        else:
            print("\nPlease enter a number from 1 through 7.")

        input("\nPress Enter to return to the menu...")


if __name__ == "__main__":
    main()