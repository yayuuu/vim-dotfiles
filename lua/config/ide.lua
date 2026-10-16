local M = {}
function M.root()
  return vim.g.ide_project_dir or LazyVim.root()
end
function M.is_tool_tab(tab)
  local diffview = package.loaded["diffview.lib"]
  return diffview and diffview.tabpage_to_view(tab or vim.api.nvim_get_current_tabpage()) ~= nil or false
end
function M.is_document(buf)
  if not vim.api.nvim_buf_is_valid(buf) or vim.b[buf].ide_diff_before then return false end
  if vim.api.nvim_buf_get_name(buf):match("^diffview://") then return false end
  local kind, ft = vim.bo[buf].buftype, vim.bo[buf].filetype
  return kind == "" or kind == "help" or ft == "checkhealth" or vim.b[buf].ide_diff_file ~= nil
end
function M.editor_window()
  local diff = package.loaded["config.diff"]
  if diff and diff.active and vim.api.nvim_win_is_valid(diff.active.right)
    and vim.api.nvim_win_get_tabpage(diff.active.right) == vim.api.nvim_get_current_tabpage() then return diff.active.right end
  local function editor(win)
    if not vim.api.nvim_win_is_valid(win) or vim.api.nvim_win_get_config(win).relative ~= "" then return false end
    if vim.api.nvim_win_get_tabpage(win) ~= vim.api.nvim_get_current_tabpage() then return false end
    local buf = vim.api.nvim_win_get_buf(win)
    return M.is_document(buf)
      and vim.bo[buf].filetype ~= "neo-tree" and vim.bo[buf].filetype ~= "NvMenu"
  end
  local function remember(win) M.main_editor = win; return win end
  if M.main_editor and editor(M.main_editor) and vim.api.nvim_win_get_tabpage(M.main_editor) == vim.api.nvim_get_current_tabpage() then
    return M.main_editor
  end
  local current = vim.api.nvim_get_current_win()
  if editor(current) then return remember(current) end
  if M.last_editor and editor(M.last_editor) then return remember(M.last_editor) end
  for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
    if editor(win) then return remember(win) end
  end
  vim.cmd("vnew")
  return remember(vim.api.nvim_get_current_win())
end
function M.discard_empty_buffers()
  for _, buf in ipairs(vim.api.nvim_list_bufs()) do
    if vim.bo[buf].buflisted and vim.bo[buf].buftype == "" and not vim.bo[buf].modified
      and vim.api.nvim_buf_get_name(buf) == "" and #vim.fn.win_findbuf(buf) == 0
      and vim.api.nvim_buf_line_count(buf) == 1
      and vim.api.nvim_buf_get_lines(buf, 0, 1, false)[1] == "" then
      vim.api.nvim_buf_delete(buf, { force = false })
    end
  end
end
function M.open_file(path, buf)
  -- Neo-tree passes -1 when the file does not have a buffer yet.
  if buf and (buf < 1 or not vim.api.nvim_buf_is_valid(buf)) then buf = nil end
  if buf and vim.bo[buf].buftype == "terminal" then
    require("config.terminals").show(buf)
    return
  end
  local diff = require("config.diff")
  if buf and diff.entries[buf] then diff.show(buf); return end
  diff.leave()
  local editor = M.editor_window()
  vim.api.nvim_set_current_win(editor)
  if not buf or buf < 1 then buf = vim.fn.bufadd(path) end
  vim.fn.bufload(buf)
  -- bufadd/bufload alone leave files unlisted, so the tab strip cannot see them.
  vim.bo[buf].buflisted = true
  vim.cmd("buffer " .. buf)
  if not vim.bo[buf].modifiable then vim.cmd("stopinsert") end
  require("config.tabs").activate(buf)
  M.discard_empty_buffers()
  vim.wo.winbar = M.winbar()
  vim.cmd("redrawstatus")
  M.outline()
end
function M.pick_file()
  vim.api.nvim_set_current_win(M.editor_window())
  Snacks.picker.files({ cwd = M.root() })
end
function M.rename_file(state)
  require("config.rename").prompt(state)
end
function M.search_project()
  require("config.project_search").show()
end
function M.open_folder()
  vim.ui.input({ prompt = "Open project folder: ", default = M.root() .. "/", completion = "dir" }, function(path)
    if not path or path == "" then return end
    M.open_project(path)
  end)
