hl.monitor({ output = "", mode = "preferred", position = "auto", scale = 1 })

hl.config({
    general = {
        layout = "master",
        gaps_in = 0,
        gaps_out = 0,
        border_size = 2,
        col = {
            active_border = {
                colors = { "rgb(8caaa0)", "rgb(b3919e)" },
                angle = 45,
            },
            inactive_border = {
                colors = { "rgb(504945)", "rgb(3c3836)" },
                angle = 45,
            },
        },
        resize_on_border = true,
    },
    master = {
        mfact = 0.55,
        new_status = "master",
        new_on_top = true,
        allow_small_split = true,
        orientation = "left",
    },
    decoration = {
        rounding = 0,
        shadow = { enabled = false },
        blur = { enabled = false },
    },
    animations = { enabled = false },
    input = {
        kb_layout = "us,ru",
        kb_options = "grp:alt_shift_toggle",
        numlock_by_default = true,
        repeat_delay = 250,
        repeat_rate = 40,
        follow_mouse = 1,
        accel_profile = "flat",
    },
    binds = { workspace_back_and_forth = false },
    misc = {
        disable_hyprland_logo = true,
        disable_splash_rendering = true,
        vrr = 2,
    },
})

hl.on("hyprland.start", function()
    hl.exec_cmd("uwsm finalize")
end)

-- Upstream dwm config.def.h, with Mod4 / SUPER and Wayland applications.
dwm_keys = dofile(os.getenv("HOME") .. "/.config/hypr/dwm-keys.lua")
window_bounds = dofile(os.getenv("HOME") .. "/.config/hypr/window-bounds.lua")
hl.bind("SUPER + P", hl.dsp.exec_cmd("fuzzel"))
hl.bind("SUPER + SHIFT + Return", hl.dsp.exec_cmd("uwsm app -- alacritty"))
hl.bind("SUPER + B", hl.dsp.exec_cmd("pkill -USR1 -x waybar"))
hl.bind("SUPER + J", function() dwm_keys.cycle(true) end)
hl.bind("SUPER + K", function() dwm_keys.cycle(false) end)
hl.bind("SUPER + I", function() dwm_keys.master("addmaster") end)
hl.bind("SUPER + D", function() dwm_keys.master("removemaster") end)
hl.bind("SUPER + H", function() dwm_keys.master("mfact -0.05") end)
hl.bind("SUPER + L", function() dwm_keys.master("mfact +0.05") end)
hl.bind("SUPER + Return", function() dwm_keys.master("swapwithmaster master") end)
hl.bind("SUPER + Tab", hl.dsp.focus({ workspace = "previous" }))
hl.bind("SUPER + SHIFT + C", hl.dsp.window.close())
hl.bind("SUPER + T", function() dwm_keys.set_layout("master") end)
hl.bind("SUPER + F", function() dwm_keys.set_layout("floating") end)
hl.bind("SUPER + M", function() dwm_keys.set_layout("monocle") end)
hl.bind("SUPER + space", function() dwm_keys.set_layout() end)
hl.bind("SUPER + SHIFT + space", hl.dsp.window.float({ action = "toggle" }))
-- dwm toggleview/toggletag/view-all/tag-all have no native workspace equivalent.
hl.bind("SUPER + comma", hl.dsp.focus({ monitor = "-1" }))
hl.bind("SUPER + period", hl.dsp.focus({ monitor = "+1" }))
hl.bind("SUPER + SHIFT + comma", hl.dsp.window.move({ monitor = "-1", follow = false }))
hl.bind("SUPER + SHIFT + period", hl.dsp.window.move({ monitor = "+1", follow = false }))
hl.bind("SUPER + SHIFT + Q", hl.dsp.exec_cmd("uwsm stop"))
for i = 1, 9 do
    hl.bind("SUPER + " .. i, hl.dsp.focus({ workspace = i }))
    hl.bind("SUPER + SHIFT + " .. i, hl.dsp.window.move({ workspace = i, follow = false }))
end

