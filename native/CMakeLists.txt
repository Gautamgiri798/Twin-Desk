cmake_minimum_required(VERSION 3.20)
project(DualDeskNative VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/capture
    ${CMAKE_CURRENT_SOURCE_DIR}/idd_driver
)

# Source files for native capture pipeline
set(CAPTURE_SOURCES
    capture/dxgi_compat.h
    capture/dxgi_capture.h
    capture/dxgi_capture.cpp
)

# Source files for Windows IddCx Indirect Display Driver
set(DRIVER_SOURCES
    idd_driver/idd_compat.h
    idd_driver/Driver.h
    idd_driver/Driver.cpp
    idd_driver/Direct3DDevice.h
    idd_driver/Direct3DDevice.cpp
    idd_driver/VirtualMonitor.h
    idd_driver/VirtualMonitor.cpp
)

# Build capture library
add_library(dualdesk_capture STATIC ${CAPTURE_SOURCES})
target_include_directories(dualdesk_capture PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/capture ${CMAKE_CURRENT_SOURCE_DIR}/idd_driver)

if (WIN32)
    target_link_libraries(dualdesk_capture PRIVATE d3d11 dxgi)
endif()

# Build IDD driver shared library (User-Mode Driver DLL)
add_library(dualdesk_idd SHARED ${DRIVER_SOURCES})
target_include_directories(dualdesk_idd PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/idd_driver ${CMAKE_CURRENT_SOURCE_DIR}/capture)

if (WIN32)
    target_link_libraries(dualdesk_idd PRIVATE d3d11 dxgi)
endif()

message(STATUS "Configured DualDesk Native components")

