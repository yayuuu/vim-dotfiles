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
- Preserve Neovim's initial parser runtime directories when Lazy resets runtimepath;
  the presence of `lib64` does not mean it contains Neovim's parsers. Merge Mason
  tool requests without duplicates: extras may request the same tool, and a second
  install during an active installation raises an error. The startup/dependency
  regression is `tests/startup_dependencies.py`.
- Communicate in Polish. Our own UI labels are currently in English. Polish
  Git messages are acceptable: do not force translations or identify errors
  by matching language-dependent message text.
- Preserve unsaved documents, terminals, and the debugger session. Do not clean up
  unrelated user changes in the working tree or index.

## Window layout and document routing

- The top contains a clickable File, Edit, Search, View, Project, Git, Debug,
  Terminal, Help menu. Menus, shortcuts, and context menus share the same actions.
  Show the repository name in bold with a deterministic pastel color derived from
  its full displayed name (before truncation) in `colors.lua`: hash the name and
  map it to HSL hue, saturation 50–72%, and hue-dependent lightness: deeper
  mint/turquoise (down to 57%), light blues/purples, and pale pink/peach reds
  (up to 80%). Interpolate lightness bounds between hue sectors to keep shades
  varied without introducing harsh reds. Keep the color stable
  across restarts, resizing, project switching, and colorscheme reloads; never
  generate dark, gray, or strongly saturated colors. Hash-derived RGB colors can
  occasionally coincide for different names; do not promise absolute uniqueness.
  Center the name on the entire menu bar when it fits
  beside the headings; otherwise align it right. Take only the final origin URL
  component without `.git`, falling back to the repository directory without origin.
  Truncate long names to preserve menu buttons. Clicking the title or blank bar
  space dismisses an open dropdown.
  Clicking outside an open dropdown, including empty panel space, dismisses it
  without activating a row underneath. Menu-bar buttons still switch dropdowns.
  Clicking the active heading closes its dropdown. Switch menus atomically and
  scope delayed close callbacks to their own popup buffer so an old callback
  cannot close or reopen the replacement menu.
  The global menu remains clickable above both diff columns: mouse events on
  screen row 1 belong to the tabline even when getmousepos reports the diff header.
  Switching Terminal → Debug (and other headings) leaves only the new dropdown
  open. A queued BufEnter for an already displayed diff must not select it again
  and steal focus from the replacement menu.
  A closed menu's pending mouse release must not block Files or Git clicks.
  A fresh press clears an unfinished menu gesture and detaches its old listener;
  never keep hit-testing the screen rectangle of a menu closed earlier.
  Keep release-guard recovery in a persistent `menu_mouse.lua` listener, separate
  from individual popups. A new press clears orphaned guards even if a popup's
  old listener disappeared; delayed cleanup only affects its own popup state.
  Opening, switching and dismissing menus preserve the rendered global status
  bar, including document details and colors. Seed each popup's statusline before
  its first frame and use a Lualine extension to retain the source format during
  timer refreshes. Returning to an editable document resumes Insert before the
  next frame, avoiding an intermediate Normal-mode badge. Verify individual UI
  flushes with `tests/menu_statusline.py`, not only the final settled screen.
  Menus open without a selected row or visible text caret. Down/Up select the
  first/last action initially, then move vertically with wrapping, skipping
  separators. Left/Right switch top-level menu headings with wrapping; context
  menus ignore horizontal navigation. Enter runs the highlighted
  action and does nothing before a selection. Use the existing full-row mouse
  hover appearance for keyboard selection too: pointer movement temporarily
  takes over the one visible highlight; leaving the menu restores the last
  keyboard row, or no selection if there was none. Reset selection on each
  popup and restore the original cursor styling when it closes or loses focus.
  Keep the menu/Volt hover-ID adapter local to `menu_navigation.lua`, recheck
  it after plugin updates, and verify the rendered rows and cursor style with
  `tests/menu_navigation.py`.
- The left side is a single column with **Projects, Files, Search, Debug, Git, Tabs** tabs,
  in that order. Leave one character of padding before the first tab.
  Selecting a tab replaces the entire column's contents instead of adding a column.
- The main editor is beside it, with a bottom panel below the editor. Opening a tool
  must not squeeze the editor into a thin strip or create duplicate panels.
- Alt+A previews the current panel's tabs first: document cards in the editor,
  or sidebar source tabs from Files/Symbols and other sidebar sections. Left/Right
  highlight a candidate without opening it; Enter commits, Esc cancels. In document
  tab selection, q closes the highlighted card through the shared close action,
  retaining save/discard/cancel prompts. Continue selection at the next surviving
  card; canceling a close keeps its candidate selected. Consume repeated q across
  asynchronous closes and focus changes; after the last card retain an empty
  selection until Enter, Esc or a mouse press, so held q cannot edit the placeholder.
  Keep real save-dialog input available. Verify bursts/held keys and slow prompts
  with `tests/panel_tab_repeat.py`. If there
  are no tabs (such as a terminal), start panel selection directly. Another Alt+A
  selects panels spatially with all four arrows and a bright frame, retaining
  focus, mode and window geometry until Enter. Another Alt+A opens File in the
  global menu; the menu bar is also a spatial panel candidate above the editor.
  Mouse presses cancel preview before normal click handling and perform the
  clicked action, including a tab scrolled into view during preview. Restore
  temporary mappings and caret styling; Esc also restores tab scrolling.
  Convert numeric mapping flags to booleans when restoring Lua keymaps,
  especially replace_keycodes=0 for completion callbacks returning encoded keys.
  Preserve actual arrow movement without inserting key bytes after selection;
  cover real Blink mappings with `tests/panel_navigation_keys.py`.
  Never send selection keystrokes to a terminal child. Keep this in
  `panel_navigation.lua`, verified with `tests/panel_navigation.py`.
- Open files, the shortcuts guide, `:help`, `:checkhealth` reports, and similar
  documents as additional buffer tabs in the main editor. Remove extra splits
  created by help commands. `q` closes a help/report tab while preserving the main window.
- A document tab is not a separate native tabpage. Managed Diffview/Git history
  views are exceptions: preserve their own tabpage and tool layout.
  Document routing and our own bars must not rebuild these views.
