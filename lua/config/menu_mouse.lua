-- Keep the release guard alive independently of any one popup's lifetime.
local M = {}
local api = vim.api

local function forget(state)
  if M.state ~= state then return end
  local ide = require("config.ide")
  M.state, ide.menu_mouse_pending = nil, false
  if ide.popup_buffer == state.buf then ide.popup_buffer, ide.menu_name = nil, nil end
end

function M.setup()
  if M.ready then return end
  M.ready = true
  local presses, releases = {}, {}
  for _, modifier in ipairs({ "", "S-", "C-", "A-" }) do
    for _, prefix in ipairs({ "", "2-", "3-", "4-" }) do
      presses[vim.keycode("<" .. modifier .. prefix .. "LeftMouse>")] = true
      releases[vim.keycode("<" .. modifier .. prefix .. "LeftRelease>")] = true
    end
  end
  vim.on_key(function(key, typed)
    local press, release = presses[typed] or presses[key], releases[typed] or releases[key]
    if not press and not release then return end
    local ide, state = require("config.ide"), M.state
    if press then
      -- Recover even if a previous popup lost both its release and its listener.
      ide.menu_mouse_pending = false
      if state then state.pressed = false end
      if state and state.closed then forget(state); state = nil end
      if not state or require("config.mouse_capture").blocked(key, typed) then return end
      local mouse = vim.fn.getmousepos()
      -- Volt may close the window earlier during this same input event.
      -- The deferred close callback marks it closed before the next event.
      if mouse.screenrow >= state.position[1] and mouse.screenrow <= state.position[1] + state.height + 2
        and mouse.screencol >= state.position[2] and mouse.screencol <= state.position[2] + state.width + 2 then
        state.pressed, ide.menu_mouse_pending = true, true
      end
    elseif state and state.pressed then
      state.pressed = false
      -- Release mappings must still see the guard for the entire event.
      vim.schedule(function()
        if M.state ~= state then return end
        ide.menu_mouse_pending = false
        if state.closed then forget(state) end
      end)
      return ""
    end
  end, api.nvim_create_namespace("DesktopMenuMouse"))
end

function M.attach(win, buf)
  M.setup()
  require("config.ide").menu_mouse_pending = false
  local state = {
    buf = buf, position = api.nvim_win_get_position(win),
    height = api.nvim_win_get_height(win), width = api.nvim_win_get_width(win),
  }
  M.state = state
  return function()
    state.closed = true
    if M.state ~= state then return end
    local ide = require("config.ide")
    if ide.popup_buffer == buf then ide.menu_name = nil; vim.cmd("redrawtabline") end
    if not state.pressed then
      forget(state)
    end
  end
end

return M
