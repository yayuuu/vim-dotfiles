local group = vim.api.nvim_create_augroup("DesktopIDE", { clear = true })
require("config.colors").setup()
require("config.panel_padding").setup()
require("config.layout").setup()
require("config.diff").setup()
require("config.documents").setup()
require("config.panel_mouse").setup()
require("config.search").setup()
require("config.terminals").setup()
require("config.editor_tabs").setup()
require("config.hscroll").setup()
require("config.selection_scroll").setup()
require("config.vscroll").setup()
require("config.breakpoints").setup()
require("config.tabs").setup()
require("config.git").setup()
require("config.git_commands").setup()
require("config.sidebar").setup()
require("config.git_sync").setup()
vim.api.nvim_create_autocmd({ "BufWinEnter", "WinClosed" }, { callback = function()
  vim.schedule(function()
    for _, field in pairs(require("config.git").inputs) do
      if field.win and vim.api.nvim_win_is_valid(field.win) then
        local found = field.treewin and vim.api.nvim_win_is_valid(field.treewin)
          and vim.api.nvim_win_get_buf(field.treewin) == field.treebuf
        if not found then vim.api.nvim_win_close(field.win, true); field.win = nil end
      end
    end
  end)
end })
-- UIEnter can precede VeryLazy when starting without a filename.
local started = false
local function start_workspace()
  if started or #vim.api.nvim_list_uis() == 0 then return end
  started = true
  vim.schedule(function()
    local ide = require("config.ide")
    local projects = require("config.projects")
    vim.g.ide_project_dir = projects.start_dir
    vim.cmd("cd " .. vim.fn.fnameescape(projects.start_dir))
    local win = ide.editor_window()
    local preferred = vim.api.nvim_win_get_buf(win)
    vim.api.nvim_set_current_win(win)
    vim.wo.winbar = ide.winbar()
    local source = projects.start_dir == projects.normalize(vim.env.HOME) and "projects" or "filesystem"
    require("neo-tree.command").execute({ source = source, action = "show", dir = ide.root() })
    if vim.api.nvim_win_is_valid(win) then vim.api.nvim_set_current_win(win) end
    projects.restore(win, vim.fn.argc() > 0 and preferred or nil)
    ide.terminal({ start_insert = false })
    if vim.api.nvim_win_is_valid(win) then vim.api.nvim_set_current_win(win) end
    require("config.sidebar").update()
    require("config.layout").restore()
    if vim.bo.buftype == "" and vim.bo.modifiable then vim.cmd("startinsert") end
  end)
end
vim.api.nvim_create_autocmd("UIEnter", { group = group, once = true, callback = start_workspace })
vim.schedule(start_workspace)
vim.api.nvim_create_autocmd("BufEnter", {
  group = group,
  callback = function(event)
    if vim.bo[event.buf].filetype ~= "snacks_picker_input" and vim.bo[event.buf].filetype ~= "snacks_input"
      and vim.bo[event.buf].filetype ~= "ide_git_message" then return end
    local win, buf = vim.api.nvim_get_current_win(), event.buf
    vim.defer_fn(function()
      if vim.api.nvim_get_current_win() == win and vim.api.nvim_get_current_buf() == buf
        and vim.fn.mode() == "n" then vim.cmd("startinsert") end
    end, 20)
  end,
})
vim.api.nvim_create_autocmd("BufEnter", {
  group = group,
  callback = function(event)
    if vim.api.nvim_win_get_config(0).relative ~= "" or vim.w.snacks_picker_preview
      or require("config.ide").is_tool_tab()
      or vim.bo[event.buf].buftype ~= "" or vim.api.nvim_buf_get_name(event.buf) == ""
      or vim.fn.isdirectory(vim.api.nvim_buf_get_name(event.buf)) == 1 then return end
    vim.bo[event.buf].buflisted = true
    vim.schedule(function()
      require("config.ide").discard_empty_buffers()
      vim.cmd("redrawstatus")
    end)
  end,
})
vim.api.nvim_create_autocmd("FileType", {
  group = group,
  pattern = "neo-tree",
  callback = function(event)
    for _, key in ipairs({ "<LeftRelease>", "<2-LeftRelease>", "<3-LeftRelease>", "<4-LeftRelease>" }) do
      vim.keymap.set({ "i", "x", "s", "t" }, key, require("config.ide").tree_click,
        { buffer = event.buf, desc = "Open file or toggle directory" })
    end
  end,
})
vim.api.nvim_create_autocmd("FileType", {
  group = group,
  pattern = "aerial",
  callback = function(event)
    -- Clicking the outline from Insert mode keeps that mode until explicitly
    -- stopped; Aerial's default mappings only handle Normal/Visual mode.
    vim.keymap.set("i", "<LeftRelease>", function()
      require("config.ide").symbols_click()
    end, { buffer = event.buf, desc = "Jump to symbol" })
  end,
})
local editor_input_request = 0
vim.api.nvim_create_autocmd("ModeChanged", {
  group = group, pattern = "i*:n", callback = function()
    -- Escape must cancel an input request queued by an earlier focus event.
    editor_input_request = editor_input_request + 1
  end,
})
-- Clicking the focused document does not emit WinEnter or BufEnter.
-- Wait for release so native mouse dragging and selection keep their modes.
local editor_releases = {}
for _, prefix in ipairs({ "", "2-", "3-", "4-" }) do
  editor_releases[vim.keycode("<" .. prefix .. "LeftRelease>")] = true