- Save proportions after dragging separators and restore them at startup.
  The blank-panel mouse guard must let native vertical divider drags through:
  Neovim may report the divider as the left window with line 0 and a column
  beyond its width. Preserve resizing beside both empty lists and scrollbars.
  Window resizing scales panels proportionally while enforcing minimum dimensions;
  enlarging the window restores the chosen proportions. Account for window roles
  and the order of width changes, especially for the tree and terminal list.
  A tall saved commit graph or a dragged Git divider must leave room for the
  pinned Git header, both change sections, and file entries. Limit the graph
  using the actual sidebar height while preserving the preferred proportion.
  Horizontal dividers, including Git Status / Commits, must not activate global
  status-bar buttons. Capture their entire left-button gesture and resize through
  the public native window API, preserving focus and mode. Status-bar actions
  validate the actual global status-bar row and honor mouse capture.
- Delayed rendering of the previous tab must not replace the newly selected tab.
  Neo-tree's file-follow/reveal lookup must resolve diff document URIs to their
  actual file paths on either side. Never scan URI components as directories.
- Creating Symbols may close the previously focused dialog. Restore focus only
  if that window still exists; avoid automatic window restoration around Aerial.open_in_win
  that can target a closed window or leave focus in the Symbols panel.
- Switching to Files must not temporarily resize the editor or terminal. Create
  Symbols directly below the tree and bind it with Aerial.open_in_win. Keep the
  Aerial `aerial_set_width` compatibility flag in our plugin adapter so cached
  widths and delayed renders do not resize the column. Recheck this internal
  integration after Aerial updates. Skip applying unchanged window dimensions.
  Menu mouse/Enter actions close through the existing close callback; scope our
  Volt.close adapter to our own popup rather than feeding q into a nested input
  loop. The construction/geometry regression is `tests/ui_stability.py`.

## Tabs above the editor

- File > New file and Ctrl+N always create a new blank document with a visible tab
  and enter Insert mode. Each subsequent invocation creates another tab.
- The initial blank tab may disappear when opening an actual file.
  Never remove a document containing unsaved text this way.
- Left-click selects a tab, right-click opens its menu, and middle-click or × closes it.
  Support repeated clicks and mouse protocols with a generic release event;
  closing with the middle button happens on press.
- Selecting or reopening a document moves it to the front of the MRU list.
  Selecting an editable document tab (including a diff) enters Insert mode;
  returning from Files or another panel to the editor does the same even when
  its buffer has not changed. Esc stays in Normal mode while that editor retains
  focus, until the next click in its text area, which enters Insert even when
  the document and focused window have not changed. Mouse dragging and selection
  retain their native modes. Read-only HEAD, help/reports, and tool panels keep
  their appropriate modes.
  The mouse wheel over tabs scrolls the list horizontally without changing the active document.
- The entire bar uses the lighter inactive tab color; the active tab uses the dark panel background.
  The separator is a one-column **▌** (`vhalf`) character in the editor background color,
  placed between tabs and after the last tab when it fits in the viewport. Do not add it
  before × or after W 1, W 2, etc. Spaces inside a tab use that tab's background.
  For a transparent editor background, use a one-column space instead of ▌:
  terminal transparency cannot be painted as a half-block's foreground color.
  The entire separator cell, including its background, matches the editor's
  background. Gaps between cards and after the last card are transparent for NONE
  and use the editor's opaque color otherwise; unused strip fill stays inactive.
  The selected card must inherit the terminal background in the rendered UI,
  including icons, diagnostics, modified markers and padding. Give the strip a
  transparent base and explicitly paint inactive cards and unused fill; setting
  only the selected highlight's background to NONE still inherits an opaque strip.
- Resolve separator colors in the editor window's highlight context. Focusing
  Commit message or another tool must not make separators inherit that tool's background.
- After a successful save, immediately remove the unsaved-change marker, including
  from both representations of a file in a diff. Keep the marker if saving fails.
- Diagnostic counters in document tabs use `` for errors and `` for warnings
  instead of E/W letters. Preserve their counts and diagnostic highlights.
- Left-clicking diagnostic icons/counts in the status bar opens the existing
  Problems panel. Repeated clicks keep it open rather than toggling it closed.
- Closing a modified document offers Save / Don't save / Cancel;
  saving a new document prompts for a name.
- Interactive `:wq` / `:wquit` in the editor save and close the current document
  using the shared document actions, preserving the editor window, other tabs,
  and tool panels. Keep the document open if saving fails or is canceled;
  closing the last document leaves a blank editor. Preserve native commands
  outside the workspace and in managed Diffview tabpages.

## Editing and mouse support

- Opened files start in Insert mode. Esc switches to Normal mode;
  `i` returns to Insert mode. Clicking code on the right side of a diff enters Insert mode.
- Preserve mouse and Shift selection, copy/cut/paste,
  duplication, and movement of entire selected blocks.
- Editing actions started in Insert or Select/Visual mode retain the selection
  or resume Insert when they finish in the same editable document. Copying a
  selection resumes Insert, as do cut, paste and duplication; comment/indent/move
  actions may retain Select. Esc explicitly enters Normal, including from a
  selection created in Insert. Preserve deliberate Normal-mode editing after Esc
  and the modes of tool panels, read-only documents and dialogs. Execute selection
  edits without draining queued user input in an intermediate Normal mode.
- Shift+Tab in editor Insert mode decreases the current line's indentation by
  one shiftwidth from any cursor position and stays in Insert. Completion and
  snippet navigation must not intercept it. Preserve selection unindent and the
  Search panel's local Shift+Tab mode toggle.
- Scrolling the editor with the mouse wheel must preserve both endpoints of
  character, line and rectangular selections, including reversed Select/Visual
  ranges. Selected text may leave the viewport without extending the range.
  `selection_scroll.lua` parks the logical range, paints its original bounds and
  hides the clamped native selection/caret. Restore the range before keyboard
  actions, context-menu editing and terminal paste. A new left click starts a
  fresh gesture at the scrolled position. Clean up highlights, scrolloff and
  cursor styling when the selection ends or its window/buffer changes; do not
  alter sidebar/terminal scrolling or another widget's mouse capture.
- Copy/Cut in the editor, including Ctrl+C/Ctrl+X and menu actions, publish to
  the system clipboard so other applications can paste the text. Use Neovim's
  native clipboard-provider detection, preferring Wayland tools in a Wayland
  session and falling back appropriately on other platforms. Do not force an
  X11 provider or replace an explicitly supplied `vim.g.clipboard` provider.
  Verify copying through an external clipboard reader, not only `getreg('+')`,
  since Neovim's provider cache can hide a failed system transfer. Preserve
  existing clipboard contents when running tests against a real desktop.
