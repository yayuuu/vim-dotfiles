local M = { bars = {}, cache = {} }
local api = vim.api
local function valid(win) return win and api.nvim_win_is_valid(win) end
local function editor(win)
  if not valid(win) or api.nvim_win_get_config(win).relative ~= "" then return false end
  local buf = api.nvim_win_get_buf(win)
  return vim.bo[buf].buftype == "" or vim.b[buf].ide_diff_file or vim.b[buf].ide_diff_before
end
local function extent(win)
  local buf = api.nvim_win_get_buf(win)
  local tick, tabstop = api.nvim_buf_get_changedtick(buf), vim.bo[buf].tabstop
  local cached = M.cache[buf]
  if not cached or cached.tick ~= tick or cached.tabstop ~= tabstop then
    local width = 0
    api.nvim_win_call(win, function()
      for _, line in ipairs(api.nvim_buf_get_lines(buf, 0, -1, false)) do width = math.max(width, vim.fn.strdisplaywidth(line)) end
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
      local last = vim.fn.strdisplaywidth(line)
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
  local previous = api.nvim_get_current_win()
  local diff = require("config.diff")
  local busy = diff.busy; diff.busy = true
  api.nvim_set_current_win(win)
  vim.cmd("belowright 1split")
  local barwin = api.nvim_get_current_win()
  -- Remove inherited diff mode before putting a scratch buffer in the split.
  vim.cmd("diffoff")
  local buf = api.nvim_create_buf(false, true)
  vim.bo[buf].bufhidden = "wipe"; vim.bo[buf].filetype = "ide_hscroll"
  vim.b[buf].ide_hscroll = true
  api.nvim_win_set_buf(barwin, buf)
  for key, value in pairs({ number = false, relativenumber = false, signcolumn = "no", statuscolumn = "", winbar = "",
    winfixheight = true, cursorline = false, scrollbind = false, cursorbind = false, wrap = false }) do vim.wo[barwin][key] = value end
  api.nvim_win_set_height(barwin, 1)
  if valid(previous) then api.nvim_set_current_win(previous) end
  diff.busy = busy
  local bar = { win = barwin, buf = buf, source = win }; M.bars[win] = bar
  return bar
end
local namespace = api.nvim_create_namespace("DesktopHorizontalScroll")
function M.draw(win)
  if not editor(win) or vim.wo[win].wrap then M.close(win); return end
  local maximum, available, longest = M.bounds(win)
  if maximum <= 0 then M.close(win); return end
  local bar = M.bars[win]
  if not bar or not valid(bar.win) then bar = make(win) end
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
end
function M.refresh()
  if M.pending or M.running then return end
  M.pending = true
  vim.defer_fn(function()
    M.pending, M.running = false, true
    local wins = api.nvim_tabpage_list_wins(0)
    for source in pairs(M.bars) do if not editor(source) then M.close(source) end end
    for _, win in ipairs(wins) do if editor(win) then M.draw(win) end end
    M.running = false
  end, 40)
end
function M.setup()
  local group = api.nvim_create_augroup("DesktopHorizontalScroll", { clear = true })
  api.nvim_create_autocmd({ "BufWinEnter", "TextChanged", "TextChangedI", "WinScrolled", "WinResized", "VimResized", "WinClosed" }, {
    group = group, callback = function(args)
      if not M.running and not M.syncing and not vim.b[args.buf].ide_hscroll then M.refresh() end
    end,
  })
  api.nvim_create_autocmd({ "BufWinEnter", "InsertEnter" }, { group = group, callback = function()
    local win = api.nvim_get_current_win()
    if M.virtual and M.virtual[win] ~= nil then vim.wo.virtualedit = M.virtual[win]; M.virtual[win] = nil end
  end })
  local mouse_keys = {}
  for _, kind in ipairs({ "Mouse", "Drag", "Release" }) do mouse_keys[vim.keycode("<Left" .. kind .. ">")] = kind end
  vim.on_key(function(key)
    local kind = mouse_keys[key]
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
