-- Own modes and row actions in our DAP UI panes and variable inspector. The Canvas adapter is
-- local: recheck its mappings/prompt fields after nvim-dap-ui updates.
local M = { rows = {} }
local api = vim.api
local types = { dapui_scopes = true, dapui_breakpoints = true, dapui_stacks = true, dapui_watches = true, dapui_hover = true }

function M.handles(win)
  if not win or win == 0 or not api.nvim_win_is_valid(win) then return false end
  local ft = vim.bo[api.nvim_win_get_buf(win)].filetype
  return types[ft] == true and (ft == "dapui_hover" or api.nvim_win_get_config(win).relative == "")
end

function M.is_input(win, row)
  if not M.handles(win) then return false end
  local buf = api.nvim_win_get_buf(win)
  return vim.bo[buf].filetype == "dapui_watches" and vim.bo[buf].buftype == "prompt"
    and (row or api.nvim_win_get_cursor(win)[1]) == api.nvim_buf_line_count(buf)
end

local function normal()
  local mode = vim.fn.mode()
  if mode:match("^i") then vim.cmd("stopinsert")
  elseif mode:match("^[vVsS]") or mode == "\22" or mode == "\19" then
    vim.cmd.normal({ args = { vim.keycode("<Esc>") }, bang = true })
  end
end

function M.sync_mode()
  local win = api.nvim_get_current_win()
  if not M.handles(win) then return end
  local navigation = package.loaded["config.panel_navigation"]
  if navigation and (navigation.state or navigation.closing) then return end
  if M.is_input(win) then
    local buf = api.nvim_win_get_buf(win)
    local cursor, prompt = api.nvim_win_get_cursor(win), vim.fn.prompt_getprompt(buf)
    local text = api.nvim_buf_get_lines(buf, cursor[1] - 1, cursor[1], false)[1] or ""
    if cursor[2] < #prompt then api.nvim_win_set_cursor(win, { cursor[1], math.max(#prompt, #text) }) end
    if not vim.fn.mode():match("^i") then vim.cmd("startinsert!") end
  else
    normal()
  end
end

local function schedule_mode()
  if M.pending then return end
  M.pending = true
  vim.schedule(function() M.pending = false; M.sync_mode() end)
end

function M.move(direction)
  local win = api.nvim_get_current_win()
  if not M.handles(win) then return end
  local row, count = api.nvim_win_get_cursor(win)[1], api.nvim_buf_line_count(0)
  normal()
  if direction > 0 then
    local last = vim.fn.foldclosedend(row)
    row = math.min(count, (last >= 0 and last or row) + 1)
  else
    row = math.max(1, row - 1)
    local first = vim.fn.foldclosed(row)
    if first >= 0 then row = first end
  end
  api.nvim_win_set_cursor(win, { row, M.is_input(win, row) and #api.nvim_buf_get_lines(0, row - 1, row, false)[1] or 0 })
  M.sync_mode()
end

function M.action(buf, row, action)
  local actions = M.rows[buf]
  local callbacks = actions and actions[action] and actions[action][row]
  if not callbacks then return false end
  for _, callback in pairs(callbacks) do callback() end
  return true
end

function M.attach(buf)
  local opts = { buffer = buf, silent = true }
  vim.b[buf].completion = false
  for _, pair in ipairs({ { "<Up>", -1 }, { "<Down>", 1 } }) do
    vim.keymap.set({ "n", "i" }, pair[1], function() M.move(pair[2]) end, opts)
  end
  vim.keymap.set("n", "<CR>", function()
    require("config.debugger_mouse").click(api.nvim_get_current_win(), api.nvim_win_get_cursor(0)[1])
  end, vim.tbl_extend("force", opts, { desc = "Activate debugger row" }))
  for _, key in ipairs({ "i", "a", "I", "A", "o", "O" }) do vim.keymap.set("n", key, M.sync_mode, opts) end
  if vim.bo[buf].filetype == "dapui_watches" then
    vim.keymap.set("i", "<Esc>", M.sync_mode, opts)
    -- Keep the prompt's native submission callback; completion must not own it.
    vim.keymap.set("i", "<CR>", "<CR>", opts)
  end
  if not vim.b[buf].ide_debug_navigation then
    vim.b[buf].ide_debug_navigation = true
    api.nvim_create_autocmd({ "BufEnter", "WinEnter", "CursorMoved", "CursorMovedI", "InsertLeave" },
      { buffer = buf, callback = schedule_mode })
    api.nvim_create_autocmd("BufWipeout", { buffer = buf, once = true, callback = function() M.rows[buf] = nil end })
  end
end

function M.setup()
  if M.ready then return end
  M.ready = true
  local canvas = require("dapui.render.canvas")
  local new = canvas.new
  canvas.new = function(...)
    local instance = new(...)
    local render = instance.render_buffer
    instance.render_buffer = function(self, buf, keys)
      if not api.nvim_buf_is_valid(buf) or not types[vim.bo[buf].filetype] then return render(self, buf, keys) end
      local draft, input_win, column
      local fill = self.prompt and self.prompt.fill
      if vim.bo[buf].filetype == "dapui_watches" and vim.bo[buf].buftype == "prompt" and not (self.prompt and self.prompt.fill) then
        local count, prompt = api.nvim_buf_line_count(buf), vim.fn.prompt_getprompt(buf)
        local text = api.nvim_buf_get_lines(buf, count - 1, count, false)[1] or ""
        if prompt ~= "" and vim.startswith(text, prompt) then draft = text:sub(#prompt + 1) end
        local win = api.nvim_get_current_win()
        if api.nvim_win_get_buf(win) == buf and api.nvim_win_get_cursor(win)[1] == count then
          input_win, column = win, api.nvim_win_get_cursor(win)[2]
        end
      end
      -- Native expression editing queues I/C-d/End. Fill the real prompt
      -- directly so those keys cannot act on a newly focused terminal/dialog.
      if self.prompt then self.prompt.fill = nil end
      local result = render(self, buf, keys)
      if self.prompt then self.prompt.fill = fill end
      if result == false then return result end
      M.rows[buf] = self.mappings
      if fill ~= nil then
        draft = fill
        local win = api.nvim_get_current_win()
        if api.nvim_win_get_buf(win) == buf then input_win, column = win, #self.prompt.text + #fill end
      end
      if draft and self.prompt then
        local count = api.nvim_buf_line_count(buf)
        api.nvim_buf_set_lines(buf, count - 1, count, false, { self.prompt.text .. draft })
        vim.bo[buf].modified = false
        if input_win and api.nvim_win_is_valid(input_win) and api.nvim_get_current_win() == input_win
          and api.nvim_win_get_buf(input_win) == buf then
          api.nvim_win_set_cursor(input_win, { count, math.min(column, #self.prompt.text + #draft) })
        end
      end
      M.attach(buf)
      schedule_mode()
      return result
    end
    return instance
  end
end

return M
