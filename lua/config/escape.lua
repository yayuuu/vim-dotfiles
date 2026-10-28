-- Escape dismisses transient UI before it can leave document input.
local M = {}
local api = vim.api
local function valid(win) return win and api.nvim_win_is_valid(win) end

function M.document(win)
  win = win or api.nvim_get_current_win()
  if not valid(win) or api.nvim_win_get_config(win).relative ~= "" then return false end
  local buf = api.nvim_win_get_buf(win)
  return (vim.bo[buf].buftype == "" or vim.b[buf].ide_diff_file ~= nil)
    and (require("config.ide").is_document(buf) or vim.wo[win].diff)
    and not vim.b[buf].ide_git_input and not vim.b[buf].ide_search_input
    and not vim.w[win].snacks_picker_preview
end

-- Return encoded keys for native completion, or an empty string when Blink
-- handled the dismissal. nil means there is no completion to dismiss.
function M.completion()
  local cmp = package.loaded["blink.cmp"]
  local dismissed = false
  if cmp then
    if cmp.is_visible() then cmp.cancel(); dismissed = true end
    if cmp.is_documentation_visible() then cmp.hide_documentation(); dismissed = true end
    if cmp.is_signature_visible() then cmp.hide_signature(); dismissed = true end
  end
  if vim.fn.pumvisible() == 1 or vim.fn.wildmenumode() == 1 then return vim.keycode("<C-e>") end
  if dismissed then return "" end
end

local function close_popup(win)
  local origin, buf = api.nvim_get_current_win(), api.nvim_get_current_buf()
  vim.schedule(function()
    if not valid(win) or api.nvim_get_current_win() ~= origin or api.nvim_get_current_buf() ~= buf then return end
    require("config.popup_ui").close(win)
    if valid(origin) and api.nvim_get_current_win() == origin and vim.fn.mode() == "n" then
      vim.cmd("startinsert")
    end
  end)
  return ""
end

function M.popup()
  local win, buf = api.nvim_get_current_win(), api.nvim_get_current_buf()
  local config = api.nvim_win_get_config(win)
  if vim.b[buf].ide_git_input or vim.b[buf].ide_panel_header then return end
  if config.relative ~= "" then
    -- An input dialog can be canceled directly, without a Normal-mode step.
    return close_popup(win)
  end
  local popup = require("config.popup_ui")
  local target, layer
  for _, candidate in ipairs(api.nvim_tabpage_list_wins(0)) do
    local c = api.nvim_win_get_config(candidate)
    local b = api.nvim_win_get_buf(candidate)
    if c.relative ~= "" and not c.hide and not c.external
      and not vim.b[b].ide_git_input and not vim.b[b].ide_panel_header
      and (popup.owners[candidate] or vim.b[buf].lsp_floating_preview == candidate
        or (c.focusable and vim.bo[b].filetype == "noice")
        or (c.focusable and popup.buttons[candidate])) then
      if not layer or (c.zindex or 50) > layer then target, layer = candidate, c.zindex or 50 end
    end
  end
  if target then return close_popup(target) end
end

function M.insert()
  local completion = M.completion()
  if completion ~= nil then return completion end
  local popup = M.popup()
  if popup ~= nil then return popup end
  if not M.document() then return "" end
  vim.cmd("nohlsearch")
  if vim.snippet then vim.snippet.stop() end
  return vim.keycode("<Esc>")
end

function M.selection()
  local completion = M.completion()
  if completion ~= nil then return completion end
  local popup = M.popup()
  if popup ~= nil then return popup end
  if not M.document() then return vim.keycode("<C-\\><C-n><Cmd>startinsert<CR>") end
  vim.cmd("nohlsearch")
  if vim.snippet then vim.snippet.stop() end
  return vim.keycode("<C-\\><C-n>")
end

function M.command()
  local completion = M.completion()
  if completion ~= nil then return completion end
  -- Native command-line cancellation also prevents Esc from executing a
  -- partially typed command. Resume the same input after CmdlineLeave.
  M.command_origin = { win = api.nvim_get_current_win(), buf = api.nvim_get_current_buf() }
  return vim.keycode("<C-c>")
end

function M.setup()
  local opts = { expr = true, replace_keycodes = false, desc = "Dismiss popup or leave document input" }
  vim.keymap.set("i", "<Esc>", M.insert, opts)
  vim.keymap.set({ "x", "s" }, "<Esc>", M.selection, opts)
  vim.keymap.set("c", "<Esc>", M.command, { expr = true, replace_keycodes = false, desc = "Dismiss completion or cancel command" })
  api.nvim_create_autocmd("CmdlineLeave", {
    group = api.nvim_create_augroup("DesktopEscape", { clear = true }),
    callback = function()
      local origin = M.command_origin
      M.command_origin = nil
      if not origin then return end
      vim.schedule(function()
        if valid(origin.win) and api.nvim_get_current_win() == origin.win and api.nvim_get_current_buf() == origin.buf
          and (vim.fn.mode() == "n" or vim.fn.mode() == "nt")
          and vim.bo.modifiable and not vim.bo.readonly then vim.cmd("startinsert") end
      end)
    end,
  })
end

return M
