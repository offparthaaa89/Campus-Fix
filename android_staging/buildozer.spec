# CampusFix Android DEBUG prototype. Build from this folder, not project root.
# Change package.domain to a domain you control before any release.
[app]
title = CampusFix
package.name = campusfix
package.domain = org.campusfix.prototype
source.dir = .
source.include_exts = py
version = 0.1.0
requirements = python3,kivy,requests,charset-normalizer==2.1.1
orientation = portrait
fullscreen = 0
android.permissions = INTERNET
android.api = 36
android.minapi = 24
android.archs = arm64-v8a
android.allow_backup = False

[buildozer]
log_level = 2
warn_on_root = 1
