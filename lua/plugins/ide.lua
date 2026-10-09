return {
  { "stevearc/aerial.nvim", lazy = false, opts = {
    backends = { "treesitter", "lsp", "markdown" },
    attach_mode = "global", close_automatic_events = {},
    ignore = { filetypes = { "neo-tree", "NvMenu", "VoltWindow", "noice", "snacks_input", "snacks_terminal", "neominimap",
      "ide_git_history", "ide_terminal_list" } },
    layout = { width = 30, min_width = 20, max_width = 40, placement = "window", default_direction = "left",
      resize_to_content = false, preserve_equality = false },
    filter_kind = { "Class", "Constructor", "Function", "Method", "Interface", "Enum", "Struct" },
    icons = { Class = "C", Constructor = "c", Function = "f", Method = "m", Interface = "I", Enum = "E", Struct = "S" },
    show_guides = true,
    keymaps = { ["<LeftRelease>"] = "actions.jump", ["<2-LeftMouse>"] = "actions.jump" },
    win_opts = { winbar = " Functions / Symbols ", number = false, relativenumber = false },
  }, config = function(_, opts)
    require("aerial").setup(opts)
    -- Keep empty Symbols panels compact; backend details remain in :AerialInfo.
    local util = require("aerial.util")
    local render_centered_text = util.render_centered_text
    util.render_centered_text = function(buf, text)
      if type(text) == "table" and text[1] == "No symbols" then text = { "No symbols" } end
      return render_centered_text(buf, text)
    end
    local window = require("aerial.window")
    local open = window.open_aerial_in_win
    local pending = false
    window.open_aerial_in_win = function(...)
      if not require("config.sidebar").symbols_enabled() then return end
      local mode = vim.fn.mode()
      if mode == "v" or mode == "V" or mode == "\22" or mode == "s" or mode == "S" or mode == "\19" then
        -- Replacing a sidebar buffer through nvim_win_set_buf cancels the
        -- editor's selection. Refresh the outline when selection ends.
        if not pending then
          pending = true
          vim.api.nvim_create_autocmd("ModeChanged", { once = true, callback = function()
            pending = false
            vim.schedule(function() require("aerial.autocommands").on_enter_buffer() end)
          end })
        end
        return
      end
      return open(...)
    end
  end },
  { "saghen/blink.cmp", opts = { keymap = {
    ["<C-y>"] = false, ["<C-n>"] = false, ["<C-f>"] = false,
    ["<Tab>"] = { "select_and_accept", "snippet_forward", "fallback" },
  } } },
  { "Mofiqul/vscode.nvim", priority = 1000, opts = { style = "dark", transparent = false } },
  { "LazyVim/LazyVim", opts = {
    colorscheme = "vscode",
    icons = {
      diagnostics = { Error = "E ", Warn = "W ", Hint = "H ", Info = "I " },
      git = { added = "+", modified = "~", removed = "-" },
      dap = { Stopped = { ">", "DiagnosticWarn", "DapStoppedLine" }, Breakpoint = "●", BreakpointCondition = "?", BreakpointRejected = "x", LogPoint = "L" },
    },
  } },
  -- ASCII file badges work with the existing Unifont in kmscon.
  { "nvim-mini/mini.icons", opts = { style = "ascii" } },
  { "nvim-neo-tree/neo-tree.nvim", opts = {
    sources = { "config.project_source", "filesystem", "config.debug_source", "config.git_source", "config.tab_source" },
    close_if_last_window = false,
    open_files_do_not_replace_types = { "aerial", "NvMenu", "neominimap", "snacks_terminal", "terminal", "nofile", "prompt", "quickfix", "Trouble", "trouble", "qf", "Outline" },
    event_handlers = { { event = "after_render", handler = function(state) require("config.git").after_render(state) end },
      { event = "neo_tree_window_after_open", handler = function(args) require("config.git").enter(args) end },
      { event = "neo_tree_window_before_open", handler = function(args) require("config.sidebar").prepare(args) end },
      { event = "neo_tree_window_after_open", handler = function() require("config.sidebar").schedule() end },
      { event = "file_open_requested", handler = function(args)
      if args.open_cmd ~= "edit" then return end
      require("config.ide").open_file(args.path, args.bufnr)
      return { handled = true }
    end } },
    source_selector = { winbar = true, statusline = false, tabs_layout = "start", padding = { left = 1, right = 0 },
      separator = { left = "", right = " ", override = "right" }, sources = {
      { source = "projects", display_name = "Projects" },
      { source = "filesystem", display_name = "Files" },
      { source = "debug", display_name = "Debug" },
      { source = "git_status", display_name = "Git" },
      { source = "buffers", display_name = "Tabs" },
    } },
    filesystem = { commands = {
      open = function(state)
        local node = state.tree and state.tree:get_node()
        if not node or node.type == "message" then return end
        require("neo-tree.sources.filesystem.commands").open(state)
      end,
    } },
    git_status = { bind_to_cwd = false, cwd_target = { sidebar = "global", current = "global" }, components = {
      name = function(...) return require("config.git").name(...) end,
      git_directory = function(...) return require("config.git").directory(...) end,
    }, renderers = { directory = { { "git_directory" } } }, commands = {
      open = function(state) require("config.git").open(state) end,
    }, window = { mappings = {
      ["R"] = function() require("config.git").refresh() end,
      ["<F5>"] = function() require("config.git").refresh() end,
      ["<LeftRelease>"] = function(state) require("config.git").click(state) end,
      ["<2-LeftRelease>"] = function(state) require("config.git").click(state) end,
      ["<3-LeftRelease>"] = function(state) require("config.git").click(state) end,
      ["<4-LeftRelease>"] = function(state) require("config.git").click(state) end,
    } } },
    window = { width = 30, mappings = {
      ["<C-s>"] = function() require("config.ide").save() end,
      ["<C-f>"] = function() require("config.ide").find() end,
      ["<LeftRelease>"] = "open", ["<2-LeftRelease>"] = "open",
      ["<3-LeftRelease>"] = "open", ["<4-LeftRelease>"] = "open",
      -- Consume repeated presses so Vim doesn't start word/line selection.
      ["<2-LeftMouse>"] = function() end,
      ["<3-LeftMouse>"] = function() end,
      ["<4-LeftMouse>"] = function() end,
    } },
    default_component_configs = {
      icon = { folder_closed = "+", folder_open = "-", folder_empty = "+", default = "·" },
      indent = { expander_collapsed = ">", expander_expanded = "v" },
      git_status = { symbols = { added = "+", modified = "~", deleted = "-", renamed = "R", untracked = "?", ignored = "!", unstaged = "~", staged = "+", conflict = "!" } },
    },
  } },
  { "akinsho/bufferline.nvim", opts = { options = {
    always_show_bufferline = true, show_buffer_icons = false,
    persist_buffer_sort = false,
    sort_by = function(a,b) return require("config.tabs").compare(a,b) end,
    separator_style = "thin", buffer_close_icon = "×", close_icon = "×",
    indicator = { style = "icon", icon = "" },
    modified_icon = "●", left_trunc_marker = "<", right_trunc_marker = ">",
    close_command = function(buf) require("config.ide").close_buffer(buf) end,
    left_mouse_command = function(buf)
      require("config.ide").open_file(nil, buf)
      if vim.bo.modifiable and vim.bo.buftype == "" then vim.cmd("startinsert") end
    end,
    right_mouse_command = function(buf) require("config.ide").tab_menu(buf) end,
    middle_mouse_command = function(buf) require("config.ide").close_buffer(buf) end,
    offsets = {},
    custom_filter = function(buf) return not vim.b[buf].ide_diff_before end,
    name_formatter = function(buf)
      if vim.b[buf.bufnr].ide_diff_file then return vim.fn.fnamemodify(vim.b[buf.bufnr].ide_diff_file, ":t") .. " (diff)" end
    end,
  } }, config = function(_, opts)
    require("bufferline").setup(opts)
    vim.o.tabline = require("config.ide").menu_bar()
    vim.api.nvim_create_autocmd({ "BufAdd", "BufDelete" }, { callback = function()
      vim.schedule(function() if _G.nvim_bufferline then pcall(_G.nvim_bufferline) end; vim.cmd("redrawstatus") end)
    end })
  end },
  { "nvim-lualine/lualine.nvim", opts = function(_, opts)
    opts.options.component_separators = { left = "|", right = "|" }
    opts.options.section_separators = { left = "", right = "" }
    opts.sections.lualine_a = { "mode" }
    opts.sections.lualine_b = { { "branch", icon = "git", on_click = function(_, button)
      if button == "l" then vim.schedule(function() require("config.git").branches() end) end
    end }, { function() return require("config.git_sync").label() end,
      cond = function() return require("config.git_sync").visible() end,
      color = { fg = "#ffffff", bg = "#3c3c3c" }, padding = { left = 1, right = 1 },
      on_click = function(_, button)
        if button == "l" then vim.schedule(function() require("config.git_sync").sync() end) end
      end,
    } }
    opts.sections.lualine_c = { { "filename", path = 1 }, "diff", "diagnostics" }
    opts.sections.lualine_x = { "encoding", "fileformat", "filetype" }
    opts.sections.lualine_y = { "progress" }
    opts.sections.lualine_z = { "location" }
  end },
  { "folke/snacks.nvim", opts = {
    dashboard = { enabled = false }, scroll = { enabled = false },
    terminal = { win = { position = "bottom", relative = "win", height = 0.25, stack = false, resize = false }, shell = "/bin/bash" },
    input = { win = { on_win = function(win)
      require("config.popup_ui").register(win.win, function() win:execute("cancel") end)
    end } },
    picker = {
      on_show = function(picker)
        require("config.popup_ui").register(picker.layout.root.win, function() picker:close() end)
      end,
      icons = { files = { enabled = false }, tree = { vertical = "│ ", middle = "├─", last = "└─" } },
    },
  } },
  { "sindrets/diffview.nvim", cmd = { "DiffviewOpen", "DiffviewFileHistory" }, opts = { use_icons = false } },
  { "nvzone/menu", lazy = true, dependencies = { "nvzone/volt" } },
  { "rcarriga/nvim-dap-ui", opts = function(_, opts)
    opts.expand_lines = false
    opts.select_window = function() return require("config.ide").editor_window() end
    opts.icons = { expanded = "v", collapsed = ">", current_frame = ">" }
    opts.controls = { enabled = true, icons = { pause = "||", play = ">", step_into = "v", step_over = ">|", step_out = "^", step_back = "<", run_last = "R", terminate = "X", disconnect = "D" } }
    opts.layouts = {}
  end, config = function(_, opts)
    require("dapui").setup(opts)
    require("config.debugger").setup(require("dap"))
  end, keys = {
    { "<leader>du", function() require("config.debugger").show() end, desc = "Debug sidebar" },
  } },
  { "mfussenegger/nvim-dap", keys = {
    { "<leader>dr", function() require("config.terminals").show_debug_console() end, desc = "Debug console" },
  } },
  { "mason-org/mason.nvim", opts = { ensure_installed = {
    "lua-language-server", "stylua", "pyright", "ruff", "bash-language-server", "shfmt", "vtsls", "prettier", "debugpy", "codelldb", "js-debug-adapter",
  } } },
  { "neovim/nvim-lspconfig", opts = { servers = { bashls = {}, clangd = { mason = false } } } },
}
