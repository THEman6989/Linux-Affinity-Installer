cmake_minimum_required(VERSION 3.21)
project(AffinityClipboardV2 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 6.5 REQUIRED COMPONENTS Core Gui Widgets)

enable_testing()

add_library(clipboard_payload STATIC
    src/clipboard_payload.cpp
)
target_include_directories(clipboard_payload PUBLIC src)
target_link_libraries(clipboard_payload PUBLIC Qt6::Core Qt6::Gui)

add_executable(affinity-clipboard-owner
    src/owner_main.cpp
)
target_link_libraries(affinity-clipboard-owner PRIVATE clipboard_payload)

add_library(tray_icon STATIC
    src/tray_icon.cpp
)
target_include_directories(tray_icon PUBLIC src)
target_link_libraries(tray_icon PUBLIC Qt6::Core Qt6::Gui)

add_executable(affinity-clipboard-tray
    src/tray_main.cpp
)
target_link_libraries(affinity-clipboard-tray PRIVATE tray_icon Qt6::Widgets)

add_executable(test_tray_icon
    tests/test_tray_icon.cpp
)
target_link_libraries(test_tray_icon PRIVATE tray_icon)
add_test(NAME tray_icon COMMAND test_tray_icon)

add_executable(test_clipboard_payload
    tests/test_clipboard_payload.cpp
)
target_link_libraries(test_clipboard_payload PRIVATE clipboard_payload)
add_test(NAME clipboard_payload COMMAND test_clipboard_payload)
