local M = { bars = {}, cache = {} }
local api = vim.api
local function valid(win) return win and api.nvim_win_is_valid(win) end
local sidebar_types = { ["neo-tree"] = true, aerial = true, ide_git_history = true,
  dapui_scopes = true, dapui_breakpoints = true, dapui_stacks = true, dapui_watches = true }
local function sidebar(win)
  return valid(win) and api.nvim_win_get_config(win).relative == ""
    and sidebar_types[vim.bo[api.nvim_win_get_buf(win)].filetype] == true
end
local function editor(win)
  if not valid(win) or api.nvim_win_get_config(win).relative ~= "" then return false end
  if require("config.ide").is_tool_tab(api.nvim_win_get_tabpage(win)) then return false end
  local buf = api.nvim_win_get_buf(win)
  return sidebar(win) or vim.bo[buf].buftype == "" or vim.b[buf].ide_diff_file or vim.b[buf].ide_diff_before
end
local function display_width(line)
  -- NUL turns a Lua string into a Vim Blob. Measure its visible ^@ form only;
  -- the binary buffer itself must keep its original bytes.
  return vim.fn.strdisplaywidth((line:gsub("%z", "^@")))
end
local function extent(win)
  local buf = api.nvim_win_get_buf(win)
  local tick, tabstop = api.nvim_buf_get_changedtick(buf), vim.bo[buf].tabstop
  local cached = M.cache[buf]
  if not cached or cached.tick ~= tick or cached.tabstop ~= tabstop then
    local width = 0
    api.nvim_win_call(win, function()
      for _, line in ipairs(api.nvim_buf_get_lines(buf, 0, -1, false)) do
        width = math.max(width, display_width((line:gsub("%s+$", ""))))
      end
    end)
    cached = { tick = tick, tabstop = tabstop, width = width }; M.cache[buf] = cached
  end
  local available = api.nvim_win_get_width(win) - vim.fn.getwininfo(win)[1].textoff
  local maps = package.loaded["neominimap.window.float.window_map"]
  local map = maps and maps.get_minimap_winid(win)
  if map then available = available - api.nvim_win_get_width(map) end
  return cached.width, math.max(1, available)
end
function M.bounds(win)
  local width, available = extent(win)
  local diff = require("config.diff").active
  if diff and (win == diff.left or win == diff.right) and valid(diff.left) and valid(diff.right) then
    local old, oldavail = extent(diff.left)
    local new, newavail = extent(diff.right)
    width, available = math.max(old, new), math.min(oldavail, newavail)
  end
  return math.max(0, width - available), available, width
end
function M.close(win)
  local bar = M.bars[win]
  if bar and valid(bar.win) then api.nvim_win_close(bar.win, true) end
  M.bars[win] = nil
end
function M.set(win, column)
  if not valid(win) then return end
  local maximum = M.bounds(win)
  column = math.floor(math.max(0, math.min(maximum, column)))
  local wins = { win }
  local diff = require("config.diff").active
  if diff and (win == diff.left or win == diff.right) then wins = { diff.left, diff.right } end
  M.syncing = true
  for _, target in ipairs(wins) do
    if valid(target) then api.nvim_win_call(target, function()
      local view = vim.fn.winsaveview()
      -- Neovim keeps the caret in the viewport. Move it by the scroll delta,
      -- just as its native zl/zh commands do, or redraw undoes the scroll.
      local _, available = extent(target)
      local margin = math.min(vim.wo.sidescrolloff, math.floor(available / 3))
      local current = vim.fn.virtcol(".") - 1
      local offset = math.max(margin, math.min(available - margin - 1, current - view.leftcol))
      local wanted = column + offset
      local bytecol = vim.fn.virtcol2col(target, view.lnum, wanted + 1)
      view.col = math.max(0, bytecol - 1)
      local line = api.nvim_buf_get_lines(0, view.lnum - 1, view.lnum, false)[1] or ""
      local last = display_width(line)
      view.coladd = math.max(0, wanted - math.max(0, last - 1))
      if view.coladd > 0 then
        M.virtual = M.virtual or {}
        if M.virtual[target] == nil then M.virtual[target] = vim.wo.virtualedit end
        vim.wo.virtualedit = "all"
      end
      view.curswant, view.leftcol, view.skipcol = wanted, column, 0
      vim.fn.winrestview(view)
    end) end
  end
  M.syncing = false
  M.refresh()