end
function M.open_project(path)
  local projects = require("config.projects")
  path = projects.normalize(path)
  if not path or vim.fn.isdirectory(path) == 0 then
    vim.notify("Directory does not exist: " .. tostring(path), vim.log.levels.ERROR)
    return false
  end
  require("config.diff").leave()
  local editor = M.editor_window()
  projects.begin(path)
  require("config.diff").hide_tabs()
  require("config.terminals").hide()
  vim.cmd("cd " .. vim.fn.fnameescape(path))
  vim.g.ide_project_dir = path
  require("config.git").set_root(path)
  vim.api.nvim_set_current_win(editor)
  vim.cmd("hide enew")
  require("neo-tree.command").execute({ source = "filesystem", action = "show", dir = path })
  vim.api.nvim_set_current_win(editor)
  projects.restore(editor)
  M.terminal({ start_insert = false })
  vim.api.nvim_set_current_win(editor)
  require("config.layout").reflow()
  vim.cmd("startinsert")
  return true
end
local function selected()
  local mode = vim.fn.mode()
  return mode == "v" or mode == "V" or mode == "\22" or mode == "s" or mode == "S" or mode == "\19"
end
local function capture_selection()
  if not selected() then return end
  local anchor = vim.fn.getpos("v")
  return {
    buf = vim.api.nvim_get_current_buf(), mode = vim.fn.mode(),
    anchor = { anchor[2], anchor[3] - 1 }, cursor = vim.api.nvim_win_get_cursor(0),
  }
end
local function restore_selection(selection)
  if not selection or vim.api.nvim_get_current_buf() ~= selection.buf then return end
  local mode = selection.mode
  local key = (mode == "V" or mode == "S") and "V"
    or ((mode == "\22" or mode == "\19") and vim.keycode("<C-v>") or "v")
  vim.api.nvim_win_set_cursor(0, selection.anchor)
  vim.cmd("normal! " .. key)
  vim.api.nvim_win_set_cursor(0, selection.cursor)
end
local function selection_keys(keys)
  local mode = vim.fn.mode()
  local prefix = (mode == "s" or mode == "S" or mode == "\19") and "<C-g>" or ""
  vim.api.nvim_feedkeys(vim.keycode(prefix .. keys), "nx", false)
end
function M.new_file()
  require("config.diff").leave()
  vim.api.nvim_set_current_win(M.editor_window())
  local buf = vim.api.nvim_create_buf(true, false)
  vim.bo[buf].bufhidden = "hide"
  vim.api.nvim_win_set_buf(M.editor_window(), buf)
  require("config.tabs").activate(buf)
  vim.wo.winbar = M.winbar()
  require("config.editor_tabs").draw()
  vim.cmd("startinsert")
end
function M.save_buffer(buf, rename, done)
  local diff = require("config.diff")
  diff.flush()
  if rename and diff.entries[buf] then buf = diff.entries[buf].filebuf end
  local function write(path)
    if not vim.api.nvim_buf_is_valid(buf) then return end
    local ok, err = pcall(vim.api.nvim_buf_call, buf, function()
      if path then vim.cmd("saveas " .. vim.fn.fnameescape(path))
      else require("config.rename").write(buf) end
    end)
    if ok then require("config.editor_tabs").draw()
    else vim.notify(err, vim.log.levels.ERROR) end
    if done then done(ok) end
  end
  if rename or vim.api.nvim_buf_get_name(buf) == "" then
    vim.ui.input({ prompt = "Save as: ", default = vim.api.nvim_buf_get_name(buf), completion = "file" }, function(path)
      if path and path ~= "" then write(path) elseif done then done(false) end
    end)
  else
    write()
  end
end
function M.save_as()
  local buf = vim.api.nvim_win_get_buf(M.editor_window())
  M.save_buffer(buf, true)
end
function M.save()
  local buf = vim.api.nvim_win_get_buf(M.editor_window())
  M.save_buffer(buf, false)
end
function M.save_all()
  require("config.diff").flush()
  local buffers = vim.tbl_filter(function(buf)
    return vim.bo[buf].buflisted and vim.bo[buf].buftype == "" and vim.bo[buf].modified
  end, vim.api.nvim_list_bufs())
  local function save(index)
    if not buffers[index] then return end
    M.save_buffer(buffers[index], false, function(ok) if ok then save(index + 1) end end)
  end
  save(1)
end
function M.close_buffer(buf, done)
  local diff = require("config.diff")
  diff.flush()
  -- Closing a comparison closes its view; the ordinary file tab still owns
  -- any unsaved edits. Only closing that file asks whether to save them.
  if diff.entries[buf] then
    if diff.active and diff.active.buf == buf then
      local filebuf = diff.entries[buf].filebuf
      diff.leave()
      if vim.api.nvim_buf_is_valid(filebuf) then M.open_file(nil, filebuf) end
    end
    vim.api.nvim_buf_delete(buf, { force = true })
    if done then done(true) end
    return
  end
  local function close()
    for proxy, entry in pairs(diff.entries) do
      if entry.filebuf == buf then M.close_buffer(proxy) end
    end
    Snacks.bufdelete({ buf = buf, force = true })
    if done then done(true) end
  end
  if not vim.api.nvim_buf_is_valid(buf) then if done then done(true) end; return end
  if not vim.bo[buf].modified then close(); return end
  local name = vim.api.nvim_buf_get_name(buf)
  vim.ui.select({ "Save", "Don't save", "Cancel" }, {
    prompt = "Save changes to " .. (name == "" and "Untitled" or vim.fn.fnamemodify(name, ":t")) .. "?",
  }, function(choice)
    if choice == "Save" then
      M.save_buffer(buf, false, function(ok) if ok then close() elseif done then done(false) end end)
    elseif choice == "Don't save" then close()
    elseif done then done(false) end
  end)
