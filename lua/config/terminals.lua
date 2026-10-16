-- One bottom terminal pane with a narrow session list on its right.
local M = { items = {}, serial = 0, rows = {} }
local api = vim.api
local namespace = api.nvim_create_namespace("DesktopTerminalList")
local function valid(win) return win and api.nvim_win_is_valid(win) end
local function buffer_valid(buf) return type(buf) == "number" and api.nvim_buf_is_valid(buf) end
local function console_input(win, buf)
  local row = api.nvim_buf_line_count(buf)
  local line = api.nvim_buf_get_lines(buf, row - 1, row, false)[1] or ""
  api.nvim_win_set_cursor(win, { row, #line })
  vim.cmd("startinsert!")
end

local function attach_console(buf)
  if vim.b[buf].ide_console_input then return end
  vim.b[buf].ide_console_input = true
  local enter
  for _, mapping in ipairs(api.nvim_buf_get_keymap(buf, "n")) do
    if mapping.lhs == "<CR>" then enter = mapping; break end
  end
  vim.keymap.set("n", "<CR>", function()
    local prompt = vim.fn.prompt_getprompt(buf)
    if api.nvim_win_get_cursor(0)[1] == api.nvim_buf_line_count(buf)
      and prompt ~= "" and vim.startswith(api.nvim_get_current_line(), prompt) then
      -- Use the native prompt callback, including REPL history and evaluation.
      return "A<CR>"
    end
    if enter and enter.callback then vim.schedule(enter.callback); return "<Ignore>" end
    return enter and enter.rhs or "<Ignore>"
  end, { buffer = buf, expr = true, silent = true, desc = "Execute debug console input or open result" })
end

function M.mouse_enabled(buf)
  for _, item in ipairs(M.items) do
    if item.buf == buf then return item.mouse.enabled end
  end
end
local function resume_input()
  local win, buf = api.nvim_get_current_win(), api.nvim_get_current_buf()
  local console = M.console_active and buf == M.console_buf and vim.bo[buf].buftype == "prompt"
  if win ~= M.win or (vim.bo[buf].buftype ~= "terminal" and not console) then return end
  vim.schedule(function()
    if valid(win) and api.nvim_get_current_win() == win and api.nvim_get_current_buf() == buf
      and vim.fn.mode() == "n" then
      if console then console_input(win, buf) else vim.cmd("startinsert") end
    end
  end)
end
local function read_proc(path)
  local fd = vim.uv.fs_open(path, "r", 0)
  if not fd then return end
  local text = vim.uv.fs_read(fd, 4096, 0)
  vim.uv.fs_close(fd)
  return text
end

function M.update_title()
  if not valid(M.win) then return end
  if M.console_active then vim.wo[M.win].winbar = " Debug console "; return end
  local title = " No active terminal "
  for _, item in ipairs(M.items) do
    if item.buf == M.active then
      local pid = item.job and vim.fn.jobpid(item.job)
      local stat = pid and read_proc("/proc/" .. pid .. "/stat")
      local fields = stat and stat:match("^%d+ %(.+%) (.+)$")
      local foreground = fields and tonumber(vim.split(fields, " ")[6])
      if not foreground or foreground <= 0 then foreground = pid end
      local program = foreground and read_proc("/proc/" .. foreground .. "/comm")
      local cwd = foreground and vim.uv.fs_readlink("/proc/" .. foreground .. "/cwd")
      cwd = cwd or (pid and vim.uv.fs_readlink("/proc/" .. pid .. "/cwd")) or item.cwd
      if cwd ~= item.cwd then item.cwd = cwd; M.refresh() end
      title = " " .. vim.trim(program or "bash") .. " - " .. vim.fn.fnamemodify(cwd, ":~") .. " "
      break
    end
  end
  title = title:gsub("%%", "%%%%")
  if vim.wo[M.win].winbar ~= title then vim.wo[M.win].winbar = title end
end

local function options(win)
  for key, value in pairs({ number = false, relativenumber = false, signcolumn = "no", statuscolumn = "",
    foldcolumn = "0", wrap = false, winfixheight = true }) do vim.wo[win][key] = value end
end

function M.refresh()
  if not valid(M.list_win) then return end
  local width, text = api.nvim_win_get_width(M.list_win), { " [+ New terminal]" }
  M.rows = {}
  for _, item in ipairs(M.items) do
    local label = (item.buf == M.active and not M.console_active and " > " or "   ") .. item.id .. ": bash · " .. vim.fn.fnamemodify(item.cwd, ":t")
    while vim.fn.strdisplaywidth(label) > width - 3 do label = vim.fn.strcharpart(label, 0, vim.fn.strchars(label) - 1) end
    text[#text + 1] = label .. string.rep(" ", math.max(0, width - 2 - vim.fn.strdisplaywidth(label))) .. "× "
    M.rows[#text] = item.buf
  end
  if #M.items == 0 then text[#text + 1] = " No open terminals" end
  M.console_row = #text + 1
  text[M.console_row] = (M.console_active and " > " or "   ") .. "Debug console"
  vim.bo[M.list_buf].modifiable = true
  api.nvim_buf_set_lines(M.list_buf, 0, -1, false, text)
  vim.bo[M.list_buf].modifiable = false
  api.nvim_buf_clear_namespace(M.list_buf, namespace, 0, -1)
  api.nvim_buf_set_extmark(M.list_buf, namespace, 0, 1, { end_col = #text[1], hl_group = "Function" })
  for row in pairs(M.rows) do
    local first = text[row]:find("×", 1, true)
    api.nvim_buf_set_extmark(M.list_buf, namespace, row - 1, first - 1, { end_col = first + 1, hl_group = "DiagnosticError" })
  end
end

local function panel()
  if not buffer_valid(M.empty_buf) then
    M.empty_buf = api.nvim_create_buf(false, true)
    vim.bo[M.empty_buf].filetype = "ide_terminal_empty"
    api.nvim_buf_set_lines(M.empty_buf, 0, -1, false, { "Select a terminal or click New terminal." })
    vim.bo[M.empty_buf].modifiable = false
  end
  if not valid(M.win) then
    M.win = api.nvim_open_win(buffer_valid(M.active) and M.active or M.empty_buf, false,
      { split = "below", win = require("config.ide").editor_window(), height = math.max(4, math.floor(vim.o.lines * 0.25)) })
    options(M.win)
  end
  if not valid(M.list_win) then
    if not buffer_valid(M.list_buf) then
      M.list_buf = api.nvim_create_buf(false, true)
      vim.bo[M.list_buf].filetype = "ide_terminal_list"
      vim.bo[M.list_buf].bufhidden = "hide"
    end
    M.list_win = api.nvim_open_win(M.list_buf, false, { split = "right", win = M.win, width = 26 })
    options(M.list_win)
    vim.wo[M.list_win].winfixwidth = true
    vim.wo[M.list_win].winbar = " Terminals "
    vim.keymap.set("n", "<CR>", function()
      local row = api.nvim_win_get_cursor(M.list_win)[1]
      if row == 1 then M.new()
      elseif row == M.console_row then M.show_debug_console()
      elseif M.rows[row] then M.show(M.rows[row]) end
    end, { buffer = M.list_buf, desc = "Select or create terminal" })
    vim.keymap.set("n", "x", function() M.close(M.rows[api.nvim_win_get_cursor(M.list_win)[1]]) end,
      { buffer = M.list_buf, desc = "Close terminal" })
  end
  M.update_title()
  M.refresh()
  require("config.layout").reflow()
end

function M.show(buf, focus)
  if not buffer_valid(buf) then return end
  if package.loaded["config.problems"] then require("config.problems").hide(false) end
  M.console_generation = (M.console_generation or 0) + 1
  M.console_active = false
  M.active = buf
  panel()
  api.nvim_win_set_buf(M.win, buf)
  M.update_title()
  M.refresh()
  if focus ~= false then api.nvim_set_current_win(M.win); vim.cmd("startinsert") end
end

function M.show_debug_console(focus, on_shown)
  if package.loaded["config.problems"] then require("config.problems").hide(false) end
  M.console_generation = (M.console_generation or 0) + 1
  local generation = M.console_generation
  require("config.debugger").console_buffer(function(buf)
    if generation ~= M.console_generation then return end
    M.console_active, M.console_buf = true, buf
    attach_console(buf)
    panel()
    api.nvim_win_set_buf(M.win, buf)
    M.update_title()
    M.refresh()
    if focus ~= false then api.nvim_set_current_win(M.win); console_input(M.win, buf) end
    if on_shown then on_shown() end
  end)
end

function M.show_empty()
  M.console_active = false
  panel()
  api.nvim_win_set_buf(M.win, M.empty_buf)
  M.update_title()
end

function M.new(opts)
  opts = opts or {}
  M.serial = M.serial + 1
  local item = { id = M.serial, cwd = opts.cwd or require("config.ide").root(), buf = api.nvim_create_buf(false, true), mouse = { enabled = false } }
  vim.bo[item.buf].bufhidden = "hide"
  vim.bo[item.buf].filetype = "snacks_terminal"
  M.items[#M.items + 1] = item
  M.show(item.buf, false)
  api.nvim_buf_call(item.buf, function()
    item.job = vim.fn.jobstart({ "/bin/bash" }, { term = true, cwd = item.cwd,
      on_stdout = function(_, data) require("config.terminal_mouse").feed(item.mouse, data) end,
      on_exit = function() vim.schedule(function() M.close(item.buf) end) end })
  end)
  if item.job <= 0 then M.close(item.buf); vim.notify("Could not start terminal", vim.log.levels.ERROR); return end
  M.show(item.buf, opts.start_insert ~= false)
  vim.keymap.set("n", "q", M.hide, { buffer = item.buf, desc = "Hide terminal panel" })
  return item.buf
end

function M.close(buf)
  if not buf then return end
  local found
  for index, item in ipairs(M.items) do
    if item.buf == buf then found = item; table.remove(M.items, index); break end
  end
  if not found then return end
  if M.active == buf then
    M.active = M.items[#M.items] and M.items[#M.items].buf or nil
    if valid(M.win) and not M.console_active then api.nvim_win_set_buf(M.win, M.active or M.empty_buf) end
  end
  if buffer_valid(buf) then api.nvim_buf_delete(buf, { force = true }) end
  M.refresh()
  M.update_title()
end

function M.hide()
  M.console_generation = (M.console_generation or 0) + 1
  require("config.layout").save()
  if valid(M.list_win) then api.nvim_win_close(M.list_win, true) end
  if valid(M.win) then api.nvim_win_close(M.win, true) end
  M.list_win, M.win = nil, nil
end

function M.toggle(opts)
  if package.loaded["config.problems"] then require("config.problems").hide(false) end
  if valid(M.win) then M.hide()
  elseif M.console_active then M.show_debug_console(not opts or opts.start_insert ~= false)
  elseif M.active then M.show(M.active, not opts or opts.start_insert ~= false)
  else M.new(opts) end
end

function M.setup()
  local group = api.nvim_create_augroup("DesktopTerminals", { clear = true })
  api.nvim_create_autocmd("WinEnter", { group = group, callback = resume_input })
  if M.title_timer then M.title_timer:stop(); M.title_timer:close() end
  M.title_timer = vim.uv.new_timer()
  M.title_timer:start(500, 500, vim.schedule_wrap(M.update_title))
  M.title_timer:unref()
  api.nvim_create_autocmd("VimLeavePre", { group = group, callback = function()
    M.title_timer:stop(); M.title_timer:close()
  end })
  api.nvim_create_autocmd({ "WinResized", "VimResized" }, { group = group, callback = function() vim.schedule(M.refresh) end })
  api.nvim_create_autocmd("BufWipeout", { group = group, callback = function(event)
    vim.schedule(function() M.close(event.buf) end)
  end })
  local keys = {}
  for _, prefix in ipairs({ "", "2-", "3-", "4-" }) do
    keys[vim.keycode("<" .. prefix .. "LeftMouse>")] = false
    keys[vim.keycode("<" .. prefix .. "LeftRelease>")] = true
  end
  vim.on_key(function(key, typed)
    if require("config.mouse_capture").blocked(key, typed) then return end
    if keys[typed] ~= nil then key = typed end
    if keys[key] == nil then return end
    local mouse = vim.fn.getmousepos()
    if mouse.winid == M.win then
      if keys[key] and mouse.line > 0 then resume_input() end
      return
    end
    if not valid(M.list_win) then return end
    if mouse.winid ~= M.list_win then return end
    if keys[key] then
      local row, column = require("config.panel_mouse").row(mouse, M.list_win), mouse.wincol
      if not row then return "" end
      vim.schedule(function()
        if row == 1 then M.new()
        elseif row == M.console_row then M.show_debug_console()
        elseif M.rows[row] then
          if column >= api.nvim_win_get_width(M.list_win) - 1 then M.close(M.rows[row]) else M.show(M.rows[row]) end
        end
      end)
    end
    return ""
  end, namespace)
end

return M
