-- Conventional editing and mouse support.
vim.opt.mouse = "a"
vim.opt.mousemodel = "popup_setpos"
vim.opt.selectmode = "mouse,key"
vim.opt.keymodel = "startsel,stopsel"
vim.opt.selection = "exclusive" -- Treat selections as positions between characters.
vim.opt.virtualedit = "onemore"
vim.opt.termguicolors = true
vim.opt.number = true
vim.opt.relativenumber = false
vim.opt.cursorline = true
vim.opt.wrap = false
vim.opt.showtabline = 2
vim.opt.signcolumn = "yes"
vim.opt.title = true
vim.opt.titlestring = "%t — Neovim"
vim.opt.confirm = true
-- Use the system clipboard and Neovim's native provider detection (Wayland/X11/etc.).
vim.opt.clipboard = "unnamedplus"
vim.opt.undofile = true
vim.opt.swapfile = false
vim.opt.winborder = "single"
vim.g.autoformat = false -- Formatting is explicit, so saving does not rewrite files.
vim.g.lazyvim_python_lsp = "pyright"
vim.opt.tabline = require("config.ide").menu_bar()
