local M = {}
local api = vim.api
local drag

local function clamp(value, low, high)
  return math.max(low, math.min(value, high))
end

local function apply(state, screenrow)
  if
    not api.nvim_win_is_valid(state.source)
    or not api.nvim_win_is_valid(state.map)
    or api.nvim_win_get_buf(state.source) ~= state.buffer
  then
    return
  end
  local count = api.nvim_buf_line_count(state.buffer)
  local top = state.top + math.floor((screenrow - state.row) * state.scale + 0.5)
  -- A drag can leave the map, so the first/last row also acts as an endpoint.
  if screenrow < state.first then
    top = 1
  end
  if screenrow > state.last then
    top = count
  end
  top = clamp(top, 1, math.max(1, count - state.height + 1))
  api.nvim_set_current_win(state.source)
  if vim.fn.mode():match("^[vVsS]") or vim.fn.mode() == "\22" or vim.fn.mode() == "\19" then
    vim.cmd.normal({ vim.keycode("<Esc>"), bang = true })
  end
  local view = vim.fn.winsaveview()
  view.topline = top
  view.lnum = clamp(top + state.cursor_offset, top, count)
  view.col = state.column
  view.topfill, view.skipcol = 0, 0
  vim.fn.winrestview(view)
  -- Clicking from a sidebar/terminal returns directly to typing in the code.
  if state.insert and vim.fn.mode() == "n" then
    vim.cmd.startinsert()
  end
end

local function start(mouse)
  if
    mouse.winid == 0
    or not api.nvim_win_is_valid(mouse.winid)
    or vim.bo[api.nvim_win_get_buf(mouse.winid)].filetype ~= "neominimap"
  then
    return
  end
  local source = require("neominimap.window.float.window_map").get_parent_winid(mouse.winid)
  if not source or not api.nvim_win_is_valid(source) then
    return
  end
  local info = vim.fn.getwininfo(source)[1]
  local height = api.nvim_win_get_height(source) - (vim.wo[source].winbar ~= "" and 1 or 0)
  local cursor = api.nvim_win_get_cursor(source)
  local lines_per_cell = 4 * require("neominimap.config").y_multiplier
  local line = require("neominimap.map.coord").mcodepoint_to_codepoint(math.max(1, mouse.line), 1)
  local top, offset = info.topline, clamp(cursor[1] - info.topline, 0, height - 1)
  -- Grab the visible region without recentering it. Elsewhere, a click jumps
  -- to that code and establishes a new grab point for subsequent dragging.
  if line + lines_per_cell - 1 < info.topline or line > info.botline then
    offset = math.floor(height / 2)
    top = line - offset
  end
  local map_height = api.nvim_win_get_height(mouse.winid)
  local position = api.nvim_win_get_position(mouse.winid)
  return {
    source = source,
    map = mouse.winid,
    buffer = info.bufnr,
    row = mouse.screenrow,
    top = clamp(top, 1, math.max(1, api.nvim_buf_line_count(info.bufnr) - height + 1)),
    height = math.max(1, height),
    cursor_offset = offset,
    column = cursor[2],
    -- The preview follows the source using file-relative positioning, so a
    -- screen row of thumb movement corresponds to this fraction of the file.
    scale = math.max(lines_per_cell, api.nvim_buf_line_count(info.bufnr) / map_height),
    first = position[1] + 1,
    last = position[1] + map_height,
    insert = vim.fn.mode() == "i" or vim.fn.mode() == "t" or vim.bo[api.nvim_get_current_buf()].buftype ~= "",
  }
end

function M.setup()
  local events = {}
  for _, prefix in ipairs({ "", "2-", "3-", "4-" }) do
    for _, kind in ipairs({ "Mouse", "Drag", "Release" }) do
      events[vim.keycode("<" .. prefix .. "Left" .. kind .. ">")] = kind
    end
  end
  -- Consume the native mouse gesture before Neovim can turn it into a text
  -- selection. An on_key listener leaves tree/menu buffer mappings intact.
  vim.on_key(function(key, typed)
    if require("config.mouse_capture").blocked(key, typed) then return end
    local kind = events[key]
    if not kind then
      return
    end
    local mouse = vim.fn.getmousepos()
    if kind == "Mouse" then
      drag = start(mouse)
    end
    if not drag then
      return
    end
    local state, row = drag, mouse.screenrow
    vim.schedule(function()
      apply(state, row)
    end)
    if kind == "Release" then
      drag = nil
    end
    return ""
  end, api.nvim_create_namespace("DesktopMinimapMouse"))
  api.nvim_create_autocmd({ "WinClosed", "VimResized", "TabLeave" }, {
    group = api.nvim_create_augroup("DesktopMinimapMouse", { clear = true }),
    callback = function()
      drag = nil
    end,
  })
end

return M
