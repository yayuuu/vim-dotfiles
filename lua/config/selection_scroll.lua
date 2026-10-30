-- Keep a logical cursor/range while scrolling clamps the native caret.
local M = {}
local api = vim.api
local namespace = api.nvim_create_namespace("DesktopSelectionScroll")
local modes = { v = "v", V = "V", ["\22"] = "\22", s = "v", S = "V", ["\19"] = "\22" }
local hidden_cursor = "a:DesktopSelectionScrollCursor"
local original_paste

local function valid(win) return win and api.nvim_win_is_valid(win) end
local function current_mode()
  local mode = vim.fn.mode()
  return mode:match("^i") and "i" or mode
end

local function clear()
  local state = M.state
  if not state then return end
  M.state = nil
  if api.nvim_buf_is_valid(state.buf) then api.nvim_buf_clear_namespace(state.buf, namespace, 0, -1) end
  if valid(state.win) then
    if vim.wo[state.win].winhighlight == state.mask then
      vim.wo[state.win].winhighlight = state.winhighlight
    else
      -- Preserve any mappings added by another integration during scrolling.
      local entries, restore = {}, {}
      for entry in vim.wo[state.win].winhighlight:gmatch("[^,]+") do
        local name, target = entry:match("^([^:]+):(.+)$")
        if target == "DesktopSelectionScrollMask" and (name == "Visual" or name == "VisualNOS") then
          restore[name] = true
        else
          entries[#entries + 1] = entry
        end
      end
      for entry in state.winhighlight:gmatch("[^,]+") do
        if restore[entry:match("^([^:]+):")] then entries[#entries + 1] = entry end
      end
      vim.wo[state.win].winhighlight = table.concat(entries, ",")
    end
    vim.wo[state.win].scrolloff = state.scrolloff
    vim.wo[state.win].sidescrolloff = state.sidescrolloff
    vim.wo[state.win].cursorline = state.cursorline
    local scroll = package.loaded["config.hscroll"]
    if scroll and scroll.virtual and scroll.virtual[state.win] ~= nil then
      vim.wo[state.win].virtualedit = scroll.virtual[state.win]
      scroll.virtual[state.win] = nil
    end
  end
  if vim.o.guicursor == hidden_cursor then vim.o.guicursor = state.guicursor end
end

function M.restore()
  local state = M.state
  if not state then return end
  local restore = valid(state.win) and api.nvim_get_current_win() == state.win
    and api.nvim_win_get_buf(state.win) == state.buf
    and (state.selection and modes[vim.fn.mode()] ~= nil or not state.selection and current_mode() == state.mode)
  clear()
  if restore then
    local cursor = vim.deepcopy(state.cursor)
    cursor[5] = state.curswant + 1
    vim.fn.setpos(".", cursor)
  end
end

local function refresh()
  local state = M.state
  if not state then return end
  if not valid(state.win) or api.nvim_get_current_win() ~= state.win
    or api.nvim_win_get_buf(state.win) ~= state.buf
    or (state.selection and not modes[vim.fn.mode()] or not state.selection and current_mode() ~= state.mode)
    or api.nvim_buf_get_changedtick(state.buf) ~= state.tick then clear(); return end
  local position = vim.fn.screenpos(state.win, state.cursor[2], state.cursor[3])
  local view = vim.fn.winsaveview()
  local info = vim.fn.getwininfo(state.win)[1]
  local visible = position.row > 0 and position.col > 0
    and state.virtcol > view.leftcol and state.virtcol <= view.leftcol + info.width - info.textoff
  if visible then
    vim.fn.setpos(".", state.cursor)
    view.lnum, view.col, view.coladd = state.cursor[2], state.cursor[3] - 1, state.cursor[4]
    view.curswant = state.curswant
    vim.fn.winrestview(view)
    if vim.o.guicursor == hidden_cursor then vim.o.guicursor = state.guicursor end
    vim.wo[state.win].cursorline = state.cursorline
  else
    vim.o.guicursor = hidden_cursor
    vim.wo[state.win].cursorline = false
  end
end

local function freeze(win, horizontal)
  local mode = current_mode()
  local buf = api.nvim_win_get_buf(win)
  local selection = modes[mode] ~= nil
  if not selection and not (horizontal and (mode == "n" or mode == "i")) then return end
  if M.state and (M.state.win ~= win or M.state.buf ~= buf or M.state.mode ~= mode) then clear() end
  if M.state then return end
  local anchor, cursor = selection and vim.fn.getpos("v") or nil, vim.fn.getpos(".")
  local regions = selection and vim.fn.getregionpos(anchor, cursor, { type = modes[mode], exclusive = vim.o.selection == "exclusive" }) or {}
  local original = vim.wo[win].winhighlight
  local entries = {}
  for entry in original:gmatch("[^,]+") do
    if not entry:match("^Visual:") and not entry:match("^VisualNOS:") then entries[#entries + 1] = entry end
  end
  if selection then
    entries[#entries + 1] = "Visual:DesktopSelectionScrollMask"
    entries[#entries + 1] = "VisualNOS:DesktopSelectionScrollMask"
  else
    entries = { original }
  end
  M.state = { win = win, buf = buf, anchor = anchor, cursor = cursor, mode = mode,
    selection = selection, virtcol = vim.fn.virtcol("."), curswant = vim.fn.winsaveview().curswant,
    tick = api.nvim_buf_get_changedtick(buf), winhighlight = original, mask = table.concat(entries, ","),
    scrolloff = vim.wo[win].scrolloff, sidescrolloff = vim.wo[win].sidescrolloff,
    cursorline = vim.wo[win].cursorline, guicursor = vim.o.guicursor }
  vim.wo[win].winhighlight = M.state.mask
  vim.wo[win].scrolloff = 0
  vim.wo[win].sidescrolloff = 0
  local function mark(row, column, end_row, end_column, eol)
    api.nvim_buf_set_extmark(buf, namespace, row, column, {
      end_row = end_row, end_col = end_column, hl_group = "DesktopSelectionScrollRange",
      hl_eol = eol, priority = 250,
    })
  end
  local function length(line) return #(api.nvim_buf_get_lines(buf, line - 1, line, false)[1] or "") end
  if #regions > 0 and modes[mode] ~= "\22" then
    -- Keep large character/line selections to one or two decorations.
    local first, last = regions[1][1], regions[#regions][2]
    if modes[mode] == "V" then
      mark(first[2] - 1, 0, last[2], 0, true)
    elseif first[2] == last[2] then
      mark(first[2] - 1, math.min(length(first[2]), first[3] - 1), last[2] - 1, math.min(length(last[2]), last[3]), false)
    else
      mark(first[2] - 1, math.min(length(first[2]), first[3] - 1), last[2] - 1, 0, true)
      mark(last[2] - 1, 0, last[2] - 1, math.min(length(last[2]), last[3]), false)
    end
  else
    for _, region in ipairs(regions) do
      local first, last = region[1], region[2]
      mark(first[2] - 1, math.min(length(first[2]), math.max(0, first[3] - 1)),
        last[2] - 1, math.min(length(last[2]), last[3]), false)
    end
  end
end

local function document(win)
  if not valid(win) or api.nvim_win_get_config(win).relative ~= ""
    or require("config.ide").is_tool_tab(api.nvim_win_get_tabpage(win)) then return false end
  local buf = api.nvim_win_get_buf(win)
  return require("config.ide").is_document(buf) or vim.b[buf].ide_diff_before ~= nil
end

function M.horizontal(win)
  local current = api.nvim_get_current_win()
  if current ~= win then
    local diff = require("config.diff").active
    if not diff or (win ~= diff.left and win ~= diff.right) or (current ~= diff.left and current ~= diff.right) then return end
  end
  if document(current) then freeze(current, true) end
end

function M.setup()
  if not original_paste then
    original_paste = vim.paste
    vim.paste = function(lines, phase)
      M.restore()
      return original_paste(lines, phase)
    end
  end
  local function range_highlight()
    local state = M.state
    -- get_hl honors the current window's remapping; read the unmasked Visual.
    if state and valid(state.win) and api.nvim_get_current_win() == state.win then
      vim.wo[state.win].winhighlight = state.winhighlight
      api.nvim_set_hl(0, "DesktopSelectionScrollRange", api.nvim_get_hl(0, { name = "Visual", link = false }))
      vim.wo[state.win].winhighlight = state.mask
    else
      api.nvim_set_hl(0, "DesktopSelectionScrollRange", api.nvim_get_hl(0, { name = "Visual", link = false }))
    end
  end
  api.nvim_set_hl(0, "DesktopSelectionScrollMask", {})
  range_highlight()
  api.nvim_set_hl(0, "DesktopSelectionScrollCursor", { reverse = true, blend = 100 })
  local group = api.nvim_create_augroup("DesktopSelectionScroll", { clear = true })
  api.nvim_create_autocmd("ColorScheme", { group = group, callback = function()
    api.nvim_set_hl(0, "DesktopSelectionScrollMask", {})
    range_highlight()
    api.nvim_set_hl(0, "DesktopSelectionScrollCursor", { reverse = true, blend = 100 })
  end })
  api.nvim_create_autocmd("WinScrolled", { group = group, callback = function() vim.schedule(refresh) end })
  api.nvim_create_autocmd({ "BufLeave", "WinLeave" }, { group = group, callback = M.restore })
  api.nvim_create_autocmd({ "ModeChanged", "BufWipeout", "WinClosed", "WinResized", "VimResized" }, { group = group, callback = function()
    if M.state then vim.schedule(refresh) end
  end })
  local wheels, clicks = {}, {}
  for _, modifier in ipairs({ "", "S-" }) do
    for _, direction in ipairs({ "Up", "Down", "Left", "Right" }) do
      wheels[vim.keycode("<" .. modifier .. "ScrollWheel" .. direction .. ">")] = modifier == "S-" or direction == "Left" or direction == "Right"
    end
  end
  for _, modifier in ipairs({ "", "S-", "C-", "A-" }) do
    for _, prefix in ipairs({ "", "2-", "3-", "4-" }) do
      for _, button in ipairs({ "Left", "Right", "Middle" }) do
        clicks[vim.keycode("<" .. modifier .. prefix .. button .. "Mouse>")] = button
      end
    end
  end
  vim.on_key(function(key, typed)
    if require("config.mouse_capture").blocked(key, typed) then return end
    if wheels[typed] ~= nil or wheels[key] ~= nil then
      local win = vim.fn.getmousepos().winid
      local horizontal = wheels[typed] or wheels[key]
      if win == api.nvim_get_current_win() and document(win) then
        freeze(win, horizontal)
        vim.schedule(refresh)
      end
      return
    end
    if not M.state or typed == "" or typed == vim.keycode("<MouseMove>") then return end
    local click = clicks[typed] or clicks[key]
    local win = vim.fn.getmousepos().winid
    if click == "Left" and valid(win) and vim.b[api.nvim_win_get_buf(win)].ide_hscroll then return end
    if click == "Left" then clear() else M.restore() end
  end, namespace)
end

return M
