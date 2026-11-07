# Workspace safety for this project

- Workspace 10 (Super+0) is reserved for the user's game. Never launch a test window there, switch to it for testing, or move, resize, focus, close, or send input to the game.
- Before opening any app or browser test window, inspect the current Hyprland workspace and window routing. Select an available workspace from 1–9 and launch directly to it without changing the active workspace or stealing focus. Do not change global desktop or window-manager behavior to accomplish this.
- Scope browser automation to the specific advisor test tab/window. Do not send global keyboard or mouse input. Respect browser access controls; do not work around a denied origin.
- If a test needs foreground control or safe background routing cannot be established, leave that test pending and continue work that can be done in the background.
- Recheck these constraints before desktop-launch, visual, or end-to-end tests in future sessions.
