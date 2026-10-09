# Neovim

LazyVim with a VS Code-style layout, mouse support, and Notepad++ shortcuts.
Run `nvim` or `nvim /path/to/project`.

Shortcuts and basic usage: [KEYBINDS.md](KEYBINDS.md).
You can also open the guide with F1 or Help in the top menu.

Requirements for the layout, behavior, and further development of the configuration:
[AGENTS.md](AGENTS.md).

Tests: `./tests.sh`. The script uses `/usr/bin/python3`, skips the helper
`tests/ui.py`, and stops at the first failure.
