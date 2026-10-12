# Neovim: shortcuts and usage

Run `nvim` or `nvim /path/to/project`.
Files open in Insert mode. Esc switches to Normal mode;
`i` returns to Insert mode. F1 or Help opens this guide.

## Files and editing

| Shortcut | Action |
| --- | --- |
| Ctrl+N | Create a new blank document in a new tab |
| Ctrl+O | Find and open a project file |
| Ctrl+S | Save; a new file prompts for a name |
| Ctrl+Shift+S / Alt+S | Save as |
| Ctrl+W | Close the file; unsaved changes require a decision |
| Ctrl+A | Select all |
| Ctrl+C / Ctrl+X / Ctrl+V | Copy / cut / paste; without a selection, copy/cut the line |
| Ctrl+Z / Ctrl+Y | Undo / redo |
| Ctrl+D | Duplicate the line or selection |
| Ctrl+Shift+↑ / Ctrl+Shift+↓ | Move the current line or selected block up / down |
| Shift+Home / Shift+End | Select from the cursor to the start / end of the line |
| Tab / Shift+Tab with a selection | Increase / decrease the indentation of selected lines |
| Ctrl+L | Delete the line |
| Ctrl+Q | Comment/uncomment the line or all selected lines |
| Ctrl+F | Find text in the file |
| F3 / Shift+F3 | Next / previous match |
| Ctrl+H | Replace panel for the current file (Grug Far) |
| Ctrl+Shift+F / Alt+F | Search the project |
| Ctrl+G | Go to line |
| Ctrl+Tab / Ctrl+Shift+Tab | Next / previous tab |
| Ctrl+PageDown / Ctrl+PageUp | Alternative tab switching |
| F1 | This guide |
| Ctrl+Shift+P / Alt+P | Command palette |

Ctrl+H opens the Grug Far panel restricted to the current file.
In the replace panel, press Esc and then \r to apply the replacement; regular expressions are supported by default.
Formatting is available from the context menu; saving does not format automatically.

## Mouse

| Gesture | Action |
| --- | --- |
| Click and drag in code | Place the cursor and select text |
| Right-click | Context menu for the selected item |
| Left-click a tab | Select the document |
| Middle-click a tab / × | Close the document |
| Mouse wheel over tabs | Scroll the tab list |
| Click a file / directory in the tree | Open / expand or collapse |
| Click the gutter before a line number | Add/remove a breakpoint |
| Click the minimap | Jump to a position in the code |
| Mouse wheel / drag on the minimap | Scroll the code |
| Click the right side of a diff | Enter Insert mode |
| Click the terminal | Enter terminal input mode |

`q` closes a help or `:checkhealth` report tab. Close dialogs with ×;
you can also close the Plugins window with `q`.

## Code completion

Completion appears automatically; Ctrl+Space triggers it manually.
Tab accepts the selected suggestion. Language tools support
Python, C/C++, JavaScript/TypeScript, Bash, and Lua, among others. The file type must be recognized;
project dependencies and settings affect the available suggestions.

| Shortcut | Action |
| --- | --- |
| F2 | Rename the selected file/folder in Files, or the current file |
| Shift+F2 | Rename the symbol through the language server |
| F12 | Go to definition |
| Shift+F12 | Find references; also available from the context menu |

The code context menu also provides documentation, code actions, and formatting.

## Project, repository, and terminal

| Shortcut | Action |
| --- | --- |
| Ctrl+Shift+E / Alt+E | Select Files |
| Ctrl+C / Ctrl+V in Files | Copy the selected file/folder / paste into the selected directory |
| Delete in Files | Delete the selected file/folder, with confirmation |
| Ctrl+Shift+G / Alt+R | Git changes in the tree |
| Alt+G | LazyGit: staging, commits, history, branches |
| Alt+D | Diffview: repository diffs |
| Ctrl+` / Alt+T / F4 | Show/hide the bottom terminal |
| Esc, Esc in the terminal | Exit terminal input mode |

File > Open folder opens a project. Terminal > New terminal creates a session.
Opening a file from Files keeps keyboard focus in the tree. Click the editor or its
tab to type. Pasting in the same directory creates `Copy of name`; further copies
use `Copy (2) of name`, etc. Existing files are preserved.
`[↓ Hide]` hides Problems. `:DiffviewClose` closes the Diffview or history view.
R / F5 in the Git panel refreshes the status. Shift+click selects a range of files,
and Ctrl+click adds or removes a file from the selection. Stage / Unstage / Discard
and Commit are available in the Git panel and its menu. Discard requires confirmation.
When a file appears in both groups, opening it from Changes compares against its staged version.
Click the branch name to select a branch. Type a new name with no matching branches
and press Enter to create and switch to it. The `[↑… ↓…]` button synchronizes
through fetch, pull, and push. Without an upstream, it publishes the branch and
sets tracking, using the configured push remote, `origin`, or the only remote;
if several remotes remain, select one. Subsequent clicks synchronize normally.

The command palette (Ctrl+Shift+P / Alt+P) includes Git commands. Search for `Git`:
`GitStatus`, `GitRefresh`, `GitSwitchBranch`, `GitMerge`, `GitMergeAbort`,
`GitFetch`, `GitPull`, `GitPush`, `GitSync`, `GitCommit`, `GitDiff`,
`GitFileHistory`, `GitProjectHistory`, `GitBlame`, and `GitStageHunk`.
Selecting a command places it on the command line; press Enter to run it.
`GitMerge` opens a branch picker and merges the selected branch into the current one.
You can also run `:GitMerge branch-name` or choose Git > Merge branch in the menu.
`GitCommit` focuses the commit message field; Enter there commits staged changes.

## Debugger

| Shortcut | Action |
| --- | --- |
| F5 | Start / continue |
| Shift+F5 | Stop |
| F9 | Add/remove a breakpoint |
| F10 | Step over |
| F11 | Step into |
| Shift+F11 | Step out |
| Alt+B | Open the Debug tab in the left panel |

Left-click expands or collapses an object. Click a breakpoint or stack frame to open
its source; right-click provides actions appropriate to the selected item.
Debug console opens the debugger console.

| Debugger shortcut | Action |
| --- | --- |
| Ctrl+W | Add the variable to Watches |
| Ctrl+C | Copy the value |
| Ctrl+E | Copy the expression |
| Ctrl+Shift+C | Copy the entire line |

Python uses debugpy. C/C++ uses CodeLLDB; compile the program with `-g`, then select the executable after pressing F5.
JavaScript uses js-debug-adapter. TypeScript requires a project runtime (e.g. tsx/ts-node)
or compiled JavaScript with source maps. Custom launch configurations can be
stored in `.vscode/launch.json`. Select the project's Python environment with :VenvSelect.
Debugging does not compile the project automatically.

## Tools

`:Lazy` manages plugins, `:Mason` manages language tools,
and `:LazyExtras` manages LazyVim extras. After changing the Lua configuration, save your documents
and restart Neovim.

If your terminal does not distinguish Ctrl+Shift, use the Alt shortcuts or context menu.
