# Instructions for working on the Neovim configuration

This file collects agreements with the user and describes behavior to preserve
in future changes. It applies throughout the repository. Newer user instructions
take precedence; update this document when the agreements change.
Descriptions of Git features do not authorize the agent to commit, push,
or perform operations on the user's actual repositories independently.

## Goals, portability, and updates

- The configuration should resemble VS Code, with mouse support, menus, and
  Notepad++ shortcuts. Basic tasks must be available without knowing Vim's modal workflow.
- It targets ordinary Neovim. Do not tie the layout or documentation to VTM,
  a particular terminal, username, root account, or PC.
  Resolve paths through `vim.fn.stdpath`, the project directory, and the environment.
- Make changes in our own `lua/config` modules and `lua/plugins` specifications.
  Do not edit downloaded plugin code or Mason tools.
- Prefer public APIs, options, events, mappings, and custom Neo-tree sources.
  Do not promise compatibility with every update: some integrations depend on
  internal modules, such as Bufferline rendering and Aerial adapters. Keep these
  integrations local, check versions, and test behavior after updates.
- When problems occur after moving the configuration, compare the Neovim version,
  `lazy-lock.json`, plugins, parsers, and language tools. Copying the repository
  alone does not guarantee an identical environment. Tested on Neovim 0.12.4;
  do not infer a minimum supported version from this.
- Communicate in Polish. Our own UI labels are currently in English. Polish
  Git messages are acceptable: do not force translations or identify errors
  by matching language-dependent message text.
- Preserve unsaved documents, terminals, and the debugger session. Do not clean up
  unrelated user changes in the working tree or index.

## Window layout and document routing

- The top contains a clickable File, Edit, Search, View, Project, Git, Debug,
  Terminal, Help menu. Menus, shortcuts, and context menus share the same actions.
- The left side is a single column with **Projects, Files, Debug, Git, Tabs** tabs,
  in that order. Leave one character of padding before the first tab.
  Selecting a tab replaces the entire column's contents instead of adding a column.
- The main editor is beside it, with a bottom panel below the editor. Opening a tool
  must not squeeze the editor into a thin strip or create duplicate panels.
- Open files, the shortcuts guide, `:help`, `:checkhealth` reports, and similar
  documents as additional buffer tabs in the main editor. Remove extra splits
  created by help commands. `q` closes a help/report tab while preserving the main window.
- A document tab is not a separate native tabpage. Managed Diffview/Git history
  views are exceptions: preserve their own tabpage and tool layout.
  Document routing and our own bars must not rebuild these views.
- Save proportions after dragging separators and restore them at startup.
  Window resizing scales panels proportionally while enforcing minimum dimensions;
  enlarging the window restores the chosen proportions. Account for window roles
  and the order of width changes, especially for the tree and terminal list.
- Delayed rendering of the previous tab must not replace the newly selected tab.
- Creating Symbols may close the previously focused dialog. Restore focus only
  if that window still exists; avoid automatic window restoration around Aerial.open
  that can target a closed window or leave focus in the Symbols panel.

## Tabs above the editor

- File > New file and Ctrl+N always create a new blank document with a visible tab
  and enter Insert mode. Each subsequent invocation creates another tab.
- The initial blank tab may disappear when opening an actual file.
  Never remove a document containing unsaved text this way.
- Left-click selects a tab, right-click opens its menu, and middle-click or × closes it.
  Support repeated clicks and mouse protocols with a generic release event;
  closing with the middle button happens on press.
- Selecting or reopening a document moves it to the front of the MRU list.
  The mouse wheel over tabs scrolls the list horizontally without changing the active document.
- The entire bar uses the inactive tab color; the active tab has a lighter background.
  The separator is a one-column **▌** (`vhalf`) character in the editor background color,
  placed between tabs and after the last tab when it fits in the viewport. Do not add it
  before × or after W 1, W 2, etc. Spaces inside a tab use that tab's background.
- Resolve separator colors in the editor window's highlight context. Focusing
  Commit message or another tool must not make separators inherit that tool's background.
