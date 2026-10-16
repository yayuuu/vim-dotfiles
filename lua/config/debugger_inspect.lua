-- Resolve and evaluate just the requested variable, without background annotations.
local M = {}
local api = vim.api
local references = { identifier = true, name = true, variable_name = true,
  member_access_expression = true, nullsafe_member_access_expression = true,
  scoped_property_access_expression = true, subscript_expression = true,
  attribute = true, subscript = true, field_expression = true }

function M.available(win)
  local dap = package.loaded.dap
  local session = dap and dap.session()
  return win and api.nvim_win_is_valid(win) and session and session.stopped_thread_id
    and session.current_frame and api.nvim_win_get_config(win).relative == ""
    and require("config.ide").is_document(api.nvim_win_get_buf(win)) or false
end

function M.expression(buf, row, column)
  local line = api.nvim_buf_get_lines(buf, row - 1, row, false)[1] or ""
  if not line:sub(column, column):match("[%w_$\128-\255]") then return end
  local ok, node = pcall(vim.treesitter.get_node, { bufnr = buf, pos = { row - 1, column - 1 } })
  local expression
  while ok and node and references[node:type()] do
    local text = vim.treesitter.get_node_text(node, buf)
    -- Keep calls out of a container expression such as values[get_index()].
    if text:find("[\r\n(]") then break end
    expression, node = text, node:parent()
  end
  if expression then return expression end
  -- Parsers are optional. Keep PHP's leading "$" in the identifier fallback.
  for first, token, last in line:gmatch("()([%w_$\128-\255]+)()") do
    if first <= column and column < last then return token end
  end
end

function M.inspect(win, row, column)
  win = win or api.nvim_get_current_win()
  if not M.available(win) then return end
  local cursor = api.nvim_win_get_cursor(win)
  row, column = row or cursor[1], column or (cursor[2] + 1)
  local expression = M.expression(api.nvim_win_get_buf(win), row, column)
  if not expression then return end
  vim.cmd("stopinsert")
  api.nvim_set_current_win(win)
  api.nvim_win_set_cursor(win, { row, column - 1 })
  require("dapui").eval(expression, { enter = true })
end

local function close_popup()
  for _, win in ipairs(api.nvim_list_wins()) do
    if api.nvim_win_get_config(win).relative ~= "" and vim.bo[api.nvim_win_get_buf(win)].filetype == "dapui_hover" then
      api.nvim_win_close(win, true)
    end
  end
end

function M.setup(dap)
  for _, event in ipairs({ "continue", "next", "stepIn", "stepOut", "event_continued", "event_terminated", "event_exited" }) do
    dap.listeners.before[event]["desktop-inspect"] = close_popup
  end
  local capture, events = require("config.mouse_capture"), {}
  for _, modifier in ipairs({ "", "C-", "S-", "A-" }) do
    for _, prefix in ipairs({ "", "2-", "3-", "4-" }) do
      for _, kind in ipairs({ "Mouse", "Drag", "Release" }) do
        events[vim.keycode("<" .. modifier .. prefix .. "Left" .. kind .. ">")] = { kind = kind, ctrl = modifier == "C-" }
      end
    end
  end
  local pressed
  vim.on_key(function(key, typed)
    local event = events[typed] or events[key]
    if not event then return end
    if event.kind == "Mouse" and pressed then capture.cancel(pressed); pressed = nil end
    local mouse = vim.fn.getmousepos()
    if pressed then
      if event.kind == "Drag" then pressed.dragged = true end
      if event.kind == "Release" then
        local start = pressed
        pressed = nil
        capture.release(start)
        if not start.dragged and mouse.winid == start.win and mouse.column == start.column
          and require("config.panel_mouse").row(mouse, start.win) == start.row then
          vim.schedule(function() M.inspect(start.win, start.row, start.column) end)
        end
      end
      return ""
    end
    if capture.active() or not event.ctrl or event.kind ~= "Mouse" or not M.available(mouse.winid)
      or not require("config.panel_mouse").row(mouse) then return end
    pressed = { win = mouse.winid, row = mouse.line, column = mouse.column }
    capture.claim(pressed)
    return ""
  end, api.nvim_create_namespace("DesktopDebuggerInspect"))
end

return M
