STRIKERS — SPRINT 7 PRODUCT POLISH

What changed
- Responsive mobile navigation drawer
- Mobile/tablet layouts for dashboards, cards, rankings, props, and predictors
- Dismissible error messages
- Improved focus states and button/card interactions
- Backend URL can now be configured with VITE_API_URL
- Added frontend/.env.example for deployment setup

Local development
The default backend remains http://127.0.0.1:8000, so no setup change is required locally.

Production frontend
Create frontend/.env and set:
VITE_API_URL=https://your-render-backend.example.com

Then build with:
npm install
npm run build
