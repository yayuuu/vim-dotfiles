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

The `"color-palette"` setting selects a JSON palette, for example
`"color-palette": "matugen.json"`. Filenames are relative to the Neovim configuration
directory; absolute paths also work. The default is `palette.json`, which is also
used if the selected file is missing or invalid. Restart Neovim after changing
the setting or regenerating a palette.

`matugen.json` uses opaque interface backgrounds, borders, selection and accent
colors from Matugen. Its 16 terminal ANSI colors come from the generated Dank16
palette. Some other colors, including syntax and Git/diffs, use nearby Matugen
shades. Distant replacements fall back to the original `palette.json` color;
the background Matugen hook checks perceptual distance and hue after generation.
The main background uses Matugen's `background` color; setting `ui_background`
to `NONE` in a custom palette still enables transparency.
The local Matugen configuration generates this file when the palette changes.
Use `palette.json` to return to the original interface and terminal colors.

Requirements for the layout, behavior, and further development of the configuration:
[AGENTS.md](AGENTS.md).

Tests: `./tests.sh`. The script uses `/usr/bin/python3`, skips the helper
`tests/ui.py`, and stops at the first failure.