- After a successful save, immediately remove the unsaved-change marker, including
  from both representations of a file in a diff. Keep the marker if saving fails.
- Closing a modified document offers Save / Don't save / Cancel;
  saving a new document prompts for a name.

## Editing and mouse support

- Opened files start in Insert mode. Esc switches to Normal mode;
  `i` returns to Insert mode. Clicking code on the right side of a diff enters Insert mode.
- Preserve mouse and Shift selection, copy/cut/paste,
  duplication, and movement of entire selected blocks.
- Ctrl+Q toggles comments on the current line or all selected lines.
  Support Normal, Insert, Visual, and **Select**, which is used by the mouse and Shift.
  Native mode-switching sequences must not remap Ctrl+G/Ctrl+O
  to our Go to line/Open file actions.
- Clicking the gutter before a line number toggles a breakpoint on that line
  without moving the cursor or changing its mode. The line number itself is not
  a breakpoint button. Account for scrolled code and editable diffs.
- Saving does not format a file automatically; formatting is an explicit action.

## Left panel and projects

- Projects lists recent projects from newest to oldest, without duplicates or the
  home directory. Clicking a project opens it and selects Files. Starting in the home
  directory selects Projects; starting in a project selects Files. File > Open folder
  updates the project directory, tree, and search.
- Each project remembers the document list/order, active file, and cursor.
  Skip deleted files when restoring. Switching projects hides clean tabs
  and preserves unsaved changes; project history does not store buffer contents.
- Files contains the tree and Functions / Symbols (Aerial). Clicking opens a file
  or expands/collapses a directory. When there are no symbols, show only a brief
  **No symbols** message; backend diagnostics remain available through `:AerialInfo`.
  Symbols and all four Debug sections have one fixed blank column on both the
  left and right edges. Preserve these margins during horizontal scrolling and
  resizing; account for them when calculating scrollbar overflow. Do not modify
  symbol/DAP buffer contents or row mappings to add visual padding.
- File clicks must work from Normal, Insert, Visual, Select, and terminal input,
  including repeated clicks. Resolve the row under the pointer instead of relying
  on the previous tree cursor. A new mouse press cancels an unfinished scrollbar
  gesture: a release lost outside the host must not swallow the next file click.
- Neo-tree rows of type `message`, such as `(3 hidden items)`, are not files.
  Clicking, Enter, and menu actions must not open their synthetic identifiers.
- View > Project files shows and selects Files without adding splits.
- Git contains the status and graph starting at HEAD. Tabs lists documents, including
  diffs, without terminals, internal HEAD buffers, or helper buffers.
  Leave one character of left padding before each commit graph row.
  Disable whitespace markers in the commit list: trailing graph spaces must not
  appear as extra dashes beside branch connections.
  Render the commit graph with Unicode nodes, lines, and rounded branch turns
  (`●`, `│`, `─`, `╭`, `╮`, `╰`, `╯`) instead of ASCII or diagonal strokes.
  Combine turns with existing lanes at junctions. Convert only the graph prefix; preserve commit subjects,
  branch names, hashes, row-to-commit mappings, and branch/merge topology.
- All left panels prevent scrolling into empty space when their content fits.
  For horizontal overflow of text that is not truncated, add a scrollbar at the bottom
  of the relevant panel; limit scrolling to the content dimensions.
  Keep scrollbar splits exactly one row high and their own view at the start.
  Native `winfixheight` alone does not prevent expansion after resizing; refresh
  geometry and visibility across Normal, Insert, and Visual modes.
  Text, selections, and value previews must not cover the main editor.

## Terminals and Problems

- One bottom area is divided vertically: a wide terminal on the left and
  a narrow session list on the right. Terminal > New terminal and the
  **New terminal** button create a session in the same area.
- Switching sessions preserves the editor document. Sessions have a clickable ×;
  a new session can still be created after closing the last one. Exiting a shell
  removes its session from the list.
- The header shows the current program and directory, e.g. `bash - ~/project`,
  instead of a fixed Terminal label. Update it after `cd` and when a program starts.
