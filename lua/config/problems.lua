-- Diagnostics occupy the bottom pane and restore its previous visibility.
local M = {}
local api = vim.api
local function valid(win) return win and api.nvim_win_is_valid(win) end

function M.hide(restore)
  if not M.view and not M.previous then return end
  local view, previous = M.view, M.previous
  M.view, M.previous = nil, nil
  if view then view:close() end
  if valid(M.suspended) then api.nvim_win_close(M.suspended, true) end
  M.suspended = nil
  if restore ~= false and previous and previous.visible then
    local terminals = require("config.terminals")
    local diff = require("config.diff")
    local comparison = diff.active and diff.active.buf
    if comparison then diff.leave() end
    local function restore_diff() if comparison then diff.show(comparison) end end
    if previous.console then terminals.show_debug_console(false, restore_diff)
    else
      if previous.active and api.nvim_buf_is_valid(previous.active) then terminals.show(previous.active, false)
      else terminals.show_empty() end
      restore_diff()
    end
  end
end

function M.open()
  if M.view then M.hide(); return end
  local ide, terminals = require("config.ide"), require("config.terminals")
  if ide.is_tool_tab() and valid(ide.main_editor) then api.nvim_set_current_win(ide.main_editor) end
  local visible = valid(terminals.win)
  local height = visible and api.nvim_win_get_height(terminals.win) or math.max(4, math.floor(vim.o.lines * 0.25))
  M.previous = { visible = visible, active = terminals.active, console = terminals.console_active }
  local diff = require("config.diff")
  local comparison
  if not visible and diff.active then
    comparison = diff.active.buf
    diff.leave()
  end
  local main = ide.editor_window()
  local parent = main
  if visible then
    require("config.layout").save()
    -- Reuse the bottom row's location, including its width below a two-column diff.
    -- Keep its wide window as an anchor until Trouble has mounted its replacement.
    M.suspended, parent = terminals.win, terminals.win
    if valid(terminals.list_win) then api.nvim_win_close(terminals.list_win, true) end
    terminals.win, terminals.list_win = nil, nil
  end
  api.nvim_set_current_win(main)
  vim.cmd("stopinsert")
  local view = require("trouble").open({ mode = "diagnostics", new = true, focus = true,
    open_no_results = true, warn_no_results = false,
    win = { type = "split", relative = "win", win = parent, position = "bottom", size = height,
      wo = { winbar = "%#Title# Problems%=%#Function#%@v:lua.DesktopProblemsHide@[↓ Hide]%T ", winfixheight = true } },
    keys = { q = function() M.hide() end, ["<esc>"] = function() M.hide() end },
  })
  M.view = view
  if not view then M.hide(); return end
  view:wait(function()
    if M.view ~= view then view:close(); return end
    if valid(M.suspended) then api.nvim_win_close(M.suspended, true) end
    M.suspended = nil
    if comparison then diff.show(comparison) end
    vim.b[view.win.buf].ide_problems = true
    api.nvim_create_autocmd("WinClosed", { pattern = tostring(view.win.win), once = true,
      callback = function() vim.schedule(function() if M.view == view then M.hide() end end) end })
    require("config.layout").reflow()
  end)
end

_G.DesktopProblemsHide = function(_, _, button)
  if button == "l" then vim.schedule(M.hide) end
end
return M