- Ctrl+Q toggles comments on the current line or all selected lines.
  Support Normal, Insert, Visual, and **Select**, which is used by the mouse and Shift.
  Native mode-switching sequences must not remap Ctrl+G/Ctrl+O
  to our Go to line/Open file actions.
- Clicking the gutter before a line number toggles a breakpoint on that line
  without moving the cursor or changing its mode. The line number itself is not
  a breakpoint button. Account for scrolled code and editable diffs.
- Saving does not format a file automatically; formatting is an explicit action.
- Find text (Ctrl+F) has a clickable `⇄` button at its right edge. It opens the
  same Replace action as Ctrl+H and Search > Replace, carrying over the Find text.
  Keep its button anchored after resizing Find; relative float updates include
  both `row` and `col`, and resizing with an open Find is covered by the UI test.
  Close the helper through Snacks' public `on_close` callback, including when
  Find closes from another WinClosed handler. Defer native helper teardown
  outside text locks and capture its own window ID so old callbacks cannot close
  a replacement. Repeated Find focuses the existing input; discard a helper
  whose owner has closed or no longer displays its original input buffer.
  Replace is one named grug-far instance in a compact floating panel at the upper
  right of the main editor, below document tabs. Keep it at most 78 columns and
  22 rows, adapting to smaller editors without adding splits. Its `×` closes the
  instance through the plugin's public close action; repeated opening focuses it.
  Follow the active editable document, including the actual path of a diff, while
  preserving search/replacement/filter inputs and editor focus. Empty input rows
  with virtual placeholders remain clickable and enter Insert mode; result-list
  blank space keeps the usual mouse guard. Keep Grug input metadata integration
  local to `search.lua`. Disable completion and automatic result folding in this
  panel so background updates do not steal input mode from a clicked field.
- F2 renames the selected file/folder in Files or the current file in the editor,
  including an editable diff. Share the action with Rename in context menus.
  Preserve buffer IDs, unsaved contents, and diff mappings; refuse existing targets.
  Notify supporting LSP clients through file rename hooks, without requiring symbol
  rename support. Shift+F2 remains the LSP symbol rename shortcut.

## Left panel and projects

- Projects lists recent projects from newest to oldest, without duplicates or the
  home directory. Clicking a project opens it and selects Files. Starting in the home
  directory selects Projects; starting in a project selects Files. File > Open folder
  updates the project directory, tree, and search.
- Each project remembers the document list/order, active file, and cursor.
  Skip deleted files when restoring. Switching projects hides clean tabs
  and preserves unsaved changes; project history does not store buffer contents.
- Files shows all files by default, including dotfiles and Git-ignored entries.
  Shift+H toggles their visibility.
- Search contains one pinned input and **Find in content ⇄** directly below its
  tabs. Clicking the green **content / file names** text or the arrows toggles the
  mode; the **Find in** prefix stays white. The entire label, including its mode
  and arrows, is bold and italic. The rounded input border starts on
  the next row without a blank line. The label, input border, summary and file
  rows share one character of left padding, aligned with the global menu.
  The input's right border reaches the panel edge without extra right padding.
  Use the existing Neo-tree custom-source API and asynchronous ripgrep. Group
  content results by relative file path with matching line numbers and excerpts
  beneath each file. Clicking a file opens its first match; clicking a line opens
  that occurrence in the main editor, preserving unsaved buffers and tool sessions.
  Content search is literal with smart case; file-name search is a case-insensitive
  substring of the relative path. Include hidden files, respect ignore files, and
  exclude `.git`. Debounce typing, cancel obsolete jobs, and cap results at 1000.
  Keep queries/modes/results in memory per project. Hide the pinned controls with
  the source, retain the source selector and single column, and preserve the input
  geometry when resizing. Ctrl+Shift+F / Alt+F and Search > Find in project select
  this source and focus the existing input.
  Search results remain in Normal mode with a hidden caret and full-row selection.
  Up/Down choose file/match rows, skipping the summary and pinned placeholders.
  Up above the first result enters the input in Insert; Down from the input
  returns to results in Normal, also safely when there are no matches. Keyboard
  scrolling must reveal rows above the pinned header instead of clamping back.
  Refreshing an already visible source renders its cached rows directly, keeping
  the selected result and viewport; a temporary header-only buffer loses them.
  Include the bordered search input in Alt+A panel selection and resume Insert
  on entry. Shift+Tab in either the input or result list uses the same mode toggle
  as the label, preserves query/focus/mode, and searches the latest typed text.
  Verify these transitions with `tests/search_keyboard.py`.
  Opening results must not edit text or change document modification flags.
  Delayed entry into Insert uses a mode-independent command, never a queued
  literal `i`: another focus handler can enter Insert before that key is consumed.
- Right-clicking blank space in Files opens its general context menu: New file,
  New directory, Paste, and New terminal, without Open/Rename/Copy/Delete.
  Files context menus do not contain Repository. New terminal creates a fresh
  session in the clicked directory, a clicked file's parent, or the displayed
  tree root for blank space. Always show the bottom terminal panel, including
  when hidden, and preserve existing terminal sessions and editor documents.
  If Problems is visible, replace it with the terminal area; never show both.
  Resolve actual screen rows so EOF-clamped pointers do not target the final file.
  Blank-space creation/paste targets the displayed tree root; a file targets its
  parent directory and a directory targets itself, including collapsed folders.
  Share creation with the native tree shortcuts. Keep the Neo-tree filesystem
  action integration in `files.lua` and pass destinations explicitly rather than
  invoking mapping commands without their per-key `state.config`.
