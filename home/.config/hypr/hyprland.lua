hl.monitor({ output = "DP-1", mode = "1920x1080@144", position = "0x0", scale = 1 })
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = 1 })

hl.config({
    general = {
        layout = "master",
        gaps_in = 0,
        gaps_out = 0,
        border_size = 2,
        col = {
            active_border = {
                colors = { "rgb(a3a878)", "rgb(8c9c91)" },
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
        new_status = "slave",
        orientation = "left",
    },
    decoration = {
        rounding = 0,
        shadow = { enabled = false },
        blur = { enabled = false },
    },
    animations = { enabled = false },
    -- Polaris: avoid damaged hardware cursor buffers after a GPU reset.
    cursor = { no_hardware_cursors = 1 },
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

hl.bind("SUPER + Return", hl.dsp.exec_cmd("uwsm app -- alacritty"))
hl.bind("SUPER + T", hl.dsp.exec_cmd("uwsm app -- alacritty"))
hl.bind("SUPER + D", hl.dsp.exec_cmd("fuzzel"))
hl.bind("SUPER + P", hl.dsp.exec_cmd("/home/alek/.local/bin/desktop-power-menu"))
hl.bind("SUPER + E", hl.dsp.exec_cmd("uwsm app -- nautilus"))
hl.bind("SUPER + Q", hl.dsp.window.close())
hl.bind("SUPER + J", hl.dsp.layout("cyclenext"))
hl.bind("SUPER + K", hl.dsp.layout("cycleprev"))
hl.bind("SUPER + SHIFT + J", hl.dsp.layout("swapnext"))
hl.bind("SUPER + SHIFT + K", hl.dsp.layout("swapprev"))
hl.bind("SUPER + SHIFT + Return", hl.dsp.layout("swapwithmaster master"))
hl.bind("SUPER + H", hl.dsp.window.resize({ x = -40, y = 0, relative = true }))
hl.bind("SUPER + L", hl.dsp.window.resize({ x = 40, y = 0, relative = true }))
hl.bind("SUPER + F", hl.dsp.window.fullscreen({ mode = "maximized" }))
hl.bind("SUPER + SHIFT + F", hl.dsp.window.fullscreen({ mode = "fullscreen" }))
hl.bind("SUPER + V", hl.dsp.window.float({ action = "toggle" }))
hl.bind("SUPER + Tab", hl.dsp.focus({ workspace = "previous" }))
for i = 1, 9 do
    hl.bind("SUPER + " .. i, hl.dsp.focus({ workspace = i }))
    hl.bind("SUPER + SHIFT + " .. i, hl.dsp.window.move({ workspace = i }))
end

for key, dir in pairs({ left = "left", right = "right", up = "up", down = "down" }) do
    hl.bind("SUPER + " .. key, hl.dsp.focus({ direction = dir }))
end

hl.bind("SUPER + mouse:272", hl.dsp.window.drag(), { mouse = true })
hl.bind("SUPER + mouse:273", hl.dsp.window.resize(), { mouse = true })
hl.bind("SUPER + ALT + L", hl.dsp.exec_cmd("loginctl lock-session"))
hl.bind("SUPER + SHIFT + E", hl.dsp.exec_cmd("desktop-session-menu"))
hl.bind("CTRL + ALT + Delete", hl.dsp.exec_cmd("desktop-session-menu"))
hl.bind("SUPER + SHIFT + R", hl.dsp.exec_cmd("hyprctl reload"))
hl.bind("SUPER + SHIFT + slash", hl.dsp.exec_cmd("uwsm app -- alacritty -e less /home/alek/.config/hypr/KEYS.txt"))
hl.bind("SUPER + N", hl.dsp.exec_cmd("makoctl dismiss"))
hl.bind("SUPER + SHIFT + N", hl.dsp.exec_cmd("makoctl restore"))
hl.bind("Print", hl.dsp.exec_cmd("desktop-screenshot region"))
hl.bind("CTRL + Print", hl.dsp.exec_cmd("desktop-screenshot screen"))
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
})
