# 🎯 Debug Marathon Platform

A professional, full-stack competitive coding platform featuring a modern landing page, secure contest environment, real-time leaderboard, and comprehensive admin panel.

## 🚀 Features

- **Participant Portal**: Secure login, ACE code editor, and real-time compilation feedback.
- **Proctoring System**: Advanced anti-cheating measures (Tab switch detection, clipboard blocking, etc.).
- **Admin Dashboard**: Live monitoring of participants, violation tracking, and contest control.
- **Live Leaderboard**: Real-time ranking with "Projector Mode" for event displays.
- **Premium UI**: Glassmorphism design system with a clean Light Theme.

## 🛠️ Technology Stack

- **Frontend**: HTML5, CSS3 (Vanilla + Variables), JavaScript (ES6).
- **Backend (Structured)**: Python Flask.
- **Tools**: ACE Editor, FontAwesome, Google Fonts.

## 📂 Project Structure

```
debug-marathon/
├── frontend/             # Single Page Application Frontend
│   ├── css/              # Modular Stylesheets
│   ├── js/               # Logic Modules (Auth, Editor, Proctoring)
│   ├── index.html        # Landing Page
│   ├── participant.html  # Contest Portal
│   ├── admin.html        # Admin Dashboard
│   └── leaderboard.html  # Public Standings
└── backend/              # Flask API Skeleton
    ├── app.py
    └── routes/
```

## 🏁 Quick Start (Frontend Demo)

Since the frontend is decoupled and performs API simulations for demonstration:

1.  Navigate to the `frontend` directory.
2.  Open **`index.html`** in your browser.
    *   *Recommendation*: Use "Live Server" extension in VS Code for the best experience.

### Access Credentials (Demo)

*   **Participant Portal**: Enter `PART001` (or any ID > 3 chars).
*   **Admin Panel**: Click "Login" (Mock auth bypasses password for demo).

## 🛡️ Proctoring Features

To test the proctoring system:
1.  Log in as a participant.
2.  Try switching tabs -> **Warning Overlay**.
3.  Try right-clicking -> **Toast Warning**.
4.  Try copying text -> **Action Blocked**.

## 🎨 Design System

The project uses a custom CSS variable system defined in `main.css`. The default theme is **Light** as requested, with high-contrast text and "Inter" typography.

---
© 2025 Debug Marathon. Built with ❤️ for coding excellence.
