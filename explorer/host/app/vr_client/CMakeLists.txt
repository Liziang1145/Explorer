cmake_minimum_required(VERSION 3.22.1)
set(PROJECT_NAME cloud_demo)
project("${PROJECT_NAME}")

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(CMAKE_CONFIGURATION_TYPES "Debug;Release")
if (CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2")
endif()
# Optional override runtime
set(XR_RUNTIME_JSON
    "$ENV{XR_RUNTIME_JSON}"
    CACHE PATH
    "Optional location of a specific OpenXR runtime configuration file."
)
# set(CMAKE_SYSTEM_NAME Android)
# set(CMAKE_SYSTEM_VERSION 24)
# set(ANDROID_PLATFORM 24) 
# set(ANDROID ON)
# add_definitions(-DXR_USE_GRAPHICS_API_VULKAN)
if(WIN32)
    add_definitions(-DXR_OS_WINDOWS)
    add_definitions(-DNOMINMAX)
elseif(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    message("Linux")
    add_definitions(-DXR_OS_LINUX)
elseif(ANDROID)
    message("Android")
    add_definitions(-DXR_OS_ANDROID)
    add_definitions(-DXR_USE_PLATFORM_ANDROID)
elseif(APPLE)
    add_definitions(-DXR_OS_APPLE)
endif()

# Additional Directories for find_package() to search within.
list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
include("cmake/graphics_api_select.cmake")


include(FetchContent)

set(BUILD_TESTS
    OFF
    CACHE INTERNAL "Build tests"
)
set(BUILD_API_LAYERS
    ON
    CACHE INTERNAL "Use OpenXR layers"
)

# Fetch OpenXR
# FetchContent_Declare(
#     OpenXR
#     URL_HASH MD5=924a94a2da0b5ef8e82154c623d88644
#     URL https://github.com/KhronosGroup/OpenXR-SDK-Source/archive/refs/tags/release-1.0.34.zip
#         SOURCE_DIR
#         openxr
# )
# FetchContent_MakeAvailable(OpenXR)
add_subdirectory(third_party/openxr)
# Fetch Eigen
# FetchContent_Declare(
#     eigen
#     GIT_REPOSITORY https://gitlab.com/libeigen/eigen.git
#     GIT_TAG 3.4.0  
# )
# FetchContent_Populate(eigen)
include_directories(third_party/eigen)

# Fetch tbb
# set(TBB_TEST OFF CACHE BOOL "" FORCE)
# FetchContent_Declare(
#     oneTBB
#     GIT_REPOSITORY https://github.com/oneapi-src/oneTBB.git
#     GIT_TAG v2022.1.0 
# )
# FetchContent_MakeAvailable(oneTBB)
set(TBB_TEST OFF)
add_subdirectory(third_party/oneTBB)

# FetchContent_Declare(
#   asio
#   GIT_REPOSITORY https://github.com/chriskohlhoff/asio.git
#   GIT_TAG asio-1-28-0  
# )
# FetchContent_MakeAvailable(asio)
include_directories(third_party/asio/asio/include)

set(SOURCES
    src/main.cpp
    src/openxr_app.cpp
    src/graphics/GraphicsAPI.cpp
    src/graphics/GraphicsAPI_Vulkan.cpp

    src/platforms/pch.cpp
    src/platforms/platformplugin_factory.cpp
    src/platforms/platformplugin_posix.cpp
    src/platforms/platformplugin_android.cpp

    # src/misc/OpenXRDebugUtils.cpp
)

set(GLSL_SHADERS "shaders/VertexShader.glsl" "shaders/PixelShader.glsl" "shaders/MeshVertexShader.glsl" "shaders/MeshFragmentShader.glsl" "shaders/CompressedVertexShader.glsl" )

if(ANDROID) # Android
    message("Build for Android")
    message("NDK $ENV{ANDROID_NDK_HOME}")

    find_path(
        ANDROID_NATIVE_APP_GLUE android_native_app_glue.h
        PATHS "$ENV{ANDROID_NDK_HOME}/sources/android/native_app_glue"
    )
    find_library(ANDROID_LIBRARY NAMES android PATHS $ENV{ANDROID_NDK_HOME})
    find_library(ANDROID_LOG_LIBRARY NAMES log)
    set(ANDROID_LIBS ${ANDROID_LIBRARY} ${ANDROID_LOG_LIBRARY})

    message(STATUS "Found Android libraries: ${ANDROID_LIBS}")

    set(MUJOCO_LIB "${CMAKE_SOURCE_DIR}/third_party/dynamic/${ANDROID_ABI}/libmujoco.so")
    if(NOT EXISTS ${MUJOCO_LIB})
        message(FATAL_ERROR "mujoco lib not found: ${MUJOCO_LIB}")
    endif()

        # Note: For some reason, just adding this to the gfxwrapper library results in failure at load time.
        # So, each consuming target must add $<TARGET_OBJECTS:android_native_app_glue> to their sources

    add_library(${PROJECT_NAME} SHARED ${SOURCES} $<TARGET_OBJECTS:android_native_app_glue>)
    target_include_directories( 
        ${PROJECT_NAME}
        PRIVATE
            # In this repo
            src/graphics/
            src/platforms/
            src/misc/
            src/maps/
            src/io/
            src/schedule/
            src/sim/
            third_party/mujoco/include
            # From OpenXR repo
            "${openxr_SOURCE_DIR}/src/common"
            "${openxr_SOURCE_DIR}/external/include" 
            "${eigen_SOURCE_DIR}"
            "${CMAKE_SYSROOT}/usr/include"
            "${ANDROID_NATIVE_APP_GLUE}"
            "${asio_SOURCE_DIR}/asio/include"
    )
    target_include_directories(
            openxr-gfxwrapper PUBLIC "${ANDROID_NATIVE_APP_GLUE}"
        )
    if(TARGET openxr-gfxwrapper)
        target_link_libraries(${PROJECT_NAME} PRIVATE openxr-gfxwrapper)
    endif()

    target_link_libraries(${PROJECT_NAME} PRIVATE OpenXR::openxr_loader ${ANDROID_LIBRARY} ${ANDROID_LOG_LIBRARY} tbb atomic ${MUJOCO_LIB})
    addgraphicsapidefine(${PROJECT_NAME})

    find_package(Vulkan) 
    # if(Vulkan_FOUND)
    #     target_include_directories(
    #         ${PROJECT_NAME} PUBLIC ${Vulkan_INCLUDE_DIRS}
    #     )
    #     target_link_libraries(${PROJECT_NAME} ${Vulkan_LIBRARIES})
    #     target_compile_definitions(
    #         ${PROJECT_NAME} PUBLIC XR_TUTORIAL_USE_VULKAN
    #     )
    # endif()
    target_include_directories(${PROJECT_NAME} PRIVATE ${Vulkan_INCLUDE_DIRS})
    target_link_libraries(${PROJECT_NAME} PRIVATE ${Vulkan_LIBRARY})
    target_compile_definitions(${PROJECT_NAME} PRIVATE XR_TUTORIAL_USE_VULKAN)
    
    # Compile shaders
    set(SHADER_DEST "${CMAKE_CURRENT_BINARY_DIR}")
    if(Vulkan_FOUND)
        include(glsl_shader)
        set_source_files_properties(
            shaders/VertexShader.glsl PROPERTIES ShaderType "vert"
        )
        set_source_files_properties(
            shaders/PixelShader.glsl PROPERTIES ShaderType "frag"
        )
        set_source_files_properties(
            shaders/MeshVertexShader.glsl PROPERTIES ShaderType "vert"
        )
        set_source_files_properties(
            shaders/MeshFragmentShader.glsl PROPERTIES ShaderType "frag"
        )
        set_source_files_properties(
            shaders/CompressedVertexShader.glsl PROPERTIES ShaderType "vert"
        )
        

        foreach(FILE ${GLSL_SHADERS})
            get_filename_component(FILE_WE ${FILE} NAME_WE)
            get_source_file_property(shadertype ${FILE} ShaderType)
            glsl_spv_shader(
                INPUT
                "${CMAKE_CURRENT_SOURCE_DIR}/${FILE}"
                OUTPUT
                "${SHADER_DEST}/${FILE_WE}.spv"
                STAGE
                ${shadertype}
                ENTRY_POINT
                main
                TARGET_ENV
                vulkan1.0
            )
            message(STATUS "Processing shader: ${FILE}")
            # Make our project depend on these files
            target_sources(
                ${PROJECT_NAME} PRIVATE "${SHADER_DEST}/${FILE_WE}.spv"
            )
        endforeach()
        file(GLOB SPV_SHADERS "${SHADER_DEST}/*.spv")
        
        add_custom_target(copy_shaders
            COMMAND ${CMAKE_COMMAND} -E make_directory "${CMAKE_SOURCE_DIR}/android_resources/shaders"
            COMMENT "Copy shaders"
        )
        foreach(SPV_FILE ${SPV_SHADERS})
            get_filename_component(FILE_NAME ${SPV_FILE} NAME)
            add_custom_command(
                TARGET copy_shaders PRE_BUILD
                COMMAND ${CMAKE_COMMAND} -E copy_if_different
                    "${SPV_FILE}"
                    "${CMAKE_SOURCE_DIR}/android_resources/shaders/${FILE_NAME}" 
                COMMENT "Copying ${SPV_FILE} -> ${FILE_NAME}"
            )
        endforeach()
        add_dependencies(${PROJECT_NAME} copy_shaders)
 

    endif()
else() #Linux
    message("Build for Linux")
    add_executable(${PROJECT_NAME} ${SOURCES})

    if(NOT "${XR_RUNTIME_JSON}" STREQUAL "")
        set_target_properties(
            ${PROJECT_NAME} PROPERTIES VS_DEBUGGER_ENVIRONMENT
                                       "XR_RUNTIME_JSON=${XR_RUNTIME_JSON}"
        )
    endif()

    target_include_directories(
        ${PROJECT_NAME}
        PRIVATE
            # In this repo
            src/graphics/
            src/platforms/
            src/misc/
            src/maps/
            src/io/
            src/schedule/
            # From OpenXR repo
            "${openxr_SOURCE_DIR}/src/common"
            "${openxr_SOURCE_DIR}/external/include"
            "${eigen_SOURCE_DIR}"
            "${asio_SOURCE_DIR}/asio/include"
    )
    target_link_libraries(${PROJECT_NAME} openxr_loader tbb atomic)
    addgraphicsapidefine(${PROJECT_NAME})

    target_compile_definitions(
        ${PROJECT_NAME} PUBLIC XR_TUTORIAL_USE_LINUX_XLIB
    )

    find_package(Vulkan)
    if(Vulkan_FOUND)
        target_include_directories(
            ${PROJECT_NAME} PUBLIC ${Vulkan_INCLUDE_DIRS}
        )
        target_link_libraries(${PROJECT_NAME} ${Vulkan_LIBRARIES})
        target_compile_definitions(
            ${PROJECT_NAME} PUBLIC XR_TUTORIAL_USE_VULKAN
        )
    endif()
    
    # Compile shaders
    set(SHADER_DEST "${CMAKE_CURRENT_BINARY_DIR}")
    if(Vulkan_FOUND)
        include(glsl_shader)
        set_source_files_properties(
            shaders/VertexShader.glsl PROPERTIES ShaderType "vert"
        )
        set_source_files_properties(
            shaders/PixelShader.glsl PROPERTIES ShaderType "frag"
        )

        set_source_files_properties(
            shaders/MeshVertexShader.glsl PROPERTIES ShaderType "vert"
        )
        set_source_files_properties(
            shaders/MeshFragmentShader.glsl PROPERTIES ShaderType "frag"
        ) 

        set_source_files_properties(
            shaders/CompressedVertexShader.glsl PROPERTIES ShaderType "vert"
        ) 

        foreach(FILE ${GLSL_SHADERS})
            get_filename_component(FILE_WE ${FILE} NAME_WE)
            get_source_file_property(shadertype ${FILE} ShaderType) 
            glsl_spv_shader(
                INPUT
                "${CMAKE_CURRENT_SOURCE_DIR}/${FILE}"
                OUTPUT
                "${SHADER_DEST}/${FILE_WE}.spv"
                STAGE
                ${shadertype}
                ENTRY_POINT
                main
                TARGET_ENV
                vulkan1.0
            )
            # Make our project depend on these files
            target_sources(
                ${PROJECT_NAME} PRIVATE "${SHADER_DEST}/${FILE_WE}.spv"
            )
        endforeach()
    endif()

endif() # EOF