-- Files and documentation share the main editor; tool panels keep their windows.
local M = {}
local api = vim.api
local function valid(win) return win and api.nvim_win_is_valid(win) end
local function routable(win, buf)
  return valid(win) and api.nvim_win_get_config(win).relative == ""
    and not require("config.ide").is_tool_tab(api.nvim_win_get_tabpage(win))
    and api.nvim_win_get_buf(win) == buf and not vim.w[win].snacks_picker_preview
    and not vim.wo[win].diff and require("config.ide").is_document(buf)
end

function M.write_close_command(command)
  local win, buf = api.nvim_get_current_win(), api.nvim_get_current_buf()
  if vim.fn.getcmdtype() == ":" and vim.fn.getcmdline():match("^%s*" .. command .. "$")
    and #api.nvim_list_uis() > 0 and api.nvim_win_get_config(win).relative == ""
    and not require("config.ide").is_tool_tab()
    and (vim.bo[buf].buftype == "" or vim.b[buf].ide_diff_file) then
    return "WriteCloseDocument"
  end
  return command
end

function M.setup()
  api.nvim_create_user_command("WriteCloseDocument", function()
    local ide = require("config.ide")
    local buf = api.nvim_win_get_buf(ide.editor_window())
    ide.save_buffer(buf, false, function(saved)
      if saved then ide.close_buffer(buf) end
    end)
  end, { desc = "Save and close the current document" })
  -- Native :wq closes a split, including our shared editor and its tab strip.
  -- Redirect only standalone interactive commands in the managed workspace.
  for _, command in ipairs({ "wq", "wquit" }) do
    vim.cmd(("cnoreabbrev <expr> %s v:lua.require'config.documents'.write_close_command('%s')"):format(command, command))
  end
  api.nvim_create_autocmd({ "BufWinEnter", "FileType", "WinNew" }, {
    group = api.nvim_create_augroup("DesktopDocuments", { clear = true }),
    callback = function()
      local ide, diff = require("config.ide"), require("config.diff")
      local win, buf = api.nvim_get_current_win(), api.nvim_get_current_buf()
      if #api.nvim_list_uis() == 0 or diff.busy or not routable(win, buf) then return end
      local target = ide.main_editor
      if not valid(target) then return end
      vim.schedule(function()
        if not routable(win, buf) or not valid(target) or diff.busy then return end
        local documentation = vim.bo[buf].buftype == "help" or vim.bo[buf].filetype == "checkhealth"
        if documentation then
          vim.bo[buf].bufhidden = "hide"
          vim.bo[buf].buflisted = true
          -- q closes the document tab rather than the main editor window.
          vim.keymap.set("n", "q", function() ide.close_buffer(buf) end,
            { buffer = buf, silent = true, desc = "Close document" })
        end
        if win ~= target then
          local cursor = api.nvim_win_get_cursor(win)
          api.nvim_set_current_win(target)
          ide.open_file(nil, buf)
          api.nvim_win_set_cursor(ide.editor_window(), cursor)
          api.nvim_win_close(win, false)
          require("config.layout").reflow()
        elseif documentation then
          vim.wo[win].winbar = ide.winbar()
          require("config.tabs").activate(buf)
        end
      end)
    end,
  })
end

return M