end
function M.close_file()
  M.close_buffer(vim.api.nvim_win_get_buf(M.editor_window()))
end
function M.tab_menu(buf)
  M.open_file(nil, buf)
  M.popup({
    { name = "Save", rtxt = "Ctrl+S", cmd = M.save },
    { name = "Save as...", rtxt = "Alt+S", cmd = M.save_as },
    { name = "Close", rtxt = "Ctrl+W", cmd = function() M.close_buffer(buf) end },
    { name = "Pin / unpin", cmd = function() vim.cmd("BufferLineTogglePin") end },
    { name = "Reveal in project", cmd = function()
      require("neo-tree.command").execute({ source = "filesystem", action = "focus", reveal_file = vim.api.nvim_buf_get_name(buf) })
    end },
  })
end
function M.copy()
  if selected() then selection_keys('"+y') else vim.cmd('normal! "+yy') end
end
function M.cut()
  if selected() then selection_keys('"+d') else vim.cmd('normal! "+dd') end
end
function M.paste()
  if selected() then selection_keys('"+p') else vim.cmd('normal! "+P') end
end
function M.duplicate()
  if selected() then
    selection_keys('"zy"zp')
  else
    local line = vim.api.nvim_win_get_cursor(0)[1]
    local text = vim.api.nvim_buf_get_lines(0, line - 1, line, false)
    vim.api.nvim_buf_set_lines(0, line, line, false, text)
    vim.api.nvim_win_set_cursor(0, { line + 1, 0 })
  end
