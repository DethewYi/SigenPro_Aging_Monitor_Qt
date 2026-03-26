cmake_minimum_required(VERSION 3.20)
project(SigenPro_Aging_Monitor VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets Sql Network SerialPort PrintSupport)
find_package(Qt6 OPTIONAL_COMPONENTS LinguistTools)

# Third-party: QCustomPlot for real-time charting
include(FetchContent)
FetchContent_Declare(
    qcustomplot
    GIT_REPOSITORY https://github.com/AmonSaken/QCustomPlot-qt6.git
    GIT_TAG v2.1.1
)
FetchContent_MakeAvailable(qcustomplot)

add_subdirectory(src)
