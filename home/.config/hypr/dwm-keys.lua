-- dwm-style layouts on Hyprland. Workspaces remain single-membership.
local M = {}
local states = {}
local float_tag = "dwm-layout-float"

local function tagged(window)
    for _, tag in ipairs(window.tags or {}) do
        if tag == float_tag then return true end
    end
    return false
end

local function restore(window)
    if not tagged(window) then return end
    hl.dispatch(hl.dsp.window.tag({ window = window, tag = "-" .. float_tag }))
    hl.dispatch(hl.dsp.window.float({ window = window, action = "off" }))
end

-- Reload resets the layout selection; restore only windows floated by this module.
for _, window in ipairs(hl.get_windows()) do restore(window) end

local function state(workspace)
    local id = workspace.id
    if not states[id] then states[id] = { current = workspace.tiled_layout, previous = "floating" } end
    return states[id]
end

local function float(window)
    if window.floating then return end
    hl.dispatch(hl.dsp.window.tag({ window = window, tag = "+" .. float_tag }))
    hl.dispatch(hl.dsp.window.float({ window = window, action = "on" }))
end

function M.set_layout(layout)
    local workspace = hl.get_active_workspace()
    if not workspace then return end
    local s = state(workspace)
    layout = layout or s.previous
    if layout == s.current then return end
    s.previous, s.current = s.current, layout
    if layout == "floating" then
        for _, window in ipairs(hl.get_workspace_windows(workspace)) do float(window) end
    else
        for _, window in ipairs(hl.get_workspace_windows(workspace)) do restore(window) end
        hl.workspace_rule({ workspace = workspace.config_name, layout = layout })
        hl.exec_scheduled_prop_refresh_immediately()
    end
end

function M.cycle(next)
    local workspace = hl.get_active_workspace()
    if not workspace then return end
    local mode = state(workspace).current
    if mode == "floating" then
        hl.dispatch(hl.dsp.window.cycle_next({ next = next }))
    else
        hl.dispatch(hl.dsp.layout(next and "cyclenext" or "cycleprev"))
    end
end

function M.master(message)
    local workspace = hl.get_active_workspace()
    if workspace and state(workspace).current == "master" then
        hl.dispatch(hl.dsp.layout(message))
    end
end

local function sync_window(window)
    if not window or not window.workspace then return end
    local s = states[window.workspace.id]
    if s and s.current == "floating" then float(window) else restore(window) end
end
hl.on("window.open", sync_window)
hl.on("window.move_to_workspace", sync_window)
hl.on("workspace.removed", function()
    -- The removed workspace handle no longer exposes its properties.
    for id in pairs(states) do
        if not hl.get_workspace(id) then states[id] = nil end
    end
end)

return M
