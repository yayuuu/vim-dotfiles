-- The left sign gutter toggles DAP breakpoints without moving the editing cursor.
local M = {}
local api = vim.api
local namespace = api.nvim_create_namespace("DesktopBreakpointMouse")
local function valid(win) return win and api.nvim_win_is_valid(win) end

function M.toggle(win, line)
  win = win or api.nvim_get_current_win()
  if not valid(win) then return end
  local buf = api.nvim_win_get_buf(win)
  line = line or api.nvim_win_get_cursor(win)[1]
  local diff = require("config.diff")
  local entry = diff.entries[buf]
  local target = entry and entry.filebuf or buf
  if line < 1 or line > api.nvim_buf_line_count(target) then return end
  local busy = diff.busy
  diff.busy = true
  local ok, err = pcall(api.nvim_buf_call, target, function()
    local cursor = api.nvim_win_get_cursor(0)
    api.nvim_win_set_cursor(0, { line, 0 })
    require("dap").toggle_breakpoint()
    api.nvim_win_set_cursor(0, cursor)
  end)
  diff.busy = busy
  if not ok then error(err) end
  -- A comparison displays a proxy buffer; its signs reflect the real file's DAP state.
  for proxy, comparison in pairs(diff.entries) do
    if comparison.filebuf == target and api.nvim_buf_is_valid(proxy) then
      vim.fn.sign_unplace("DesktopBreakpointMirror", { buffer = proxy })
      local placements = vim.fn.sign_getplaced(target, { group = "dap_breakpoints" })
      for _, sign in ipairs(placements[1] and placements[1].signs or {}) do
        vim.fn.sign_place(0, "DesktopBreakpointMirror", sign.name, proxy, { lnum = sign.lnum, priority = 21 })
      end
    end
  end
  if package.loaded["config.debugger"] then require("config.debugger").refresh_breakpoints() end
end

function M.setup()
  local keys = {}
  for _, prefix in ipairs({ "", "2-", "3-", "4-" }) do
    for _, kind in ipairs({ "Mouse", "Drag", "Release" }) do
      keys[vim.keycode("<" .. prefix .. "Left" .. kind .. ">")] = kind
    end
  end
  local pressed
  vim.on_key(function(key, typed)
    if require("config.mouse_capture").blocked(key, typed) then return end
    local kind = keys[typed] or keys[key]
    if not kind then return end
    local mouse = vim.fn.getmousepos()
    local win = mouse.winid
    if kind == "Drag" and pressed then pressed = nil; return "" end
    if kind == "Release" and pressed then
      local start = pressed
      pressed = nil
      if win == start.win and mouse.line == start.line and mouse.wincol <= 2 then
        vim.schedule(function() if valid(win) then M.toggle(win, start.line) end end)
      end
      return ""
    end
    if kind ~= "Mouse" or not valid(win) or mouse.wincol < 1 or mouse.wincol > 2 or mouse.line < 1 then return end
    local buf = api.nvim_win_get_buf(win)
    if api.nvim_win_get_config(win).relative ~= "" or not vim.wo[win].number or vim.wo[win].signcolumn == "no"
      or not require("config.ide").is_document(buf) or not vim.bo[buf].modifiable
      or (vim.bo[buf].buftype ~= "" and not vim.b[buf].ide_diff_file)
      or vim.b[buf].snacks_statuscolumn_left == false then return end
    pressed = { win = win, line = mouse.line }
    return ""
  end, namespace)
end
return M
