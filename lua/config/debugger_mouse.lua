-- Mouse actions use DAP UI's buffer mappings and DAP's variable metadata.
local M = {}
local api = vim.api
local types = { dapui_scopes = true, dapui_breakpoints = true, dapui_stacks = true, dapui_watches = true }
local namespace = api.nvim_create_namespace("DesktopDebuggerMouse")
local function valid(win) return win and win ~= 0 and api.nvim_win_is_valid(win) end
function M.handles(win)
  return valid(win) and api.nvim_win_get_config(win).relative == ""
    and types[vim.bo[api.nvim_win_get_buf(win)].filetype] == true
end

local function row_info(buf, row)
  local text = api.nvim_buf_get_lines(buf, row - 1, row, false)[1] or ""
  local info = { text = text, indent = #(text:match("^%s*") or ""), groups = {} }
  local ns = api.nvim_get_namespaces().dapui
  if ns then
    for _, mark in ipairs(api.nvim_buf_get_extmarks(buf, ns, { row - 1, 0 }, { row - 1, -1 }, { details = true })) do
      local details = mark[4]
      if details.hl_group and details.end_col then
        info.groups[details.hl_group] = text:sub(mark[3] + 1, details.end_col)
        if details.hl_group == "DapUIVariable" then info.indent = math.max(0, mark[3] - 2) end
      end
    end
  end
  info.name = info.groups.DapUIVariable
  return info
end

local function select_row(win, row)
  if not M.handles(win) or row < 1 then return false end
  local buf = api.nvim_win_get_buf(win)
  if row > api.nvim_buf_line_count(buf) then return false end
  vim.cmd("stopinsert")
  api.nvim_feedkeys(vim.keycode("<Esc>"), "nx", false)
  api.nvim_set_current_win(win)
  local view = vim.fn.winsaveview()
  api.nvim_win_set_cursor(win, { row, 0 })
  if view.leftcol > 0 then require("config.hscroll").set(win, view.leftcol) end
  return true
end

function M.action(win, row, action)
  if not select_row(win, row) then return end
  for _, mapping in ipairs(api.nvim_buf_get_keymap(api.nvim_win_get_buf(win), "n")) do
    if mapping.desc == action and mapping.callback then mapping.callback(row); return end
  end
end

function M.toggle_group(win, row, highlight)
  if not select_row(win, row) then return end
  local buf, last = api.nvim_win_get_buf(win), row
  for next_row = row + 1, api.nvim_buf_line_count(buf) do
    local info = row_info(buf, next_row)
    if info.groups[highlight] or (highlight == "DapUIThread" and info.groups.DapUIStoppedThread) then break end
    if vim.trim(info.text) ~= "" then last = next_row end
  end
  if last <= row then return end
  vim.wo[win].foldmethod, vim.wo[win].foldenable = "manual", true
  vim.wo[win].foldminlines = 0
  api.nvim_win_call(win, function()
    if vim.fn.foldclosed(row + 1) ~= -1 then vim.cmd((row + 1) .. "foldopen!")
    elseif vim.fn.foldlevel(row + 1) > 0 then vim.cmd((row + 1) .. "foldclose")
    else vim.cmd((row + 1) .. "," .. last .. "fold") end
  end)
end

function M.click(win, row)
  if require("config.ide").menu_mouse_pending or not select_row(win, row) then return end
  local buf = api.nvim_win_get_buf(win)
  local info, ft = row_info(buf, row), vim.bo[buf].filetype
  if (ft == "dapui_stacks" or ft == "dapui_breakpoints")
    and api.nvim_win_call(win, function() return vim.fn.foldclosed(row) end) ~= -1 then
    vim.cmd(row .. "foldopen!")
    return
  end
  if ft == "dapui_stacks" then
    if info.groups.DapUIFrameName or info.groups.DapUICurrentFrameName then M.action(win, row, "open")
    elseif info.groups.DapUIThread or info.groups.DapUIStoppedThread then M.toggle_group(win, row, "DapUIThread") end
  elseif ft == "dapui_breakpoints" then
    if info.groups.DapUIBreakpointsPath then M.toggle_group(win, row, "DapUIBreakpointsPath")
    elseif vim.trim(info.text) ~= "" then M.action(win, row, "open") end
  elseif ft == "dapui_watches" and info.text:match("^>%s*$") then
    api.nvim_win_set_cursor(win, { row, #info.text })
    vim.cmd("startinsert")
  elseif info.text:match("^%s*[v>] ") and not info.text:match("^%s*>%s*$") then
    M.action(win, row, "expand")
  end
end

-- Resolve nested variables through their references rather than guessing an expression.
function M.selection(win, row, callback)
  if not M.handles(win) then return end
  local buf = api.nvim_win_get_buf(win)
  local info = row_info(buf, row)
  local result = { sentence = info.text, value = info.groups.DapUIValue or info.groups.DapUIModifiedValue }
  local function watch_expression(text)
    for _, watch in ipairs(require("dapui").elements.watches.get()) do
      local last = #watch.expression + 2
      if text:sub(3, last) == watch.expression and text:sub(last + 1, last + 1):match("[ :]") then return watch.expression end
    end
  end
  if vim.bo[buf].filetype == "dapui_watches" and not info.name then
    result.expression = watch_expression(info.text)
  end
  local session = require("dap").session()
  local function finish(variable)
    if variable then
      result.expression, result.value = variable.evaluateName, variable.value
      result.expandable = (variable.variablesReference or 0) > 0
    end
    vim.schedule(function() if M.handles(win) and api.nvim_win_get_buf(win) == buf then callback(result) end end)
  end
  if not session or not session.current_frame then finish(); return end
  local ancestry = {}
  if info.name then ancestry[1] = info.name end
  local indent, scope, expression = info.indent, nil, result.expression
  for previous = row - 1, 1, -1 do
    local parent = row_info(buf, previous)
    if parent.name and parent.indent < indent then
      table.insert(ancestry, 1, parent.name)
      indent = parent.indent
    elseif parent.groups.DapUIScope then scope = parent.groups.DapUIScope; break
    elseif vim.bo[buf].filetype == "dapui_watches" and parent.text:match("^[v>] ") then
      expression = watch_expression(parent.text)
      if expression then break end
    end
  end
  local function descend(reference, index)
    if not reference or reference == 0 then finish(); return end
    session:request("variables", { variablesReference = reference }, function(err, response)
      if err or not response then finish(); return end
      for _, variable in ipairs(response.variables or {}) do
        if variable.name == ancestry[index] then
          if index == #ancestry then finish(variable)
          else descend(variable.variablesReference, index + 1) end
          return
        end
      end
      finish()
    end)
  end
  if expression then
    session:evaluate({ expression = expression, context = "watch" }, function(err, evaluated)
      if err or not evaluated then finish(); return end
      if #ancestry > 0 then descend(evaluated.variablesReference, 1)
      else finish({ evaluateName = expression, value = evaluated.result, variablesReference = evaluated.variablesReference }) end
    end)
  elseif scope and #ancestry > 0 then
    for _, item in ipairs(session.current_frame.scopes or {}) do
      if item.name == scope then descend(item.variablesReference, 1); return end
    end
    finish()
  else finish() end
end

local function copy(text)
  if not text then return end
  vim.fn.setreg('"', text)
  vim.fn.setreg("+", text)
end
local function with_selection(action)
  local win = api.nvim_get_current_win()
  M.selection(win, api.nvim_win_get_cursor(win)[1], action)
end

function M.attach(buf)
  local opts = { buffer = buf, silent = true }
  vim.keymap.set("n", "<C-c>", function() with_selection(function(item) copy(item.value or item.sentence) end) end,
    vim.tbl_extend("force", opts, { desc = "Copy debugger value" }))
  vim.keymap.set("n", "<C-S-c>", function() copy(vim.fn.getline(".")) end,
    vim.tbl_extend("force", opts, { desc = "Copy debugger sentence" }))
  vim.keymap.set("n", "<C-e>", function() with_selection(function(item) copy(item.expression) end) end,
    vim.tbl_extend("force", opts, { desc = "Copy debugger expression" }))
  vim.keymap.set("n", "<C-w>", function() with_selection(function(item)
    if item.expression then require("dapui").elements.watches.add(item.expression) end
  end) end, vim.tbl_extend("force", opts, { desc = "Add debugger expression to watches" }))
end

function M.context_menu(win, row)
  if not select_row(win, row) then return end
  local buf, info = api.nvim_win_get_buf(win), row_info(api.nvim_win_get_buf(win), row)
  local ft = vim.bo[buf].filetype
  M.selection(win, row, function(item)
    if not select_row(win, row) then return end
    local items = {}
    local function add(name, action, shortcut) items[#items + 1] = { name = name, cmd = action, rtxt = shortcut } end
    if item.expandable or info.groups.DapUIScope then
      add("Expand / collapse", function() M.action(win, row, "expand") end, "Enter")
    end
    if item.expression then
      add("Add to watches", function() require("dapui").elements.watches.add(item.expression) end, "Ctrl+W")
      add("Copy expression", function() copy(item.expression) end, "Ctrl+E")
      add("Evaluate in debug console", function()
        require("config.terminals").show_debug_console(false, function() require("dap.repl").execute(item.expression) end)
      end, "r")
    end
    if item.value then
      add("Copy value", function() copy(item.value) end, "Ctrl+C")
      add(ft == "dapui_watches" and not info.name and "Edit expression" or "Edit value",
        function() M.action(win, row, "edit") end, "e")
    end
    if ft == "dapui_watches" then
      add("Add expression…", function() vim.ui.input({ prompt = "Watch expression: " }, function(value)
        if value and value ~= "" then require("dapui").elements.watches.add(value) end
      end) end)
      if vim.trim(info.text) ~= "" and not info.text:match("^> %s*$") and info.text ~= "No Expressions" then
        add("Remove from watches", function() M.action(win, row, "remove") end, "d")
      end
    elseif ft == "dapui_breakpoints" and not info.groups.DapUIBreakpointsPath and vim.trim(info.text) ~= "" then
      add("Go to source", function() M.action(win, row, "open") end, "o")
      add("Enable / disable breakpoint", function() M.action(win, row, "toggle") end, "t")
      add("Remove breakpoint", function() M.action(win, row, "remove") end, "d")
    elseif ft == "dapui_breakpoints" and info.groups.DapUIBreakpointsPath then
      add("Expand / collapse", function() M.toggle_group(win, row, "DapUIBreakpointsPath") end, "Enter")
    elseif ft == "dapui_stacks" then
      if info.groups.DapUIFrameName or info.groups.DapUICurrentFrameName then
        add("Go to source", function() M.action(win, row, "open") end, "o")
      end
      if info.groups.DapUIThread or info.groups.DapUIStoppedThread then
        add("Expand / collapse", function() M.toggle_group(win, row, "DapUIThread") end, "Enter")
      end
      if vim.trim(info.text) ~= "" then add("Show / hide internal frames", function() M.action(win, row, "toggle") end, "t") end
    end
    add("Copy sentence", function() copy(item.sentence) end, "Ctrl+Shift+C")
    require("config.ide").popup(items)
  end)
end

function M.setup()
  local keys = {}
  for _, prefix in ipairs({ "", "2-", "3-", "4-" }) do
    for _, kind in ipairs({ "Mouse", "Drag", "Release" }) do keys[vim.keycode("<" .. prefix .. "Left" .. kind .. ">")] = kind end
  end
  local pressed
  vim.on_key(function(key, typed)
    if require("config.mouse_capture").blocked(key, typed) then return end
    local kind = keys[typed] or keys[key]
    if not kind then return end
    local mouse = vim.fn.getmousepos()
    if kind == "Release" and pressed then
      local start = pressed; pressed = nil
      if require("config.panel_mouse").row(mouse, start.win) == start.row then vim.schedule(function() M.click(start.win, start.row) end) end
      return ""
    end
    if kind == "Drag" and pressed then pressed = nil; return "" end
    if kind == "Mouse" and M.handles(mouse.winid) and require("config.panel_mouse").row(mouse)
      and not require("config.ide").menu_mouse_pending then
      pressed = { win = mouse.winid, row = mouse.line }
      return ""
    end
  end, namespace)
end
return M
