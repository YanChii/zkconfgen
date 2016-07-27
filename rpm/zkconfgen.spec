Summary: Config file generator from Zookeeper nodes using templates
Name: zkconfgen
Version: 0.2
Release: 0
License: Apache 2.0
Group: Productivity/Networking
URL: https://github.com/YanChii/zkconfgen
Source0: zkconfgen
Source1: zkconfgen.ini.sample
Source2: examples
Source3: zkconfgen.service
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root
Requires: python-kazoo
Requires: python-gevent
Requires: python-configparser

%description
Generate configuration files (for nginx, apache, haproxy, etc.) from Zookeeper registered services using file templates. This program watches for changes in Zookeeper (using triggers), immediately re-generates all defined output config files and calls specified reload command to apply the new configuration.


%prep

%build

%install
mkdir -p %{buildroot}/etc/zkconfgen
install -p -D -m 755 %{S:0} %{buildroot}/usr/bin/zkconfgen
install -p -D -m 644 %{S:1} %{buildroot}/etc/zkconfgen/zkconfgen.ini.sample
install -p -D -m 644 %{S:1} %{buildroot}/etc/zkconfgen/zkconfgen.ini
cp -r %{S:2} %{buildroot}/etc/zkconfgen/examples
install -p -D -m 644 %{S:3} %{buildroot}/lib/systemd/system/zkconfgen.service

%clean
%{__rm} -rf %{buildroot}


%post
%systemd_post zkconfgen.service

# Package removal, not upgrade
%preun
%systemd_preun zkconfgen.service

# Package upgrade, not uninstall
# restartni pri upgrade:
%postun
%systemd_postun_with_restart zkconfgen.service


%files
%defattr(-, root, root, 0755)
/usr/bin/*
/lib/systemd/system/zkconfgen.service
/etc/zkconfgen
%config(noreplace) /etc/zkconfgen/zkconfgen.ini

%pre
