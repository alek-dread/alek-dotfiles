Name: gtkgreet-controls
Version: 0.8.20261017
Release: 2.local%{?dist}
Summary: Locally maintained English greetd login screen
License: GPL-3.0-or-later
URL: https://git.sr.ht/~kennylevinsen/gtkgreet
Source0: %{name}-%{version}.tar.xz
BuildRequires: gcc meson ninja-build pkgconfig(gtk+-3.0) pkgconfig(json-c)

%description
The existing locally audited gtkgreet with login, clock and power controls.
Source, Fedora hardening flags and RPM ownership make the build maintainable.

%prep
%setup -q

%build
meson setup build --prefix=/usr --buildtype=release -Db_pie=true -Db_lto=true -Dlayershell=disabled -Dman-pages=disabled -Dc_args='["-fstack-protector-strong","-fstack-clash-protection","-D_FORTIFY_SOURCE=3","-Wformat=2","-Wformat-security"]'  -Dc_link_args='["-Wl,-z,relro,-z,now"]' 
meson compile -C build

%install
DESTDIR=%{buildroot} meson install -C build --no-rebuild
mv %{buildroot}%{_bindir}/gtkgreet %{buildroot}%{_bindir}/gtkgreet-controls
rm -rf %{buildroot}%{_datadir}/locale

%files
%license LICENSE
%doc README.md local-changes.patch
%{_bindir}/gtkgreet-controls

%changelog
* Fri Oct 23 2026 Local Desktop Maintenance <root@localhost> - 0.8.20261017-2.local
- Draw the Fedora wordmark using its GTK CSS color

* Mon Oct 19 2026 Local Desktop Maintenance <root@localhost> - 0.8.20261017-1.local
- Package the existing audited greeter with reproducible source inputs
