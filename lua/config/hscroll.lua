local M = { bars = {}, cache = {} }
local api = vim.api
local capture = require("config.mouse_capture")
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
  local pinned = require("config.git_header").height(win)
  local cached = M.cache[buf]
  if not cached or cached.tick ~= tick or cached.tabstop ~= tabstop or cached.pinned ~= pinned then
    local width = 0
    api.nvim_win_call(win, function()
      for _, line in ipairs(api.nvim_buf_get_lines(buf, pinned, -1, false)) do
        width = math.max(width, display_width((line:gsub("%s+$", ""))))
      end
    end)
    cached = { tick = tick, tabstop = tabstop, width = width, pinned = pinned }; M.cache[buf] = cached
  end
  local available = api.nvim_win_get_width(win) - vim.fn.getwininfo(win)[1].textoff
    - require("config.panel_padding").right(win)
    - require("config.vscroll").width(win)
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
  if bar and valid(win) and bar.original_scrolloff ~= nil and vim.wo[win].scrolloff == 1 then
    vim.wo[win].scrolloff = bar.original_scrolloff
  end
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
      local viewport = api.nvim_win_get_width(target) - vim.fn.getwininfo(target)[1].textoff
      -- Match Neovim's native cursor margin. A smaller margin makes redraw
      -- scroll back again, particularly in narrow diff columns.
      local margin = math.min(vim.wo.sidescrolloff, math.floor(viewport / 2))
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
function M.content_height(win)
  local height = vim.fn.getwininfo(win)[1].height
  return math.max(1, height - (M.bars[win] and 1 or 0))
end
function M.vertical(win, delta)
  if not sidebar(win) then return end
  local view = api.nvim_win_call(win, vim.fn.winsaveview)
  local offset = api.nvim_win_text_height(win, { end_row = view.topline - 1, end_vcol = view.skipcol }).all - view.topfill
  -- Share pre-clamping and mode-independent scrolling with the vertical bar.
  require("config.vscroll").set(win, offset + delta)
  M.refresh()
end
local function configuration(win)
  return { relative = "win", win = win, row = math.max(0, vim.fn.getwininfo(win)[1].height - 1),
    col = 0, width = api.nvim_win_get_width(win), height = 1, style = "minimal",
    border = "none", focusable = false, mouse = true, zindex = 20, noautocmd = true }
end
local function make(win)
  local buf = api.nvim_create_buf(false, true)
  vim.bo[buf].bufhidden = "wipe"; vim.bo[buf].filetype = "ide_hscroll"
  vim.b[buf].ide_hscroll = true
  -- One row inside the panel, with no extra split or separator taking space.
  local ok, barwin = pcall(api.nvim_open_win, buf, false, configuration(win))
  if not ok then api.nvim_buf_delete(buf, { force = true }); error(barwin, 0) end
  for key, value in pairs({ number = false, relativenumber = false, signcolumn = "no", statuscolumn = "", winbar = "",
    cursorline = false, scrollbind = false, cursorbind = false, wrap = false,
    scrolloff = 0, sidescrolloff = 0, winhighlight = "Normal:DesktopScrollbarTrack,EndOfBuffer:DesktopScrollbarTrack" }) do
    vim.wo[barwin][key] = value
  end
  local bar = { win = barwin, buf = buf, source = win }
  M.bars[win] = bar
  return bar
end
local function protect_cursor(win)
  -- The last row belongs to the bar. Keep the cursor above it, including at EOF
  -- where native scrolloff can otherwise place it on the final screen row.
  if M.mouse_pressed then return end
  local diff = require("config.diff").active
  if diff and win == diff.left then return end
  local cursor = api.nvim_win_get_cursor(win)
  local position = vim.fn.screenpos(win, cursor[1], cursor[2] + 1)
  local bottom = api.nvim_win_get_position(win)[1] + api.nvim_win_get_height(win)
  if position.row >= bottom then
    api.nvim_win_call(win, function() vim.cmd.normal({ args = { vim.keycode("<C-e>") }, bang = true }) end)
  end
end
local namespace = api.nvim_create_namespace("DesktopHorizontalScroll")
function M.draw(win)
  if not editor(win) or vim.wo[win].wrap then M.close(win); return end
  local maximum, available, longest = M.bounds(win)
  if sidebar(win) then
    -- Remove both bars when the full content fits without either reservation.
    -- Otherwise each bar can keep the other alive after a resize/shrink.
    if longest <= available + require("config.vscroll").width(win)
      and api.nvim_win_text_height(win, {}).all <= api.nvim_win_get_height(win) then maximum = 0 end
    vim.wo[win].scrolloff, vim.wo[win].sidescrolloff = 0, 0
    local view = api.nvim_win_call(win, vim.fn.winsaveview)
    if view.leftcol > maximum then M.set(win, maximum) end
    local height = M.content_height(win)
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
  if bar and not valid(bar.win) then M.close(win); bar = nil end
  if not bar then bar = make(win) end
  api.nvim_win_set_config(bar.win, configuration(win))
  if vim.wo[win].scrolloff == 0 then
    bar.original_scrolloff = bar.original_scrolloff or 0
    vim.wo[win].scrolloff = 1
  end
  protect_cursor(win)
  local width = api.nvim_win_get_width(bar.win)
  local track = math.max(1, width)
  local thumb = math.max(1, math.min(track, math.floor(track * available / math.max(1, longest))))
  local view = api.nvim_win_call(win, vim.fn.winsaveview)
  local offset = math.floor(math.min(maximum, view.leftcol) / maximum * (track - thumb))
  local glyph = "▄"
  local text = string.rep(glyph, track)
  bar.maximum, bar.span, bar.thumb, bar.start = maximum, track - thumb, thumb, offset + 1
  vim.bo[bar.buf].modifiable = true
  api.nvim_buf_set_lines(bar.buf, 0, -1, false, { text })
  api.nvim_buf_clear_namespace(bar.buf, namespace, 0, -1)
  api.nvim_buf_set_extmark(bar.buf, namespace, 0, #glyph * offset, {
    end_col = #glyph * (offset + thumb), hl_group = "DesktopScrollbarThumb" })
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
    require("config.vscroll").refresh()
    if not ok then vim.notify("Horizontal scrollbar: " .. tostring(err), vim.log.levels.ERROR) end
  end, 40)