- Clicking the terminal or entering it with the keyboard enables terminal input.
  Esc, Esc exits input mode; clicking again resumes it. Preserve text selection.
- **Debug console** is a permanent, nonclosable list entry using the same wide area.
  Switching preserves both the console and terminal.
- View > Problems replaces the entire bottom area with diagnostics, a title, and
  a clickable **[↓ Hide]** in the top-right corner. Hide restores the previously
  visible terminal/console. If the panel was hidden, Hide only hides Problems.

## Debugger

- View > Debugger, Debug > Debugger panels, and Alt+B select the same Debug tab.
  Do not open the default additional DAP UI columns.
- The existing column contains four titled sections: **Scopes · Variables**,
  **Breakpoints · Stops**, **Call stack · Frames**, and **Watches · Expressions**.
  Switching tabs hides them while preserving the session.
- Left-click expands/collapses variables, Watches, and thread/breakpoint groups.
  Clicking a breakpoint or stack frame opens its source in the main editor.
- Each section has a context menu with appropriate actions and shortcuts. Variables:
  expand/collapse, Add to watches, Copy value, Copy expression, Copy sentence
  (the entire line), Edit value, Evaluate in debug console. Watches: add,
  edit, and remove expressions; breakpoints: Go to source, Enable/disable,
  Remove; stack: Go to source and visibility of internal frames.
- Local mappings: Ctrl+W adds to Watches, Ctrl+C copies the value,
  Ctrl+E copies the expression, and Ctrl+Shift+C copies the entire line.
- Use the complete value and `evaluateName` from DAP for operations, including
  nested objects. A truncated label is not a data source.
- Clip long values to the panel and provide a scrollbar. Do not enable
  `expand_lines` previews that spill text over the editor.
- A diff breakpoint belongs to the actual file buffer; the proxy only
  mirrors its sign. HEAD remains read-only.

## Git, diffs, and history

- Clicking a changed file opens one `name (diff)` tab with two columns:
  read-only HEAD and the editable current version. A shared tab bar spans
  both columns; Previous / Next buttons are below it.
- Compare files absent from HEAD against an empty side. Check the Git tree instead
  of error text. Do not hide other errors, such as failures to read the repository.
- If a file appears in both Changes and Staged Changes, opening it from Changes
  compares the working version (including unsaved edits) against the Git index.
  Label this baseline Staged. Other entries retain their HEAD comparison.
  Mouse clicks, Enter, and Open diff in the context menu use the same rule.
  Switching baselines reuses the document card without losing edits.
- Synchronize unsaved changes between the ordinary tab and diff proxy. Saving
  writes the actual file, and closing a diff preserves its changes.
- Additions are green, deletions red, and changes orange, including on the minimap.
  Both sides have synchronized horizontal scrolling.
- Horizontal scrollbars depend on overflow across both columns together: an empty
  HEAD side must not disable scrollbars for a long new file. Refresh them when
  opening and switching diffs. Rendering errors must not leave `hscroll.running`
  or `diff.busy` guards set, preventing further refreshes.
  Keep each horizontal bar directly below its source window. Reopening terminals
  or Problems must not leave an editor scrollbar below the bottom tool panel;
  repair split placement while preserving focus and existing sessions.
- Width measurement must handle NUL bytes in binary files (e.g. `.pyc`)
  without `E976: Using a Blob as a String`. Replace them with visible `^@` only
  for measurement; preserve the original buffer bytes and working scrollbars
  after switching to the next file.
- When closing a diff, unregister both sides from the native diff set;
  repeated switching must not color unchanged lines.
- Project history / File history preserve a separate Diffview view and one history
  panel. `:DiffviewClose` returns to the previous tab without destroying its layout.
- Clicking a commit in the sidebar graph opens its message and patch in a picker.
  Custom items using Snacks' `git_log` formatter must provide `msg` as well as
  `commit` and searchable `text`; closing the picker preserves panels and unsaved edits.
