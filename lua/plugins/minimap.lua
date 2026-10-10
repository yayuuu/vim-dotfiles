return {
  {
    "Isrothy/neominimap.nvim",
    lazy = false,
    version = "v3.x.x",
    init = function()
      vim.g.neominimap = {
        auto_enable = true,
        layout = "float",
        current_line_position = "percent",
        x_multiplier = 4,
        y_multiplier = 1,
        delay = 120,
        float = {
          minimap_width = 12,
          window_border = "none",
          z_index = 10,
          margin = { right = 0, top = 0, bottom = 0 },
        },
        click = { enabled = true, auto_switch_focus = false },
        exclude_filetypes = {
          "help",
          "bigfile",
          "neo-tree",
          "aerial",
          "NvMenu",
          "VoltWindow",
          "noice",
          "snacks_input",
          "snacks_picker_list",
          "snacks_picker_preview",
          "snacks_terminal",
          "Trouble",
          "trouble",
          "lazy",
          "mason",
          "dapui_scopes",
          "dapui_breakpoints",
          "dapui_stacks",
          "dapui_watches",
          "dapui_console",
          "dap-repl",
          "DiffviewFiles",
          "DiffviewFileHistory",
        },
        buf_filter = function(buf)
          return (vim.bo[buf].buftype == "" or vim.b[buf].ide_diff_file)
            and vim.bo[buf].buflisted
            and vim.api.nvim_buf_get_name(buf) ~= ""
            and vim.fn.isdirectory(vim.api.nvim_buf_get_name(buf)) == 0
        end,
        win_filter = function(win)
          return vim.api.nvim_win_get_config(win).relative == "" and not vim.w[win].snacks_picker_preview
        end,
        winopt = function(opt)
          opt.winbar = ""
          opt.statuscolumn = ""
          opt.signcolumn = "yes:1"
        end,
        diagnostic = {
          mode = "icon",
          icon = { ERROR = "!", WARN = "!", INFO = "i", HINT = "." },
        },
        git = { enabled = true, mode = "sign" },
        search = { enabled = true, mode = "sign" },
        fold = { enabled = false },
        handlers = {
          {
            name = "desktop_diff", mode = "line",
            namespace = vim.api.nvim_create_namespace("DesktopMinimapDiff"), init = function() end,
            autocmds = { { event = { "TextChanged", "TextChangedI", "BufWinEnter" }, opts = { get_buffers = function(args) return args.buf end } } },
            get_annotations = function(buf)
              local result = {}
              if not vim.b[buf].ide_diff_file then return result end
              for i, h in ipairs(require("config.diff").hunks(buf)) do
                local first = math.max(1, h[3])
                result[#result + 1] = { lnum = first, end_lnum = first + math.max(0, h[4] - 1), id = i,
                  priority = 110, highlight = h[2] == 0 and "DesktopMapAdd" or h[4] == 0 and "DesktopMapDelete" or "DesktopMapChange" }
              end
              return result
            end,
          },
          {
            name = "desktop_viewport",
            mode = "line",
            namespace = vim.api.nvim_create_namespace("DesktopMinimapViewport"),
            init = function() end,
            autocmds = {
              {
                event = { "WinScrolled", "WinResized", "BufWinEnter" },
                opts = {
                  callback = function()
                    require("config.minimap").refresh_viewport()
                  end,
                },
              },
            },
            get_annotations = function(buf)
              local ranges = {}
              for _, win in ipairs(vim.fn.win_findbuf(buf)) do
                if vim.api.nvim_win_get_config(win).relative == "" then
                  local info = vim.fn.getwininfo(win)[1]
                  ranges[#ranges + 1] = {
                    lnum = info.topline,
                    end_lnum = info.botline,
                    id = win,
                    priority = 90,
                    highlight = "DesktopMinimapViewport",
                  }
                end
              end
              return ranges
            end,
          },
        },
      }
      -- Keep the cursor clear of the floating map when editing long lines.
      vim.opt.sidescrolloff = 16
    end,
    config = function()
      local function colors()
        vim.api.nvim_set_hl(0, "NeominimapBackground", { link = "Normal" })
        vim.api.nvim_set_hl(0, "NeominimapCursorLine", { link = "Visual" })
        vim.api.nvim_set_hl(0, "DesktopMinimapViewport", { link = "CursorLine" })
      end
      colors()
      vim.api.nvim_create_autocmd("ColorScheme", {
        group = vim.api.nvim_create_augroup("DesktopMinimap", { clear = true }),
        callback = colors,
      })
      require("config.minimap").setup()
      -- Native wheel events scroll only the floating preview. Route those
      -- over the map to its source, preserving the user's current mode.
      for key, command in pairs({
        ["<ScrollWheelDown>"] = "3" .. vim.keycode("<C-e>"),
        ["<ScrollWheelUp>"] = "3" .. vim.keycode("<C-y>"),
      }) do
        vim.keymap.set({ "n", "i", "x", "s", "t" }, key, function()
          local mouse = vim.fn.getmousepos()
          if
            mouse.winid == 0
            or not vim.api.nvim_win_is_valid(mouse.winid)
            or vim.bo[vim.api.nvim_win_get_buf(mouse.winid)].filetype ~= "neominimap"
          then
            return key
          end
          local source = require("neominimap.window.float.window_map").get_parent_winid(mouse.winid)
          if source then
            vim.schedule(function()
              if vim.api.nvim_win_is_valid(source) then
                vim.api.nvim_win_call(source, function()
                  vim.cmd.normal({ command, bang = true })
                end)
              end
            end)
          end
          return "<Ignore>"
        end, { expr = true, silent = true, desc = "Scroll code from its minimap" })
      end
    end,
  },
}
