set(SOURCES
    main.cpp
    app/Application.cpp
    app/ThemeManager.cpp
    app/LanguageManager.cpp
    ui/main_window/MainWindow.cpp
    ui/settings/SettingsPage.cpp
    storage/local_db/LocalDatabase.cpp
    storage/remote_db/RemoteDatabase.cpp
    storage/sync/DataSyncManager.cpp
    storage/DatabaseManager.cpp
    protocol/plugin_loader/PluginManager.cpp
)

set(HEADERS
    app/Application.h
    app/ThemeManager.h
    app/LanguageManager.h
    ui/main_window/MainWindow.h
    ui/settings/SettingsPage.h
    storage/local_db/LocalDatabase.h
    storage/remote_db/RemoteDatabase.h
    storage/sync/DataSyncManager.h
    storage/DatabaseManager.h
    protocol/interface/IProtocolParser.h
    protocol/interface/IInstrumentController.h
    protocol/plugin_loader/PluginManager.h
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
