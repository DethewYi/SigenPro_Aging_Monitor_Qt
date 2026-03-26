set(SOURCES
    main.cpp
    app/Application.cpp
    app/ThemeManager.cpp
    app/LanguageManager.cpp
    ui/main_window/MainWindow.cpp
    ui/settings/SettingsPage.cpp
    ui/device_overview/StatsBarWidget.cpp
    ui/device_overview/DeviceCardWidget.cpp
    ui/device_overview/DeviceOverviewPage.cpp
    storage/local_db/LocalDatabase.cpp
    storage/remote_db/RemoteDatabase.cpp
    storage/sync/DataSyncManager.cpp
    storage/DatabaseManager.cpp
    protocol/plugin_loader/PluginManager.cpp
    communication/tcp/TcpDeviceConnection.cpp
    communication/tcp/TcpConnectionManager.cpp
    communication/can/CanBridge.cpp
    communication/rs485/Rs485Bridge.cpp
    core/data_bus/DataBus.cpp
    core/alarm_engine/AlarmEngine.cpp
    core/template_manager/TemplateManager.cpp
    core/test_engine/TestEngine.cpp
    instrument/channel_manager/ChannelManager.cpp
    instrument/scanner/BarcodeScanner.cpp
)

set(HEADERS
    app/Application.h
    app/ThemeManager.h
    app/LanguageManager.h
    ui/main_window/MainWindow.h
    ui/settings/SettingsPage.h
    ui/device_overview/StatsBarWidget.h
    ui/device_overview/DeviceCardWidget.h
    ui/device_overview/DeviceOverviewPage.h
    storage/local_db/LocalDatabase.h
    storage/remote_db/RemoteDatabase.h
    storage/sync/DataSyncManager.h
    storage/DatabaseManager.h
    protocol/interface/IProtocolParser.h
    protocol/interface/IInstrumentController.h
    protocol/plugin_loader/PluginManager.h
    communication/tcp/TcpDeviceConnection.h
    communication/tcp/TcpConnectionManager.h
    communication/can/CanBridge.h
    communication/rs485/Rs485Bridge.h
    core/data_bus/DataBus.h
    core/alarm_engine/AlarmEngine.h
    core/template_manager/TemplateManager.h
    core/test_engine/TestEngine.h
    instrument/channel_manager/ChannelManager.h
    instrument/scanner/BarcodeScanner.h
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
