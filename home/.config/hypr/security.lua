-- Rules are applied when Hyprland starts; reload cannot replace permissions.
hl.config({ ecosystem = { enforce_permissions = true } })
for _, binary in ipairs({ "/usr/bin/grim", "/usr/bin/wf-recorder",
                          "/usr/libexec/xdg-desktop-portal-hyprland" }) do
    hl.permission({ binary = "^" .. binary .. "$", type = "screencopy", mode = "allow" })
end
