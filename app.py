from services.games import display_today_games
from services.teams import display_team_search
from services.players import display_player_search
from services.standings import display_standings
from services.comparison import display_team_comparison
from services.prediction import predict_matchup
from services.power_ratings import display_power_rating


def print_menu():
    print("\n" + "=" * 50)
    print("STRIKERS MLB ANALYTICS".center(50))
    print("=" * 50)
    print("1. Today's Games")
    print("2. Search Team")
    print("3. Search Player")
    print("4. View Standings")
    print("5. Compare Two Teams")
    print("6. Predict a Matchup")
    print("7. Team Power Rating")
    print("8. Exit")
    print("=" * 50)


def main():
    while True:
        print_menu()

        choice = input("\nChoose an option: ").strip()

        if choice == "1":
            display_today_games()

        elif choice == "2":
            display_team_search()

        elif choice == "3":
            display_player_search()

        elif choice == "4":
            display_standings()

        elif choice == "5":
            display_team_comparison()

        elif choice == "6":
            predict_matchup()

        elif choice == "7":
            display_power_rating()

        elif choice == "8":
            print("\nThanks for using Strikers!")
            break

        else:
            print("\nInvalid option. Please try again.")


if __name__ == "__main__":
    main()