- Long commit previews have a vertical scrollbar on the right preview border.
  Support track clicks, thumb dragging, and the wheel without stealing input focus.
  Measure screen lines, including wrapped text and virtual lines; follow scrolling
  and resizing, hide the scrollbar when content fits, and remove it with the picker.
  Capture the entire drag through release, including outside the popup. Releasing
  over a terminal entry, tab, or close button must not activate that control.
  Other mouse listeners and release mappings must honor the capture; clear it
  after all handlers for the release event have finished.
- Staged Changes and Changes are separate and initially expanded. Shift+click
  selects a range, Ctrl+click toggles an individual selection, and right-click
  preserves the selection. The menu offers Stage/Discard in Changes and Unstage
  in Staged Changes.
- Stage saves the buffer before adding it to the index. Discard requires confirmation,
  creates a backup in the state directory, and restores the index version while
  preserving staged changes. Commit includes staged changes and the message from
  the panel's input field.
- Refresh the status, graph, branch, and upstream after operations. The ahead/behind
  button performs fetch, pull according to Git settings, and push; errors/conflicts
  stop subsequent steps. Do not duplicate synchronization. `vim.g.ide_git_autofetch=false`
  disables background fetch. Switching branches also refreshes Files and the status bar.
- Ex commands registered by `git_commands.lua` expose Git actions in the ordinary
  Ctrl+Shift+P / Alt+P command palette. Keep actions shared with menus where applicable.
  `GitMerge` selects a local/remote branch to merge into the current branch; it
  must not switch branches or run anything when selection is canceled. Also accept
  an explicit branch argument. `GitMergeAbort` aborts a merge. Refresh status after
  success and failure, including conflicts, while preserving unsaved editor buffers.
  GitFetch/Pull/Push use ordinary Git settings without forcing changes; GitSync
  reuses the existing synchronization action. GitCommit focuses the message field.

## Dialogs, pickers, and minimap

- Keep the complete editable palette in
  `palette.json` as a plain list of color names and values, with no code:
  theme tokens for backgrounds/syntax/diagnostics/Git,
  status bar colors, and our highlight overrides for diffs, minimap, sidebar
  selectors, and tab separators. Keep loading, highlight definitions, and plugin
  integration in `lua/config/colors.lua`. Other modules consume that module instead
  of defining RGB values or writing their own color overrides. Feed the theme through
  its public `color_overrides` / `group_overrides` options and reapply our highlights
  after a colorscheme reload. Do not edit downloaded theme/plugin files.
- Centered dialogs have a border and a clickable × in the top-right corner,
  including Plugins (Lazy), Mason, input, and composite Snacks pickers. Close the
  entire object through its owner's appropriate action, including its backdrop
  and callbacks. Closing input cancels entry instead of accepting it.
- Command palette and Edit configuration have consistent dividers: input must not
  overlap the preview separator, and the bottom must not have a double border.
  Preserve geometry after resizing; floating window configuration must include `relative`.
- The minimap shows structure, visible range, cursor, diagnostics, Git,
  and search. Clicking moves the cursor; the mouse wheel and dragging scroll.
  Do not extend it into terminals or left panels; hide it when the editor is narrow.
  Refresh the visible-range highlight immediately while scrolling or dragging,
  separately from the debounce for regenerating minimap text. Coalesce queued
  movements to the latest pointer position and respect the source's scrolloff
  margin so redraw does not shift the viewport again after moving the cursor.

## Module map and state

