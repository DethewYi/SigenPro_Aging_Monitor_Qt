set(SOURCES
    main.cpp
    app/Application.cpp
    app/ThemeManager.cpp
    ui/main_window/MainWindow.cpp
)

set(HEADERS
    app/Application.h
    app/ThemeManager.h
    ui/main_window/MainWindow.h
)

set(RESOURCES
    ../resources/resources.qrc
)

add_executable(${PROJECT_NAME} WIN32 ${SOURCES} ${HEADERS} ${RESOURCES})

target_link_libraries(${PROJECT_NAME} PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Widgets
    Qt6::Sql
    Qt6::Network
    Qt6::SerialPort
    Qt6::PrintSupport
)

target_include_directories(${PROJECT_NAME} PRIVATE ${CMAKE_SOURCE_DIR}/src)
