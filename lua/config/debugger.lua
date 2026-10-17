-- Use DAP UI's public element buffers inside the existing sidebar column.
local M = { wins = {}, generation = 0 }
local api = vim.api
local sections = {
  { id = "scopes", title = "Scopes · Variables" },
  { id = "breakpoints", title = "Breakpoints · Stops" },
  { id = "stacks", title = "Call stack · Frames" },
  { id = "watches", title = "Watches · Expressions" },
}
local function valid(win) return win and api.nvim_win_is_valid(win) end

function M.close()
  M.generation = M.generation + 1
  for _, win in ipairs(M.wins) do if valid(win) then api.nvim_win_close(win, true) end end
  M.wins, M.opening = {}, false
  if valid(M.root) and M.saved then
    vim.wo[M.root].winfixheight = M.saved.winfixheight
    api.nvim_win_set_height(M.root, M.saved.height)
  end
  M.root, M.saved = nil, nil
end

function M.is_open()
  if #M.wins ~= #sections or not valid(M.root) then return false end
  for _, win in ipairs(M.wins) do if not valid(win) then return false end end
  return true
end

function M.resize()
  if not M.is_open() or not valid(M.root) then return end
  local total = api.nvim_win_get_height(M.root)
  for _, win in ipairs(M.wins) do total = total + api.nvim_win_get_height(win) end
  api.nvim_win_set_height(M.root, 2)
  local height = math.max(2, math.floor((total - 2) / 4))
  for index = 1, 3 do api.nvim_win_set_height(M.wins[index], height) end
end

local function render_section(section, generation)
  require("nio").run(function()
    if generation ~= M.generation then return end
    local ok, err = xpcall(require("dapui").elements[section.id].render, debug.traceback)
    if not ok then
      vim.schedule(function()
        if generation == M.generation then
          vim.notify("Debug " .. section.title .. ": " .. tostring(err), vim.log.levels.ERROR)
        end
      end)
    end
  end)
end

function M.open(tree)
  if M.opening or M.is_open() then return end
  -- An interrupted mount or a closed interior pane must not leave stale splits.
  if M.root or #M.wins > 0 then M.close() end
  local dapui = require("dapui")
  M.generation = M.generation + 1
  local generation = M.generation
  M.opening, M.root = true, tree
  M.saved = { height = api.nvim_win_get_height(tree), winfixheight = vim.wo[tree].winfixheight }
  require("nio").run(function()
    local ok, buffers = xpcall(function()
      local result = {}
      for _, section in ipairs(sections) do result[#result + 1] = dapui.elements[section.id].buffer() end
      return result
    end, debug.traceback)
    vim.schedule(function()
      if generation ~= M.generation then return end
      local state, current = require("config.sidebar").state()
      if not valid(tree) or current ~= tree or not state or state.name ~= "debug" then M.close(); return end
      if not ok then
        M.close()
        vim.notify("Cannot open Debug panels: " .. tostring(buffers), vim.log.levels.ERROR)
        return
      end
      local previous, parent = api.nvim_get_current_win(), tree
      local mounted, err = xpcall(function()
        for index, section in ipairs(sections) do
          local win = api.nvim_open_win(buffers[index], false, { split = "below", win = parent,
            height = math.max(3, math.floor(M.saved.height / 5)) })
          M.wins[#M.wins + 1], parent = win, win
          for key, value in pairs({ number = false, relativenumber = false, signcolumn = "no",
            foldcolumn = "0", statuscolumn = "", wrap = false, winfixwidth = true }) do vim.wo[win][key] = value end
          vim.wo[win].winbar = " " .. section.title .. " "
          require("config.panel_padding").attach(win)
          require("config.debugger_mouse").attach(buffers[index])
        end
        vim.wo[tree].winfixheight = true
        M.resize()
      end, debug.traceback)
      M.opening = false
      if not mounted then
        M.close()
        vim.notify("Cannot open Debug panels: " .. tostring(err), vim.log.levels.ERROR)
      else
        -- DAP requests can wait or fail. Mount the layout first, then render
        -- independently so Scopes cannot block the other three sections.
        for _, section in ipairs(sections) do render_section(section, generation) end
      end
      if valid(previous) then api.nvim_set_current_win(previous) end
      require("config.layout").reflow()
    end)
  end)
end

function M.show()
  local ide = require("config.ide")
  if ide.is_tool_tab() and valid(ide.main_editor) then api.nvim_set_current_win(ide.main_editor) end
  vim.cmd("stopinsert")
  require("neo-tree.command").execute({ source = "debug", action = "focus", dir = ide.root() })
  require("config.sidebar").schedule()
end

function M.console_buffer(win, callback)
  -- DAP UI's buffer helper creates and closes a temporary split. With fixed
  -- terminal heights that redistributes the editor and bottom panel. Reuse our
  -- existing window through the public REPL API instead (:buffer is a no-op
  -- until the API installs its own prompt buffer).
  local buf = api.nvim_win_call(win, function()
    return require("dap").repl.open({ signcolumn = "no", winfixheight = true }, "buffer")
  end)
  callback(buf)
end

function M.refresh_breakpoints()
  if not M.is_open() then return end
  render_section(sections[2], M.generation)
end

function M.setup(dap)
  require("config.debugger_mouse").setup()
  require("config.debugger_inspect").setup(dap)
  dap.listeners.after.event_initialized["dapui_config"] = function() vim.schedule(M.show) end
  -- Keep the shared sidebar and console available after the process exits.
  dap.listeners.before.event_terminated["dapui_config"] = nil
  dap.listeners.before.event_exited["dapui_config"] = nil
  local group = api.nvim_create_augroup("DesktopDebugger", { clear = true })
  api.nvim_create_autocmd("VimResized", { group = group, callback = function() vim.schedule(M.resize) end })
end
return M