end
function M.setup()
  local group = api.nvim_create_augroup("DesktopHorizontalScroll", { clear = true })
  api.nvim_create_autocmd({ "BufWinEnter", "TextChanged", "TextChangedI", "WinScrolled", "WinResized", "VimResized", "WinClosed", "ModeChanged", "CursorMoved", "CursorMovedI" }, {
    group = group, callback = function(args)
      if not M.running and not M.syncing and not vim.b[args.buf].ide_hscroll then M.refresh() end
    end,
  })
  api.nvim_create_autocmd({ "BufWinEnter", "InsertEnter" }, { group = group, callback = function()
    local win = api.nvim_get_current_win()
    if M.virtual and M.virtual[win] ~= nil then vim.wo.virtualedit = M.virtual[win]; M.virtual[win] = nil end
  end })
  local mouse_keys = {}
  for _, modifier in ipairs({ "", "S-", "C-", "A-" }) do
    for _, prefix in ipairs({ "", "2-", "3-", "4-" }) do
      for _, kind in ipairs({ "Mouse", "Drag", "Release" }) do
        mouse_keys[vim.keycode("<" .. modifier .. prefix .. "Left" .. kind .. ">")] = kind
      end
    end
  end
  local wheels = {}
  for _, direction in ipairs({ "Left", "Right", "Up", "Down" }) do
    wheels[vim.keycode("<ScrollWheel" .. direction .. ">")] = direction
  end
  vim.on_key(function(key, typed)
    local kind = mouse_keys[typed] or mouse_keys[key]
    if kind == "Mouse" then capture.cancel(M.drag); M.drag = nil end
    if capture.blocked(key, typed) and capture.owner ~= M.drag then return end
    local wheel = wheels[typed] or wheels[key]
    if wheel then
      local mouse = vim.fn.getmousepos()
      local win = mouse.winid
      local diff = require("config.diff").active
      if diff and win == diff.left and valid(diff.right) and (wheel == "Up" or wheel == "Down") then
        local buf = api.nvim_win_get_buf(win)
        if api.nvim_buf_line_count(buf) == 1 and api.nvim_buf_get_lines(buf, 0, 1, false)[1] == "" then
          -- Native scrolling cannot move an empty baseline through its diff
          -- filler. Scroll the populated side and let scrollbind follow it.
          local right = diff.right
          local row = mouse.screenrow - 1
          vim.schedule(function()
            if not valid(right) then return end
            local position = api.nvim_win_get_position(right)
            api.nvim_input_mouse("wheel", wheel:lower(), "", 0,
              math.max(position[1], math.min(row, position[1] + M.content_height(right) - 1)), position[2] + 5)
          end)
          return ""
        end
      end
      if sidebar(win) then
        if wheel == "Left" or wheel == "Right" then
          local column = api.nvim_win_call(win, vim.fn.winsaveview).leftcol + (wheel == "Right" and 4 or -4)
          vim.schedule(function() M.set(win, column) end)
          return ""
        end
        local amount = tonumber(vim.o.mousescroll:match("ver:(%d+)")) or 3
        vim.schedule(function() M.vertical(win, wheel == "Down" and amount or -amount) end)
        return ""
      end
    end
    if not kind then return end
    M.mouse_pressed = kind ~= "Release"
    local mouse = vim.fn.getmousepos()
    if kind == "Mouse" then
      -- A new press starts a new gesture even if the previous release was lost
      -- outside the terminal. Do not consume a file click as an old bar drag.
      for source, bar in pairs(M.bars) do
        if mouse.winid == bar.win then
          local on_thumb = mouse.wincol >= bar.start and mouse.wincol < bar.start + bar.thumb
          local grab = on_thumb and mouse.wincol - bar.start or math.floor(bar.thumb / 2)
          M.drag = { source = source, bar = bar, pointer = mouse.screencol,
            column = on_thumb and api.nvim_win_call(source, vim.fn.winsaveview).leftcol
              or (mouse.wincol - 1 - grab) / math.max(1, bar.span) * bar.maximum,
            scale = bar.maximum / math.max(1, bar.span) }
          capture.claim(M.drag)
          break
        end
      end
    end
    local drag = M.drag
    if not drag then return end
    local bar = drag.bar
    if valid(bar.win) then
      -- Anchor to the exact view offset, rather than the rounded thumb cell.
      -- The rendered thumb loses precision when many text columns fit a cell;
      -- recalculating from it makes a stationary grab/release jump backwards.
      local target = drag.column + (mouse.screencol - drag.pointer) * drag.scale
      vim.schedule(function() M.set(drag.source, target) end)
    end
    if kind == "Release" then capture.release(drag); M.drag = nil end
    return ""
  end, namespace)
end
return M