| File in `lua/config` unless otherwise specified | Responsibility |
| --- | --- |
| `init.lua`, `lua/config/lazy.lua` | Startup, LazyVim, imports, Lazy window |
| `options.lua`, `keymaps.lua`, `autocmds.lua` | Options, shortcuts, and events |
| `ide.lua`, `documents.lua` | Actions/menus, opening/saving/closing, document routing |
| `editor_tabs.lua`, `tabs.lua`, `tab_source.lua` | Tab bar, MRU, Tabs source |
| `layout.lua`, `sidebar.lua` | Proportions, column switching, graph |
| `projects.lua`, `project_source.lua` | Project history and tab restoration |
| `terminals.lua`, `problems.lua` | Bottom panel and visibility restoration |
| `debugger.lua`, `debug_source.lua`, `debugger_mouse.lua`, `breakpoints.lua` | DAP, sections, gestures, and breakpoints |
| `git.lua`, `git_source.lua`, `git_sync.lua`, `git_commands.lua`, `diff.lua` | Status, Git operations, command palette, upstream, and editable diff |
| `hscroll.lua`, `vscroll.lua`, `minimap.lua`, `popup_ui.lua` | Scrollbars, minimap, borders, and closing |
| `mouse_capture.lua` | Shared mouse gesture ownership for dragged widgets |
| `panel_padding.lua` | Fixed Symbols and Debug margins using window options and decorations |
| `colors.lua`, root `palette.json` | Palette data loader, theme/status bar options, and our highlight overrides |
| `lua/plugins/ide.lua`, `lua/plugins/minimap.lua` | Plugin options and integrations |
| `lazy-lock.json` | Pinned plugin versions |
| `tests/ui.py`, `tests/*.py`, `tests.sh` | UI/RPC client and regression scenarios |

Store state in `vim.fn.stdpath("state")`: proportions in
`desktop-ide-layout.json`, projects in `desktop-ide-projects.json`, and Discard
backups in `git-discard/`. Python caches do not belong in Git.

`KEYBINDS.md` is a brief user guide: shortcuts and basic gestures.
Layout details, the module map, and development requirements belong here. Preserve
opening the guide through F1 / Help. Do not present local clipboard bridges or
terminal workarounds as configuration requirements; the existing `xclip` provider
is an environment detail to account for when moving the configuration.

## Verification and logging

Run the full suite from the repository directory:

```bash
./tests.sh
```

Run a single scenario:

```bash
/usr/bin/python3 -B tests/save_markers.py
```

- `tests.sh` also works when invoked by path from another directory. It uses system
  Python with `msgpack`, skips the helper `tests/ui.py`, and stops at the first failure.
  `-B` prevents creating `__pycache__`.
- Tests run real Neovim through UI/RPC with temporary state, files, and Git repositories.
  Plugins and tools must be installed. `debugger_mouse.py` uses Mason's debugpy and
  a local DAP connection; the sandbox may require approval for that connection.
  Distinguish environment restrictions from UI behavior bugs.
  Do not test Git operations on the user's repository.
- Choose scenarios relevant to the change: tabs → `editor_controls.py`,
  `editor_tab_separators.py`, `tab_focus_colors.py`, `save_markers.py`; diff → `diff.py`, `diff_input.py`,
  `breakpoint_mouse.py`, `diff_scrollbar.py`, `binary_diff_scrollbar.py`,
  `hscroll_recovery.py`, `scrollbar_placement.py`, `staged_diff.py`;
  terminal/Problems → `terminal_input.py`, `panels.py`,
  `debugger_panels.py`; debugger → `debugger_mouse.py`; left panel/projects →
  `sidebar.py`, `sidebar_scroll.py`, `projects.py`; documents/history/dialogs →
  `documents.py`, `git_history_view.py`, `git_commit_preview.py`, `commit_scrollbar.py`,
  `outline_focus.py`, `picker_layout.py`, `popup_resize.py`;
  Git command palette and merging → `git_commands.py`;
  editing → `comment_selection.py`; document creation → `new_file.py`;
  informational tree rows → `tree_messages.py`; file clicks across modes and
  recovery after a lost scrollbar release → `tree_click.py`.
  Minimap gestures and immediate viewport updates → `minimap_drag.py`.
- Check visible behavior and actual gestures. For regressions, consider a test
  that fails before the fix. Documentation-only changes do not require the full UI suite.
  Run `git diff --check`.
- After Lua changes, mention restarting Neovim; changes to Markdown/.gitignore
  do not require a restart.
- Follow the global logging instructions: append diagnostics, tests, and operational
  actions to `~/codex.log` with timestamp, directory, complete command, stdout/stderr,
  and exit status. Output must also remain visible in the session.
  Do not log commands whose purpose is to create, edit, or delete file contents.
