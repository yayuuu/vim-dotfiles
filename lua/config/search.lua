-- Shared Find/Replace actions and the single file-scoped Replace panel.
local M = { instance_name = "desktop-replace" }
local api = vim.api
local namespace = api.nvim_create_namespace("DesktopSearchMouse")
local function valid(win) return win and api.nvim_win_is_valid(win) end

local function instance()
  local grug = package.loaded["grug-far"]
  return grug and grug.has_instance(M.instance_name) and grug.get_instance(M.instance_name) or nil
end

local function document()
  local ide = require("config.ide")
  local win = ide.editor_window()
  local buf = api.nvim_win_get_buf(win)
  local path = vim.b[buf].ide_diff_file or api.nvim_buf_get_name(buf)
  if not (vim.bo[buf].buftype == "" or vim.b[buf].ide_diff_file) or not vim.bo[buf].modifiable
    or vim.bo[buf].readonly or vim.b[buf].ide_diff_before or path == "" then return win end
  return win, path
end

local function geometry()
  local win = require("config.ide").editor_window()
  local pos = api.nvim_win_get_position(win)
  local editor_width, editor_height = api.nvim_win_get_width(win), api.nvim_win_get_height(win)
  local width = math.max(1, math.min(78, math.floor(editor_width * 0.8), vim.o.columns - 4))
  local height = math.max(1, math.min(22, editor_height - 4))
  return { relative = "editor", row = pos[1] + 2,
    col = pos[2] + math.max(0, editor_width - width - 2),
    width = width, height = height }
end

function M.create_window()
  local config = geometry()
  config.style, config.border, config.title = "minimal", "rounded", " Replace "
  config.zindex = 50
  local buf = api.nvim_create_buf(false, true)
  vim.bo[buf].bufhidden = "wipe"
  M.win = api.nvim_open_win(buf, true, config)
  vim.wo[M.win].winbar = ""
end

function M.close()
  local inst = instance()
  if inst then inst:close() end
end

function M.replace(search)
  local win, path = document()
  if not path then vim.notify("Save the document before replacing text", vim.log.levels.INFO); return end
  vim.cmd("stopinsert")
  local inst = instance()
  if inst then
    inst:open()
    inst:update_input_values({ paths = path:gsub(" ", "\\ "), search = search }, false)
    inst:goto_input("search")
  else
    api.nvim_set_current_win(win)
    inst = require("grug-far").open({
      instanceName = M.instance_name, transient = true, staticTitle = "Replace",
      windowCreationCommand = "lua require('config.search').create_window()",
      visualSelectionUsage = "ignore",
      folding = { enabled = false },
      prefills = { paths = path:gsub(" ", "\\ "), search = search },
    })
  end
  M.path = path
  M.win = vim.fn.bufwinid(inst:get_buf())
  vim.b[inst:get_buf()].ide_replace = true
  vim.b[inst:get_buf()].completion = false
  require("config.popup_ui").register(M.win, M.close)
  vim.keymap.set({ "n", "i" }, "<C-h>", function() M.replace() end,
    { buffer = inst:get_buf(), desc = "Focus Replace" })
  vim.cmd("startinsert")
end

function M.follow()
  local inst = instance()
  if not inst or not inst:is_open() then return end
  local _, path = document()
  if not path then inst:hide(); M.path = nil; return end
  if path ~= M.path then
    M.path = path
    inst:update_input_values({ paths = path:gsub(" ", "\\ ") }, false)
  end
end

