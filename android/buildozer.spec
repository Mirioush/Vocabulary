[app]
title = 考研单词
package.name = kaoyanwords
package.domain = org.example
source.dir = .
source.include_exts = py
version = 1.0
requirements = python3,kivy==2.3.1
p4a.branch = v2024.01.21
orientation = portrait
fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 1

[android]
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
