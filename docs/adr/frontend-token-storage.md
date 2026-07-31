# Frontend Token Storage

For the v1 frontend, the access token is stored in memory and the refresh token is stored in `sessionStorage`.

Closing the tab or browser clears `sessionStorage`, so closing the app logs the user out. A normal same-tab page reload attempts a silent refresh with the stored refresh token before showing logged-out UI.

The app does not include a "remember me" option in v1 and must not store auth tokens in `localStorage`.

This app must not add any third-party script, including analytics SDKs, chat widgets, ad scripts, or similar, without revisiting the `sessionStorage` refresh-token decision first.