end
local function make(win)
  local diff = require("config.diff")
  local busy = diff.busy; diff.busy = true
  local buf, barwin
  local ok, err = pcall(function()
    buf = api.nvim_create_buf(false, true)
    vim.bo[buf].bufhidden = "wipe"; vim.bo[buf].filetype = "ide_hscroll"
    vim.b[buf].ide_hscroll = true
    -- Creating a bar must not move focus out of an open picker or dialog.
    barwin = api.nvim_open_win(buf, false, { split = "below", win = win, height = 1, noautocmd = true })
    api.nvim_win_call(barwin, function() vim.cmd("diffoff") end)
    for key, value in pairs({ number = false, relativenumber = false, signcolumn = "no", statuscolumn = "", winbar = "",
      winfixheight = true, cursorline = false, scrollbind = false, cursorbind = false, wrap = false,
      scrolloff = 0, sidescrolloff = 0 }) do vim.wo[barwin][key] = value end
    api.nvim_win_set_height(barwin, 1)
  end)
  diff.busy = busy
  if not ok then
    if valid(barwin) then pcall(api.nvim_win_close, barwin, true) end
    if buf and api.nvim_buf_is_valid(buf) then pcall(api.nvim_buf_delete, buf, { force = true }) end
    error(err, 0)
  end
  local bar = { win = barwin, buf = buf, source = win }; M.bars[win] = bar
  return bar
end
local function adjacent(node, source, bar)
  if node[1] == "leaf" then return false end
  for index, child in ipairs(node[2]) do
    local following = node[2][index + 1]
    if node[1] == "col" and child[1] == "leaf" and child[2] == source
      and following and following[1] == "leaf" and following[2] == bar then return true end
    if adjacent(child, source, bar) then return true end
  end
  return false
end
local function place(win, bar)
  if adjacent(vim.fn.winlayout(), win, bar.win) then return end
  -- Reopening a bottom tool can insert it between the editor and its bar.
  -- Move the existing split back next to its source without recreating it.
  local diff = require("config.diff")
  local busy = diff.busy; diff.busy = true
  local ok, err = pcall(api.nvim_win_set_config, bar.win, { split = "below", win = win, height = 1 })
  diff.busy = busy
  if not ok then error(err, 0) end
