Strikers v3.1.3 - Automatic Game Grading

- The backend grades pending predictions once at startup and every 5 minutes while Uvicorn is running.
- Only games marked Final by MLB are graded.
- Scheduled games are matched by gamePk first, then by official date and matchup as a legacy fallback.
- The Model Performance tab refreshes itself every 60 seconds while open.
- The Refresh Now button remains available as a manual fallback.
- Optional: set STRIKERS_AUTO_GRADE_SECONDS before starting Uvicorn to change the backend interval. Minimum is 60 seconds.

Important: automatic grading runs only while the backend is online.
