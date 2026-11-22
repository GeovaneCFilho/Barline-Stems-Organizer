cmake_minimum_required(VERSION 3.22)

project(Barline VERSION 0.0.1 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Versão do JUCE fixada por tag para o build ser reproduzível.
# Para trocar: cmake -S . -B build -DBARLINE_JUCE_TAG=<tag>
set(BARLINE_JUCE_TAG "8.0.15" CACHE STRING "Tag do JUCE usada pelo Barline")

include(FetchContent)
FetchContent_Declare(
    JUCE
    GIT_REPOSITORY https://github.com/juce-framework/JUCE.git
    GIT_TAG        ${BARLINE_JUCE_TAG}
    GIT_SHALLOW    ON
)
FetchContent_MakeAvailable(JUCE)

juce_add_gui_app(Barline
    PRODUCT_NAME "Barline"
    COMPANY_NAME "Barline"
    VERSION      ${PROJECT_VERSION}
)

target_sources(Barline PRIVATE
    Source/Main.cpp
)

target_compile_definitions(Barline PRIVATE
    JUCE_WEB_BROWSER=0
    JUCE_USE_CURL=0
    JUCE_APPLICATION_NAME_STRING="$<TARGET_PROPERTY:Barline,JUCE_PRODUCT_NAME>"
    JUCE_APPLICATION_VERSION_STRING="$<TARGET_PROPERTY:Barline,JUCE_VERSION>"
)

target_link_libraries(Barline
    PRIVATE
        juce::juce_gui_basics
        juce::juce_audio_basics
        juce::juce_audio_formats
    PUBLIC
        juce::juce_recommended_config_flags
        juce::juce_recommended_lto_flags
        juce::juce_recommended_warning_flags
)