end
local namespace = api.nvim_create_namespace("DesktopHorizontalScroll")
function M.draw(win)
  if not editor(win) or vim.wo[win].wrap then M.close(win); return end
  local maximum, available, longest = M.bounds(win)
  if sidebar(win) then
    vim.wo[win].scrolloff, vim.wo[win].sidescrolloff = 0, 0
    local view = api.nvim_win_call(win, vim.fn.winsaveview)
    if view.leftcol > maximum then M.set(win, maximum) end
    local height = api.nvim_win_get_height(win) - (vim.wo[win].winbar ~= "" and 1 or 0)
    local count = api.nvim_buf_line_count(api.nvim_win_get_buf(win))
    local top = math.max(1, count - height + 1)
    if api.nvim_win_text_height(win, {}).all <= height then top = 1 end
    if view.topline > top then
      api.nvim_win_call(win, function()
        local current = vim.fn.winsaveview(); current.topline = top; vim.fn.winrestview(current)
      end)
    end
  end
  if maximum <= 0 then M.close(win); return end
  local bar = M.bars[win]
  if not bar or not valid(bar.win) then bar = make(win) end
  place(win, bar)
  -- winfixheight is a preference: resizing a column whose other panels are
  -- fixed can still allocate all spare rows to the scrollbar.
  if api.nvim_win_get_height(bar.win) ~= 1 then api.nvim_win_set_height(bar.win, 1) end
  local width = api.nvim_win_get_width(bar.win)
  local track = math.max(1, width - 2)
  local thumb = math.max(1, math.min(track, math.floor(track * available / math.max(1, longest))))
  local view = api.nvim_win_call(win, vim.fn.winsaveview)
  local offset = math.floor(math.min(maximum, view.leftcol) / maximum * (track - thumb))
  local text = "◀" .. string.rep("─", offset) .. string.rep("━", thumb) .. string.rep("─", track - thumb - offset) .. "▶"
  bar.maximum, bar.span, bar.thumb, bar.start = maximum, track - thumb, thumb, offset + 2
  vim.bo[bar.buf].modifiable = true
  api.nvim_buf_set_lines(bar.buf, 0, -1, false, { text })
  api.nvim_buf_clear_namespace(bar.buf, namespace, 0, -1)
  api.nvim_buf_set_extmark(bar.buf, namespace, 0, #("◀" .. string.rep("─", offset)), {
    end_col = #("◀" .. string.rep("─", offset) .. string.rep("━", thumb)), hl_group = "Visual" })
  vim.bo[bar.buf].modified = false; vim.bo[bar.buf].modifiable = false
  api.nvim_win_call(bar.win, function()
    vim.fn.winrestview({ topline = 1, lnum = 1, col = 0, leftcol = 0, skipcol = 0 })
  end)
end
function M.refresh()
  if M.pending or M.running then return end
  M.pending = true
  vim.defer_fn(function()
    M.pending, M.running = false, true
    local ok, err = pcall(function()
      local wins = api.nvim_tabpage_list_wins(0)
      for source in pairs(M.bars) do if not editor(source) then M.close(source) end end
      for _, win in ipairs(wins) do if editor(win) then M.draw(win) end end
    end)
    M.running = false
    if not ok then vim.notify("Horizontal scrollbar: " .. tostring(err), vim.log.levels.ERROR) end
  end, 40)
end
function M.setup()
  local group = api.nvim_create_augroup("DesktopHorizontalScroll", { clear = true })
  api.nvim_create_autocmd({ "BufWinEnter", "TextChanged", "TextChangedI", "WinScrolled", "WinResized", "VimResized", "WinClosed", "ModeChanged" }, {
    group = group, callback = function(args)
      if not M.running and not M.syncing and not vim.b[args.buf].ide_hscroll then M.refresh() end
    end,
  })
  api.nvim_create_autocmd({ "BufWinEnter", "InsertEnter" }, { group = group, callback = function()
    local win = api.nvim_get_current_win()
    if M.virtual and M.virtual[win] ~= nil then vim.wo.virtualedit = M.virtual[win]; M.virtual[win] = nil end
  end })
  local mouse_keys = {}
  for _, prefix in ipairs({ "", "2-", "3-", "4-" }) do
    for _, kind in ipairs({ "Mouse", "Drag", "Release" }) do mouse_keys[vim.keycode("<" .. prefix .. "Left" .. kind .. ">")] = kind end
  end
  local wheels = {}
  for _, direction in ipairs({ "Left", "Right", "Up", "Down" }) do
    wheels[vim.keycode("<ScrollWheel" .. direction .. ">")] = direction
  end
  vim.on_key(function(key, typed)
    if require("config.mouse_capture").blocked(key, typed) then return end
    local wheel = wheels[typed] or wheels[key]
    if wheel then
      local win = vim.fn.getmousepos().winid
      if sidebar(win) then
        if wheel == "Left" or wheel == "Right" then
          local column = api.nvim_win_call(win, vim.fn.winsaveview).leftcol + (wheel == "Right" and 4 or -4)
          vim.schedule(function() M.set(win, column) end)
          return ""
        end
        local height = api.nvim_win_get_height(win) - (vim.wo[win].winbar ~= "" and 1 or 0)
        if api.nvim_win_text_height(win, {}).all <= height then return "" end
      end
    end
    local kind = mouse_keys[typed] or mouse_keys[key]
    if not kind then return end
    local mouse = vim.fn.getmousepos()
    if kind == "Mouse" then
      for source, bar in pairs(M.bars) do
        if mouse.winid == bar.win then
          M.drag = { source = source, bar = bar, grab = mouse.wincol >= bar.start and mouse.wincol < bar.start + bar.thumb
            and mouse.wincol - bar.start or math.floor(bar.thumb / 2) }
          break
        end
      end
    end
    local drag = M.drag
    if not drag then return end
    local bar = drag.bar
    if valid(bar.win) then
      local col = mouse.screencol - api.nvim_win_get_position(bar.win)[2]
      local target
      if kind == "Mouse" and col == 1 then drag.arrow = true; target = api.nvim_win_call(drag.source, vim.fn.winsaveview).leftcol - 4
      elseif kind == "Mouse" and col == api.nvim_win_get_width(bar.win) then drag.arrow = true; target = api.nvim_win_call(drag.source, vim.fn.winsaveview).leftcol + 4
      else target = (col - 2 - drag.grab) / math.max(1, bar.span) * bar.maximum end
      if not drag.arrow or kind == "Mouse" then vim.schedule(function() M.set(drag.source, target) end) end
    end
    if kind == "Release" then M.drag = nil end
    return ""
  end, namespace)
end
return M