-- Grug-far exposes input navigation publicly, but its rendered field ranges
-- require this small adapter to its input metadata (covered by the UI test).
function M.input_at_mouse(mouse)
  local inst = instance()
  if not inst or not valid(mouse.winid) or api.nvim_win_get_buf(mouse.winid) ~= inst:get_buf() then return end
  local context = inst._context
  if not context then return end
  for _, field in ipairs(context.engine.inputs) do
    local mark = context.extmarkIds[field.name]
    local pos = mark and api.nvim_buf_get_extmark_by_id(inst:get_buf(), context.namespace, mark, {})
    if pos and pos[1] then
      local ok, input = pcall(require("grug-far.inputs").getInputAtRow, context, inst:get_buf(), pos[1])
      if ok and input then
        for row = input.start_row, input.end_row do
          local text = api.nvim_buf_get_lines(inst:get_buf(), row, row + 1, false)[1] or ""
          local first = vim.fn.screenpos(mouse.winid, row + 1, 1)
          local last = vim.fn.screenpos(mouse.winid, row + 1, math.max(1, #text))
          if first.row > 0 and mouse.screenrow >= first.row and mouse.screenrow <= last.row then return input, row + 1 end
        end
      end
    end
  end
end

local function find_button(win)
  require("config.popup_ui").register(win.win, function() win:execute("cancel") end)
  local buf = api.nvim_create_buf(false, true)
  vim.bo[buf].bufhidden = "wipe"
  api.nvim_buf_set_lines(buf, 0, -1, false, { " ⇄ " })
  vim.bo[buf].modifiable = false
  local config = api.nvim_win_get_config(win.win)
  local button = api.nvim_open_win(buf, false, { relative = "win", win = win.win,
    row = -1, col = config.width, width = 3, height = 1, border = "rounded",
    style = "minimal", focusable = false, mouse = true, zindex = (config.zindex or 50) + 5,
    noautocmd = true })
  vim.wo[button].winbar = ""
  M.find_input, M.find_button = win, button
  win:on("WinResized", function()
    if valid(button) and win:valid() then
      api.nvim_win_set_config(button, { relative = "win", win = win.win,
        row = -1, col = api.nvim_win_get_width(win.win) })
    end
  end)
  win:on("WinClosed", function()
    if valid(button) then api.nvim_win_close(button, true) end
    if M.find_input == win then M.find_input, M.find_button = nil, nil end
  end, { win = true })
end

function M.find()
  local ide = require("config.ide")
  local win = ide.editor_window()
  api.nvim_set_current_win(win)
  Snacks.input({ prompt = "Find text: ", expand = false, win = {
    width = function() return math.max(1, math.min(60, vim.o.columns - 12)) end,
    on_win = find_button,
    actions = { replace = function(self)
      local text = self:text()
      self:execute("cancel")
      vim.schedule(function() M.replace(text) end)
    end },
    keys = { replace = { "<C-h>", "replace", mode = { "n", "i" } } },
  } }, function(text)
    if text and text ~= "" and valid(win) then
      api.nvim_set_current_win(win)
      local pattern = "\\V" .. vim.fn.escape(text, "\\")
      vim.fn.setreg("/", pattern)
      vim.v.searchforward = 1
      vim.o.hlsearch = true
      if vim.fn.search(pattern, "c") == 0 then vim.notify("Text not found: " .. text, vim.log.levels.INFO) end
    end
  end)
end

function M.setup()
  local group = api.nvim_create_augroup("DesktopSearch", { clear = true })
  api.nvim_create_autocmd({ "BufEnter", "BufWinEnter", "WinEnter" }, { group = group, callback = function()
    if api.nvim_win_get_config(0).relative ~= "" or not require("config.ide").is_document(api.nvim_get_current_buf()) then return end
    vim.schedule(M.follow)
  end })
  api.nvim_create_autocmd({ "WinResized", "VimResized" }, { group = group, callback = function()
    if valid(M.win) then api.nvim_win_set_config(M.win, geometry()) end
  end })
  local events, dragged, input_press = {}, false, nil
  for _, prefix in ipairs({ "", "2-", "3-", "4-" }) do
    for _, kind in ipairs({ "Mouse", "Drag", "Release" }) do events[vim.keycode("<" .. prefix .. "Left" .. kind .. ">")] = kind end
  end
  vim.on_key(function(key, typed)
    if require("config.mouse_capture").blocked(key, typed) then return end
    local kind = events[typed] or events[key]
    if not kind then return end
    if kind == "Mouse" then dragged = false elseif kind == "Drag" then dragged = true end
    local mouse = vim.fn.getmousepos()
    if kind == "Mouse" then
      local input, row = M.input_at_mouse(mouse)
      input_press = input and { win = mouse.winid, row = row, column = mouse.column,
        screenrow = mouse.screenrow, screencol = mouse.screencol } or nil
    end
    if mouse.winid == M.find_button and valid(M.find_button) then
      if kind == "Release" then
        local input = M.find_input
        vim.schedule(function() if input and input:valid() then input:execute("replace") end end)
      end
      return ""
    end
    if kind ~= "Release" or dragged then return end
    local input, row = M.input_at_mouse(mouse)
    local win, column = mouse.winid, mouse.column
    if not input and input_press and mouse.screenrow == input_press.screenrow and mouse.screencol == input_press.screencol then
      win, row, column = input_press.win, input_press.row, input_press.column
    end
    input_press = nil
    if not row then return end
    vim.defer_fn(function()
      if not valid(win) or api.nvim_get_current_win() ~= win or vim.fn.mode():match("^[vVsS\22\19]") then return end
      local text = api.nvim_buf_get_lines(api.nvim_win_get_buf(win), row - 1, row, false)[1] or ""
      vim.cmd(column > #text and "startinsert!" or "startinsert")
    end, 20)
  end, namespace)
end

return M
