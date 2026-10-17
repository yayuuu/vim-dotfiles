-- One row selection shared by keyboard navigation and Volt's mouse renderer.
local M = {}
local api = vim.api
local namespace = api.nvim_create_namespace("DesktopMenuNavigation")
local hidden_cursor = "a:DesktopMenuCursor"

local function active(state)
  return M.state == state and api.nvim_win_is_valid(state.win) and api.nvim_buf_is_valid(state.buf)
    and api.nvim_win_get_buf(state.win) == state.buf
end

local function detach()
  local state = M.state
  if not state then return end
  M.state = nil
  if vim.o.guicursor == hidden_cursor then vim.o.guicursor = state.guicursor end
end

local function selected(state)
  if state.mouse_active then return state.mouse end
  return state.keyboard
end

local function paint(state)
  if not active(state) then return end
  local row = selected(state)
  -- menu.ui renders every segment of this row with its existing hover color.
  -- Keep this plugin-specific hover ID here, rather than adding a second layer
  -- of highlights on top of Volt's virtual text.
  vim.g.nvmark_hovered = row and (row .. "menu" .. state.buf) or nil
  require("volt").redraw(state.buf, "items")
end

local function move(state, direction)
  if not active(state) or #state.rows == 0 then return end
  local index
  for i, row in ipairs(state.rows) do if row == state.keyboard then index = i; break end end
  index = index and ((index - 1 + direction) % #state.rows + 1) or (direction > 0 and 1 or #state.rows)
  state.keyboard, state.mouse, state.mouse_active = state.rows[index], nil, false
  api.nvim_win_set_cursor(state.win, { state.keyboard, 0 })
  paint(state)
end

local function hover(state)
  if not active(state) then return end
  local mouse = vim.fn.getmousepos()
  local row = require("config.panel_mouse").row(mouse, state.win)
  local pos = row and vim.fn.screenpos(state.win, row, 1)
  local inside = pos and mouse.screencol >= pos.col and mouse.screencol < pos.col + api.nvim_win_get_width(state.win)
  state.mouse_active = not not inside
  state.mouse = inside and state.enabled[row] and row or nil
  -- Volt handles MouseMove in its own on_key listener. Paint after all listeners
  -- finish, including on exit (where Volt doesn't clear its previous hover).
  if state.pending then return end
  state.pending = true
  vim.schedule(function() state.pending = false; paint(state) end)
end

local function setup()
  if M.ready then return end
  M.ready = true
  local function cursor_highlight()
    api.nvim_set_hl(0, "DesktopMenuCursor", { reverse = true, blend = 100 })
  end
  cursor_highlight()
  local group = api.nvim_create_augroup("DesktopMenuNavigation", { clear = true })
  api.nvim_create_autocmd("ColorScheme", { group = group, callback = cursor_highlight })
  api.nvim_create_autocmd({ "WinLeave", "BufWipeout" }, { group = group, callback = function(event)
    if M.state and event.buf == M.state.buf then detach() end
  end })
  local mousemove = vim.keycode("<MouseMove>")
  vim.on_key(function(key, typed)
    local state = M.state
    if not state or (key ~= mousemove and typed ~= mousemove)
      or require("config.mouse_capture").blocked(key, typed) then return end
    hover(state)
  end, namespace)
end

function M.attach(win, buf, items)
  setup()
  detach()
  local state = { win = win, buf = buf, rows = {}, enabled = {}, guicursor = vim.o.guicursor }
  for row, item in ipairs(items) do
    if not item.title and item.name ~= "separator" and (item.cmd or item.items) then
      state.rows[#state.rows + 1], state.enabled[row] = row, true
    end
  end
  M.state = state
  vim.o.guicursor = hidden_cursor
  vim.wo[win].cursorline, vim.wo[win].cursorcolumn = false, false
  api.nvim_create_autocmd("WinClosed", { group = "DesktopMenuNavigation", pattern = tostring(win), once = true,
    callback = function() if M.state == state then detach() end end })
  local modes = { "n", "i", "x", "s" }
  for _, key in ipairs({ "<Down>", "<Tab>", "j" }) do
    vim.keymap.set(modes, key, function() move(state, 1) end, { buffer = buf, silent = true })
  end
  for _, key in ipairs({ "<Up>", "<S-Tab>", "k" }) do
    vim.keymap.set(modes, key, function() move(state, -1) end, { buffer = buf, silent = true })
  end
  for _, key in ipairs({ "<Left>", "<Right>", "<S-Left>", "<S-Right>", "<C-Left>", "<C-Right>",
    "<Home>", "<End>", "h", "l", "0", "$", "w", "b", "e" }) do
    vim.keymap.set(modes, key, "<Nop>", { buffer = buf, silent = true })
  end
  vim.keymap.set(modes, "<CR>", function()
    if not active(state) then return end
    local row = selected(state)
    local item = row and items[row]
    if not item then return end
    if item.items then require("menu.utils").toggle_nested_menu(item.name, item.items); return end
    require("config.ide").close_menu()
    item.cmd()
  end, { buffer = buf, silent = true })
  for key, direction in pairs({ ["<Left>"] = -1, ["<Right>"] = 1 }) do
    vim.keymap.set(modes, key, function() require("config.ide").step_menu(direction) end, { buffer = buf, silent = true })
  end
  paint(state)
end

return M
