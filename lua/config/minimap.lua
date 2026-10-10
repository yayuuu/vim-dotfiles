local M = {}
local api = vim.api
local drag
local viewport_namespace = api.nvim_create_namespace("DesktopMinimapViewport")

local function clamp(value, low, high)
  return math.max(low, math.min(value, high))
end

-- Viewport highlights are cheap to update and must not wait for the plugin's
-- debounce used to regenerate code, syntax colors, and other annotations.
function M.refresh_viewport(buffer)
  local minimap = require("neominimap.buffer")
  local coord = require("neominimap.map.coord")
  for _, buf in ipairs(buffer and { buffer } or minimap.list_buffers()) do
    local mapbuf = minimap.get_minimap_bufnr(buf)
    if mapbuf and api.nvim_buf_is_valid(mapbuf) then
      api.nvim_buf_clear_namespace(mapbuf, viewport_namespace, 0, -1)
      local count = api.nvim_buf_line_count(mapbuf)
      for _, win in ipairs(vim.fn.win_findbuf(buf)) do
        if api.nvim_win_get_config(win).relative == "" then
          local info = vim.fn.getwininfo(win)[1]
          local first = coord.codepoint_to_mcodepoint(info.topline, 1)
          local last = coord.codepoint_to_mcodepoint(info.botline, 1)
          first, last = clamp(first, 1, count), clamp(last, 1, count)
          api.nvim_buf_set_extmark(mapbuf, viewport_namespace, first - 1, 0,
            { end_row = last, end_col = 0, hl_group = "DesktopMinimapViewport", hl_eol = true, priority = 90 })
        end
      end
    end
  end
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
  local margin = math.min(vim.wo[state.source].scrolloff, math.floor((state.height - 1) / 2))
  local offset = clamp(state.cursor_offset, margin, state.height - margin - 1)
  view.topline = top
  view.lnum = clamp(top + offset, top, count)
  view.col = state.column
  view.topfill, view.skipcol = 0, 0
  vim.fn.winrestview(view)
  M.refresh_viewport(state.buffer)
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
    local state = drag
    state.latest_row = mouse.screenrow
    -- Collapse queued movements into the latest position so a fast drag
    -- cannot build up stale scroll operations behind the pointer.
    if not state.pending then
      state.pending = true
      vim.schedule(function()
        state.pending = false
        apply(state, state.latest_row)
      end)
    end
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