end
function M.move_lines(direction)
  local selection = capture_selection()
  local editor = M.editor_window()
  vim.api.nvim_set_current_win(editor)
  local buf = vim.api.nvim_get_current_buf()
  if selection and selection.buf ~= buf then selection = nil end
  local cursor = vim.api.nvim_win_get_cursor(0)
  local first, last = cursor[1], cursor[1]
  if selection then
    first, last = math.min(selection.anchor[1], cursor[1]), math.max(selection.anchor[1], cursor[1])
  end
  if (direction < 0 and first == 1) or (direction > 0 and last == vim.api.nvim_buf_line_count(buf)) then return end
  local lines = vim.api.nvim_buf_get_lines(buf, first - 1, last, false)
  if direction < 0 then
    lines[#lines + 1] = vim.api.nvim_buf_get_lines(buf, first - 2, first - 1, false)[1]
    vim.api.nvim_buf_set_lines(buf, first - 2, last, false, lines)
  else
    table.insert(lines, 1, vim.api.nvim_buf_get_lines(buf, last, last + 1, false)[1])
    vim.api.nvim_buf_set_lines(buf, first - 1, last + 1, false, lines)
  end
  vim.api.nvim_win_set_cursor(0, { cursor[1] + direction, cursor[2] })
  if selection then
    vim.api.nvim_feedkeys(vim.keycode("<Esc>"), "nx", false)
    selection.anchor[1] = selection.anchor[1] + direction
    selection.cursor[1] = selection.cursor[1] + direction
    restore_selection(selection)
    vim.api.nvim_feedkeys(vim.keycode("<C-g>"), "nx", false)
  end
end
function M.find()
  require("config.search").find()
end
function M.replace()
  require("config.search").replace()
end
function M.goto_line()
  vim.api.nvim_set_current_win(M.editor_window())
  local win = vim.api.nvim_get_current_win()
  vim.ui.input({ prompt = "Go to line: " }, function(value)
    local line = tonumber(value)
    if line and vim.api.nvim_win_is_valid(win) then
      line = math.max(1, math.min(math.floor(line), vim.api.nvim_buf_line_count(vim.api.nvim_win_get_buf(win))))
      vim.api.nvim_win_set_cursor(win, { line, 0 })
    end
  end)
end
function M.explorer()
  if M.is_tool_tab() and M.main_editor and vim.api.nvim_win_is_valid(M.main_editor) then
    vim.api.nvim_set_current_win(M.main_editor)
  end
  require("neo-tree.command").execute({ source = "filesystem", action = "focus", dir = M.root() })
  require("config.layout").reflow()
end
function M.symbols_click()
  if require("config.mouse_capture").active() or M.menu_mouse_pending then return end
  local mouse = vim.fn.getmousepos()
  if not require("config.panel_mouse").row(mouse) then return end
  if vim.bo[vim.api.nvim_win_get_buf(mouse.winid)].filetype ~= "aerial" then return end
  vim.cmd("stopinsert")
  vim.api.nvim_win_set_cursor(mouse.winid, { mouse.line, 0 })
  require("aerial").select({ winid = M.editor_window() })
end

function M.tree_click()
  if require("config.mouse_capture").active() then return end
  if M.menu_mouse_pending or require("config.git").selection_mouse_pending then return end
  local mouse = vim.fn.getmousepos()
  local win = mouse.winid
  if mouse.line < 1 or win == 0 or not vim.api.nvim_win_is_valid(win) then return end
  if not require("config.panel_mouse").row(mouse, win) then return end
  if vim.bo[vim.api.nvim_win_get_buf(win)].filetype ~= "neo-tree" then return end
  -- Mouse presses can move from an editor/terminal into Neo-tree while
  -- keeping Insert/Select mode. Finish that mode before running tree commands.
  vim.schedule(function()
    if not vim.api.nvim_win_is_valid(win) then return end
    local buf = vim.api.nvim_win_get_buf(win)
    if vim.bo[buf].filetype ~= "neo-tree" then return end
    vim.cmd("stopinsert")
    vim.api.nvim_feedkeys(vim.keycode("<Esc>"), "nx", false)
    vim.api.nvim_set_current_win(win)
    local line = math.min(mouse.line, vim.api.nvim_buf_line_count(buf))
    vim.api.nvim_win_set_cursor(win, { line, 0 })
    local state = require("neo-tree.sources.manager").get_state_for_window(win)
    if state and state.commands.open then
      if state.name == "git_status" then require("config.git").click(state, mouse)
      else state.commands.open(state) end
    end
    if vim.bo.buftype == "" and vim.bo.modifiable then vim.cmd("startinsert") end
  end)
end
function M.git_explorer()
  vim.cmd("stopinsert")
  require("neo-tree.command").execute({ source = "git_status", action = "focus", dir = M.root() })
  -- Neo-tree reuses the Files window without focusing it on the first source switch.
  local state = require("neo-tree.sources.manager").get_state("git_status")
  if state.winid and vim.api.nvim_win_is_valid(state.winid) then vim.api.nvim_set_current_win(state.winid) end
  require("config.layout").reflow()
end
function M.repository()
  if vim.fn.executable("lazygit") ~= 1 then
    vim.notify("LazyGit is not installed or is not on PATH. Install lazygit to use Repository (Alt+G). "
      .. "The Git sidebar is available with Alt+R.", vim.log.levels.WARN)
    return
  end
  return Snacks.lazygit({
    cwd = M.root(),
    auto_close = false,
    win = {
      position = "float", relative = "editor", width = 0.8, height = 0.8,
      border = "rounded", backdrop = 60, resize = true, zindex = 50,
      on_buf = function(win)
        win:on("TermClose", function()
          -- Closing the popup deletes its buffer and stops the child with -1.
          -- Report failures only while this terminal still owns a live buffer.
          if not win:buf_valid() then return end
          local status = vim.v.event.status
          if status ~= 0 then
            Snacks.notify.error("LazyGit exited with code " .. tostring(status) .. ".\nCheck the terminal for errors.")
            return
          end
          win:close()
          vim.cmd("checktime")
        end, { buf = true })
      end,
      on_win = function(win)
        require("config.popup_ui").register(win.win, function() win:close() end)
      end,
    },
  })
end
function M.terminal(options)
  require("config.terminals").toggle(options)
end
function M.new_terminal(opts)
  return require("config.terminals").new(opts)
end
function M.help()
  M.open_file(vim.fn.stdpath("config") .. "/KEYBINDS.md")
end
function M.close_menu()
  local state = package.loaded["menu.state"]
  local buf = state and state.bufids[1]
  if not buf or not vim.api.nvim_buf_is_valid(buf) then M.menu_name = nil; return end
  -- Invoke the menu's existing close action without feeding keys or briefly
  -- displaying its buffer in the editor during a toolbar switch.
  for _, mapping in ipairs(vim.api.nvim_buf_get_keymap(buf, "n")) do
    if mapping.lhs == "q" and mapping.callback then
      M.menu_name = nil
      mapping.callback()
      return
    end
  end
  require("menu.utils").delete_old_menus()
  M.menu_name = nil
end
function M.popup(items)
  M.close_menu()
  -- Menu's default mouse mode installs a global click handler that closes
  -- a newly opened toolbar menu when switching between menu headings.
  pcall(vim.keymap.del, "n", "<LeftMouse>")
  vim.cmd("stopinsert")
  local mouse = vim.fn.getmousepos()
  local source_win, source_buf = vim.api.nvim_get_current_win(), vim.api.nvim_get_current_buf()
  items = vim.deepcopy(items)
  for _, item in ipairs(items) do
    local action = item.cmd
    if action then
      -- Let the mouse press and the menu's focus restoration finish before
      -- opening another prompt/window from a menu action.
      item.cmd = function()
        vim.schedule(function()
          if vim.api.nvim_win_is_valid(source_win) and vim.api.nvim_buf_is_valid(source_buf) then
            vim.api.nvim_set_current_win(source_win)
            if vim.api.nvim_win_get_buf(source_win) ~= source_buf then
              vim.api.nvim_win_set_buf(source_win, source_buf)
            end
          end
          if type(action) == "string" then vim.cmd(action) else action() end
        end)
      end
    end
  end
  require("menu").open(items, { mouse = false, border = true })
  local win, buf = vim.api.nvim_get_current_win(), vim.api.nvim_get_current_buf()
  M.popup_buffer = buf
  vim.wo[win].winbar = ""
  -- Mouse focus/repeated clicks can preserve Insert or selection mode.
  -- Volt feeds q to dismiss; use its existing close action in these modes too.
  local close_menu = vim.fn.maparg("q", "n", false, true).callback
  if close_menu then
    vim.keymap.set({ "i", "x", "s" }, "q", close_menu, { buffer = buf, silent = true })
  end
  for _, item in ipairs(items) do
    if item.cmd and item.rtxt then
      local key = item.rtxt:gsub("Ctrl", "C"):gsub("Shift", "S"):gsub("Alt", "M"):gsub("%+", "-")
      vim.keymap.set("n", #key == 1 and key or "<" .. key .. ">", function()
        require("menu.utils").delete_old_menus()
        item.cmd()
      end, { buffer = buf, desc = item.name })
    end
  end
  local config = vim.api.nvim_win_get_config(win)
  config.relative = "editor"
  config.row = math.max(0, math.min(mouse.screenrow, vim.o.lines - config.height - 3))
  config.col = math.max(0, math.min(mouse.screencol - 1, vim.o.columns - config.width - 2))
  config.win = nil
  vim.api.nvim_win_set_config(win, config)
  -- An action closes the popup on press. Consume the matching release so
  -- it cannot open the tree row or select code underneath the vanished menu.
  local pressed, closed = false, false
  local position = vim.api.nvim_win_get_position(win)
  local height, width = vim.api.nvim_win_get_height(win), vim.api.nvim_win_get_width(win)
  local presses, releases = {}, {}
  for _, prefix in ipairs({ "", "2-", "3-", "4-" }) do
    presses[vim.keycode("<" .. prefix .. "LeftMouse>")] = true
    releases[vim.keycode("<" .. prefix .. "LeftRelease>")] = true
  end
  vim.on_key(function(key, typed)
    if require("config.mouse_capture").blocked(key, typed) then return end
    if presses[typed] or presses[key] then
      -- A release may be lost outside the host. A fresh press starts a new
      -- gesture, and a closed popup must never capture its old screen area.
      pressed, M.menu_mouse_pending = false, false
      if closed then
        if M.popup_buffer == buf then M.popup_buffer, M.menu_name = nil, nil end
        vim.on_key(nil, vim.api.nvim_create_namespace("DesktopMenuRelease"))
        return
      end
      local mouse = vim.fn.getmousepos()
      -- Volt may have already closed the popup in its own on_key listener.
      -- Screen coordinates still identify the press after its window is gone.
      if mouse.screenrow >= position[1] and mouse.screenrow <= position[1] + height + 2
        and mouse.screencol >= position[2] and mouse.screencol <= position[2] + width + 2 then
        pressed, M.menu_mouse_pending = true, true
      end
    elseif (releases[typed] or releases[key]) and pressed then
      pressed = false
      -- Buffer-local release mappings may have run before on_key. They also
      -- check this flag; clear it after the entire input event has finished.
      vim.schedule(function() M.menu_mouse_pending = false end)
      vim.on_key(nil, vim.api.nvim_create_namespace("DesktopMenuRelease"))
      return ""
    end
  end, vim.api.nvim_create_namespace("DesktopMenuRelease"))
  vim.api.nvim_create_autocmd("WinClosed", { pattern = tostring(win), once = true, callback = function()
    vim.schedule(function()
      closed = true
      -- Keyboard dismissal must not leave a mouse listener over the old popup.
      -- A mouse action keeps it only until the matching release arrives.
      if not pressed and M.popup_buffer == buf then
        M.popup_buffer, M.menu_name = nil, nil
        vim.on_key(nil, vim.api.nvim_create_namespace("DesktopMenuRelease"))
      end
    end)
  end })
  vim.api.nvim_create_autocmd("WinLeave", { buffer = buf, once = true, callback = function()
    vim.schedule(function()
      if vim.api.nvim_buf_is_valid(buf) and M.popup_buffer == buf then M.close_menu() end
    end)
  end })
end
function M.context_menu()
  if require("config.mouse_capture").active() then return end
  local debugger = package.loaded["config.debugger_mouse"]
  local pointer = vim.fn.getmousepos()
  if pointer.winid ~= 0 and vim.api.nvim_win_is_valid(pointer.winid)
    and vim.bo[vim.api.nvim_win_get_buf(pointer.winid)].filetype == "NvMenu" then return end
  if pointer.winid ~= 0 and vim.api.nvim_win_is_valid(pointer.winid)
    and vim.bo[vim.api.nvim_win_get_buf(pointer.winid)].filetype == "neo-tree" then
    local state = require("neo-tree.sources.manager").get_state_for_window(pointer.winid)
    if state and state.name == "filesystem" then
      local row = require("config.panel_mouse").row(pointer)
      local node = row and state.tree and state.tree:get_node(row)
      if node and node.type ~= "file" and node.type ~= "directory" then return end
      vim.cmd("stopinsert")
      vim.api.nvim_feedkeys(vim.keycode("<Esc>"), "nx", false)
      vim.api.nvim_set_current_win(pointer.winid)
      if node then require("config.files").select(state, node) end
      M.popup(require("config.files").menu(state, node))
      return
    end
  end
  if pointer.winid ~= 0 and vim.api.nvim_win_is_valid(pointer.winid)
    and not M.is_document(vim.api.nvim_win_get_buf(pointer.winid))
    and not require("config.panel_mouse").row(pointer) then return end
  if debugger and debugger.handles(pointer.winid) then
    debugger.context_menu(pointer.winid, pointer.line)
    return
  end
  local selection = capture_selection()
  local mouse = vim.fn.getmousepos()
  if not selection and mouse.winid ~= 0 and vim.api.nvim_win_is_valid(mouse.winid) then
    vim.api.nvim_set_current_win(mouse.winid)
    if mouse.line > 0 then
      local line = vim.api.nvim_buf_get_lines(0, mouse.line - 1, mouse.line, false)[1] or ""
      vim.api.nvim_win_set_cursor(0, { mouse.line, math.min(math.max(0, mouse.column - 1), #line) })
    end
  end
  if selection then vim.api.nvim_feedkeys(vim.keycode("<Esc>"), "nx", false) end
  require("menu.utils").delete_old_menus()
  local function edit_action(fn)
    return function()
      restore_selection(selection)
      fn()
    end
  end
  local items
  if vim.bo.filetype == "neo-tree" then
    local state = require("neo-tree.sources.manager").get_state_for_window(vim.api.nvim_get_current_win())
    local node = state and state.tree and state.tree:get_node()
    if not state or (node and node.type == "message") then return end
    if state.name == "projects" then
      M.popup({ { name = "Open project", cmd = function() state.commands.open(state) end } })
      return
    end
    if state.name == "buffers" then
      M.popup({
        { name = "Open", cmd = function() state.commands.open(state) end },
        { name = "Close tab", cmd = function() state.commands.buffer_delete(state) end },
      })
      return
    end
    if state.name == "git_status" then
      local node = state.tree and state.tree:get_node()
      items = require("config.git").menu(state, node)
    else return end
  else
    items = {
      { name = "Copy", rtxt = "Ctrl+C", cmd = edit_action(M.copy) },
      { name = "Cut", rtxt = "Ctrl+X", cmd = edit_action(M.cut) },
      { name = "Paste", rtxt = "Ctrl+V", cmd = edit_action(M.paste) },
      { name = "Save", rtxt = "Ctrl+S", cmd = M.save },
      { name = "separator" },
      { name = "Go to definition", cmd = vim.lsp.buf.definition },
      { name = "Find references", cmd = vim.lsp.buf.references },
      { name = "Documentation", cmd = vim.lsp.buf.hover },
      { name = "Rename file", rtxt = "F2", cmd = M.rename_file },
      { name = "Rename symbol", rtxt = "Shift+F2", cmd = vim.lsp.buf.rename },
      { name = "Code actions", cmd = vim.lsp.buf.code_action },
      { name = "Format", cmd = function() require("conform").format({ lsp_fallback = true }) end },
      { name = "separator" },
      { name = "Toggle breakpoint", rtxt = "F9", cmd = function() require("config.breakpoints").toggle() end },
      { name = "Terminal", rtxt = "Alt+T", cmd = M.terminal },
    }
    local inspect = package.loaded["config.debugger_inspect"]
    if inspect and inspect.available(vim.api.nvim_get_current_win()) then
      table.insert(items, #items, { name = "Inspect variable", rtxt = "Ctrl+click", cmd = inspect.inspect })
    end
  end
  M.popup(items)
end
function M.outline()
  if M.is_tool_tab() then return end
  if not require("config.sidebar").symbols_enabled() then return end
  if M.outline_busy or #vim.api.nvim_list_uis() == 0 then return end
  local previous = vim.api.nvim_get_current_win()
  local editor = M.editor_window()
  local tree
  for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
    if vim.bo[vim.api.nvim_win_get_buf(win)].filetype == "neo-tree" then tree = win; break end
  end
  if not tree then return end
  -- Aerial's delayed focus handler may see Files instead of the new document.
  -- Bind the existing Symbols window explicitly, without reopening its split.
  local treepos = vim.api.nvim_win_get_position(tree)
  for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
    if vim.bo[vim.api.nvim_win_get_buf(win)].filetype == "aerial" then
      local pos = vim.api.nvim_win_get_position(win)
      if pos[2] == treepos[2] and pos[1] > treepos[1] then
        if vim.b[vim.api.nvim_win_get_buf(win)].source_buffer ~= vim.api.nvim_win_get_buf(editor)
          or vim.w[win].source_win ~= editor then
          require("aerial").open_in_win(win, editor)
        end
        return
      end
    end
  end
  M.outline_busy = true
  local ok, err = pcall(function()
    -- Aerial can close the previously focused dialog while opening Symbols.
    -- Restore focus explicitly below, checking validity, rather than letting
    -- win_call restore a window that may no longer exist.
    vim.api.nvim_set_current_win(editor)
    require("aerial").open({ focus = false, direction = "left" })
    for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
      if vim.bo[vim.api.nvim_win_get_buf(win)].filetype == "aerial" then
        local pos, treepos = vim.api.nvim_win_get_position(win), vim.api.nvim_win_get_position(tree)
        if pos[2] ~= treepos[2] or pos[1] <= treepos[1] then
          vim.fn.win_splitmove(win, tree, { vertical = false, rightbelow = true })
        end
        vim.api.nvim_win_set_height(win, math.min(14, math.max(5, math.floor(vim.o.lines * 0.3))))
        vim.wo[win].winfixheight = true
        require("config.layout").apply("outline")
      end
    end
  end)
  if vim.api.nvim_win_is_valid(previous) then vim.api.nvim_set_current_win(previous) end
  M.outline_busy = false
  if not ok then vim.notify(err, vim.log.levels.ERROR) end
end
local menu_names = { "File", "Edit", "Search", "View", "Project", "Git", "Debug", "Terminal", "Help" }
function M.menu_width()
  local width = 0
  for _, name in ipairs(menu_names) do width = width + vim.fn.strdisplaywidth(name) + 2 end
  return width
end
function M.menu(name)
  if M.menu_name == name and M.popup_buffer and vim.api.nvim_buf_is_valid(M.popup_buffer) then
    M.close_menu()
    return
  end
  local selection = capture_selection()
  M.close_menu()
  vim.api.nvim_set_current_win(M.editor_window())
  local function edit_action(fn)
    return function()
      restore_selection(selection)
      fn()
    end
  end
  local function item(label, fn, shortcut) return { name = label, cmd = fn, rtxt = shortcut } end
  local function cmd(command) return function() vim.cmd(command) end end
  local function dap(fn) return function() require("dap")[fn]() end end
  local menus = {
    File = {
      item("New file", M.new_file, "Ctrl+N"),
      item("Open file...", M.pick_file, "Ctrl+O"),
      item("Open folder...", M.open_folder),
      { name = "separator" },
      item("Save", M.save, "Ctrl+S"), item("Save as...", M.save_as, "Alt+S"),
      item("Save all", M.save_all), item("Close file", M.close_file, "Ctrl+W"),
      { name = "separator" }, item("Exit", cmd("confirm qa")),
    },
    Edit = {
      item("Undo", cmd("undo"), "Ctrl+Z"), item("Redo", cmd("redo"), "Ctrl+Y"),
      { name = "separator" }, item("Copy", edit_action(M.copy), "Ctrl+C"), item("Cut", edit_action(M.cut), "Ctrl+X"), item("Paste", edit_action(M.paste), "Ctrl+V"),
      item("Select all", cmd("normal! ggVG" .. vim.keycode("<C-g>")), "Ctrl+A"), item("Duplicate line", edit_action(M.duplicate), "Ctrl+D"),
      item("Comment line", cmd("normal gcc"), "Ctrl+Q"),
      item("Format file", function() require("conform").format({ lsp_fallback = true }) end),
    },
    Search = {
      item("Find text...", M.find, "Ctrl+F"), item("Find next", cmd("normal! n"), "F3"), item("Find previous", cmd("normal! N"), "Shift+F3"),
      item("Replace in file...", M.replace, "Ctrl+H"),
      item("Find in project...", M.search_project, "Alt+F"),
      item("Go to line...", M.goto_line, "Ctrl+G"),
    },
    View = {
      item("Project files", M.explorer, "Alt+E"), item("Git changes", M.git_explorer, "Alt+R"),
      item("Terminal", M.terminal, "Alt+T"), item("Debugger", function() require("config.debugger").show() end, "Alt+B"),
      item("Functions / symbols", M.outline),
      item("Toggle code minimap", function() vim.cmd("Neominimap Toggle") end),
      item("Problems", function() require("config.problems").open() end),
      item("Toggle word wrap", function() vim.wo.wrap = not vim.wo.wrap end),
      item("Toggle line numbers", function() vim.wo.number = not vim.wo.number end),
    },
    Project = {
      item("Open folder...", M.open_folder), item("Find file...", M.pick_file),
      item("Terminal in project", M.terminal),
      item("Language servers", cmd("checkhealth vim.lsp")),
      item("Python environment...", cmd("VenvSelect")),
    },
    Git = {
      item("Repository", M.repository, "Alt+G"),
      item("Refresh status", function() require("config.git").refresh() end),
      item("Switch branch...", function() require("config.git").branches() end),
      item("Merge branch...", function() require("config.git_commands").merge() end),
      item("Rebase onto branch...", function() require("config.git_commands").rebase() end),
      item("Changed files", M.git_explorer, "Alt+R"), item("Diff view", cmd("DiffviewOpen"), "Alt+D"),
      item("File history", cmd("DiffviewFileHistory %")), item("Project history", cmd("DiffviewFileHistory")),
      item("Blame current line", function() require("gitsigns").blame_line({ full = true }) end),
      item("Stage hunk", function() require("gitsigns").stage_hunk() end),
    },
    Debug = {
      item("Start / continue", dap("continue"), "F5"), item("Stop", dap("terminate"), "Shift+F5"),
      item("Toggle breakpoint", function() require("config.breakpoints").toggle() end, "F9"),
      item("Conditional breakpoint...", function() require("dap").set_breakpoint(vim.fn.input("Condition: ")) end),
      item("Step over", dap("step_over"), "F10"), item("Step into", dap("step_into"), "F11"), item("Step out", dap("step_out"), "Shift+F11"),
      item("Debugger panels", function() require("config.debugger").show() end, "Alt+B"),
      item("Evaluate expression", function() require("dapui").eval() end),
    },
    Terminal = { item("Show / hide", M.terminal, "Alt+T"), item("New terminal", M.new_terminal) },
    Help = {
      item("Shortcut guide", M.help, "F1"), item("Neovim help", cmd("help")),
      item("Command palette", function() Snacks.picker.commands() end, "Alt+P"),
      item("Plugins", cmd("Lazy")), item("Language tools", cmd("Mason")), item("LazyVim extras", cmd("LazyExtras")),
      item("Health check", cmd("checkhealth")), item("Edit configuration", function() Snacks.picker.files({ cwd = vim.fn.stdpath("config") }) end),
    },
  }
  M.popup(menus[name])
  M.menu_name = name
end
_G.DesktopIDEMenu = function(id, _, button)
  if button == "l" and menu_names[id] then M.menu(menu_names[id]) end
end
_G.DesktopIDERepository = function()
  local name = require("config.git_sync").repository_name()
  local menu_width = M.menu_width()
  local available = vim.o.columns - menu_width - 2
  if name == "" or available < 1 then return "" end
  if vim.fn.strdisplaywidth(name) > available then
    name = vim.fn.strcharpart(name, 0, available - 1)
    while vim.fn.strdisplaywidth(name) > available - 1 do
      name = vim.fn.strcharpart(name, 0, vim.fn.strchars(name) - 1)
    end
    name = name .. "…"
  end
  local width = vim.fn.strdisplaywidth(name)
  local start = math.floor((vim.o.columns - width) / 2)
  if start <= menu_width then start = vim.o.columns - width - 1 end
  return string.rep(" ", start - menu_width) .. name
end
function M.menu_bar()
  local parts = { "%#WinBar#" }
  for id, name in ipairs(menu_names) do
    parts[#parts + 1] = "%" .. id .. "@v:lua.DesktopIDEMenu@ " .. name .. " %T"
  end
  parts[#parts + 1] = "%#DesktopRepositoryName#%{v:lua.DesktopIDERepository()}%#WinBar#"
  return table.concat(parts)
end
_G.DesktopIDEBufferline = function()
  if _G.nvim_bufferline then
    local ok, line = pcall(_G.nvim_bufferline)
    if ok then return line end
  end
  return " %t "
end
function M.winbar() return "%!v:lua.DesktopIDEBufferline()" end
return M