- Files contains the tree and Functions / Symbols (Aerial). Clicking opens a file
  or expands/collapses a directory. Opening a file from Files keeps keyboard focus
  in Files: Ctrl+C copies the selected file/folder, Ctrl+V copies it into the selected
  directory (or the selected file's parent), and Delete asks to delete the selection.
  Copying into the same directory produces `Copy of name`; further collisions use
  `Copy (2) of name`, etc., without overwriting existing files. Keep copies binary-safe,
  retain the file clipboard for repeated pastes, and preserve unsaved editor contents.
  Clicking the editor/tab moves keyboard focus to it and enters Insert mode.
  Files and Symbols remain in Normal mode, hide the text caret and highlight the
  whole selected row. Preserve other sources' input and selection modes. Shift+F10
  opens the selected file/folder's context menu at that row without using a stale
  mouse position. Also accept the optional Kitty standalone LEFT_ALT key event;
  ordinary terminals do not report bare modifier keys or distinguish left/right
  Alt in Alt+A. Do not require a terminal-specific keyboard protocol or host setup.
  File-type icons use mini.icons in `glyph` mode rather than letter badges.
  Rendering requires a font with Nerd Fonts symbols; keep this independent of
  the terminal/GUI and do not change its font as part of Neovim configuration.
  Directory expanders use filled triangles: `▸` collapsed and `▾` expanded.
  Folder icons use `` closed and `` open, including empty folders,
  instead of plus/minus signs.
  Files indicates Git status through name colors. Hide added/modified/deleted,
  renamed/untracked/ignored, staged and unstaged markers in this source only;
  retain conflict markers, diagnostics, file-type icons, and unsaved-change marks.
  The dedicated Git source keeps its status markers.
  Files diagnostic markers have one extra blank column after them, shifting
  the marker left to leave space beside the vertical scrollbar.
  Symbols follows the displayed editor document immediately after opening it,
  even while Files retains keyboard focus. Bind Aerial's existing window through
  its public API; preserve the layout, selection, and focused panel.
  The symbol containing the editor cursor is bold with the same background as
  the selected file row, using `ui_bar_background` through Aerial's highlights.
  Cursor tracking also runs in Insert mode: update position/highlights on
  `CursorMovedI` through the same Aerial window integration, preserving editor
  focus and mode and scrolling the active symbol into view.
  When there are no symbols, show only a brief
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
  Empty space below list content must never activate the final item. Apply this
  universally to Files, Symbols, Projects, Tabs, Git Status, commits, terminal
  sessions, Debug panes, Problems, and picker/dialog lists. Validate the rendered
  screen row instead of trusting Neovim's EOF-clamped mouse line. Keep terminal
  and editor body clicks available for input/cursor placement.
- View > Project files shows and selects Files without adding splits.
- Git contains the status and graph starting at HEAD. Tabs lists documents, including
  diffs, without terminals, internal HEAD buffers, or helper buffers.
  Leave one character of left padding before each commit graph row.
  Disable whitespace markers in the commit list: trailing graph spaces must not
  appear as extra dashes beside branch connections.
  Render the commit graph like LazyGit: one row per commit, `◯` for ordinary
  commits, `⏣` for merges, and rounded Unicode connections. Build lanes from full
  parent hashes instead of converting Git's ASCII graph row by row, which can
  invent loops and junctions. Keep the local LazyGit v0.50.0 adapter in
  `git_graph.lua`, with its MIT notice in `LICENSES/lazygit.txt`; compare it with
  upstream fixtures after changes. Preserve subjects, branch names, hashes,
  row-to-commit mappings and topology, including shared bases and octopus merges.
  Map LazyGit's default MD5/HSL author colors to the nearest existing ANSI color
  from `terminal_0` through `terminal_15`, using Oklab distance. Prefer colors with
  contrast at least 3 against the panel background (use `terminal_0` as the
  reference for transparent backgrounds); if none qualify, use the ANSI color
  with the highest contrast. Never introduce another RGB for author nodes or
  edges. Assignments are deterministic, may repeat for different authors, and
  adapt to the active palette. Crossing edges retain their separate colors when
  their palette assignments differ. Keep the color implementation and highlight
  definitions in `colors.lua`, and recalculate assignments on colorscheme reload.
  Focusing a commit highlights its parent paths as in
  LazyGit. Test geometry, RGBs and rendered highlights with `tests/commit_graph.py`.
- All left panels prevent scrolling into empty space when their content fits.
  Clamp vertical mouse scrolling before it changes the viewport, including the
  final partial wheel step. Do not allow overshoot followed by a visible snap back.
  For horizontal overflow of text that is not truncated, add a scrollbar at the bottom
  of the relevant panel; limit scrolling to the content dimensions.
  Render each scrollbar as a borderless, one-row float inside the source panel's
  last row. Do not allocate a separate split or blank separator row above it:
  the saved row belongs to visible content. Keep the caret above the scrollbar,
  including at EOF, and account for the reserved row in viewport calculations.
  Retain the native separator below the panel for resizing the terminal/panels;
  scrollbar clicks must not intercept a drag on that separator. Track the source
  window's size and placement across Normal, Insert, and Visual modes.
  Text, selections, and value previews must not cover the main editor.
- Every content panel with vertical overflow has a vertical scrollbar made of
  full `█` blocks. Native editor and diff windows use their minimaps instead.
  Include Files, Symbols, Git, Debug, Problems, terminals/console, session lists,
  and dialog/picker panels. For virtualized picker lists, use item count and list
  scrolling rather than the visible buffer's line count.
  Horizontal bars span the entire panel width; vertical bars end above them.
  Put vertical bars inside native panels, preserving their resize separators,
  and on the existing right border of bordered dialogs. Preserve padding beside them.
  Native-panel scrollbars stay below floating dialogs such as Plugins/Mason;
  a dialog's own scrollbar follows its layer. Reserve their column in scrolling
  content width calculations. Git Status has a separate full-width pinned header.
- Horizontal scrollbars use the lower half-block `▄` for both track and thumb, with no arrows.
  The track foreground uses `ui_bar_background`; the thumb foreground uses
  `scrollbar_thumb`. Their background matches `ui_background`. Clicking either
  endpoint scrolls to that end; keep dragging and terminal resize working.
  Horizontal bars and document minimaps own the entire left-button gesture
  through release. Use the shared mouse capture so releasing over another
  control only stops scrolling; it must not focus a terminal, open menus, switch
  tabs, or close documents. Retain capture through every release handler, then
  clear it; a fresh press must recover from a release lost outside the host.

## Terminals and Problems

- One bottom area is divided vertically: a wide terminal on the left and
  a narrow session list on the right. Terminal > New terminal and the
  **New terminal** button create a session in the same area.
- Switching sessions preserves the editor document. Sessions have a clickable ×;
  a new session can still be created after closing the last one. Exiting a shell
  removes its session from the list.
  The Terminals session list stays in Normal mode with full-row selection and
  no text caret, including entry from Insert/terminal input through Alt+A.
- The header shows the current program and directory, e.g. `bash - ~/project`,
  instead of a fixed Terminal label. Update it after `cd` and when a program starts.
- Clicking the terminal or entering it with the keyboard enables terminal input.
  Keypad navigation with NumLock off must reach terminal programs as Home/End,
  arrows, PageUp/PageDown, Insert/Delete, preserving numeric keypad digit input.
  Esc, Esc exits input mode; clicking again resumes it. Preserve text selection.
  Dragging/clicking its vertical scrollbar enters native scrollback mode so
  history stays at the requested position. Consume the mouse gesture and use
  an unremapped terminal escape; never invoke `:normal` from terminal input or
  send scrolling keys to the shell. Clicking the terminal body resumes input.
  Clamp the mouse wheel over the terminal body before moving its viewport;
  it must not scroll into empty space beyond the last history row.
  Body wheel events leave Terminal mode only for actual history with our vertical
  scrollbar. Without history they keep Terminal mode. When the child enables
  mouse reporting, forward body wheel events through Neovim's native terminal
  handling, even if history exists. Observe reporting modes through the public
  job stdout callback, including sequences split across chunks; do not infer
  support from the process name. Clicking our scrollbar still opens scrollback.
- Right-click in an ordinary managed terminal uses our shared popup/navigation
  for Copy (or Copy line), Paste, Select all, and New terminal. Dismissal restores
  input or scrollback mode and any selection. Copy publishes through the native
  clipboard provider; Paste uses native terminal put, preserving bracketed paste
  and buffer contents. Menu navigation must not send keys to the child. Keep the
  context/restore guard in `terminals.lua` and use the shared popup close callback.
  Forward right-button presses/releases to mouse-reporting children, and preserve
  native handling for terminal jobs owned by other plugins. Verify PTY bytes,
  cross-process clipboard transfers and session/document preservation with
  `tests/terminal_menu.py`.
- **Debug console** is a permanent, nonclosable list entry using the same wide area.
  Switching preserves both the console and terminal.
  First and repeated opening preserve native window dimensions and saved panel
  proportions. Initialize the REPL through its public open API in the existing
  terminal window; DAP UI's buffer helper creates a temporary split and must not
  be used here. Verify keyboard/mouse entry with `tests/terminal_navigation.py`.
  Clicking the console or returning to it resumes native prompt input, including
  repeated clicks in the same window and blank space below output. Preserve
  mouse selection. Enter on the final `dap>` prompt submits it through the native
  REPL callback even in Normal mode; Enter on results retains native tree actions.
  Preserve command history, the selected debug frame, and the paused session.
- View > Problems replaces the entire bottom area with diagnostics, a title, and
  a clickable **[↓ Hide]** in the top-right corner. Hide restores the previously
  visible terminal/console. If the panel was hidden, Hide only hides Problems.

## Debugger

- View > Debugger, Debug > Debugger panels, and Alt+B select the same Debug tab.
  Do not open the default additional DAP UI columns.
- The existing column contains four titled sections: **Scopes · Variables**,
  **Breakpoints · Stops**, **Call stack · Frames**, and **Watches · Expressions**.
  Switching tabs hides them while preserving the session.
  Mount all four windows before requesting their contents. A slow or failed
  renderer must not block the other sections or leave the opening guard set.
  Report render errors, rebuild incomplete pane sets, and ignore callbacks from
  earlier visits after switching sources.
- Keep `nvim-dap-virtual-text` disabled: repeatedly parsing large documents for
  annotations slows debugging. Inspect variables on demand through Ctrl+click
  or the editor's Inspect variable context action while paused, using DAP UI's
  evaluation popup. Preserve ordinary clicking, selection and document text;
  capture the complete Ctrl+click gesture, including generic releases and lost
  release recovery. Limit popup dimensions and close stale values on stepping
  or continuing. Resolve PHP's leading `$`, property/array references and a
  simple identifier fallback when no parser is available. Do not include calls
  from a container's index expression.
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

- Git > Repository and Alt+G share the same action opening
  LazyGit for the project in a large, centered, bordered popup, like Plugins
  and LazyVim Extras. Explicitly override the bottom-terminal geometry, resize
  with the editor, and register its close button with `popup_ui` using the
  Snacks window's public close action. Opening/closing must preserve the editor
  layout, unsaved documents, existing terminal sessions and Problems visibility.
  Check for the external `lazygit` executable first;
  if absent, show a brief installation hint and point to the Git sidebar (Alt+R)
  instead of calling Snacks and raising an exception. Document this dependency.
  LazyGit's `e` uses a temporary remote-edit tab that document routing moves into
  the main editor. Neominimap v3 may refresh that tab after it has closed; keep
  the guarded tab refresh in `minimap.lua` and skip invalid tab handles without
  suppressing other errors. Test actual LazyGit edits and preservation of unsaved
  buffers, minimaps, panel windows and running terminal sessions.
  Closing Repository with × intentionally stops its terminal job and must not
  show a failure notification for that termination. Use a local TermClose handler
  through Snacks' public callbacks, skipping a buffer already released by close.
  Preserve normal exit cleanup/checktime and report unexpected nonzero exits,
  retaining the failed terminal for inspection. Do not mute global notifications.
- Show one Git blame annotation at the end of the current editor line after a
  short idle delay, in both Normal and Insert mode: author, author date in
  YYYY-MM-DD format using the commit's recorded timezone, short commit hash,
  and subject. Mark local edits as Uncommitted changes instead of attributing
  them to an old commit. Use asynchronous, debounced single-line Git queries,
  short-lived caching, and discard canceled/stale results. Editable diffs use
  their real paths and buffer contents. Do not annotate tool panels or HEAD.
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
- Diff and minimap additions, deletions, and changes use the matching palette colors.
  Both sides have synchronized horizontal scrolling.
- Horizontal scrollbars depend on overflow across both columns together: an empty
  HEAD side must not disable scrollbars for a long new file. Refresh them when
  opening and switching diffs. Rendering errors must not leave `hscroll.running`
  or `diff.busy` guards set, preventing further refreshes.
  Keep each horizontal bar at the bottom inside its source window. Reopening
  terminals or Problems must not place it below the bottom tool panel;
  update float geometry while preserving focus and existing sessions.
- Width measurement must handle NUL bytes in binary files (e.g. `.pyc`)
  without `E976: Using a Blob as a String`. Replace them with visible `^@` only
  for measurement; preserve the original buffer bytes and working scrollbars
  after switching to the next file.
- Horizontal scrollbar dragging anchors to the exact initial view offset and
  pointer position, not the rounded thumb cell. Match Neovim's native cursor
  margin so redraw does not undo scrolling in narrow diff columns. Grabbing or
  releasing a stationary thumb must not shift the view; both sides stay aligned.
- Vertical wheel scrolling over either side of an added-file diff moves the
  populated comparison. Do not let the empty read-only baseline's cursor force
  the editable side back to the start. Tool-panel scrolling beside a Select-mode
  editor must not execute an insertion command against a read-only panel.
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
- Staged Changes and Changes are separate and initially expanded.
  Use the same filled `▸` / `▾` section expanders as Files, file-type glyphs,
  and glyph badges for Git change statuses. Preserve the original status codes
  in node data for staging, diffs, renames, and selection; icons are presentation.
  The Git Status title and Commit message input stay pinned; scrolling and the
  vertical scrollbar begin below them at Staged Changes. Preserve the commit
  input's width; it is part of the header and does not overlap the scrollbar.
  Keep the commit field's right border inside the sidebar, before its native
  vertical resize separator, including after resizing and opening diffs.
  The commit input has no close button and remains present while Git is selected.
  Keep its rounded border and geometry stable when opening diffs. Empty input
  clicks start editing; the blank-list click guard must not consume them.
  Shift+click selects a range, Ctrl+click toggles an individual selection, and right-click
  preserves the selection. The menu offers Stage/Discard in Changes and Unstage
  in Staged Changes.
- Git Status and Commits use Normal mode, a hidden caret and full-row selection.
  Up/Down in Git Status moves only the current-row highlight, clearing earlier
  mouse selections without creating a Visual selection; retain Shift/Ctrl mouse
  range selection. Shift+F10 opens the same item
  menu as right-click, anchored at the keyboard row. Commits offers View commit,
  Copy commit hash and Refresh commits; closing its preview returns to the list.
  Up at the first visible Git Status row enters Commit message in Insert mode.
  Down from that input returns to the first status row in Normal mode, preserving
  the draft. Include the existing bordered input among Alt+A panel candidates;
  preview frames do not alter native geometry. Verify with `tests/git_keyboard.py`.
- Clicks in the empty area below Git Status rows do not open the last file or
  alter range selections. Check the rendered screen row; Neovim clamps the mouse
  buffer line to EOF even when the pointer is below the list.
- Stage saves the buffer before adding it to the index. Discard requires confirmation,
  creates a backup in the state directory, and restores the index version while
  preserving staged changes. Commit includes staged changes and the message from
  the panel's input field.
- Refresh the status, graph, branch, and upstream after operations. The ahead/behind
  button performs fetch, pull according to Git settings, and push. Without upstream,
  publish the current branch with `push --set-upstream`, respecting configured push
  remotes, then preferring origin or the only remote; offer a selection if ambiguous.
  Detached HEAD and repositories without remotes must produce a helpful message.
  In the branch picker, Enter on a new name with no matches creates and switches to
  that branch; validate literal branch names and preserve ordinary selection/cancel.
  Show local and remote branches. Opening the switch picker fetches all origin
  branches asynchronously, including those outside a single-branch clone's refspec;
  keep cached branches usable if fetch fails. Selecting a remote branch creates
  its local counterpart with explicit tracking, or switches to the existing local
  branch and sets its upstream without resetting local commits. Cancellation does
  not switch or create branches. This explicit fetch also works with autofetch off.
  When tracking a branch outside configured fetch mappings, add that branch's
  exact refspec so Git can resolve and fetch its upstream on subsequent syncs.
  Errors/conflicts stop subsequent steps. Do not duplicate synchronization. `vim.g.ide_git_autofetch=false`
  disables background fetch. Switching branches also refreshes Files and the status bar.
- Ex commands registered by `git_commands.lua` expose Git actions in the ordinary
  Ctrl+Shift+P / Alt+P command palette. Keep actions shared with menus where applicable.
  `GitMerge` selects a local/remote branch to merge into the current branch; it
  must not switch branches or run anything when selection is canceled. Also accept
  an explicit branch argument. `GitMergeAbort` aborts a merge. Refresh status after
  success and failure, including conflicts, while preserving unsaved editor buffers.
  GitFetch/Pull/Push use ordinary Git settings without forcing changes; GitSync
  reuses the existing synchronization action. GitCommit focuses the message field.
  `GitRebase` selects a local/remote upstream just like GitMerge, or accepts an
  explicit branch argument. Rebase the current branch onto the selection without
  switching branches or creating a merge commit; cancellation does nothing.
  `GitRebaseAbort` and `GitRebaseContinue` expose native conflict recovery actions.
  Refresh status after success/failure and preserve unsaved editor buffers.

## Dialogs, pickers, and minimap

- `settings.json` contains plain user preferences. Its boolean `icons` switch
  selects glyph icons (true) or standard letters/symbols (false) for file types,
  folders, tree expanders, Git status markers, and diagnostics in Files/tabs. Load it once
  through `config.settings`; restart Neovim after editing. Default to icons when
  missing; warn and fall back safely if malformed. The string `color-palette`
  selects any JSON palette filename relative to `stdpath("config")`, or an absolute
  path. Default to `palette.json`; the current selection is `matugen.json`.
  Validate settings independently, so a bad palette setting preserves a valid
  icons setting and vice versa. Keep palette colors separate.
- Keep the complete editable palette in
  the selected JSON file as a plain list of color names and values, with no code:
  theme tokens for backgrounds/syntax/diagnostics/Git,
  status bar colors, and our highlight overrides for diffs, minimap, sidebar
  selectors, and tab separators. Keep loading, highlight definitions, and plugin
  integration in `lua/config/colors.lua`. Other modules consume that module instead
  of defining RGB values or writing their own color overrides. Feed the theme through
  its public `color_overrides` / `group_overrides` options and reapply our highlights
  after a colorscheme reload. Do not edit downloaded theme/plugin files.
  Keep `palette.json` as the base palette and fallback if the selected file is
  missing or invalid. Matugen generates `matugen.json` using a template based on
  `palette.json`, changing interface surfaces, selections, accents and terminal
  ANSI colors. Syntax, diagnostics and Git/diff colors may also use close Matugen
  replacements. Leave colors without a close match unchanged. The refinement
  hook compares against `palette.json` after each generation: maximum Oklab
  distance 0.070, and for chromatic colors (chroma >= 0.015) maximum hue shift
  35 degrees with at least 60% of the original chroma. Neutral source colors
  keep chroma <= 0.030 so gray text does not acquire a strong tint. Reject gray/green/red
  substitutions that would erase semantic distinctions, even in dark diff fills.
  The currently approved semantic substitutions are listed in `tests/color_palette.py`.
  Generate all 16 `terminal_0` through `terminal_15` colors from Dank16's matching
  `dank16.colorN.default.hex` entries, independently of syntax tokens.
- Structural UI colors have exactly three editable entries in each palette:
  `ui_background` for every editor/tool/dialog panel, panel headers, menus, and the active tab,
  `ui_bar_background` for inactive tabs, tab strip fill,
  and the status bar, and `ui_separator` for panel dividers and popup borders.
  Derive the theme's background tokens from these entries in `colors.lua`;
  do not add per-panel background RGB duplicates to JSON. Separator backgrounds
  match the adjacent dark panels, including border/close-button helper windows.
  `ui_background` may be `NONE` to inherit the terminal background; Matugen uses
  its opaque `colors.background.default.hex` value. Keep mode-badge foregrounds readable in the transparent
  case. Optional `status_accent_fg` gives the foreground for the normal-mode accent
  badge; other palettes fall back to `status_fg`.
  Matugen preserves the original background as `git_line_fg` for the inverted
  GitSigns line highlights, so transparency does not change diff text colors.
  Keep distinct colors for selections, mode badges, diff highlights, and scrollbars.
  `default.json` stores the original pre-DankShell colors in the same schema,
  with the original editor/bar/separator colors used as its three UI entries.
- Syntax and accent colors come from a portable snapshot of the active VS Code
  **Dynamic Base16 DankShell** theme from `DankLinux.dms-theme`, including syntax,
  semantic tokens, diagnostics, Git decorations, and all 16 ANSI colors.
  Do not depend on a local VS Code extension at runtime. `vsc*` names are the
  `vscode.nvim` theme API tokens; their names do not describe the imported hues.
  VS Code alpha colors are composited over the editor background into opaque RGB.
  Keep terminal ANSI colors independent from syntax tokens and preserve a visible
  minimap viewport even when the theme's current-line background matches the editor.
- Centered dialogs have a border and a clickable × in the top-right corner,
  including Plugins (Lazy), Mason, input, and composite Snacks pickers. Close the
  entire object through its owner's appropriate action, including its backdrop
  and callbacks. Closing input cancels entry instead of accepting it.
  Repeated clicks after replacing a popup can report line 0 in an underlying
  window. Share close-button screen hit testing with the blank-panel mouse guard
  so that guard does not capture the gesture before the button handles release.
  Preserve existing mouse capture while dragging scrollbars or dividers.
- Command palette and Edit configuration have consistent dividers: input must not
  overlap the preview separator, and the bottom must not have a double border.
  Preserve geometry after resizing; floating window configuration must include `relative`.
  Noice/Nui command inputs may use a separate border/padding window. Do not add
  another native border to their content window: completion must keep text in
  its original frame and place suggestions below it.
- The minimap shows structure, visible range, cursor, diagnostics, Git,
  and search. Clicking moves the cursor; the mouse wheel and dragging scroll.
  Do not extend it into terminals or left panels; hide it when the editor is narrow.
  Refresh the visible-range highlight immediately while scrolling or dragging,
  separately from the debounce for regenerating minimap text. Coalesce queued
  movements to the latest pointer position and respect the source's scrolloff
  margin so redraw does not shift the viewport again after moving the cursor.
  Use a clearly visible accent viewport background (`minimap_viewport_bg`),
  independently of the theme's current-line highlight.

## Module map and state

| File in `lua/config` unless otherwise specified | Responsibility |
| --- | --- |
| `init.lua`, `lua/config/lazy.lua` | Startup, LazyVim, imports, Lazy window |
| `options.lua`, `keymaps.lua`, `autocmds.lua` | Options, shortcuts, and events |
| `ide.lua`, `documents.lua` | Actions/menus, opening/saving/closing, document routing |
| `menu_navigation.lua` | Shared keyboard/mouse row selection, hidden menu caret and cursor restoration |
| `menu_mouse.lua` | Persistent popup gesture/release guard and recovery of orphaned click blocks |
| `panel_navigation.lua` | Alt+A tab previews, spatial panel frames, menu access and Normal Files/Symbols |
| `search.lua` | Find input, Replace button, singleton panel, active file and clickable fields |
| `project_search.lua`, `search_source.lua` | Search sidebar, pinned input/modes, streamed rg results and source navigation |
| `editor_tabs.lua`, `tabs.lua`, `tab_source.lua` | Tab bar, MRU, Tabs source |
| `layout.lua`, `sidebar.lua` | Proportions, column switching, graph |
| `projects.lua`, `project_source.lua` | Project history and tab restoration |
| `terminals.lua`, `problems.lua` | Bottom panel and visibility restoration |
| `terminal_mouse.lua` | Child mouse-reporting requests observed from terminal output |
| `debugger.lua`, `debug_source.lua`, `debugger_mouse.lua`, `breakpoints.lua` | DAP, sections, gestures, and breakpoints |
| `debugger_inspect.lua` | On-demand variable popup, expression lookup, and Ctrl+click capture |
| `git.lua`, `git_source.lua`, `git_sync.lua`, `git_commands.lua`, `diff.lua` | Status, Git operations, command palette, upstream, and editable diff |
| `git_header.lua` | Pinned Git Status header and permanent commit input geometry |
| `git_graph.lua` | Local LazyGit graph routing/rendering adapter based on commit parents |
| `git_line_blame.lua` | Current-line author/commit annotation in Normal and Insert mode |
| `rename.lua` | File/folder rename, preserved buffers/diffs, and LSP file notifications |
| `files.lua` | Files focus, file clipboard, duplicate naming, and deletion |
| `hscroll.lua`, `vscroll.lua`, `minimap.lua`, `popup_ui.lua` | Scrollbars, minimap, borders, and closing |
| `mouse_capture.lua` | Shared mouse gesture ownership for dragged widgets |
| `selection_scroll.lua` | Stable offscreen selections during wheel scrolling and restoration before editing |
| `panel_mouse.lua` | Rendered row validation, blank panel gestures, and horizontal divider dragging |
| `panel_padding.lua` | Fixed Symbols and Debug margins using window options and decorations |
| `colors.lua`, root `palette.json`, `matugen.json` and `default.json` | Selected/base/original palette data, loader, theme/status bar options, and our highlight overrides |
| `settings.lua`, root `settings.json` | User preferences, palette filename and the icons/letters switch |
| `lua/plugins/ide.lua`, `lua/plugins/minimap.lua` | Plugin options and integrations |
| `lazy-lock.json` | Pinned plugin versions |
| `tests/ui.py`, `tests/*.py`, `tests.sh` | UI/RPC client and regression scenarios |

Store state in `vim.fn.stdpath("state")`: proportions in
`desktop-ide-layout.json`, projects in `desktop-ide-projects.json`, and Discard
backups in `git-discard/`. Python caches do not belong in Git.

`KEYBINDS.md` is a brief user guide: shortcuts and basic gestures.
Layout details, the module map, and development requirements belong here. Preserve
opening the guide through F1 / Help. Do not present local clipboard bridges or
terminal workarounds as configuration requirements. Available clipboard tools and
the display environment are environment details to account for when moving the configuration.

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
  `hscroll_recovery.py`, `scrollbar_placement.py`, `scrollbar_layout.py`, `staged_diff.py`;
  terminal/Problems → `terminal_input.py`, `panels.py`,
  `debugger_panels.py`; debugger → `debugger_mouse.py`, `debugger_recovery.py`,
  `debugger_values.py`, `debug_console_input.py`; left panel/projects →
  `sidebar.py`, `sidebar_scroll.py`, `projects.py`; documents/history/dialogs →
  `documents.py`, `git_history_view.py`, `git_commit_preview.py`, `commit_scrollbar.py`,
  `outline_focus.py`, `picker_layout.py`, `popup_resize.py`;
  Git command palette and merging → `git_commands.py`; rebase → `git_rebase.py`;
  Current-line Git authorship, Insert mode, and unsaved diff attribution → `git_line_blame.py`;
  Find/Replace button, panel lifecycle, field clicks and active file → `search_replace.py`;
  Find button ownership, nested close, and repeated opening → `find_button_lifecycle.py`;
  Search sidebar, grouped line navigation and file-name mode → `project_search.py`;
  Search field/results keyboard focus, Normal highlights, scrolling and Shift+Tab → `search_keyboard.py`;
  Status-bar branch creation and publication → `git_branch_publish.py`;
  Remote branch discovery and tracked switching → `git_remote_branches.py`;
  editing → `comment_selection.py`, `editor_focus_input.py`; selection action modes,
  Escape and queued typing → `editing_modes.py`; document creation → `new_file.py`;
  Offscreen mouse/keyboard selections, copy, typing and terminal paste → `selection_scroll.py`.
  system clipboard provider selection and cross-process Copy/Cut/Paste → `clipboard.py`;
  file/folder renaming → `file_rename.py`;
  informational tree rows → `tree_messages.py`; file clicks across modes and
  recovery after a lost scrollbar/menu release → `tree_click.py`.
  Git-file clicks after a lost menu release → `git_selection.py`.
  LazyGit-compatible graph topology, ANSI author colors, selected paths and commit rows → `commit_graph.py`.
  Empty Git Status clicks → `git_empty_click.py`.
  File clipboard/focus and deletion → `file_clipboard.py`.
  File/directory creation and blank Files context menus → `file_create_menu.py`.
  Immediate Symbols refresh → `symbols_refresh.py`; vertical boundaries → `sidebar_vertical_scroll.py`.
  Symbols following cursor movement in Normal/Insert → `symbols_follow.py`.
  Automatic vertical bars and combined-axis geometry → `panel_scrollbars.py`.
  Terminal scrollback gestures, wheel boundaries, and return to input → `terminal_scrollbar.py`.
  Terminal wheel routing to mouse-aware child applications versus history → `terminal_wheel.py`.
  Empty panel/list clicks → `panel_empty_click.py`.
  Dialog layers and pinned Git header → `scrollbar_layering.py`.
  Top menu switching and repeated-heading clicks → `menu_switch.py`.
  Tab/panel keyboard previews, mouse cancellation and terminal key isolation → `panel_navigation.py`.
  Completion mapping flags and real editor arrows after panel/tab selection → `panel_navigation_keys.py`.
  Closing previewed cards with q, repeated selection and unsaved prompts → `panel_tab_close.py`.
  Held/queued q across closes, dialogs and the final card → `panel_tab_repeat.py`.
  Git keyboard rows/context menus and Commit message focus/mode → `git_keyboard.py`.
  Normal terminal list and console opening without layout changes → `terminal_navigation.py`.
  Global menu clicks above diff columns across resizing → `diff_menu.py`.
  Terminal keypad navigation and preserved numeric input → `terminal_keypad.py`.
  Command input geometry while completion is visible → `cmdline_popup.py`.
  Command-line save/close without destroying editor panels → `write_close.py`.
  Vertical sidebar dividers beside blank lists and scrollbars → `sidebar_resize.py`.
  Git Status visibility beside an oversized saved commit graph → `git_panel_layout.py`.
  Git divider clicks/drags versus real status-bar buttons → `git_divider.py`.
  Icon/letter preferences and invalid/missing settings fallback → `settings.py`.
  Palette filenames, transparency, syntax/Git preservation and fallbacks → `color_palette.py`.
  Rendered active-tab transparency, inactive fill and tab switching → `transparent_tabs.py`.
  Added-file diff wheel scrolling and Select-mode panel scrolling → `diff_vertical_scroll.py`.
  Precise horizontal diff dragging in Normal/Insert → `diff_horizontal_drag.py`.
  Files following/revealing diff documents → `diff_files_tree.py`.
  Minimap gestures and immediate viewport updates → `minimap_drag.py`.
  Minimap/horizontal drag releases over other controls → `scroll_drag_capture.py`.
- Check visible behavior and actual gestures. For regressions, consider a test
  that fails before the fix. Documentation-only changes do not require the full UI suite.
  Run `git diff --check`.
- After Lua changes, mention restarting Neovim; changes to Markdown/.gitignore
  do not require a restart.
- Follow the global logging instructions: append diagnostics, tests, and operational
  actions to `~/codex.log` with timestamp, directory, complete command, stdout/stderr,
  and exit status. Output must also remain visible in the session.
  Do not log commands whose purpose is to create, edit, or delete file contents.
