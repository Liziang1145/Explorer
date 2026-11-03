// Copyright 2023, The Khronos Group Inc.
//
// SPDX-License-Identifier: Apache-2.0

#version 450

layout(std140, binding = 0) uniform CameraConstants {
    mat4 viewProj;
    mat4 view;          
    uvec4 padding;
};
layout(std430, binding = 1) readonly buffer PointCloud {
    vec4 points[]; // xyz positions and size
};

layout(std430, binding = 2) readonly buffer Colors {
    vec4 colors[]; // rgba colors
};


// layout(location = 0) out vec4 v_Color;
// layout(location = 1) out flat uint v_ID;
layout(location = 0) out vec4 v_Light;
layout(location = 1) out vec4 v_worldPos;
layout(location = 2) out vec4 v_color;
layout(location = 3) out flat float v_realPointSize;
layout(location = 4) out flat float v_pointSize;

const vec4 sunDir = vec4(0.0f, -1.0f, 0.5f, 0.0f);

void main() {
    uint id = uint(gl_VertexIndex);
    vec4 worldPos = vec4(points[id].xyz, 1.0f);
    float pointSize = points[id].w * 30;
    gl_Position = viewProj * worldPos;
    // gl_PointSize =(pointSize / gl_Position.w);
    gl_PointSize =clamp((pointSize / gl_Position.w),3, 50);


    v_Light = viewProj * normalize(sunDir);
    v_worldPos = worldPos;
    v_realPointSize = pointSize;
    v_color = colors[id];
    v_pointSize = gl_PointSize;

}