end
vim.on_key(function(key, typed)
  if require("config.mouse_capture").blocked(key, typed) then return end
  if not editor_releases[typed] and not editor_releases[key] then return end
  local mouse, ide = vim.fn.getmousepos(), require("config.ide")
  local win = mouse.winid
  if ide.menu_mouse_pending or win == 0 or not vim.api.nvim_win_is_valid(win)
    or vim.api.nvim_win_get_config(win).relative ~= "" or ide.is_tool_tab()
    or mouse.line < 1 or mouse.winrow < 1 then return end
  local buf, info = vim.api.nvim_win_get_buf(win), vim.fn.getwininfo(win)[1]
  if vim.bo[buf].buftype ~= "" or not vim.bo[buf].modifiable or vim.bo[buf].readonly
    or not info or mouse.winrow > info.height + info.winbar
    or mouse.wincol <= info.textoff or mouse.wincol > info.width then return end
  local request = editor_input_request
  vim.defer_fn(function()
    if request == editor_input_request and vim.api.nvim_win_is_valid(win)
      and vim.api.nvim_get_current_win() == win and vim.api.nvim_get_current_buf() == buf
      and not ide.menu_mouse_pending and not ide.is_tool_tab()
      and vim.bo[buf].modifiable and not vim.bo[buf].readonly and vim.fn.mode() == "n" then
      vim.cmd("startinsert")
    end
  end, 20)
end, vim.api.nvim_create_namespace("DesktopEditorInputMouse"))
vim.api.nvim_create_autocmd({ "BufWinEnter", "BufEnter", "WinEnter" }, {
  group = group,
  callback = function()
    local ide, diff, scroll = require("config.ide"), require("config.diff"), require("config.hscroll")
    if ide.outline_busy or diff.busy or scroll.running then return end
    if #vim.api.nvim_list_uis() > 0 and (vim.bo.buftype == "" or vim.b.ide_diff_file) and vim.bo.modifiable
      and not vim.bo.readonly
      and not require("config.ide").is_tool_tab()
      and vim.api.nvim_win_get_config(0).relative == "" then
      local win, buf = vim.api.nvim_get_current_win(), vim.api.nvim_get_current_buf()
      editor_input_request = editor_input_request + 1
      local request = editor_input_request
      -- Leaving terminal input finishes after focus events. Wait for that mode
      -- transition before starting ordinary editor input.
      vim.defer_fn(function()
        if request == editor_input_request and vim.api.nvim_get_current_win() == win and vim.api.nvim_get_current_buf() == buf
          and not require("config.ide").is_tool_tab()
          and (vim.bo.buftype == "" or vim.b.ide_diff_file) and vim.bo.modifiable
          and not vim.bo.readonly and vim.fn.mode() == "n" then
          vim.cmd("startinsert")
        end
      end, 20)
    end
  end,
})

vim.api.nvim_create_autocmd({ "BufWinEnter", "WinEnter" }, {
  group = group,
  callback = function()
    if vim.bo.buftype == "" and vim.bo.filetype ~= "neo-tree" and vim.bo.filetype ~= "NvMenu"
      and vim.api.nvim_win_get_config(0).relative == "" then
      local ide = require("config.ide")
      if ide.main_editor and ide.main_editor ~= vim.api.nvim_get_current_win() then return end
      ide.last_editor = vim.api.nvim_get_current_win()
      vim.wo.winbar = ide.winbar()
    end
  end,
})

vim.api.nvim_create_autocmd({ "BufEnter", "LspAttach" }, {
  group = group,
  callback = function()
    if #vim.api.nvim_list_uis() > 0 and vim.bo.buftype == "" and vim.bo.filetype ~= "neo-tree"
      and vim.api.nvim_win_get_config(0).relative == "" and not require("config.ide").outline_busy then
      vim.defer_fn(function() require("config.ide").outline() end, 150)
    end
  end,
})
