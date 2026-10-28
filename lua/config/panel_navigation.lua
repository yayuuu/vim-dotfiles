-- Preview tabs and spatial panel choices without changing focus or documents.
local M = {}
local api = vim.api
local namespace = api.nvim_create_namespace("DesktopPanelNavigation")
local hidden_cursor = "a:DesktopPanelPickerCursor"
local panel_cursor = "a:DesktopPanelCursor"
local modes = { "n", "i", "x", "s", "t" }
local function valid(win) return win and api.nvim_win_is_valid(win) end

local function rect(win)
  if win == "menu" then return { row = 0, col = 0, width = vim.o.columns, height = 1 } end
  local p = api.nvim_win_get_position(win)
  local buf = api.nvim_win_get_buf(win)
  local bordered = vim.b[buf].ide_git_input or vim.b[buf].ide_search_input
  -- The API height already includes the winbar, unlike getwininfo().height.
  return { row = p[1], col = p[2], width = api.nvim_win_get_width(win) + (bordered and 2 or 0),
    height = api.nvim_win_get_height(win) + (bordered and 2 or 0) }
end

local function close_overlays(state)
  for _, win in ipairs(state.overlays) do if valid(win) then api.nvim_win_close(win, true) end end
  state.overlays = {}
end

local function overlay(state, row, col, width, height, text, spans)
  if width < 1 or height < 1 then return end
  local buf = api.nvim_create_buf(false, true)
  vim.bo[buf].bufhidden = "wipe"
  vim.b[buf].ide_navigation_overlay = true
  api.nvim_buf_set_lines(buf, 0, -1, false, text)
  local win = api.nvim_open_win(buf, false, { relative = "editor", row = row, col = col,
    width = width, height = height, style = "minimal", border = "none", focusable = false,
    mouse = false, noautocmd = true, zindex = 45 })
  vim.wo[win].winhighlight = "Normal:DesktopNavigationFrame,EndOfBuffer:DesktopNavigationFrame"
  vim.wo[win].winbar = ""
  for index, span in ipairs(spans or {}) do
    local last = spans[index + 1] and spans[index + 1].start or #text[1]
    if last > span.start then
      local group = span.groups and span.groups[#span.groups] or span.group
      if group then api.nvim_buf_set_extmark(buf, namespace, 0, span.start, { end_col = last, hl_group = group }) end
    end
  end
  state.overlays[#state.overlays + 1] = win
end

local function frame(state, r)
  if r.height < 3 then
    overlay(state, r.row, r.col, r.width, 1, { " Menu " .. string.rep("─", math.max(0, r.width - 6)) })
    return
  end
  local width = math.max(0, r.width - 2)
  overlay(state, r.row, r.col, r.width, 1, { "╭" .. string.rep("─", width) .. "╮" })
  overlay(state, r.row + r.height - 1, r.col, r.width, 1, { "╰" .. string.rep("─", width) .. "╯" })
  local edge = {}; for _ = 1, r.height - 2 do edge[#edge + 1] = "│" end
  overlay(state, r.row + 1, r.col, 1, r.height - 2, edge)
  overlay(state, r.row + 1, r.col + r.width - 1, 1, r.height - 2, edge)
end

local function candidates()
  local result = { "menu" }
  for _, win in ipairs(api.nvim_tabpage_list_wins(0)) do
    local buf = api.nvim_win_get_buf(win)
    if (api.nvim_win_get_config(win).relative == "" and vim.bo[buf].filetype ~= "ide_diff_toolbar")
      or vim.b[buf].ide_git_input or vim.b[buf].ide_search_input then
      result[#result + 1] = win
    end
  end
  return result
end

local function select_tabs(state)
  local win = state.target
  if win == "menu" or not valid(win) then return false end
  local buf = api.nvim_win_get_buf(win)
  local ft = vim.bo[buf].filetype
  local ide = require("config.ide")
  local diff = require("config.diff").active
  local diff_pane = diff and (win == diff.left or win == diff.right)
  local sidebar, tree = require("config.sidebar").state()
  if sidebar and (ft == "neo-tree" or ft == "aerial" or ft == "ide_git_history" or ft:match("^dapui_")
    or vim.b[buf].ide_search_input or vim.b[buf].ide_git_input) then
    state.kind, state.tree, state.items = "sidebar", tree, vim.deepcopy(require("neo-tree").config.source_selector.sources)
    for index, item in ipairs(state.items) do if item.source == sidebar.name then state.index = index end end
  elseif (ide.is_document(buf) or diff_pane) and not ide.is_tool_tab() then
    local strip = require("config.editor_tabs")
    strip.draw()
    state.kind, state.items, state.first = "documents", vim.deepcopy(strip.ids or {}), strip.first
    for index, item in ipairs(state.items) do if item == (diff_pane and diff.buf or buf) then state.index = index end end
  else
    return false
  end
  if #state.items == 0 then return false end
  state.phase = "tabs"
  return true
end

local function sidebar_bar(state)
  local tree = state.tree
  if not valid(tree) then M.cancel(); return end
  local source = require("neo-tree.sources.manager").get_state_for_window(tree)
  if not source then M.cancel(); return end
  local r = rect(tree)
  local format = require("neo-tree.ui.selector").get_selector(source, r.width)
  -- Keep Neo-tree's own truncation, padding and click geometry. The public
  -- selector returns one click span per source; recolor only the preview span.
  local starts = {}
  for first in format:gmatch("()%%%d+@v:lua%.___neotree_selector_click@") do starts[#starts + 1] = first end
  local first, last = starts[state.index], (starts[state.index + 1] or (#format + 1)) - 1
  if first then
    local chunk = format:sub(first, last):gsub("%%#[^#]+#", "%%#DesktopNavigationTab#")
    format = format:sub(1, first - 1) .. chunk .. format:sub(last + 1)
  end
  local evaluated = api.nvim_eval_statusline(format, { winid = tree, use_winbar = true, maxwidth = r.width, highlights = true })
  overlay(state, r.row, r.col, r.width, 1, { evaluated.str }, evaluated.highlights)
end

function M.show()
  local state = M.state
  if not state then return end
  close_overlays(state)
  if state.phase == "panels" then
    if state.target ~= "menu" and not valid(state.target) then M.cancel(); return end
    frame(state, rect(state.target))
  elseif state.kind == "sidebar" then
    sidebar_bar(state)
  else
    local strip = require("config.editor_tabs")
    strip.preview = state.items[state.index]
    local visible = false
    for _, hit in ipairs(strip.hits or {}) do if hit.id == strip.preview then visible = true; break end end
    if not visible then strip.first = state.index end
    strip.draw()
  end
end

local function restore_maps(state)
  if not api.nvim_buf_is_valid(state.buf) then return end
  for _, binding in ipairs(state.bindings) do
    pcall(vim.keymap.del, binding.mode, binding.key, { buffer = state.buf })
    local saved = binding.saved
    if saved then
      vim.keymap.set(binding.mode, binding.key, saved.callback or saved.rhs, { buffer = state.buf,
        expr = saved.expr == 1, silent = saved.silent == 1, nowait = saved.nowait == 1,
        -- The API returns 0/1; Lua treats 0 as true. Preserve false explicitly
        -- for completion callbacks that already return encoded arrow keys.
        remap = saved.noremap == 0, desc = saved.desc, replace_keycodes = saved.replace_keycodes == 1 })
    end
  end
end

function M.cancel(keep_view)
  M.closing = nil
  local state = M.state
  if not state then return end
  M.state = nil
  restore_maps(state)
  close_overlays(state)
  local strip = require("config.editor_tabs")
  strip.preview = nil
  if not keep_view and state.first then strip.first = state.first end
  strip.draw()
  if vim.o.guicursor == hidden_cursor then vim.o.guicursor = state.guicursor end
end

function M.arrow(direction)
  local state = M.state
  if not state then return end
  if state.phase == "tabs" then
    if #state.items > 0 and (direction == "left" or direction == "right") then
      state.index = (state.index - 1 + (direction == "right" and 1 or -1)) % #state.items + 1
      M.show()
    end
    return
  end
  local from = rect(state.target)
  local vertical = direction == "up" or direction == "down"
  local sign = (direction == "down" or direction == "right") and 1 or -1
  local center = vertical and from.row + from.height / 2 or from.col + from.width / 2
  local cross = vertical and from.col + from.width / 2 or from.row + from.height / 2
  local best, distance
  for _, target in ipairs(candidates()) do
    if target ~= state.target then
      local r = rect(target)
      local along = vertical and r.row + r.height / 2 or r.col + r.width / 2
      local across = vertical and r.col + r.width / 2 or r.row + r.height / 2
      local low, high = vertical and r.col or r.row, vertical and r.col + r.width or r.row + r.height
      if (along - center) * sign > 0 then
        local gap = math.max(low - cross, cross - high, 0)
        local score = gap * 1000 + math.abs(along - center) * 10 + math.abs(across - cross)
        if not distance or score < distance then best, distance = target, score end
      end
    end
  end
  if best then state.target = best; M.show() end
end

function M.confirm()
  local state = M.state
  if not state then return end
  local target, item = state.target, state.items and state.items[state.index]
  M.cancel(true)
  if state.phase == "tabs" then
    if state.kind == "sidebar" then
      if valid(state.tree) then api.nvim_set_current_win(state.tree) end
      vim.cmd("stopinsert")
      require("neo-tree.command").execute({ source = item.source, action = "focus" })
      vim.cmd("stopinsert")
    else
      if valid(target) then api.nvim_set_current_win(target) end
      if item and api.nvim_buf_is_valid(item) then require("config.ide").open_file(nil, item) end
      if vim.bo.modifiable and not vim.bo.readonly and (vim.bo.buftype == "" or vim.b.ide_diff_file) then vim.cmd("startinsert") end
    end
  elseif target == "menu" then
    require("config.ide").menu("File", true)
  elseif valid(target) then
    api.nvim_set_current_win(target)
    local ft = vim.bo.filetype
    if ft == "neo-tree" or ft == "aerial" or ft == "ide_terminal_list" or ft == "ide_git_history" then vim.cmd("stopinsert")
    elseif vim.b.ide_git_input or vim.b.ide_search_input then vim.cmd("startinsert!")
    elseif vim.bo.buftype == "terminal" then vim.cmd("startinsert")
    elseif require("config.ide").is_document(api.nvim_get_current_buf()) and vim.bo.modifiable and not vim.bo.readonly then
      vim.cmd("startinsert")
    end
  end
end

function M.close_tab()
  local state = M.state
  if not state or state.phase ~= "tabs" or state.kind ~= "documents" or #state.items == 0 then return end
  local buf = state.items[state.index]
  M.cancel(true)
  M.closing = state
  -- Reuse the document close action, including its unsaved-changes dialog.
  -- Resume after dialog teardown and after closing an active diff's windows.
  local ok, err = pcall(require("config.ide").close_buffer, buf, function(closed)
    vim.schedule(function()
      if M.closing ~= state then return end
      M.closing = nil
      if M.state then return end
      local next_buf
      for offset = 0, #state.items - 1 do
        local candidate = state.items[(state.index - 1 + (closed and 1 or 0) + offset) % #state.items + 1]
        if api.nvim_buf_is_valid(candidate) and vim.bo[candidate].buflisted then next_buf = candidate; break end
      end
      api.nvim_set_current_win(valid(state.origin) and state.origin or require("config.ide").editor_window())
      M.toggle()
      local replacement = M.state
      if not replacement then return end
      replacement.target = valid(state.target) and state.target or require("config.ide").editor_window()
      if not select_tabs(replacement) or replacement.kind ~= "documents" then return end
      local document = api.nvim_win_get_buf(replacement.target)
      if not next_buf and api.nvim_buf_get_name(document) == "" and not vim.bo[document].modified
        and api.nvim_buf_line_count(document) == 1 and api.nvim_buf_get_lines(document, 0, 1, false)[1] == "" then
        -- Closing the last real card leaves a placeholder editor. Keep owning
        -- input until Enter/Esc/click, instead of typing the remaining repeats.
        replacement.phase, replacement.items = "tabs", {}
      end
      for index, item in ipairs(replacement.items) do if item == next_buf then replacement.index = index; break end end
      M.show()
      if state.accept then M.confirm() end
    end)
  end)
  if not ok then M.closing = nil; error(err) end
end

local function bind(state)
  local keys = { ["<M-a>"] = M.toggle, ["<CR>"] = M.confirm, ["<Esc>"] = M.cancel, ["<C-c>"] = M.cancel,
    ["<Left>"] = function() M.arrow("left") end, ["<Right>"] = function() M.arrow("right") end,
    ["<Up>"] = function() M.arrow("up") end, ["<Down>"] = function() M.arrow("down") end }
  for code = 32, 126 do keys[code == 60 and "<lt>" or string.char(code)] = "<Nop>" end
  keys.q = M.close_tab
  for _, key in ipairs({ "<BS>", "<Del>", "<Tab>", "<S-Tab>", "<PageUp>", "<PageDown>" }) do keys[key] = "<Nop>" end
  for _, mode in ipairs(modes) do
    local saved = {}
    for _, map in ipairs(api.nvim_buf_get_keymap(state.buf, mode)) do saved[vim.keycode(map.lhs)] = map end
    for key, action in pairs(keys) do
      state.bindings[#state.bindings + 1] = { key = key, mode = mode, saved = saved[vim.keycode(key)] }
      vim.keymap.set(mode, key, action, { buffer = state.buf, silent = true, nowait = true })
    end
  end
end

function M.toggle()
  local state = M.state
  if state then
    if state.phase == "panels" and select_tabs(state) then
      M.show()
    else
      M.cancel(true)
      require("config.ide").menu("File", true)
    end
    return
  end
  local ide = require("config.ide")
  if vim.bo.filetype == "NvMenu" then ide.close_menu() end
  local win, buf = api.nvim_get_current_win(), api.nvim_get_current_buf()
  state = { origin = win, buf = buf, target = win, phase = "panels", index = 1, bindings = {}, overlays = {}, guicursor = vim.o.guicursor }
  local found = false
  for _, target in ipairs(candidates()) do if target == win then found = true end end
  if not found then state.target = ide.editor_window() end
  M.state = state
  bind(state)
  vim.o.guicursor = hidden_cursor
  M.show()
end

function M.context()
  local win = api.nvim_get_current_win()
  local row, items = api.nvim_win_get_cursor(win)[1]
  if vim.bo.filetype == "ide_git_history" then
    items = require("config.sidebar").history_menu(row)
  elseif vim.bo.filetype == "neo-tree" then
    local state = require("neo-tree.sources.manager").get_state_for_window(win)
    local node = state and state.tree and state.tree:get_node()
    if state and state.name == "git_status" then
      if node and node.type == "message" then return end
      items = require("config.git").menu(state, node)
    elseif state and state.name == "filesystem" and node and (node.type == "file" or node.type == "directory") then
      items = require("config.files").menu(state, node)
    end
  end
  if not items then return end
  local point = vim.fn.screenpos(win, row, 1)
  require("config.ide").popup(items, nil, { mouse = { screenrow = point.row, screencol = point.col + 2 } })
end

local function panel_mode()
  if M.state then return end
  local ft = vim.bo.filetype
  local debug = package.loaded["config.debugger_navigation"]
  local debug_list = debug and debug.handles(api.nvim_get_current_win()) and not debug.is_input(api.nvim_get_current_win())
  local source = ft == "neo-tree" and require("neo-tree.sources.manager").get_state_for_window(api.nvim_get_current_win())
  if debug_list or ft == "aerial" or ft == "ide_terminal_list" or ft == "ide_git_history"
    or (source and (source.name == "filesystem" or source.name == "git_status" or source.name == "search")) then
    if not M.panel_guicursor then M.panel_guicursor = vim.o.guicursor end
    vim.o.guicursor = panel_cursor
    vim.wo.cursorline = true
    vim.wo.cursorlineopt = "both"
    if (debug_list or ft == "aerial" or ft == "ide_terminal_list" or ft == "ide_git_history")
      and not vim.wo.winhighlight:find("CursorLine:", 1, true) then
      vim.wo.winhighlight = vim.wo.winhighlight .. ",CursorLine:NeoTreeCursorLine"
    end
    local mode = vim.fn.mode()
    if mode:match("^i") then vim.cmd("stopinsert")
    elseif mode:match("^[vVsS]") or mode == "\22" or mode == "\19" then
      api.nvim_feedkeys(vim.keycode("<Esc>"), "ni", false)
    end
  elseif M.panel_guicursor then
    if vim.o.guicursor == panel_cursor then vim.o.guicursor = M.panel_guicursor end
    M.panel_guicursor = nil
  end
end

function M.setup()
  local function highlights()
    for _, group in ipairs({ "DesktopPanelCursor", "DesktopPanelPickerCursor" }) do
      api.nvim_set_hl(0, group, { reverse = true, blend = 100 })
    end
  end
  highlights()
  local group = api.nvim_create_augroup("DesktopPanelNavigation", { clear = true })
  api.nvim_create_autocmd("ColorScheme", { group = group, callback = highlights })
  api.nvim_create_autocmd({ "WinEnter", "BufEnter", "FileType", "ModeChanged" }, { group = group, callback = function()
    -- Aerial binds buffers while temporarily visiting a window without focus
    -- events. Apply global cursor styling only after that operation completes.
    if M.mode_pending then return end
    M.mode_pending = true
    vim.schedule(function() M.mode_pending = false; panel_mode() end)
  end })
  api.nvim_create_autocmd("WinLeave", { group = group, callback = function()
    if M.state and api.nvim_get_current_win() == M.state.origin then M.cancel() end
    if M.panel_guicursor then
      if vim.o.guicursor == panel_cursor then vim.o.guicursor = M.panel_guicursor end
      M.panel_guicursor = nil
    end
  end })
  api.nvim_create_autocmd("BufLeave", { group = group, callback = function(event)
    if M.state and event.buf == M.state.buf then M.cancel() end
  end })
  api.nvim_create_autocmd({ "WinResized", "VimResized" }, { group = group, callback = function()
    if M.state then local state = M.state; vim.schedule(function() if M.state == state then M.show() end end) end
  end })
  api.nvim_create_autocmd("WinClosed", { group = group, callback = function(event)
    if M.state and tonumber(event.match) == M.state.origin then M.cancel() end
  end })
  local presses = {}
  for _, modifier in ipairs({ "", "S-", "C-", "A-" }) do
    for _, prefix in ipairs({ "", "2-", "3-", "4-" }) do
      for _, button in ipairs({ "Left", "Right", "Middle" }) do
        presses[vim.keycode("<" .. modifier .. prefix .. button .. "Mouse>")] = true
      end
    end
  end
  vim.on_key(function(key, typed)
    -- Keep a scrolled preview in place so the native click hits the tab the
    -- user actually saw, rather than a different card at its restored column.
    if (M.state or M.closing) and (presses[key] or presses[typed]) then M.cancel(true) end
    if M.closing then
      local document_input = api.nvim_win_get_config(0).relative == "" and vim.fn.mode():match("^[nivVsStT\22\19]")
      if typed == vim.keycode("<Esc>") or typed == vim.keycode("<C-c>") then
        M.cancel(true)
        if document_input then return "" end
        return -- Let the real save dialog receive its dismissal key too.
      end
      -- Buffer-local mappings disappear while the shared close action switches
      -- buffers and tears down dialogs. Own input across that entire gap, but
      -- leave actual dialog input (such as a Save as filename) alone.
      if document_input then
        if typed == vim.keycode("<CR>") then M.closing.accept = true end
        if typed ~= "" or key == "q" then return "" end
      end
    end
  end, namespace)
  vim.keymap.set(modes, "<M-a>", M.toggle, { desc = "Choose panels / tabs / menu" })
  vim.keymap.set(modes, "<S-F10>", M.context, { desc = "Selected item context menu" })
  -- Kitty's optional standalone LEFT_ALT code; ordinary terminals do not send
  -- modifier-only events. Shift+F10 remains available without that protocol.
  vim.keymap.set("n", "<Char-57443>", M.context, { desc = "Selected file context menu (left Alt)" })
  vim.keymap.set("n", "<M-Char-57443>", M.context, { desc = "Selected file context menu (left Alt)" })
end

return M
