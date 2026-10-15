-- Notepad++ editing shortcuts; the IDE module keeps actions shared with menus.
local map = vim.keymap.set
local ide = require("config.ide")
local edit = { "n", "i", "x", "s" }
local function action(key, fn, desc, modes)
  map(modes or edit, key, fn, { desc = desc, silent = true })
end
action("<C-n>", ide.new_file, "New file")
action("<C-o>", ide.pick_file, "Open file")
action("<C-s>", ide.save, "Save file")
action("<C-S-s>", ide.save_as, "Save as")
action("<C-w>", ide.close_file, "Close file")
map(edit, "<C-a>", "<Esc>ggVG<C-g>", { desc = "Select all" })
map("s", "<Tab>", "<C-g>>gv<C-g>", { desc = "Indent selection" })
map("x", "<Tab>", ">gv<C-g>", { desc = "Indent selection" })
map("s", "<S-Tab>", "<C-g><gv<C-g>", { desc = "Unindent selection" })
map("x", "<S-Tab>", "<gv<C-g>", { desc = "Unindent selection" })
action("<C-c>", ide.copy, "Copy selection or line")
action("<C-x>", ide.cut, "Cut selection or line")
map({ "n", "x", "s" }, "<C-v>", ide.paste, { desc = "Paste" })
map("i", "<C-v>", "<C-r><C-p>+", { desc = "Paste" })
map("n", "<C-z>", "u", { desc = "Undo" })
map("i", "<C-z>", "<C-o>u", { desc = "Undo" })
map({ "x", "s" }, "<C-z>", "<Esc>u<Cmd>startinsert<CR>", { desc = "Undo" })
map("n", "<C-y>", "<C-r>", { desc = "Redo" })
map("i", "<C-y>", "<C-o><C-r>", { desc = "Redo" })
map({ "x", "s" }, "<C-y>", "<Esc><C-r><Cmd>startinsert<CR>", { desc = "Redo" })
action("<C-d>", ide.duplicate, "Duplicate line/selection")
action("<C-S-Up>", function() ide.move_lines(-1) end, "Move line/selection up")
action("<C-S-Down>", function() ide.move_lines(1) end, "Move line/selection down")
map("n", "<C-l>", '"_dd', { desc = "Delete line" })
map("i", "<C-l>", '<C-o>"_dd', { desc = "Delete line" })
action("<C-f>", ide.find, "Find in file")
action("<C-h>", ide.replace, "Replace in file")
action("<C-S-f>", ide.search_project, "Find in project")
action("<F3>", function() vim.cmd("normal! n") end, "Find next", { "n", "i" })
action("<S-F3>", function() vim.cmd("normal! N") end, "Find previous", { "n", "i" })
action("<C-g>", ide.goto_line, "Go to line")
action("<C-Tab>", function() vim.cmd("BufferLineCycleNext") end, "Next file")
action("<C-S-Tab>", function() vim.cmd("BufferLineCyclePrev") end, "Previous file")
action("<C-PageDown>", function() vim.cmd("BufferLineCycleNext") end, "Next file")
action("<C-PageUp>", function() vim.cmd("BufferLineCyclePrev") end, "Previous file")
action("<C-q>", function() vim.cmd("normal gcc") end, "Toggle comment", { "n" })
map("i", "<C-q>", "<Cmd>normal gcc<CR>", { desc = "Toggle comment" })
map("x", "<C-q>", "gc", { desc = "Toggle comment", remap = true })
map("s", "<C-q>", "<C-g><Cmd>normal gc<CR>", { desc = "Toggle comment" })
action("<C-S-e>", ide.explorer, "Project explorer")
action("<C-S-g>", ide.git_explorer, "Git changes")
action("<M-g>", function() Snacks.lazygit({ cwd = ide.root() }) end, "Repository (LazyGit)")
action("<M-d>", function() vim.cmd("DiffviewOpen") end, "Git diff")
action("<C-`>", ide.terminal, "Bottom terminal", { "n", "i", "t" })
action("<M-t>", ide.terminal, "Bottom terminal", { "n", "i", "t" })
action("<F4>", ide.terminal, "Bottom terminal", { "n", "i", "t" })
action("<F5>", function() require("dap").continue() end, "Debug: start/continue", { "n", "i" })
action("<S-F5>", function() require("dap").terminate() end, "Debug: stop", { "n", "i" })
action("<F9>", function() require("config.breakpoints").toggle() end, "Debug: breakpoint", { "n", "i" })
action("<F10>", function() require("dap").step_over() end, "Debug: step over", { "n", "i" })
action("<F11>", function() require("dap").step_into() end, "Debug: step into", { "n", "i" })
action("<S-F11>", function() require("dap").step_out() end, "Debug: step out", { "n", "i" })
action("<M-b>", function() require("config.debugger").show() end, "Debug sidebar", { "n", "i" })
action("<F1>", ide.help, "Shortcut guide")
action("<F2>", ide.rename_file, "Rename file")
action("<S-F2>", function() vim.api.nvim_set_current_win(ide.editor_window());vim.lsp.buf.rename() end, "Rename symbol")
action("<F12>", function() vim.api.nvim_set_current_win(ide.editor_window());vim.lsp.buf.definition() end, "Go to definition")
action("<S-F12>", function() vim.api.nvim_set_current_win(ide.editor_window());vim.lsp.buf.references() end, "Find references")
action("<C-S-p>", function() Snacks.picker.commands() end, "Command palette")
action("<M-p>", function() Snacks.picker.commands() end, "Command palette")
map("t", "<Esc><Esc>", "<C-\\><C-n>", { desc = "Leave terminal input" })
-- Neovim's terminal encodes keypad navigation as keypad digits. Normalize only
-- navigation names; <k0>...<k9> and ordinary digits retain numeric input.
for _, key in ipairs({ "Home", "End", "Up", "Down", "Left", "Right", "PageUp", "PageDown", "Insert", "Del" }) do
  map("t", "<k" .. key .. ">", "<" .. key .. ">", { desc = "Terminal keypad " .. key })
end
for _, prefix in ipairs({ "", "2-", "3-", "4-" }) do
map({ "n", "x", "s", "i", "t" }, "<" .. prefix .. "RightMouse>", function()
  local mouse = vim.fn.getmousepos()
  local terminal = vim.fn.mode() == "t"
  if terminal and (mouse.winid == 0 or not vim.api.nvim_win_is_valid(mouse.winid)
    or vim.bo[vim.api.nvim_win_get_buf(mouse.winid)].filetype ~= "neo-tree") then
    return "<RightMouse>"
  end
  if mouse.winid ~= 0 and vim.api.nvim_win_is_valid(mouse.winid)
    and mouse.winrow == 1 and vim.wo[mouse.winid].winbar ~= ""
    and vim.bo[vim.api.nvim_win_get_buf(mouse.winid)].buftype == "" then
    return "<RightMouse>" -- Let the file tab handle its own context menu.
  end
  vim.schedule(ide.context_menu)
  return terminal and "<C-\\><C-n>" or "<Ignore>"
end, { desc = "Context menu", expr = true })
end

-- Reliable alternatives for terminals/KVMs that cannot distinguish Ctrl+Shift.
action("<M-e>", ide.explorer, "Project explorer")
action("<M-r>", ide.git_explorer, "Git changes")
action("<M-f>", ide.search_project, "Find in project")
action("<M-s>", ide.save_as, "Save as")