-- Additional desktop functions, without aliases for upstream dwm bindings.
hl.bind("SUPER + E", hl.dsp.exec_cmd("uwsm app -- desktop-file-manager"))
hl.bind("SUPER + SHIFT + P", hl.dsp.exec_cmd("desktop-power-menu"))
hl.bind("SUPER + SHIFT + J", hl.dsp.layout("swapnext"))
hl.bind("SUPER + SHIFT + K", hl.dsp.layout("swapprev"))
hl.bind("SUPER + SHIFT + F", hl.dsp.window.fullscreen({ mode = "fullscreen" }))
hl.bind("SUPER + SHIFT + M", hl.dsp.window.fullscreen({ mode = "maximized" }))
for key, dir in pairs({ left = "left", right = "right", up = "up", down = "down" }) do
    hl.bind("SUPER + " .. key, hl.dsp.focus({ direction = dir }))
end

hl.bind("SUPER + mouse:272", hl.dsp.window.drag())
hl.bind("SUPER + mouse:274", hl.dsp.window.float({ action = "toggle" }))
hl.bind("SUPER + mouse:273", hl.dsp.window.resize())
hl.bind("SUPER + ALT + L", hl.dsp.exec_cmd("loginctl lock-session"))
hl.bind("SUPER + SHIFT + E", hl.dsp.exec_cmd("desktop-session-menu"))
hl.bind("SUPER + SHIFT + R", hl.dsp.exec_cmd("hyprctl reload"))
hl.bind("SUPER + F1", hl.dsp.exec_cmd("uwsm app -- alacritty -e sh -c 'less \"$HOME/.config/hypr/KEYS.txt\"'"))
hl.bind("SUPER + N", hl.dsp.exec_cmd("makoctl dismiss"))
hl.bind("SUPER + SHIFT + N", hl.dsp.exec_cmd("makoctl restore"))
hl.bind("Print", hl.dsp.exec_cmd("desktop-screenshot region"))
hl.bind("CTRL + Print", hl.dsp.exec_cmd("desktop-screenshot screen"))
hl.bind("SUPER + Print", hl.dsp.exec_cmd("desktop-record region"))
hl.bind("SUPER + CTRL + Print", hl.dsp.exec_cmd("desktop-record screen"))
hl.bind("SUPER + SHIFT + Print", hl.dsp.exec_cmd("desktop-record-menu"))
hl.bind(
    "XF86AudioRaiseVolume",
    hl.dsp.exec_cmd("wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+"),
    { locked = true, repeating = true }
)
hl.bind(
    "XF86AudioLowerVolume",
    hl.dsp.exec_cmd("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"),
    { locked = true, repeating = true }
)
hl.bind("XF86AudioMute", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"), { locked = true })
hl.bind("XF86AudioMicMute", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"), { locked = true })
for key, action in pairs({
    XF86AudioPlay = "play-pause",
    XF86AudioPause = "play-pause",
    XF86AudioNext = "next",
    XF86AudioPrev = "previous",
    XF86AudioStop = "stop",
}) do
    hl.bind(key, hl.dsp.exec_cmd("playerctl " .. action), { locked = true })
end

hl.window_rule({
    name = "picture-in-picture",
    match = { title = "^(Picture-in-Picture|Картинка в картинке)$" },
    float = true,
    pin = true,
})
hl.window_rule({
    name = "audio-controls",
    match = { class = "^(org.pulseaudio.pavucontrol|pavucontrol)$" },
    float = true,
    center = true,
})

hl.window_rule({
    name = "calculator",
    match = { class = "^mate-calc$" },
    float = true,
    center = true,
})
hl.window_rule({
    name = "archive-manager",
    match = { class = "^([Xx]archiver|desktop-archive-action)$" },
    float = true,
    center = true,
})

hl.window_rule({
    name = "file-chooser",
    match = { class = "^xdg-desktop-portal-gtk$" },
    float = true,
    center = true,
})

-- Machine-specific overrides are optional and are preserved by the installer.
local local_config = os.getenv("HOME") .. "/.config/hypr/local.lua"
local local_file = io.open(local_config, "r")
if local_file then
    local_file:close()
    dofile(local_config)
end
