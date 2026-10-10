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
  return #M.wins == 4 and valid(M.wins[1]) and valid(M.wins[4])
end

function M.resize()
  if not M.is_open() or not valid(M.root) then return end
  local total = api.nvim_win_get_height(M.root)
  for _, win in ipairs(M.wins) do total = total + api.nvim_win_get_height(win) end
  api.nvim_win_set_height(M.root, 2)
  local height = math.max(2, math.floor((total - 2) / 4))
  for index = 1, 3 do api.nvim_win_set_height(M.wins[index], height) end
end

function M.open(tree)
  if M.opening or M.is_open() then return end
  local dapui = require("dapui")
  M.generation = M.generation + 1
  local generation = M.generation
  M.opening, M.root = true, tree
  M.saved = { height = api.nvim_win_get_height(tree), winfixheight = vim.wo[tree].winfixheight }
  require("nio").run(function()
    local buffers = {}
    for _, section in ipairs(sections) do
      local element = dapui.elements[section.id]
      buffers[#buffers + 1] = element.buffer()
      element.render()
    end
    vim.schedule(function()
      local state = require("config.sidebar").state()
      if generation ~= M.generation or not valid(tree) or not state or state.name ~= "debug" then return end
      local previous, parent = api.nvim_get_current_win(), tree
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
      M.opening = false
      vim.wo[tree].winfixheight = true
      M.resize()
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

function M.console_buffer(callback)
  local dapui = require("dapui")
  require("nio").run(function()
    local buf = dapui.elements.repl.buffer()
    vim.schedule(function() callback(buf) end)
  end)
end

function M.refresh_breakpoints()
  if not M.is_open() then return end
  require("nio").run(function() require("dapui").elements.breakpoints.render() end)
end

function M.setup(dap)
  require("config.debugger_mouse").setup()
  dap.listeners.after.event_initialized["dapui_config"] = function() vim.schedule(M.show) end
  -- Keep the shared sidebar and console available after the process exits.
  dap.listeners.before.event_terminated["dapui_config"] = nil
  dap.listeners.before.event_exited["dapui_config"] = nil
  local group = api.nvim_create_augroup("DesktopDebugger", { clear = true })
  api.nvim_create_autocmd("VimResized", { group = group, callback = function() vim.schedule(M.resize) end })
end
return M
