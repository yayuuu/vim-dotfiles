-- Window-local margins without changing symbol/DAP buffers or their row data.
local M = {}
local api = vim.api
local namespace = api.nvim_create_namespace("DesktopPanelPadding")
local types = { aerial = true, dapui_scopes = true, dapui_breakpoints = true,
  dapui_stacks = true, dapui_watches = true }

function M.right(win)
  return types[vim.bo[api.nvim_win_get_buf(win)].filetype] and 1 or 0
end

function M.attach(win)
  if M.right(win) == 0 then return end
  -- A nonzero native gutter reserves the column; statuscolumn renders only a
  -- blank instead of fold controls. It stays fixed during horizontal scrolling.
  for key, value in pairs({ number = false, relativenumber = false, signcolumn = "no",
    foldcolumn = "1", statuscolumn = "%#Normal# " }) do vim.wo[win][key] = value end
end

function M.setup()
  local columns = {}
  api.nvim_set_decoration_provider(namespace, {
    on_win = function(_, win)
      if M.right(win) == 0 or api.nvim_win_get_config(win).relative ~= "" then return false end
      columns[win] = math.max(0, api.nvim_win_get_width(win) - vim.fn.getwininfo(win)[1].textoff
        - require("config.vscroll").width(win) - 1)
    end,
    on_line = function(_, win, buf, row)
      api.nvim_buf_set_extmark(buf, namespace, row, 0, { ephemeral = true,
        virt_text = { { " ", "Normal" } }, virt_text_pos = "overlay",
        virt_text_win_col = columns[win], priority = 1000 })
    end,
  })
  api.nvim_create_autocmd({ "FileType", "BufWinEnter" }, {
    group = api.nvim_create_augroup("DesktopPanelPadding", { clear = true }),
    callback = function() M.attach(api.nvim_get_current_win()) end,
  })
end

return M
