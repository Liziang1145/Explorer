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
    uvec2 morton[]; //morton code
};

layout(std430, binding = 2) readonly buffer Colors {
    uint colors[]; // rgba colors
};


// layout(location = 0) out vec4 v_Color;
// layout(location = 1) out flat uint v_ID;
layout(location = 0) out vec4 v_Light;
layout(location = 1) out vec4 v_worldPos;
layout(location = 2) out vec4 v_color;
layout(location = 3) out flat float v_realPointSize;
layout(location = 4) out flat float v_pointSize;

const vec4 sunDir = vec4(0.0f, -1.0f, 0.5f, 0.0f);



float compactBits(uint hi, uint lo) {
    const uint bitmask = 1 << 20;
    lo &= 0x49249249u;
    hi = (hi >> 1) & 0x49249249u;

    lo = (lo ^ (lo >> 2)) & 0x430c30c3u;
    lo = (lo ^ (lo >> 4)) & 0x0700f00fu;
    lo = (lo ^ (lo >> 8)) & 0x070000ffu;
    lo = (lo ^ (lo >> 16)) & 0x00007ffu;

    hi = (hi ^ (hi >> 2)) & 0x430c30c3u;
    hi = (hi ^ (hi >> 4)) & 0x0700f00fu;
    hi = (hi ^ (hi >> 8)) & 0x070000ffu;
    hi = (hi ^ (hi >> 16)) & 0x00003ffu;

    int tmpInt = int((hi << 11) | lo) - int(bitmask);
    return float(tmpInt)*0.01f;
}

vec4 decodeColor(uint color) {
    return vec4(
        float((color >> 24) & 0xFFu) / 255.0f,
        float((color >> 16) & 0xFFu) / 255.0f,
        float((color >> 8) & 0xFFu) / 255.0f,
        float((color >> 0) & 0xFFu) / 255.0f
    );
}


void main() {
    uint id = uint(gl_VertexIndex);
    uint hi = morton[id].y;
    uint lo = morton[id].x;

    if((hi & (1u << 31)) != 0u )
    {
        gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
        return;
    }

    float _x = compactBits(hi, lo);
    lo = (lo >> 1) | ((hi & 1u) << 31);
    hi >>= 1;
    float _y = compactBits(hi, lo);
    lo = (lo >> 1) | ((hi & 1u) << 31);
    hi >>= 1;
    float _z = compactBits(hi, lo);

    vec4 worldPos = vec4(-_y, _z, -_x, 1.0f);
    float pointSize = 8;
    gl_Position = viewProj * worldPos;
    // gl_PointSize =(pointSize / gl_Position.w);
    gl_PointSize =clamp((pointSize / abs(gl_Position.w)),1, 8);


    v_Light = viewProj * normalize(sunDir);
    v_worldPos = worldPos;
    v_realPointSize = pointSize;
    // v_color = colors[id];

    v_color = decodeColor(colors[id]);
    gl_PointSize *=1.5;
    if(v_color[0]==1.0f&&v_color[1]==1.0f&&v_color[2]==1.0f)
    {
        gl_PointSize *=2;
    }
        

    
    v_pointSize = gl_PointSize;

}
