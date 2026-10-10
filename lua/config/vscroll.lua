-- A mouse scrollbar on the right border of an attached preview window.
local M = { sources = {}, buffers = {} }
local api = vim.api
local capture = require("config.mouse_capture")
local namespace = api.nvim_create_namespace("DesktopVerticalScroll")
local function valid(win) return win and api.nvim_win_is_valid(win) end

local function close_bar(state)
  if state.bar and valid(state.bar.win) then api.nvim_win_close(state.bar.win, true) end
  state.bar = nil
end

function M.detach(win)
  if not win then return end
  local state = M.sources[win]
  if state then close_bar(state) end
  M.sources[win] = nil
  if M.drag and M.drag.source == win then capture.release(M.drag); M.drag = nil end
end

local function bounds(win)
  local height = api.nvim_win_get_height(win)
  local total = api.nvim_win_text_height(win, {}).all
  local view = api.nvim_win_call(win, vim.fn.winsaveview)
  local offset = api.nvim_win_text_height(win, { end_row = view.topline - 1, end_vcol = view.skipcol }).all - view.topfill
  local maximum = math.max(0, total - height)
  return math.max(0, math.min(maximum, offset)), maximum, height, total
end

function M.set(win, offset)
  if not valid(win) then return end
  local current, maximum = bounds(win)
  offset = math.floor(math.max(0, math.min(maximum, offset)))
  local delta = offset - current
  if delta ~= 0 then
    -- Native screen-line scrolling handles wrapped text and virtual lines.
    -- win_call restores focus to the picker input after moving the preview.
    api.nvim_win_call(win, function()
      vim.cmd.normal({ args = { tostring(math.abs(delta)) .. vim.keycode(delta > 0 and "<C-e>" or "<C-y>") }, bang = true })
    end)
  end
  M.refresh()
end

local function draw(win, state)
  local buf = api.nvim_win_get_buf(win)
  if not M.buffers[buf] then
    M.buffers[buf] = true
    api.nvim_buf_attach(buf, false, {
      on_lines = function() M.refresh() end,
      on_detach = function() M.buffers[buf] = nil end,
    })
  end
  local offset, maximum, height, total = bounds(win)
  if maximum == 0 then close_bar(state); return end
  local config = api.nvim_win_get_config(win)
  local bar_config = { relative = "win", win = win, row = 0, col = api.nvim_win_get_width(win),
    width = 1, height = height, focusable = false, mouse = true, style = "minimal", border = "none",
    zindex = math.min(32000, (config.zindex or 50) + 5), noautocmd = true }
  local bar = state.bar
  if not bar or not valid(bar.win) then
    local barbuf = api.nvim_create_buf(false, true)
    vim.bo[barbuf].bufhidden = "wipe"; vim.bo[barbuf].filetype = "ide_vscroll"
    vim.b[barbuf].ide_vscroll = true
    bar = { buf = barbuf, win = api.nvim_open_win(barbuf, false, bar_config) }
    state.bar = bar
    vim.wo[bar.win].winbar = ""
    vim.wo[bar.win].winhighlight = "Normal:FloatBorder,EndOfBuffer:FloatBorder"
  else api.nvim_win_set_config(bar.win, bar_config) end
  bar.thumb = math.max(1, math.floor(height * height / total))
  bar.span, bar.maximum = height - bar.thumb, maximum
  bar.start = math.floor(offset / maximum * bar.span)
  local lines = {}
  for row = 0, height - 1 do lines[#lines + 1] = row >= bar.start and row < bar.start + bar.thumb and "█" or "│" end
  vim.bo[bar.buf].modifiable = true
  api.nvim_buf_set_lines(bar.buf, 0, -1, false, lines)
  api.nvim_buf_clear_namespace(bar.buf, namespace, 0, -1)
  for row = bar.start, bar.start + bar.thumb - 1 do
    api.nvim_buf_set_extmark(bar.buf, namespace, row, 0, { end_col = #"█", hl_group = "Visual" })
  end
  vim.bo[bar.buf].modified = false; vim.bo[bar.buf].modifiable = false
end

function M.refresh()
  if M.pending or M.running or not next(M.sources) then return end
  M.pending = true
  vim.schedule(function()
    M.pending, M.running = false, true
    local ok, err = pcall(function()
      for win, state in pairs(M.sources) do
        if valid(win) then draw(win, state) else M.detach(win) end
      end
    end)
    M.running = false
    if not ok then vim.notify("Vertical scrollbar: " .. tostring(err), vim.log.levels.ERROR) end
  end)
end

function M.attach(win)
  if not valid(win) then return end
  if not M.ready then M.setup() end
  M.sources[win] = M.sources[win] or {}
  M.refresh()
end

function M.setup()
  M.ready = true
  local group = api.nvim_create_augroup("DesktopVerticalScroll", { clear = true })
  api.nvim_create_autocmd({ "WinScrolled", "WinResized", "VimResized", "WinClosed", "BufWinEnter", "TextChanged", "TextChangedI" },
    { group = group, callback = M.refresh })
  local events = {}
  for _, prefix in ipairs({ "", "2-", "3-", "4-" }) do
    for _, kind in ipairs({ "Mouse", "Drag", "Release" }) do events[vim.keycode("<" .. prefix .. "Left" .. kind .. ">")] = kind end
  end
  local wheels = { [vim.keycode("<ScrollWheelUp>")] = -3, [vim.keycode("<ScrollWheelDown>")] = 3 }
  vim.on_key(function(key, typed)
    local kind, wheel = events[typed] or events[key], wheels[typed] or wheels[key]
    if not kind and not wheel then return end
    local mouse = vim.fn.getmousepos()
    if kind == "Mouse" then
      -- The host may miss a release outside its window. The next press must
      -- release the old capture before starting another independent gesture.
      capture.cancel(M.drag)
      M.drag = nil
    end
    for source, state in pairs(M.sources) do
      if state.bar and mouse.winid == state.bar.win then
        if wheel then
          local offset = bounds(source)
          vim.schedule(function() M.set(source, offset + wheel) end)
          return ""
        end
        if kind == "Mouse" then
          local row, bar = mouse.winrow - 1, state.bar
          M.drag = { source = source, bar = bar,
            grab = row >= bar.start and row < bar.start + bar.thumb and row - bar.start or math.floor(bar.thumb / 2) }
          capture.claim(M.drag)
        end
        break
      end
    end
    local drag = M.drag
    if not drag or not kind then return end
    if valid(drag.bar.win) then
      local row = mouse.screenrow - api.nvim_win_get_position(drag.bar.win)[1] - 1
      local offset = (row - drag.grab) / math.max(1, drag.bar.span) * drag.bar.maximum
      vim.schedule(function() M.set(drag.source, offset) end)
    end
    if kind == "Release" then capture.release(drag); M.drag = nil end
    return ""
  end, namespace)
end

return M
