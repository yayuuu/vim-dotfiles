# Neovim

LazyVim with a VS Code-style layout, mouse support, and Notepad++ shortcuts.
Run `nvim` or `nvim /path/to/project`.

Install Git, LazyGit, ripgrep, fd (`fd-find` on Debian), a C compiler, curl, tar,
unzip, Node.js/npm, and Python with virtual environment support. The C/C++
configuration uses system `clangd`. On Debian these dependencies can be installed with:

```sh
sudo apt install git lazygit ripgrep fd-find build-essential curl tar unzip nodejs npm python3-venv clangd
```

Repository in the Git menu, and Alt+G, open LazyGit for the current project in
a large centered popup with a close button, preserving the editor and bottom
panel layout. This requires the separate `lazygit` executable on PATH.
If it is unavailable, the action shows an installation hint; the Git sidebar
remains available with Alt+R.

New terminal in the Files context menu creates a session in the selected folder
or the selected file's parent directory. On blank space it uses the displayed
tree root. It also shows the terminal panel if hidden, replacing Problems when
visible and preserving existing sessions.

On the first launch, leave Neovim running until Mason finishes installing language
tools and Tree-sitter finishes installing parsers. Those tools are stored outside
this repository in Neovim's data directory; copying the configuration alone does
not copy them. Installation details are available in `:Mason` and `:TSLog`.

Shortcuts and basic usage: [KEYBINDS.md](KEYBINDS.md).
You can also open the guide with F1 or Help in the top menu.

Set `"icons": true` in [settings.json](settings.json) for file/folder icons,
tree expanders, Git status markers, and diagnostic icons in Files and document tabs.
Set it to `false` for standard letters and symbols. Restart Neovim after changing it.

Requirements for the layout, behavior, and further development of the configuration:
[AGENTS.md](AGENTS.md).

Tests: `./tests.sh`. The script uses `/usr/bin/python3`, skips the helper
`tests/ui.py`, and stops at the first failure.
